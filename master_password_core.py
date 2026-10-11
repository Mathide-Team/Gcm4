#!/usr/bin/python3
# -*- coding: UTF-8 -*-
"""Protection par mot de passe maître du fichier de clé locale (``KEY_FILE``).

Zéro dépendance GTK — voir ``CONSIGNES-AGENTS-IA.md``. Traite l'item
« Master password au démarrage » de `docs/features-backlog.md`
(urgence haute, sécurité), non commencé jusqu'à cette session.

## Constat sur l'existant

``gcm4_core.initialise_encyption_key()``/``load_encryption_key()`` génèrent
et lisent ``KEY_FILE`` (``~/.gcm/.gcm.key``) en clair sur disque (permissions
``0o600``, donc protégé des autres utilisateurs du système, mais lisible par
quiconque a accès au compte — ex. une sauvegarde non chiffrée, un accès
physique à la machine déverrouillée). C'est cette clé locale qui sert
ensuite (via ``pyAES``/``gcm4_core.encrypt``/``decrypt``) à chiffrer les mots
de passe stockés dans ``gcm.conf``. Un « master password » a pour but de ne
plus jamais écrire cette clé en clair : elle est enveloppée
(chiffrée) par une clé dérivée du mot de passe maître, que l'utilisatrice
retape à chaque démarrage — sans ce mot de passe, ``KEY_FILE`` seul ne
suffit plus à déchiffrer les mots de passe stockés.

## Ce que ce module fait (et ne fait pas)

Ce module fournit uniquement la **logique de protection/déverrouillage du
contenu de ``KEY_FILE``** — dérivation de clé (PBKDF2-HMAC-SHA256, stdlib
``hashlib``, pas de nouvelle dépendance), enveloppe/désenveloppe via
``pyAES`` (déjà utilisé par le reste du projet pour les mots de passe,
cohérence délibérée plutôt qu'un deuxième algorithme), vérificateur
d'intégrité (détecte un mauvais mot de passe au lieu de renvoyer une clé
corrompue silencieusement), et **rétrocompatibilité totale** : un
``KEY_FILE`` existant, non protégé, reste lisible tel quel
(``is_protected()`` renvoie ``False``) — aucune migration forcée, aucun
risque de casser la configuration d'une utilisatrice existante (contrainte
explicite de `CLAUDE.md`).

Ce module ne fait **pas** : demander le mot de passe maître à l'utilisatrice
(boîte de dialogue GTK au démarrage), décider de la politique en cas d'oubli
du mot de passe (pas de mécanisme de recouvrement identifié — un mot de
passe maître perdu rend les mots de passe stockés définitivement
inaccessibles, choix de compromis à confirmer avec l'auteure), ni modifier
``gcm4_core.load_encryption_key()``/``initialise_encyption_key()`` pour
appeler ce module — ces trois points touchent à l'expérience utilisatrice
(GTK, flux de démarrage, gestion d'erreur en cas d'oubli) et restent
volontairement hors périmètre de cette session, documentés dans
`docs/sessions/` plutôt que tranchés seul en même temps que la logique de
chiffrement elle-même.

## Format du contenu protégé

``GCM4MPW1:<salt base64>:<vérificateur hex>:<clé locale chiffrée base64>``
(``GCM4MPW1`` — préfixe magique versionné, permet de faire évoluer le format
plus tard sans ambiguïté avec un ``KEY_FILE`` non protégé, qui ne commence
jamais par ce préfixe puisqu'il ne contient que le résultat de
``"%x" % (x * y)`` de ``initialise_encyption_key()``, uniquement des
chiffres hexadécimaux).
"""

from __future__ import annotations

import base64
import hashlib
import os

from loguru import logger as app_logger

import pyAES

__all__ = [
    "MASTER_PASSWORD_MAGIC",
    "PBKDF2_ITERATIONS",
    "InvalidMasterPasswordError",
    "CorruptedProtectedContentError",
    "is_protected",
    "protect_key_file_content",
    "unlock_key_file_content",
    "rewrap_key_file_content",
    "remove_master_password_protection",
]

MASTER_PASSWORD_MAGIC = "GCM4MPW1:"

# 200 000 itérations : recommandation OWASP 2023 pour PBKDF2-HMAC-SHA256
# (>= 600 000 recommandé pour un stockage de mots de passe utilisateur côté
# serveur ; ici la menace est différente — dérivation locale, à chaque
# démarrage de l'app sur le poste de l'utilisatrice — un compromis a été
# choisi entre coût de calcul au démarrage et résistance au brute-force
# hors-ligne si le KEY_FILE protégé est exfiltré. Non mesuré sur une machine
# réelle dans cet environnement de travail (pas de GTK/matériel cible
# disponible ici) — à valider empiriquement (temps de démarrage perçu)
# avant de considérer ce chiffre définitif.
PBKDF2_ITERATIONS = 200_000

_VERIFIER_CONTEXT = "gcm4-master-password-check"


