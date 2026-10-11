"""Cœur métier (sans GTK) du déploiement de configuration en masse par SNMP.

Alternative à ``netmiko_bulk_core.py`` : au lieu d'une session CLI interactive
par équipement (SSH + prompt scraping), on dépose le fichier de configuration
rendu sur un serveur de dépôt (SFTP/FTP/TFTP), puis on déclenche par un
``SNMP SET`` l'opération constructeur qui fait fusionner ("merge") ce fichier
dans la configuration courante de l'équipement — ``net2Running`` chez
H3C/Comware (``HH3C-CONFIG-MAN-MIB``), ``networkFile -> runningConfig`` chez
Cisco (``CISCO-CONFIG-COPY-MIB``). Voir la conversation qui a mené à ce
module : gain principal sur H3C/Comware, où le SNMP est déjà éprouvé sur le
terrain, sans les fragilités d'un ``send_config_set`` interactif ni le besoin
de connaître le schéma XML par fonctionnalité comme en NETCONF.

Deux différences structurelles assumées avec ``netmiko_bulk_core.py`` :

- **Transport UDP sans session persistante** : contrairement à SSH, un accès
  SNMP est un aller-retour par opération, pas une session à maintenir. Ce
  module est écrit en ``asyncio`` (``asyncio.gather`` + ``Semaphore``)
  plutôt qu'avec un ``ThreadPoolExecutor`` complet — mais la bibliothèque
  SNMP utilisée (``ezsnmp``, bindings natifs Net-SNMP) est une extension C
  BLOQUANTE, sans asyncio natif. Chaque appel SNMP individuel est donc
  enrobé dans ``asyncio.to_thread`` : un thread n'est occupé que le temps
  d'un GET/SET/WALK, pas pendant toute la durée du polling (qui reste un
  simple ``await asyncio.sleep``) — on garde l'essentiel du bénéfice
  asyncio pour le polling, sans avoir besoin d'une bibliothèque SNMP async.
  ``run_bulk_snmp_push()`` fournit un point d'entrée synchrone
  (``asyncio.run`` interne) pour être appelé depuis le thread d'arrière-plan
  du plugin GTK exactement comme ``netmiko_bulk_core.run_bulk_push``.
- **Multi-constructeur par "driver"** : chaque constructeur expose un MIB de
  gestion de configuration différent (colonnes, types d'opération,
  sémantique du polling de statut). ``SnmpPushDriver`` est le point
  d'extension : ajouter un constructeur = ajouter une sous-classe et
  l'enregistrer dans ``SNMP_PUSH_DRIVERS``, sans toucher au reste.

``InventoryRow``, ``load_inventory``, ``find_missing_variables``,
``render_template`` sont réutilisés tels quels depuis ``netmiko_bulk_core``
(mêmes formats CSV/gabarit, rien de spécifique au transport). ``SnmpPushResult``
a délibérément les mêmes champs que ``PushResult`` pour pouvoir réutiliser
``_write_log``/``_write_manifest``/``summarize_results`` sans duplication.

AVERTISSEMENT — partie SNMP non testée en conditions réelles : je n'ai ni
environnement ``ezsnmp`` actif ni équipement sous la main pour valider ce
module de bout en bout. L'API ``ezsnmp.Session`` (``get``, ``set_multiple``,
``walk``, ``Session(...)``...) est vérifiée contre la documentation
officielle ezsnmp 2.4, mais cette bibliothèque a changé des noms de
paramètres entre easysnmp et ezsnmp par le passé — teste impérativement
contre la version installée, sur un équipement de
labo avant tout usage en production — en particulier le polling de statut
H3C (table de résultat indexée séparément, la partie la plus délicate).
"""

from __future__ import annotations

import asyncio
import csv  # noqa: F401  (ré-exporté implicitement via netmiko_bulk_core, gardé pour clarté)
import ftplib
import re
import socket
import struct
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

# Réutilisation explicite : mêmes formats CSV/gabarit/log/manifest que pour
# Netmiko, aucune raison de les dupliquer (cf. docstring de module).
from netmiko_bulk_core import (  # noqa: F401
    InventoryRow,
    _write_log,
    _write_manifest,
    find_missing_variables,
    load_inventory,
    render_template,
    summarize_results,
)

__all__ = [
    "STATUS_OK",
    "STATUS_FAILED",
    "STATUS_REJECTED",
    "STATUS_SKIPPED",
    "FileTransferConfig",
    "SnmpCredentials",
    "SnmpDeviceProfile",
    "SnmpProfileStore",
    "SnmpPushResult",
    "SnmpPushDriver",
    "Hh3cComwareDriver",
    "CiscoConfigCopyDriver",
    "SNMP_PUSH_DRIVERS",
    "upload_config_file",
    "push_config_via_snmp",
    "run_bulk_snmp_push",
    "run_bulk_snmp_push_async",
]

# Mêmes libellés que netmiko_bulk_core.STATUS_* pour rester compatible avec
# summarize_results()/_write_manifest() (duck typing sur le champ .status).
STATUS_OK = "ok"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


# ══════════════════════════════════════════════════════════════════════
# Transfert du fichier de configuration vers le serveur de dépôt
# ══════════════════════════════════════════════════════════════════════


@dataclass
class FileTransferConfig:
    """Paramètres du serveur de dépôt où le fichier rendu est déposé avant
    que l'équipement n'aille le chercher (l'équipement est le CLIENT de ce
    transfert-là ; nous sommes le client du transfert initial vers ce
    serveur).

    Attributes:
        protocol: ``"sftp"``, ``"ftp"`` ou ``"tftp"``.
        host: Adresse du serveur de dépôt (doit être joignable à la fois
            depuis cette machine ET depuis les équipements cibles).
        port: Port du service (22 SFTP / 21 FTP / 69 TFTP par défaut).
        username: Utilisateur (SFTP/FTP ; ignoré en TFTP, qui n'authentifie
            pas).
        password: Mot de passe (SFTP/FTP).
        remote_dir: Dossier distant où déposer les fichiers (chemin déjà
            existant côté serveur).
    """

    protocol: str  # "sftp" | "ftp" | "tftp"
    host: str
    port: int = 0  # 0 -> port par défaut du protocole, résolu dans upload_config_file
    username: str = ""
    password: str = ""
    remote_dir: str = "/"

    def default_port(self) -> int:
        """Port par défaut du protocole de transfert configuré.

        Returns:
            Le port par défaut, ou 0 si le protocole est inconnu.
        """
        logger.debug(f"FileTransferConfig.default_port | protocol={self.protocol}")
        return {"sftp": 22, "ftp": 21, "tftp": 69}.get(self.protocol, 0)


