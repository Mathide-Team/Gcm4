"""Ligne de commande de gcm4, analysée avant toute initialisation GTK (#133).

``gcm4 --version`` et ``gcm4 --help`` doivent fonctionner sans display ni
GTK installé (test de fumée des paquets, #156/#157).
"""

from __future__ import annotations

import argparse
import os

from loguru import logger

import logging_config
from gcm4 import __version__
from gcm4.core import chemins, echange_cli


def build_parser() -> argparse.ArgumentParser:
    """Analyseur de la commande ``gcm4``."""
    logger.debug("build_parser: construction")
    parser = argparse.ArgumentParser(
        prog="gcm4",
        description="Gestionnaire de connexions à onglets (GTK4).",
    )
    parser.add_argument("--version", action="version", version=f"gcm4 {__version__}")
    logging_config.add_debug_argument(parser)
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="DOSSIER",
        default=None,
        help="dossier de configuration (défaut : $XDG_CONFIG_HOME/gcm4, soit ~/.config/gcm4)",
    )
    parser.add_argument(
        "hotes",
        nargs="*",
        metavar="GROUPE/NOM",
        help="hôtes à sélectionner au démarrage, connectés si un plugin gère leur protocole",
    )
    echange_cli.ajouter_arguments(parser)
    logger.debug("build_parser: prêt")
    return parser


def parse_args(
    argv: list[str], home: str | None = None, environ: dict[str, str] | None = None
) -> argparse.Namespace:
    """Analyse ``argv`` (sans ``argv[0]``) ; ajoute ``config_dir`` et ``ancien_dossier``.

    ``config_dir`` (absolu) : ``-c/--config``, sinon ``$XDG_CONFIG_HOME/gcm4``
    (#99, remplace D3 de #118). ``ancien_dossier`` : ``~/.gcm`` à migrer si
    le dossier par défaut est utilisé, ``None`` avec ``-c``.
    """
    logger.debug("parse_args: {} argument(s)", len(argv))
    args = build_parser().parse_args(argv)
    maison = home or os.path.expanduser("~")
    if args.config:
        args.config_dir = os.path.abspath(os.path.expanduser(args.config))
        args.ancien_dossier = None
    else:
        args.config_dir = os.path.abspath(chemins.dossier_par_defaut(maison, environ))
        args.ancien_dossier = chemins.ancien_dossier(maison)
    logger.debug("parse_args: config_dir={} hotes={}", args.config_dir, len(args.hotes))
    return args
