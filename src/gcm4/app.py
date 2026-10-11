"""Point d'entrée ``gcm4`` (``[project.scripts]``, #133).

Ordre imposé : ligne de commande et journalisation d'abord, GTK ensuite.
Si PyGObject, GTK4 ou libadwaita manquent, l'utilisateur reçoit la
commande d'installation de sa distribution, sans trace Python, et un code
de sortie non nul.
"""

from __future__ import annotations

import sys

from loguru import logger

import gcm4_core
import logging_config
from gcm4.core import cli, i18n

# Paquets système de PyGObject, GTK4 et libadwaita (D1 de #118).
PAQUETS_GTK = {
    "debian": "python3-gi gir1.2-gtk-4.0 gir1.2-adw-1",
    "fedora": "python3-gobject gtk4 libadwaita",
    "arch": "python-gobject gtk4 libadwaita",
}
CODE_GTK_ABSENT = 3


def main(argv: list[str] | None = None) -> int:
    """Lance gcm4 ; renvoie le code de sortie du processus."""
    logger.debug("main: entrée")  # muet : gcm4 est désactivé jusqu'à configure_logging
    # Journalisation configurée avant tout : niveau de GCM_LOG_LEVEL /
    # GCM_DEBUG, sans quoi loguru écrirait du DEBUG sur stderr par défaut.
    logging_config.configure_logging()
    args = cli.parse_args(sys.argv[1:] if argv is None else argv)
    i18n.install()
    if args.debug:
        logging_config.enable_debug(config_dir=args.config_dir)
    else:
        logging_config.configure_logging(config_dir=args.config_dir, force=True)
    try:
        from gcm4.ui import application
    except (ImportError, ValueError) as exc:
        logger.warning("main: interface GTK4 indisponible ({})", exc)
        conseil = gcm4_core.dep_install_hint(
            PAQUETS_GTK["debian"], PAQUETS_GTK["fedora"], PAQUETS_GTK["arch"]
        )
        print(
            f"gcm4 : GTK4, libadwaita ou PyGObject est introuvable ({exc}).\n"
            f"Installez-les avec : {conseil}",
            file=sys.stderr,
        )
        logger.debug("main: sortie {} (GTK absent)", CODE_GTK_ABSENT)
        return CODE_GTK_ABSENT
    code = application.run(args)
    logger.debug("main: sortie {}", code)
    return code