def _upload_sftp(cfg: FileTransferConfig, filename: str, content: bytes) -> None:
    """Dépose *content* sur le serveur de dépôt via SFTP.

    Args:
        cfg: Paramètres de connexion au serveur de dépôt.
        filename: Nom du fichier distant à créer.
        content: Contenu binaire à écrire.
    """
    logger.debug(f"_upload_sftp | host={cfg.host} filename={filename}")
    import paramiko  # import paresseux : dépendance optionnelle, cf. hypervisor_import_common.py

    port = cfg.port or cfg.default_port()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            cfg.host, port=port, username=cfg.username, password=cfg.password, timeout=15
        )
        sftp = client.open_sftp()
        try:
            remote_path = cfg.remote_dir.rstrip("/") + "/" + filename
            with sftp.open(remote_path, "wb") as fh:
                fh.write(content)
        finally:
            sftp.close()
    finally:
        client.close()


def _upload_ftp(cfg: FileTransferConfig, filename: str, content: bytes) -> None:
    """Dépose *content* sur le serveur de dépôt via FTP.

    Args:
        cfg: Paramètres de connexion au serveur de dépôt.
        filename: Nom du fichier distant à créer.
        content: Contenu binaire à écrire.
    """
    logger.debug(f"_upload_ftp | host={cfg.host} filename={filename}")
    import io

    port = cfg.port or cfg.default_port()
    with ftplib.FTP() as ftp:
        ftp.connect(cfg.host, port, timeout=15)
        ftp.login(cfg.username or "anonymous", cfg.password or "")
        if cfg.remote_dir and cfg.remote_dir not in ("", "/"):
            try:
                ftp.cwd(cfg.remote_dir)
            except ftplib.error_perm as exc:
                raise RuntimeError(
                    f"Dossier distant FTP inaccessible ({cfg.remote_dir}) : {exc}"
                ) from exc
        ftp.storbinary(f"STOR {filename}", io.BytesIO(content))


# ── Client TFTP minimal (RFC 1350), aucune dépendance externe ───────────
#
# TFTP n'a pas de bibliothèque cliente dans la stdlib. On implémente ici le
# strict nécessaire à un WRQ (write request) suivi de blocs DATA/ACK de 512
# octets — assez pour déposer un fichier de config, pas une implémentation
# générale du protocole (pas de RRQ, pas d'options RFC 2347).

_TFTP_OPCODE_WRQ = 2
_TFTP_OPCODE_DATA = 3
_TFTP_OPCODE_ACK = 4
_TFTP_OPCODE_ERROR = 5
_TFTP_BLOCK_SIZE = 512
_TFTP_TIMEOUT_S = 5.0
_TFTP_MAX_RETRIES = 4


def _tftp_upload(
    host: str, port: int, filename: str, content: bytes, timeout: float = _TFTP_TIMEOUT_S
) -> None:
    """Dépose *content* sous *filename* sur un serveur TFTP (mode octet).

    Args:
        host: Adresse du serveur TFTP.
        port: Port du serveur TFTP.
        filename: Nom (chemin distant) du fichier à créer.
        content: Contenu binaire à écrire.
        timeout: Délai d'attente par paquet, en secondes.
    """
    logger.debug(f"_tftp_upload | host={host} port={port} filename={filename}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        wrq = (
            struct.pack("!H", _TFTP_OPCODE_WRQ)
            + filename.encode("ascii")
            + b"\x00"
            + b"octet"
            + b"\x00"
        )
        server_addr = (host, port)

        def _send_and_wait_ack(packet: bytes, expected_block: int, addr) -> tuple:
            """Envoie *packet* et attend l'ACK du bloc *expected_block*.

            Args:
                packet: Paquet TFTP à envoyer.
                expected_block: Numéro de bloc attendu dans l'ACK.
                addr: Adresse ``(host, port)`` du destinataire.

            Returns:
                Tuple ``(data, from_addr)`` de la réponse reçue.
            """
            logger.debug(
                f"_tftp_upload._send_and_wait_ack | expected_block={expected_block} addr={addr}"
            )
            last_exc: Exception | None = None
            for _attempt in range(_TFTP_MAX_RETRIES):
                sock.sendto(packet, addr)
                try:
                    data, from_addr = sock.recvfrom(516)
                except TimeoutError as exc:
                    last_exc = exc
                    continue
                opcode = struct.unpack("!H", data[:2])[0]
                if opcode == _TFTP_OPCODE_ERROR:
                    _err_code, msg = (
                        struct.unpack("!H", data[2:4])[0],
                        data[4:-1].decode("ascii", "replace"),
                    )
                    raise RuntimeError(f"Erreur TFTP du serveur : {msg}")
                if opcode == _TFTP_OPCODE_ACK:
                    block = struct.unpack("!H", data[2:4])[0]
                    if block == expected_block:
                        return data, from_addr
                    # ACK d'un bloc différent (paquet dupliqué/en retard) : on réessaie l'attente.
                    continue
                raise RuntimeError(f"Réponse TFTP inattendue (opcode {opcode}).")
            raise TimeoutError(
                f"Pas d'ACK TFTP pour le bloc {expected_block} après {_TFTP_MAX_RETRIES} tentatives"
            ) from last_exc

        # WRQ -> ACK(0), et le serveur TFTP peut répondre depuis un port éphémère
        # différent du port 69 initial (comportement standard du protocole) :
        # on retient l'adresse de la première réponse pour la suite de l'échange.
        _ack_data, peer_addr = _send_and_wait_ack(wrq, 0, server_addr)

        block_no = 1
        offset = 0
        total = len(content)
        while True:
            chunk = content[offset : offset + _TFTP_BLOCK_SIZE]
            packet = struct.pack("!HH", _TFTP_OPCODE_DATA, block_no) + chunk
            _send_and_wait_ack(packet, block_no, peer_addr)
            offset += len(chunk)
            if len(chunk) < _TFTP_BLOCK_SIZE:
                break  # dernier bloc (y compris bloc vide si total est multiple de 512)
            block_no += 1
            if offset > total:  # garde-fou, ne devrait jamais arriver
                break
    finally:
        sock.close()


def _upload_tftp(cfg: FileTransferConfig, filename: str, content: bytes) -> None:
    """Dépose *content* sur le serveur de dépôt via TFTP.

    Args:
        cfg: Paramètres de connexion au serveur de dépôt.
        filename: Nom du fichier distant à créer.
        content: Contenu binaire à écrire.
    """
    logger.debug(f"_upload_tftp | host={cfg.host} filename={filename}")
    port = cfg.port or cfg.default_port()
    remote_name = (
        (cfg.remote_dir.rstrip("/") + "/" + filename)
        if cfg.remote_dir not in ("", "/")
        else filename
    )
    _tftp_upload(cfg.host, port, remote_name, content)