class InvalidMasterPasswordError(Exception):
    """Levée quand le mot de passe maître fourni ne correspond pas."""


class CorruptedProtectedContentError(Exception):
    """Levée quand le contenu protégé est malformé (format inattendu)."""


def is_protected(key_file_content: str) -> bool:
    """Indique si ``key_file_content`` est protégé par un mot de passe maître.

    Args:
        key_file_content (str): Contenu brut lu depuis ``KEY_FILE``.

    Returns:
        bool: ``True`` si le contenu porte le préfixe magique
            :data:`MASTER_PASSWORD_MAGIC` (donc protégé), ``False`` sinon
            (y compris pour un ``KEY_FILE`` legacy en clair ou un contenu
            vide).
    """
    app_logger.debug(f"is_protected() called | len={len(key_file_content)}")
    result = key_file_content.startswith(MASTER_PASSWORD_MAGIC)
    app_logger.debug(f"is_protected() returning | result={result}")
    return result


def _derive_key_hex(master_password: str, salt: bytes) -> str:
    """Dérive une clé AES-256 (en hexadécimal) depuis un mot de passe maître.

    Args:
        master_password (str): Mot de passe maître saisi par l'utilisatrice.
        salt (bytes): Sel aléatoire propre à ce ``KEY_FILE`` protégé.

    Returns:
        str: Clé dérivée de 32 octets, représentée en hexadécimal (64
            caractères) — format accepté par ``pyAES.encrypt``/``decrypt``
            comme mot de passe.
    """
    app_logger.debug(f"_derive_key_hex() called | len(salt)={len(salt)} (mot de passe masqué)")
    derived = hashlib.pbkdf2_hmac(
        "sha256", master_password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )
    result = derived.hex()
    app_logger.debug("_derive_key_hex() returning | clé dérivée (masquée)")
    return result


def _verifier_for(derived_key_hex: str) -> str:
    """Calcule le vérificateur d'intégrité associé à une clé dérivée.

    Le vérificateur permet de détecter un mot de passe maître incorrect
    *sans* déchiffrer la clé locale au préalable : il ne dépend que de la
    clé dérivée, jamais du contenu chiffré.

    Args:
        derived_key_hex (str): Clé dérivée (hex) issue de
            :func:`_derive_key_hex`.

    Returns:
        str: Empreinte SHA-256 (hex) de la clé dérivée concaténée à un
            contexte fixe.
    """
    app_logger.debug("_verifier_for() called | clé dérivée (masquée)")
    result = hashlib.sha256(f"{derived_key_hex}:{_VERIFIER_CONTEXT}".encode()).hexdigest()
    app_logger.debug(f"_verifier_for() returning | verifier={result[:8]}...")
    return result


def protect_key_file_content(raw_key: str, master_password: str) -> str:
    """Enveloppe une clé locale en clair sous un mot de passe maître.

    Args:
        raw_key (str): Contenu actuel de ``KEY_FILE`` (clé locale en clair,
            telle que produite par ``gcm4_core.initialise_encyption_key()``).
        master_password (str): Mot de passe maître choisi par l'utilisatrice.

    Returns:
        str: Nouveau contenu à écrire dans ``KEY_FILE``, au format décrit
            dans la docstring de module (préfixé
            :data:`MASTER_PASSWORD_MAGIC`).

    Raises:
        ValueError: Si ``master_password`` est vide — un mot de passe maître
            vide n'apporterait aucune protection réelle tout en donnant une
            fausse impression de sécurité.
    """
    app_logger.debug(
        f"protect_key_file_content() called | len(raw_key)={len(raw_key)} (clés masquées)"
    )
    if not master_password:
        app_logger.debug("protect_key_file_content() raising | mot de passe maître vide")
        raise ValueError("master_password must not be empty")
    salt = os.urandom(16)
    derived_key_hex = _derive_key_hex(master_password, salt)
    verifier = _verifier_for(derived_key_hex)
    ciphertext = pyAES.encrypt(raw_key, derived_key_hex)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    result = f"{MASTER_PASSWORD_MAGIC}{salt_b64}:{verifier}:{ciphertext}"
    app_logger.debug(f"protect_key_file_content() returning | len(result)={len(result)}")
    return result


