"""Application libadwaita de gcm4 (#133 ; fenêtre et actions : #134)."""

from __future__ import annotations

import argparse

from gi.repository import Adw, Gio
from loguru import logger

APPLICATION_ID = "io.github.MathildeDec.gcm4"


class Gcm4Application(Adw.Application):
    """Application unique (une deuxième exécution active la première)."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Garde les arguments déjà analysés par ``gcm4.core.cli``."""
        logger.debug("Gcm4Application.__init__: config_dir={}", args.config_dir)
        super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.args = args
        self.connect("activate", self._on_activate)
        logger.debug("Gcm4Application.__init__: prête")

    def _on_activate(self, app: Adw.Application) -> None:
        """Présente la fenêtre principale (vide jusqu'au lot 1b, #134)."""
        logger.debug("_on_activate: entrée")
        fenetre = self.get_active_window() or Adw.ApplicationWindow(
            application=self,
            title="Gnome Connection Manager",
            default_width=900,
            default_height=600,
        )
        fenetre.present()
        logger.debug("_on_activate: fenêtre présentée")


def run(args: argparse.Namespace) -> int:
    """Exécute la boucle GTK ; les arguments sont déjà analysés (pas de reparse)."""
    logger.debug("run: entrée")
    code = Gcm4Application(args).run([])
    logger.debug("run: sortie {}", code)
    return int(code)