def upload_config_file(cfg: FileTransferConfig, filename: str, content: str) -> None:
    """Dépose *content* (texte) sous *filename* sur le serveur de dépôt
    configuré par *cfg*, en dispatchant vers le bon protocole.

    Bloquant (paramiko/ftplib ne sont pas asyncio) — à appeler via
    ``asyncio.to_thread`` depuis le code async, ce que ``push_config_via_snmp``
    fait déjà.

    Args:
        cfg: Paramètres de connexion au serveur de dépôt.
        filename: Nom du fichier distant à créer.
        content: Contenu texte à écrire.
    """
    logger.debug(
        f"upload_config_file | protocol={cfg.protocol} host={cfg.host} filename={filename}"
    )
    data = content.encode("utf-8")
    if cfg.protocol == "sftp":
        _upload_sftp(cfg, filename, data)
    elif cfg.protocol == "ftp":
        _upload_ftp(cfg, filename, data)
    elif cfg.protocol == "tftp":
        _upload_tftp(cfg, filename, data)
    else:
        raise ValueError(f"Protocole de transfert inconnu : {cfg.protocol!r}")


# ══════════════════════════════════════════════════════════════════════
# Identifiants SNMP (v2c ou v3) — via ezsnmp (bindings Net-SNMP natifs)
# ══════════════════════════════════════════════════════════════════════
#
# ezsnmp (fork actif de l'ancien easysnmp) est une extension C (SWIG autour
# de libnetsnmp), donc BLOQUANTE — pas d'équivalent asyncio natif,
# contrairement à pysnmp. On garde volontairement l'orchestration asyncio
# du reste de ce module (cf. docstring de fichier) en enrobant chaque appel
# ezsnmp dans ``asyncio.to_thread`` — un thread n'est occupé que le temps
# d'un GET/SET/WALK (quelques ms à quelques centaines de ms), pas pendant
# toute la durée du polling (qui, lui, reste un simple ``await asyncio.sleep``).
#
# AVERTISSEMENT — non testé en conditions réelles (cf. avertissement en
# tête de module) : les noms de paramètres ``Session()`` ci-dessous
# (``port_number``, ``security_level``, ``auth_protocol``...) sont vérifiés
# contre la documentation ezsnmp 2.4 en ligne, mais cette bibliothèque a
# changé de noms de paramètres entre easysnmp et ezsnmp par le passé
# (``remote_port`` -> ``port_number`` notamment) — recontrôle contre la
# version d'ezsnmp effectivement installée avant un usage en production.


def _require_ezsnmp():
    """Import paresseux d'ezsnmp (dépendance optionnelle, extension C).

    Returns:
        Le module ``ezsnmp`` importé.

    Raises:
        RuntimeError: Si ``ezsnmp`` n'est pas installable/installé.
    """
    logger.debug("_require_ezsnmp")
    try:
        import ezsnmp
    except ImportError as exc:  # pragma: no cover - dépendance externe
        raise RuntimeError(
            "ezsnmp n'est pas installé (pip install ezsnmp, ou paquet système "
            "python3-ezsnmp sur Debian/Ubuntu — nécessite la bibliothèque "
            "Net-SNMP)."
        ) from exc
    return ezsnmp


@dataclass
class SnmpCredentials:
    """Identifiants SNMP, v2c (communauté) ou v3 (USM).

    Attributes:
        version: ``"v2c"`` ou ``"v3"``.
        community: Communauté SNMP (v2c uniquement — en écriture, donc à ne
            jamais laisser en ``public``/``private`` par défaut).
        username: Utilisateur USM (v3).
        auth_protocol: ``"SHA"``, ``"MD5"`` ou ``""`` (pas d'authentification).
            Volontairement restreint à ce que Net-SNMP accepte de façon
            fiable toutes versions confondues — les variantes SHA-224/256
            dépendent de la build locale de Net-SNMP, non garanties.
        auth_key: Phrase d'authentification (v3, si ``auth_protocol`` non vide).
        priv_protocol: ``"AES"``, ``"DES"`` ou ``""`` (pas de chiffrement).
            Même remarque que pour ``auth_protocol`` : AES-192/256 omis car
            leur nom exact varie selon la build Net-SNMP.
        priv_key: Phrase de confidentialité (v3, si ``priv_protocol`` non vide).
    """

    version: str = "v2c"  # "v2c" | "v3"
    community: str = ""
    username: str = ""
    auth_protocol: str = "SHA"
    auth_key: str = ""
    priv_protocol: str = "AES"
    priv_key: str = ""

    def _security_level(self) -> str:
        """Déduit le ``securityLevel`` USM à partir des protocoles configurés.

        Returns:
            ``"authPriv"``, ``"authNoPriv"`` ou ``"noAuthNoPriv"``.
        """
        logger.debug(f"SnmpCredentials._security_level | version={self.version}")
        if self.auth_protocol and self.priv_protocol:
            return "authPriv"
        if self.auth_protocol:
            return "authNoPriv"
        return "noAuthNoPriv"

    def build_session_kwargs(
        self, hostname: str, port: int, timeout: float, retries: int = 2
    ) -> dict:
        """Construit les kwargs pour ``ezsnmp.Session(**kwargs)``.

        Args:
            hostname: IP/hôte de l'équipement cible.
            port: Port SNMP de l'équipement (0 = port par défaut).
            timeout: Délai d'attente par requête, en secondes.
            retries: Nombre de nouvelles tentatives en cas de timeout.

        Returns:
            Dictionnaire de kwargs prêt à passer à ``ezsnmp.Session(...)``.
        """
        logger.debug(f"SnmpCredentials.build_session_kwargs | hostname={hostname} port={port}")
        kwargs: dict = {
            "hostname": hostname,
            "version": 2 if self.version == "v2c" else 3,
            "timeout": timeout,
            "retries": retries,
        }
        if port:
            kwargs["port_number"] = str(port)
        if self.version == "v2c":
            kwargs["community"] = self.community
        else:
            kwargs["security_level"] = self._security_level()
            kwargs["security_username"] = self.username
            if self.auth_protocol:
                kwargs["auth_protocol"] = self.auth_protocol
                kwargs["auth_passphrase"] = self.auth_key
            if self.priv_protocol:
                kwargs["privacy_protocol"] = self.priv_protocol
                kwargs["privacy_passphrase"] = self.priv_key
        return kwargs


# ══════════════════════════════════════════════════════════════════════
# Drivers de push par constructeur
# ══════════════════════════════════════════════════════════════════════


@dataclass
class _PollOutcome:
    """Résultat normalisé d'un polling de statut, quel que soit le driver."""

    done: bool
    ok: bool
    detail: str = ""


