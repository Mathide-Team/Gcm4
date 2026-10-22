"""Logique du plugin telnet, sans GTK : commande, environnement, commandes après connexion.

Reprend ``plugins/plugin_telnet.py`` (GTK3) :

- sans utilisateur **ou** sans mot de passe : ``telnet [paramètres] hôte port``
  (pas de saisie automatique, l'utilisateur est ignoré comme en GTK3) ;
- avec les deux : ``expect -f telnet.expect telnet -l utilisateur
  [paramètres] hôte port`` ; le mot de passe est donné au script par un
  tube (descripteur 3), jamais par la ligne de commande ;
- ``commands`` : lignes envoyées après la connexion, la première fois au
  bout de 3 s ; une ligne ``##D=<ms>`` ajoute un délai avant les suivantes.

Options de l'hôte (``host.protocol_options["telnet"]``), mêmes clés INI que
GTK3 : :data:`OPT_COMMANDES`, :data:`OPT_RETOUR_ARRIERE`,
:data:`OPT_SUPPRESSION`, :data:`OPT_TERM`.
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

#: Port telnet par défaut.
PORT_DEFAUT = 23

#: Commandes envoyées après la connexion (fin de ligne écrite ``\n`` dans l'INI).
OPT_COMMANDES = "commands"
#: Liaison de la touche Retour arrière (``Vte.EraseBinding``, 0 à 4).
OPT_RETOUR_ARRIERE = "backspace-key"
#: Liaison de la touche Suppr (``Vte.EraseBinding``, 0 à 4).
OPT_SUPPRESSION = "delete-key"
#: Valeur de ``TERM`` transmise à telnet ; vide : ``xterm``.
OPT_TERM = "term"

#: ``TERM`` quand l'option est vide (``widgets.vte_run`` de GTK3).
TERM_DEFAUT = "xterm"

#: Nombre de valeurs de ``Vte.EraseBinding`` (AUTO, ASCII_BACKSPACE,
#: ASCII_DELETE, DELETE_SEQUENCE, TTY), dans l'ordre des listes de GTK3.
NB_LIAISONS = 5

#: Délai avant le premier envoi de ``commands`` (ms), comme GTK3.
DELAI_COMMANDES_MS = 3000

#: Préfixe d'une ligne de délai dans ``commands``.
PREFIXE_DELAI = "##D="

#: Script expect livré avec le plugin.
SCRIPT_EXPECT = Path(__file__).with_name("telnet.expect")


@dataclass(frozen=True)
class Lancement:
    """Commande à lancer dans le terminal.

    Attributes:
        argv: programme et arguments (``argv[0]`` est le chemin du programme).
        mot_de_passe: à écrire sur le descripteur 3 du script expect ;
            vide quand ``telnet`` est lancé directement.
    """

    argv: list[str]
    mot_de_passe: str = ""

    def __repr__(self) -> str:
        """Représentation sans le mot de passe (journal)."""
        return (
            f"Lancement(argv={self.argv!r}, mot_de_passe={'***' if self.mot_de_passe else ''!r})"
        )


def lancement(
    adresse: str,
    port: int | None,
    utilisateur: str,
    mot_de_passe: str,
    parametres: str,
    telnet: str,
    expect: str | None,
    script: Path = SCRIPT_EXPECT,
) -> Lancement:
    """Commande telnet de l'hôte, avec ``expect`` seulement si utilisateur et mot de passe sont donnés.

    Args:
        adresse: hôte distant.
        port: port ; ``None`` : :data:`PORT_DEFAUT`.
        utilisateur: utilisateur (ignoré sans mot de passe, comme GTK3).
        mot_de_passe: mot de passe (ignoré sans utilisateur).
        parametres: paramètres supplémentaires de telnet, découpés comme un shell.
        telnet: chemin du programme ``telnet``.
        expect: chemin du programme ``expect`` ; ``None`` s'il est absent.
        script: script expect.

    Raises:
        ValueError: ``parametres`` mal formé (guillemet non fermé).
        FileNotFoundError: saisie automatique demandée sans ``expect`` ;
            ``args[0]`` est le nom du programme manquant.
    """
    logger.debug("lancement: {}:{} utilisateur={!r}", adresse, port, utilisateur)
    fin = [*shlex.split(parametres), adresse, str(PORT_DEFAUT if port is None else port)]
    if utilisateur and mot_de_passe:
        if expect is None:
            logger.debug("lancement: expect absent")
            raise FileNotFoundError("expect")
        resultat = Lancement(
            [expect, "-f", str(script), telnet, "-l", utilisateur, *fin], mot_de_passe
        )
    else:
        resultat = Lancement([telnet, *fin])
    logger.debug("lancement: {!r}", resultat)
    return resultat


def environnement(options: Mapping[str, str]) -> list[str]:
    """Variables ajoutées à l'environnement du terminal : ``TERM`` seulement.

    Le reste de l'environnement de gcm4 est hérité (VTE l'ajoute).
    """
    logger.debug("environnement: entrée")
    term = options.get(OPT_TERM, "").strip() or TERM_DEFAUT
    logger.debug("environnement: TERM={}", term)
    return [f"TERM={term}"]


def liaison(options: Mapping[str, str], cle: str) -> int:
    """Liaison d'effacement de ``cle`` ; valeur absente ou invalide : 0 (automatique, comme GTK3)."""
    logger.debug("liaison: {}", cle)
    brut = options.get(cle, "").strip()
    resultat = int(brut) if brut.isdigit() and int(brut) < NB_LIAISONS else 0
    logger.debug("liaison: {}", resultat)
    return resultat