def _parse_protected_content(protected_content: str) -> tuple[bytes, str, str]:
    """Décompose un contenu protégé en (salt, vérificateur, texte chiffré).

    Args:
        protected_content (str): Contenu de ``KEY_FILE``, tel que produit
            par :func:`protect_key_file_content`.

    Returns:
        tuple[bytes, str, str]: Le sel décodé, le vérificateur (hex), et le
            texte chiffré (base64, tel quel, à passer à ``pyAES.decrypt``).

    Raises:
        CorruptedProtectedContentError: Si ``protected_content`` ne porte
            pas le préfixe magique, ou n'a pas le nombre de parties attendu,
            ou si le sel n'est pas du base64 valide.
    """
    app_logger.debug(f"_parse_protected_content() called | len={len(protected_content)}")
    if not is_protected(protected_content):
        app_logger.debug("_parse_protected_content() raising | préfixe magique absent")
        raise CorruptedProtectedContentError(
            "Content is not master-password-protected (missing magic prefix)"
        )
    body = protected_content[len(MASTER_PASSWORD_MAGIC) :]
    parts = body.split(":", 2)
    if len(parts) != 3:
        app_logger.debug(f"_parse_protected_content() raising | nombre de parties={len(parts)}")
        raise CorruptedProtectedContentError(f"Expected 3 ':'-separated fields, got {len(parts)}")
    salt_b64, verifier, ciphertext = parts
    try:
        salt = base64.b64decode(salt_b64, validate=True)
    except Exception as exc:
        app_logger.debug(f"_parse_protected_content() raising | salt invalide: {exc}")
        raise CorruptedProtectedContentError("Salt is not valid base64") from exc
    app_logger.debug("_parse_protected_content() returning | contenu décomposé")
    return salt, verifier, ciphertext


def unlock_key_file_content(protected_content: str, master_password: str) -> str:
    """Déchiffre une clé locale protégée à l'aide du mot de passe maître.

    Args:
        protected_content (str): Contenu de ``KEY_FILE``, tel que produit
            par :func:`protect_key_file_content`.
        master_password (str): Mot de passe maître saisi par l'utilisatrice.

    Returns:
        str: La clé locale en clair (même valeur que ``raw_key`` passé à
            :func:`protect_key_file_content` lors de la protection).

    Raises:
        CorruptedProtectedContentError: Si ``protected_content`` est
            malformé (voir :func:`_parse_protected_content`).
        InvalidMasterPasswordError: Si ``master_password`` ne correspond pas
            au mot de passe utilisé lors de la protection (vérificateur
            invalide) — la clé locale n'est **pas** déchiffrée dans ce cas.
    """
    app_logger.debug(
        f"unlock_key_file_content() called | len={len(protected_content)} (mot de passe masqué)"
    )
    salt, expected_verifier, ciphertext = _parse_protected_content(protected_content)
    derived_key_hex = _derive_key_hex(master_password, salt)
    if _verifier_for(derived_key_hex) != expected_verifier:
        app_logger.debug("unlock_key_file_content() raising | mot de passe maître incorrect")
        raise InvalidMasterPasswordError("Incorrect master password")
    raw_key = pyAES.decrypt(ciphertext, derived_key_hex)
    app_logger.debug(f"unlock_key_file_content() returning | len(raw_key)={len(raw_key)} (masqué)")
    return raw_key


def rewrap_key_file_content(
    protected_content: str, old_master_password: str, new_master_password: str
) -> str:
    """Change le mot de passe maître protégeant une clé locale.

    Args:
        protected_content (str): Contenu actuellement protégé de
            ``KEY_FILE``.
        old_master_password (str): Mot de passe maître actuel.
        new_master_password (str): Nouveau mot de passe maître souhaité.

    Returns:
        str: Nouveau contenu à écrire dans ``KEY_FILE``, protégé par
            ``new_master_password`` (nouveau sel, nouveau vérificateur).

    Raises:
        CorruptedProtectedContentError: Voir :func:`unlock_key_file_content`.
        InvalidMasterPasswordError: Si ``old_master_password`` est incorrect.
        ValueError: Si ``new_master_password`` est vide (voir
            :func:`protect_key_file_content`).
    """
    app_logger.debug(
        f"rewrap_key_file_content() called | len={len(protected_content)} (mots de passe masqués)"
    )
    raw_key = unlock_key_file_content(protected_content, old_master_password)
    result = protect_key_file_content(raw_key, new_master_password)
    app_logger.debug(f"rewrap_key_file_content() returning | len(result)={len(result)}")
    return result


def remove_master_password_protection(protected_content: str, master_password: str) -> str:
    """Retire la protection par mot de passe maître d'une clé locale.

    Renvoie la clé locale en clair, prête à être réécrite telle quelle dans
    ``KEY_FILE`` (revient au comportement legacy — voir docstring de
    module). Le choix de désactiver la protection reste une décision GTK
    (bouton dans les préférences) hors périmètre de ce module.

    Args:
        protected_content (str): Contenu actuellement protégé de
            ``KEY_FILE``.
        master_password (str): Mot de passe maître actuel, requis pour
            confirmer le retrait de la protection.

    Returns:
        str: La clé locale en clair (contenu legacy, non protégé).

    Raises:
        CorruptedProtectedContentError: Voir :func:`unlock_key_file_content`.
        InvalidMasterPasswordError: Voir :func:`unlock_key_file_content`.
    """
    app_logger.debug(
        f"remove_master_password_protection() called | len={len(protected_content)} (masqué)"
    )
    raw_key = unlock_key_file_content(protected_content, master_password)
    app_logger.debug(
        f"remove_master_password_protection() returning | len(raw_key)={len(raw_key)} (masqué)"
    )
    return raw_key