class SnmpPushDriver(ABC):
    """Contrat qu'un « pilote » de push SNMP par constructeur doit implémenter.

    Chaque constructeur expose un MIB de gestion de configuration différent
    (colonnes, valeurs d'énumération, sémantique du polling). Ajouter un
    constructeur = ajouter une sous-classe + l'enregistrer dans
    ``SNMP_PUSH_DRIVERS`` — rien d'autre à toucher dans ce module ni dans le
    plugin GTK, qui ne connaissent que cette interface.

    Les deux méthodes sont volontairement SYNCHRONES (ezsnmp est bloquant) :
    c'est ``push_config_via_snmp`` qui les enrobe dans ``asyncio.to_thread``,
    pas les drivers eux-mêmes — un driver ne connaît rien à asyncio.
    """

    vendor_id: str = ""
    display_name: str = ""
    #: Protocoles de transfert que l'ÉQUIPEMENT sait utiliser pour aller
    #: chercher le fichier lui-même (distinct de ``FileTransferConfig.protocol``,
    #: qui est NOTRE dépôt initial vers le serveur relais).
    supported_fetch_protocols: tuple[str, ...] = ("tftp",)

    @abstractmethod
    def build_push_operations(
        self,
        index: int,
        *,
        filename: str,
        server_host: str,
        protocol: str,
        username: str,
        password: str,
    ) -> list[tuple[str, str, str]]:
        """Retourne la liste d'opérations ``(oid, valeur, type_netsnmp)`` à
        passer à ``session.set_multiple()`` pour déclencher le push.

        ``type_netsnmp`` utilise les codes courts Net-SNMP habituels :
        ``"i"`` (INTEGER), ``"s"`` (OCTET STRING), ``"a"`` (IP ADDRESS).

        Args:
            index: Index de ligne à utiliser dans la table de requête.
            filename: Nom du fichier à récupérer par l'équipement.
            server_host: Adresse du serveur de dépôt.
            protocol: Protocole que l'équipement doit utiliser pour le fetch.
            username: Identifiant optionnel (FTP).
            password: Mot de passe optionnel (FTP).

        Raises:
            NotImplementedError: Toujours, à surcharger par sous-classe.
        """
        logger.debug(f"SnmpPushDriver.build_push_operations | index={index} protocol={protocol}")
        raise NotImplementedError

    @abstractmethod
    def poll_status(self, session, *, row_index: int) -> _PollOutcome:
        """Interroge (GET/WALK synchrones sur *session*) l'état de
        l'opération déclenchée par ``build_push_operations``.

        Appelé en boucle par ``push_config_via_snmp`` jusqu'à ``done=True``
        ou expiration du délai.

        Args:
            session: Session ``ezsnmp`` ouverte vers l'équipement.
            row_index: Index de ligne utilisé lors du push.

        Raises:
            NotImplementedError: Toujours, à surcharger par sous-classe.
        """
        logger.debug(f"SnmpPushDriver.poll_status | row_index={row_index}")
        raise NotImplementedError


class Hh3cComwareDriver(SnmpPushDriver):
    """``HH3C-CONFIG-MAN-MIB`` — opération ``net2Running`` (racine
    ``1.3.6.1.4.1.25506.2.4``).

    Point délicat (cf. avertissement en tête de module) : la table de
    résultat (``hh3cCfgOperateResultTable``) a son propre index, distinct de
    celui de la table d'opération — il faut la parcourir (``session.walk``
    sur la colonne ``hh3cCfgOperateResultOptIndex``) pour retrouver la ligne
    qui correspond à NOTRE opération. ``ezsnmp`` expose directement
    ``item.oid_index`` sur chaque résultat de walk, ce qui évite d'avoir à
    parser la chaîne d'OID à la main pour retrouver cet index (contrairement
    à l'implémentation pysnmp précédente).
    """

    vendor_id = "hh3c_comware"
    display_name = "H3C / HPE Comware"
    supported_fetch_protocols = ("tftp", "ftp")

    _ROOT = "1.3.6.1.4.1.25506.2.4"
    _OPERATE_TYPE = f"{_ROOT}.1.2.4.1.2"
    _OPERATE_PROTOCOL = f"{_ROOT}.1.2.4.1.3"
    _OPERATE_FILENAME = f"{_ROOT}.1.2.4.1.4"
    _OPERATE_SERVER_ADDR = f"{_ROOT}.1.2.4.1.5"
    _OPERATE_USERNAME = f"{_ROOT}.1.2.4.1.6"
    _OPERATE_PASSWORD = f"{_ROOT}.1.2.4.1.7"
    _OPERATE_ROW_STATUS = f"{_ROOT}.1.2.4.1.9"

    _RESULT_OPT_INDEX = f"{_ROOT}.1.2.5.1.2"
    _RESULT_STATE = f"{_ROOT}.1.2.5.1.4"
    _RESULT_FAIL_REASON = f"{_ROOT}.1.2.5.1.7"

    _NET2RUNNING = 4  # ConfigOperationType::net2Running
    _PROTOCOL_VALUES = {"ftp": 1, "tftp": 2}
    _CREATE_AND_GO = 4  # RowStatus::createAndGo

    # ConfigOperationStateType (cf. hh3cCfgOperateState) :
    _STATE_IN_PROGRESS = 1
    _STATE_SUCCESS = 2
    _STATE_LABELS = {
        1: "en cours",
        2: "succès",
        3: "opération invalide",
        4: "protocole invalide",
        5: "nom source invalide",
        6: "nom destination invalide",
        7: "adresse serveur invalide",
        8: "équipement occupé",
        9: "erreur d'ouverture équipement",
        10: "erreur équipement",
        13: "erreur d'ouverture de fichier",
        14: "erreur de transfert de fichier",
        15: "erreur de somme de contrôle",
        17: "échec d'authentification",
        18: "délai dépassé",
        20: "fichier de configuration invalide",
    }

    def build_push_operations(self, index, *, filename, server_host, protocol, username, password):
        """Construit les opérations SNMP SET pour déclencher ``net2Running``.

        Args:
            index: Index de ligne à utiliser dans la table de requête.
            filename: Nom du fichier à récupérer par l'équipement.
            server_host: Adresse du serveur de dépôt.
            protocol: Protocole que l'équipement doit utiliser pour le fetch.
            username: Identifiant optionnel (FTP).
            password: Mot de passe optionnel (FTP).

        Returns:
            Liste de tuples ``(oid, valeur, type_netsnmp)``.
        """
        logger.debug(
            f"Hh3cComwareDriver.build_push_operations | index={index} protocol={protocol}"
        )
        protocol_value = self._PROTOCOL_VALUES.get(protocol)
        if protocol_value is None:
            raise RuntimeError(f"Protocole non supporté par le driver H3C/Comware : {protocol!r}")

        ops = [
            (f"{self._OPERATE_TYPE}.{index}", str(self._NET2RUNNING), "i"),
            (f"{self._OPERATE_PROTOCOL}.{index}", str(protocol_value), "i"),
            (f"{self._OPERATE_FILENAME}.{index}", filename, "s"),
            (f"{self._OPERATE_SERVER_ADDR}.{index}", server_host, "a"),
        ]
        if protocol == "ftp":
            ops.append((f"{self._OPERATE_USERNAME}.{index}", username, "s"))
            ops.append((f"{self._OPERATE_PASSWORD}.{index}", password, "s"))
        # Création de la ligne EN DERNIER (createAndGo déclenche l'opération
        # dès que la ligne devient active — les autres colonnes doivent déjà
        # être connues du SET, cf. sémantique read-create de la RFC 2579).
        ops.append((f"{self._OPERATE_ROW_STATUS}.{index}", str(self._CREATE_AND_GO), "i"))
        return ops

    def poll_status(self, session, *, row_index: int) -> _PollOutcome:
        """Recherche la ligne de résultat correspondant à *row_index*.

        Args:
            session: Session ``ezsnmp`` ouverte vers l'équipement.
            row_index: Index de ligne utilisé lors du push.

        Returns:
            Le ``_PollOutcome`` courant (pas forcément terminé).
        """
        logger.debug(f"Hh3cComwareDriver.poll_status | row_index={row_index}")
        try:
            items = session.walk(self._RESULT_OPT_INDEX)
        except Exception as exc:  # noqa: BLE001
            return _PollOutcome(
                done=True, ok=False, detail=f"Erreur SNMP pendant le polling : {exc}"
            )

        for item in items:
            try:
                value = int(item.value)
            except (TypeError, ValueError):
                continue
            if value != row_index:
                continue
            result_index = item.oid_index
            return self._read_result_row(session, result_index)
        # Pas encore de ligne de résultat pour notre index : l'opération
        # n'a probablement pas encore été traitée par l'équipement.
        return _PollOutcome(done=False, ok=False)

    def _read_result_row(self, session, result_index: str) -> _PollOutcome:
        """Lit l'état et la raison d'échec d'une ligne de résultat.

        Args:
            session: Session ``ezsnmp`` ouverte vers l'équipement.
            result_index: Index de la ligne dans la table de résultat.

        Returns:
            Le ``_PollOutcome`` correspondant à l'état lu.
        """
        logger.debug(f"Hh3cComwareDriver._read_result_row | result_index={result_index}")
        try:
            state_res = session.get(f"{self._RESULT_STATE}.{result_index}")
            fail_res = session.get(f"{self._RESULT_FAIL_REASON}.{result_index}")
        except Exception as exc:  # noqa: BLE001
            return _PollOutcome(
                done=True, ok=False, detail=f"Erreur SNMP pendant la lecture du résultat : {exc}"
            )

        state_item = state_res[0] if isinstance(state_res, (list, tuple)) else state_res
        fail_item = fail_res[0] if isinstance(fail_res, (list, tuple)) else fail_res
        try:
            state_val = int(state_item.value)
        except (TypeError, ValueError):
            return _PollOutcome(
                done=True, ok=False, detail=f"Valeur d'état inattendue : {state_item.value!r}"
            )
        fail_reason = str(fail_item.value) if fail_item.value else ""
        label = self._STATE_LABELS.get(state_val, f"état inconnu ({state_val})")
        if state_val == self._STATE_IN_PROGRESS:
            return _PollOutcome(done=False, ok=False)
        if state_val == self._STATE_SUCCESS:
            return _PollOutcome(done=True, ok=True, detail=label)
        return _PollOutcome(
            done=True, ok=False, detail=f"{label}" + (f" : {fail_reason}" if fail_reason else "")
        )