def lire_commandes(brut: str) -> str:
    r"""Texte de ``commands`` tel qu'édité, depuis sa forme INI (``\n`` ou NUL : fin de ligne)."""
    logger.debug("lire_commandes: {} caractère(s)", len(brut))
    resultat = brut.replace("\x00", "\n").replace("\\n", "\n")
    logger.debug("lire_commandes: fait")
    return resultat


def ecrire_commandes(texte: str) -> str:
    r"""Forme INI de ``commands`` (une ligne : fins de ligne écrites ``\n``, comme GTK3)."""
    logger.debug("ecrire_commandes: {} caractère(s)", len(texte))
    resultat = texte.replace("\r\n", "\n").replace("\n", "\\n")
    logger.debug("ecrire_commandes: fait")
    return resultat


def est_delai(ligne: str) -> bool:
    """Vrai pour une ligne ``##D=<millisecondes>``."""
    logger.trace("est_delai: {!r}", ligne)
    resultat = ligne.startswith(PREFIXE_DELAI) and ligne[len(PREFIXE_DELAI) :].isdigit()
    logger.trace("est_delai: {}", resultat)
    return resultat


def etapes(commandes: str) -> list[tuple[int, str]]:
    r"""Envois de ``commands`` : ``(délai depuis l'ouverture en ms, texte)``.

    Comme GTK3 : les lignes consécutives partent ensemble, séparées et
    terminées par ``\r`` ; une ligne ``##D=<ms>`` repousse les suivantes.

    Args:
        commandes: texte édité (voir :func:`lire_commandes`).
    """
    logger.debug("etapes: {} caractère(s)", len(commandes))
    resultat: list[tuple[int, str]] = []
    instant = DELAI_COMMANDES_MS
    lignes: list[str] = []
    for ligne in commandes.splitlines():
        if est_delai(ligne):
            if lignes:
                resultat.append((instant, "\r".join(lignes) + "\r"))
                lignes = []
            instant += int(ligne[len(PREFIXE_DELAI) :])
        else:
            lignes.append(ligne)
    if lignes:
        resultat.append((instant, "\r".join(lignes) + "\r"))
    logger.debug("etapes: {} envoi(s)", len(resultat))
    return resultat
