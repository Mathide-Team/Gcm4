"""Ligne de commande de gcm4, analysée avant toute initialisation GTK (#133).

``gcm4 --version`` et ``gcm4 --help`` doivent fonctionner sans display ni
GTK installé (test de fumée des paquets, #156/#157).
"""

from __future__ import annotations

import argparse
import os

from loguru import logger

import gcm4_core
import logging_config
from gcm4 import __version__


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
        help="dossier de configuration (défaut : ~/.gcm)",
    )
    parser.add_argument(
        "hotes",
        nargs="*",
        metavar="GROUPE/NOM",
        help="hôtes à ouvrir au démarrage (pris en charge avec les plugins)",
    )
    logger.debug("build_parser: prêt")
    return parser


def parse_args(argv: list[str], home: str | None = None) -> argparse.Namespace:
    """Analyse ``argv`` (sans ``argv[0]``) ; ajoute ``config_dir``, chemin absolu.

    Le dossier de configuration suit la règle de l'application GTK3
    (``gcm4_core._resolve_config_dir`` : ``--config``/``-c``, sinon
    ``~/.gcm``, décision D3 de #118).
    """
    logger.debug("parse_args: {} argument(s)", len(argv))
    args = build_parser().parse_args(argv)
    config_dir, _reste = gcm4_core._resolve_config_dir(
        ["--config", args.config] if args.config else [], home or os.path.expanduser("~")
    )
    args.config_dir = config_dir
    logger.debug("parse_args: config_dir={} hotes={}", config_dir, len(args.hotes))
    return args