class CiscoConfigCopyDriver(SnmpPushDriver):
    """``CISCO-CONFIG-COPY-MIB`` (``ccCopyTable``, racine
    ``1.3.6.1.4.1.9.9.96.1.1.1``). Push = ``ccCopySourceFileType=networkFile(1)``
    -> ``ccCopyDestFileType=runningConfig(4)``.

    Plus simple à interroger que H3C : le statut (``ccCopyState``) est une
    colonne de la MÊME ligne/table que celle utilisée pour déclencher
    l'opération — un simple GET sur ``ccCopyState.<index>`` suffit.

    Le FTP est marqué historiquement peu fiable en SNMP sur certains IOS
    anciens (bug Cisco CSCdm53866) — préférer TFTP si disponible.
    """

    vendor_id = "cisco_ios"
    display_name = "Cisco IOS / IOS XE"
    supported_fetch_protocols = (
        "tftp",
        "ftp",
    )  # scp/sftp omis : nécessitent des creds SSH device-side hors périmètre de ce plugin

    _ROOT = "1.3.6.1.4.1.9.9.96.1.1.1.1"
    _PROTOCOL = f"{_ROOT}.2"
    _SOURCE_TYPE = f"{_ROOT}.3"
    _DEST_TYPE = f"{_ROOT}.4"
    _SERVER_ADDR = f"{_ROOT}.5"
    _FILENAME = f"{_ROOT}.6"
    _USERNAME = f"{_ROOT}.7"
    _PASSWORD = f"{_ROOT}.8"
    _STATE = f"{_ROOT}.10"
    _FAIL_CAUSE = f"{_ROOT}.13"
    _ROW_STATUS = f"{_ROOT}.14"

    _NETWORK_FILE = 1
    _RUNNING_CONFIG = 4
    _PROTOCOL_VALUES = {"tftp": 1, "ftp": 2, "rcp": 3, "scp": 4, "sftp": 5}
    _CREATE_AND_GO = 4

    # ccCopyState : waiting(1) running(2) successful(3) failed(4)
    _STATE_WAITING = 1
    _STATE_RUNNING = 2
    _STATE_SUCCESSFUL = 3
    _STATE_LABELS = {1: "en attente", 2: "en cours", 3: "succès", 4: "échec"}

    def build_push_operations(self, index, *, filename, server_host, protocol, username, password):
        """Construit les opérations SNMP SET pour déclencher la copie.

        Args:
            index: Index de ligne à utiliser dans ``ccCopyTable``.
            filename: Nom du fichier à récupérer par l'équipement.
            server_host: Adresse du serveur de dépôt.
            protocol: Protocole que l'équipement doit utiliser pour le fetch.
            username: Identifiant optionnel (FTP).
            password: Mot de passe optionnel (FTP).

        Returns:
            Liste de tuples ``(oid, valeur, type_netsnmp)``.
        """
        logger.debug(
            f"CiscoConfigCopyDriver.build_push_operations | index={index} protocol={protocol}"
        )
        protocol_value = self._PROTOCOL_VALUES.get(protocol)
        if protocol_value is None:
            raise RuntimeError(f"Protocole non supporté par le driver Cisco : {protocol!r}")

        ops = [
            (f"{self._PROTOCOL}.{index}", str(protocol_value), "i"),
            (f"{self._SOURCE_TYPE}.{index}", str(self._NETWORK_FILE), "i"),
            (f"{self._DEST_TYPE}.{index}", str(self._RUNNING_CONFIG), "i"),
            (f"{self._SERVER_ADDR}.{index}", server_host, "a"),
            (f"{self._FILENAME}.{index}", filename, "s"),
        ]
        if protocol == "ftp":
            ops.append((f"{self._USERNAME}.{index}", username, "s"))
            ops.append((f"{self._PASSWORD}.{index}", password, "s"))
        ops.append((f"{self._ROW_STATUS}.{index}", str(self._CREATE_AND_GO), "i"))
        return ops

    def poll_status(self, session, *, row_index: int) -> _PollOutcome:
        """Lit l'état ``ccCopyState``/``ccCopyFailCause`` de la ligne du push.

        Args:
            session: Session ``ezsnmp`` ouverte vers l'équipement.
            row_index: Index de ligne utilisé lors du push.

        Returns:
            Le ``_PollOutcome`` correspondant à l'état lu.
        """
        logger.debug(f"CiscoConfigCopyDriver.poll_status | row_index={row_index}")
        try:
            state_res = session.get(f"{self._STATE}.{row_index}")
            fail_res = session.get(f"{self._FAIL_CAUSE}.{row_index}")
        except Exception as exc:  # noqa: BLE001
            return _PollOutcome(
                done=True, ok=False, detail=f"Erreur SNMP pendant le polling : {exc}"
            )

        state_item = state_res[0] if isinstance(state_res, (list, tuple)) else state_res
        fail_item = fail_res[0] if isinstance(fail_res, (list, tuple)) else fail_res
        try:
            state_val = int(state_item.value)
        except (TypeError, ValueError):
            return _PollOutcome(
                done=True, ok=False, detail=f"Valeur d'état inattendue : {state_item.value!r}"
            )
        fail_cause = str(fail_item.value) if fail_item.value else ""
        label = self._STATE_LABELS.get(state_val, f"état inconnu ({state_val})")
        if state_val in (self._STATE_WAITING, self._STATE_RUNNING):
            return _PollOutcome(done=False, ok=False)
        if state_val == self._STATE_SUCCESSFUL:
            return _PollOutcome(done=True, ok=True, detail=label)
        return _PollOutcome(
            done=True, ok=False, detail=f"{label}" + (f" : {fail_cause}" if fail_cause else "")
        )


SNMP_PUSH_DRIVERS: dict[str, SnmpPushDriver] = {
    "hh3c_comware": Hh3cComwareDriver(),
    "cisco_ios": CiscoConfigCopyDriver(),
}


def iter_driver_choices() -> list[tuple[str, str]]:
    """Retourne ``[(vendor_id, display_name), ...]`` pour peupler un sélecteur."""
    logger.debug("iter_driver_choices")
    return [(v.vendor_id, v.display_name) for v in SNMP_PUSH_DRIVERS.values()]


# ══════════════════════════════════════════════════════════════════════
# Profils SNMP (équivalent de DeviceProfile/ProfileStore pour Netmiko)
# ══════════════════════════════════════════════════════════════════════


@dataclass
class SnmpDeviceProfile:
    """Un profil SNMP, référencé par nom depuis la colonne ``type``/``profile``
    de l'inventaire CSV (même fichier/format que pour Netmiko — mais un
    inventaire SNMP est distinct d'un inventaire Netmiko : ne pas les
    mélanger dans un même CSV, les colonnes de profil pointent vers deux
    ``ProfileStore`` différents).
    """

    name: str
    vendor_id: str  # clé dans SNMP_PUSH_DRIVERS, ex. "hh3c_comware"
    snmp: SnmpCredentials = field(default_factory=SnmpCredentials)
    port: int = 161
    timeout: float = 5.0

    def driver(self) -> SnmpPushDriver:
        """Résout le driver SNMP correspondant à ``vendor_id``.

        Returns:
            L'instance ``SnmpPushDriver`` enregistrée pour ce constructeur.

        Raises:
            ValueError: Si ``vendor_id`` ne correspond à aucun driver connu.
        """
        logger.debug(f"SnmpDeviceProfile.driver | vendor_id={self.vendor_id}")
        driver = SNMP_PUSH_DRIVERS.get(self.vendor_id)
        if driver is None:
            raise ValueError(f"Constructeur inconnu : {self.vendor_id!r}")
        return driver


class SnmpProfileStore:
    """Charge/sauvegarde des ``SnmpDeviceProfile`` dans un ``.ini`` séparé de
    celui de Netmiko (``snmp_profiles.ini`` par convention côté plugin).
    """

    def __init__(self, path: str | Path):
        """Initialise le magasin et charge les profils existants.

        Args:
            path: Chemin du fichier ``.ini`` de profils SNMP.
        """
        logger.debug(f"SnmpProfileStore.__init__ | path={path}")
        self.path = Path(path)
        self._profiles: dict[str, SnmpDeviceProfile] = {}
        if self.path.exists():
            self.reload()

    def reload(self) -> None:
        """Recharge les profils depuis le fichier ``.ini``."""
        logger.debug(f"SnmpProfileStore.reload | path={self.path}")
        import configparser

        cp = configparser.ConfigParser()
        cp.read(self.path, encoding="utf-8")
        profiles: dict[str, SnmpDeviceProfile] = {}
        for section in cp.sections():
            s = cp[section]
            creds = SnmpCredentials(
                version=s.get("snmp_version", fallback="v2c"),
                community=s.get("community", fallback=""),
                username=s.get("username", fallback=""),
                auth_protocol=s.get("auth_protocol", fallback="SHA"),
                auth_key=s.get("auth_key", fallback=""),
                priv_protocol=s.get("priv_protocol", fallback="AES128"),
                priv_key=s.get("priv_key", fallback=""),
            )
            profiles[section] = SnmpDeviceProfile(
                name=section,
                vendor_id=s.get("vendor_id", fallback=""),
                snmp=creds,
                port=s.getint("port", fallback=161),
                timeout=s.getfloat("timeout", fallback=5.0),
            )
        self._profiles = profiles

    def get(self, name: str) -> SnmpDeviceProfile | None:
        """Récupère un profil par nom.

        Args:
            name: Nom du profil recherché.
        """
        logger.debug(f"SnmpProfileStore.get | name={name}")
        return self._profiles.get(name)

    def names(self) -> list[str]:
        """Retourne les noms de profils, triés alphabétiquement."""
        logger.debug("SnmpProfileStore.names")
        return sorted(self._profiles.keys())

    def all(self) -> list[SnmpDeviceProfile]:
        """Retourne tous les profils, triés par nom."""
        logger.debug("SnmpProfileStore.all")
        return [self._profiles[n] for n in self.names()]

    def set(self, profile: SnmpDeviceProfile) -> None:
        """Ajoute ou met à jour un profil.

        Args:
            profile: Instance ``SnmpDeviceProfile`` à enregistrer.
        """
        logger.debug(f"SnmpProfileStore.set | name={profile.name}")
        self._profiles[profile.name] = profile

    def delete(self, name: str) -> None:
        """Supprime un profil.

        Args:
            name: Nom du profil à supprimer.
        """
        logger.debug(f"SnmpProfileStore.delete | name={name}")
        self._profiles.pop(name, None)

    def save(self) -> None:
        """Écrit tous les profils sur disque (permissions restreintes)."""
        logger.debug(f"SnmpProfileStore.save | path={self.path} n={len(self._profiles)}")
        import configparser

        cp = configparser.ConfigParser()
        for name in self.names():
            p = self._profiles[name]
            cp[name] = {
                "vendor_id": p.vendor_id,
                "port": str(p.port),
                "timeout": str(p.timeout),
                "snmp_version": p.snmp.version,
                "community": p.snmp.community,
                "username": p.snmp.username,
                "auth_protocol": p.snmp.auth_protocol,
                "auth_key": p.snmp.auth_key,
                "priv_protocol": p.snmp.priv_protocol,
                "priv_key": p.snmp.priv_key,
            }
        with open(self.path, "w", encoding="utf-8") as fh:
            cp.write(fh)
        try:
            self.path.chmod(
                0o600
            )  # contient des secrets (communauté, clés v3) : permissions restreintes
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════
# Push d'un hôte + orchestration en masse
# ══════════════════════════════════════════════════════════════════════


@dataclass
class SnmpPushResult:
    """Même forme que ``netmiko_bulk_core.PushResult`` (champs identiques),
    pour pouvoir réutiliser ``_write_log``/``_write_manifest``/
    ``summarize_results`` sans duplication (duck typing sur ces attributs).
    """

    row: InventoryRow
    status: str  # STATUS_*
    output: str = ""
    error: str = ""
    config_errors: list[str] = field(default_factory=list)
    log_path: str = ""
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        """``True`` si le statut de ce résultat est ``STATUS_OK``."""
        logger.debug(f"SnmpPushResult.ok | status={self.status}")
        return self.status == STATUS_OK


async def push_config_via_snmp(
    row: InventoryRow,
    profile: SnmpDeviceProfile,
    rendered_config: str,
    transfer: FileTransferConfig,
    *,
    poll_timeout_s: float = 60.0,
    poll_interval_s: float = 2.0,
) -> SnmpPushResult:
    """Pousse *rendered_config* sur l'hôte de *row* via le driver SNMP de
    *profile*, en le déposant d'abord sur le serveur relais décrit par
    *transfer*.

    Toute la partie ezsnmp (bloquante) est déportée dans des fonctions
    synchrones internes, appelées via ``asyncio.to_thread`` — cf. le
    docstring en tête de la section "Identifiants SNMP" plus haut dans ce
    fichier pour le pourquoi de ce choix (ezsnmp = extension C sans
    asyncio natif).

    Ne journalise pas sur disque elle-même (même convention que
    ``netmiko_bulk_core.push_to_device`` — cf. ``run_bulk_snmp_push``).

    Args:
        row: Ligne d'inventaire de l'équipement cible.
        profile: Profil SNMP (driver + identifiants) à utiliser.
        rendered_config: Configuration déjà rendue (variables substituées).
        transfer: Paramètres du serveur de dépôt intermédiaire.
        poll_timeout_s: Délai maximal d'attente du résultat, en secondes.
        poll_interval_s: Intervalle entre deux sondages, en secondes.

    Returns:
        Le ``SnmpPushResult`` de l'envoi.
    """
    logger.debug(
        f"push_config_via_snmp | ip={row.ip} vendor={profile.vendor_id} transfer_host={transfer.host}"
    )
    started = time.monotonic()
    try:
        driver = profile.driver()
    except ValueError as exc:
        return SnmpPushResult(row=row, status=STATUS_FAILED, error=str(exc))

    if transfer.protocol not in driver.supported_fetch_protocols:
        return SnmpPushResult(
            row=row,
            status=STATUS_FAILED,
            error=(
                f"Le driver {driver.display_name} ne sait pas récupérer un fichier en "
                f"{transfer.protocol} (protocoles supportés : {', '.join(driver.supported_fetch_protocols)})."
            ),
        )

    safe_ip = re.sub(r"[^A-Za-z0-9_.-]", "_", row.ip)
    filename = f"gcm_push_{safe_ip}_{row.line_no}.cfg"

    try:
        await asyncio.to_thread(upload_config_file, transfer, filename, rendered_config)
    except Exception as exc:  # noqa: BLE001
        return SnmpPushResult(
            row=row,
            status=STATUS_FAILED,
            error=f"Échec du dépôt du fichier ({transfer.protocol} vers {transfer.host}) : {exc}",
            duration_s=time.monotonic() - started,
        )

    try:
        ezsnmp = _require_ezsnmp()
    except RuntimeError as exc:
        return SnmpPushResult(
            row=row, status=STATUS_FAILED, error=str(exc), duration_s=time.monotonic() - started
        )

    # Index de ligne unique pour cette exécution : horodatage (ms) tronqué +
    # numéro de ligne CSV, pour limiter le risque de collision entre hôtes
    # poussés en parallèle dans le même run (chaque hôte a sa PROPRE session
    # SNMP/table, donc une collision n'est risquée qu'en cas de réutilisation
    # d'un ancien index déjà présent côté équipement — extrêmement improbable
    # avec cet horodatage).
    row_index = (int(time.time() * 1000) % 1_000_000) * 100 + (row.line_no % 100)

    def _open_session():
        """Ouvre une session ``ezsnmp`` vers l'équipement de *row*."""
        logger.debug(f"push_config_via_snmp._open_session | ip={row.ip}")
        kwargs = profile.snmp.build_session_kwargs(
            hostname=row.ip, port=profile.port, timeout=profile.timeout
        )
        return ezsnmp.Session(**kwargs)

    def _trigger():
        """Déclenche l'opération de push via le driver du profil."""
        logger.debug(f"push_config_via_snmp._trigger | ip={row.ip} row_index={row_index}")
        session = _open_session()
        ops = driver.build_push_operations(
            row_index,
            filename=filename,
            server_host=transfer.host,
            protocol=transfer.protocol,
            username=transfer.username,
            password=transfer.password,
        )
        session.set_multiple(ops)
        return session

    try:
        session = await asyncio.to_thread(_trigger)
    except Exception as exc:  # noqa: BLE001
        return SnmpPushResult(
            row=row,
            status=STATUS_FAILED,
            error=f"Erreur SNMP (déclenchement) : {exc}",
            duration_s=time.monotonic() - started,
        )

    deadline = time.monotonic() + poll_timeout_s
    while True:
        try:
            outcome = await asyncio.to_thread(driver.poll_status, session, row_index=row_index)
        except Exception as exc:  # noqa: BLE001
            return SnmpPushResult(
                row=row,
                status=STATUS_FAILED,
                error=f"Erreur SNMP (polling) : {exc}",
                duration_s=time.monotonic() - started,
            )
        if outcome.done:
            status = STATUS_OK if outcome.ok else STATUS_FAILED
            return SnmpPushResult(
                row=row,
                status=status,
                output=outcome.detail if outcome.ok else "",
                error=""
                if outcome.ok
                else (outcome.detail or "Échec du push SNMP (raison inconnue)."),
                duration_s=time.monotonic() - started,
            )
        if time.monotonic() >= deadline:
            return SnmpPushResult(
                row=row,
                status=STATUS_FAILED,
                error=f"Délai de {poll_timeout_s:.0f}s dépassé en attendant la confirmation de l'équipement.",
                duration_s=time.monotonic() - started,
            )
        await asyncio.sleep(poll_interval_s)


async def run_bulk_snmp_push_async(
    rows: list[InventoryRow],
    profiles: SnmpProfileStore,
    template_text: str,
    transfer: FileTransferConfig,
    *,
    log_dir: str | Path,
    max_workers: int = 10,
    on_row_start: Callable[[InventoryRow], None] | None = None,
    on_row_done: Callable[[SnmpPushResult], None] | None = None,
    cancel_event=None,  # threading.Event, vérifié depuis la coroutine (pas de dépendance asyncio.Event imposée à l'appelant GTK)
) -> list[SnmpPushResult]:
    """Équivalent asyncio de ``netmiko_bulk_core.run_bulk_push`` : pousse sur
    tous les *rows* en parallèle (borné par *max_workers*, via un
    ``asyncio.Semaphore`` plutôt qu'un ``ThreadPoolExecutor`` — le SNMP/UDP
    n'a pas le coût par connexion du SSH, cf. docstring de module),
    journalise chaque hôte sur disque, écrit un manifeste JSON agrégé.

    Args:
        rows: Lignes d'inventaire à traiter.
        profiles: Magasin de profils SNMP.
        template_text: Contenu du gabarit de configuration.
        transfer: Paramètres du serveur de dépôt intermédiaire.
        log_dir: Dossier où écrire les journaux d'envoi.
        max_workers: Nombre d'envois concurrents (borne le ``Semaphore``).
        on_row_start: Callback appelé avant l'envoi d'une ligne.
        on_row_done: Callback appelé après l'envoi d'une ligne.
        cancel_event: ``threading.Event`` permettant d'annuler l'exécution.

    Returns:
        Liste des ``SnmpPushResult`` de tous les envois effectués.
    """
    logger.debug(f"run_bulk_snmp_push_async | n_rows={len(rows)} max_workers={max_workers}")
    log_dir = Path(log_dir)
    semaphore = asyncio.Semaphore(max(1, max_workers))
    results: list[SnmpPushResult] = []

    async def _work(row: InventoryRow) -> SnmpPushResult:
        """Traite une ligne d'inventaire (profil, gabarit, push, journal).

        Args:
            row: Ligne d'inventaire à traiter.

        Returns:
            Le ``SnmpPushResult`` de cette ligne.
        """
        logger.debug(f"run_bulk_snmp_push_async._work | ip={row.ip}")
        async with semaphore:
            if cancel_event is not None and cancel_event.is_set():
                result = SnmpPushResult(
                    row=row, status=STATUS_SKIPPED, error="Annulé avant envoi."
                )
                result.log_path = _write_log(log_dir, row, result)
                return result

            profile = profiles.get(row.profile_name)
            if profile is None:
                result = SnmpPushResult(
                    row=row, status=STATUS_FAILED, error=f"Profil inconnu : '{row.profile_name}'"
                )
                result.log_path = _write_log(log_dir, row, result)
                return result

            context = row.render_context()
            missing = find_missing_variables(template_text, context)
            if missing:
                result = SnmpPushResult(
                    row=row,
                    status=STATUS_FAILED,
                    error=f"Variables manquantes dans le CSV : {', '.join(missing)}",
                )
                result.log_path = _write_log(log_dir, row, result)
                return result

            if on_row_start:
                on_row_start(row)
            rendered = render_template(template_text, context)
            result = await push_config_via_snmp(row, profile, rendered, transfer)
            result.log_path = _write_log(log_dir, row, result)
            if on_row_done:
                on_row_done(result)
            return result

    results = await asyncio.gather(*(_work(row) for row in rows))
    results = list(results)
    _write_manifest(log_dir, results)
    return results


def run_bulk_snmp_push(
    rows: list[InventoryRow],
    profiles: SnmpProfileStore,
    template_text: str,
    transfer: FileTransferConfig,
    *,
    log_dir: str | Path,
    max_workers: int = 10,
    on_row_start: Callable[[InventoryRow], None] | None = None,
    on_row_done: Callable[[SnmpPushResult], None] | None = None,
    cancel_event=None,
) -> list[SnmpPushResult]:
    """Point d'entrée synchrone (``asyncio.run`` interne) — à appeler depuis
    le thread d'arrière-plan du plugin GTK, exactement comme
    ``netmiko_bulk_core.run_bulk_push`` (même signature d'appelant, cf.
    ``plugin_snmp_push.py``). Ne PAS appeler depuis le thread GTK principal :
    ``asyncio.run`` bloque jusqu'à la fin de tous les pushes.

    Args:
        rows: Lignes d'inventaire à traiter.
        profiles: Magasin de profils SNMP.
        template_text: Contenu du gabarit de configuration.
        transfer: Paramètres du serveur de dépôt intermédiaire.
        log_dir: Dossier où écrire les journaux d'envoi.
        max_workers: Nombre d'envois concurrents.
        on_row_start: Callback appelé avant l'envoi d'une ligne.
        on_row_done: Callback appelé après l'envoi d'une ligne.
        cancel_event: ``threading.Event`` permettant d'annuler l'exécution.

    Returns:
        Liste des ``SnmpPushResult`` de tous les envois effectués.
    """
    logger.debug(f"run_bulk_snmp_push | n_rows={len(rows)} max_workers={max_workers}")
    return asyncio.run(
        run_bulk_snmp_push_async(
            rows,
            profiles,
            template_text,
            transfer,
            log_dir=log_dir,
            max_workers=max_workers,
            on_row_start=on_row_start,
            on_row_done=on_row_done,
            cancel_event=cancel_event,
        )
    )
