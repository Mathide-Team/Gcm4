"""Application libadwaita de gcm4 : instance unique, actions, À propos (#133, #134)."""

from __future__ import annotations

import argparse

from gi.repository import Adw, Gio, Gtk
from loguru import logger

from gcm4 import __version__
from gcm4.core import menu
from gcm4.core.i18n import _
from gcm4.ui.main_window import MainWindow

APPLICATION_ID = "io.github.MathildeDec.gcm4"
SITE = "https://github.com/Mathide-Team/Gcm4"
DEVELOPPEURS = ["Renzo Bertuzzi L. <kuthulu@gmail.com>", "MathildeDec"]


class Gcm4Application(Adw.Application):
    """Application unique : une deuxième exécution active la fenêtre existante."""

    def __init__(
        self, args: argparse.Namespace, flags: Gio.ApplicationFlags | None = None
    ) -> None:
        """Garde les arguments déjà analysés par ``gcm4.core.cli``."""
        logger.debug("Gcm4Application.__init__: config_dir={}", args.config_dir)
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE if flags is None else flags,
        )
        self.args = args
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)
        self.connect("command-line", self._on_command_line)
        logger.debug("Gcm4Application.__init__: prête")

    def _on_startup(self, _app: Adw.Application) -> None:
        """Actions de l'application et raccourcis clavier."""
        logger.debug("_on_startup: entrée")
        for nom, rappel in (
            ("quit", self._on_quit),
            ("about", self._on_about),
            ("preferences", self._on_preferences),
        ):
            action = Gio.SimpleAction.new(nom, None)
            action.connect("activate", rappel)
            self.add_action(action)
        # Préférences : page construite au lot 5 (#147) ; action présente mais inactive.
        preferences = self.lookup_action("preferences")
        if isinstance(preferences, Gio.SimpleAction):
            preferences.set_enabled(False)
        for action, touches in menu.RACCOURCIS.items():
            self.set_accels_for_action(action, list(touches))
        logger.debug("_on_startup: fin")

    def _on_command_line(self, _app: Adw.Application, _ligne: Gio.ApplicationCommandLine) -> int:
        """Ligne de commande (déjà analysée) : active la fenêtre, y compris d'une 2e instance."""
        logger.debug("_on_command_line: entrée")
        self.activate()
        logger.debug("_on_command_line: sortie 0")
        return 0

    def _on_activate(self, _app: Adw.Application) -> None:
        """Présente la fenêtre principale, créée au premier appel."""
        logger.debug("_on_activate: entrée")
        fenetre = self.get_active_window() or MainWindow(self, self.args.config_dir)
        fenetre.present()
        logger.debug("_on_activate: fenêtre présentée")

    def _on_quit(self, _action: Gio.SimpleAction, _param: object) -> None:
        """Ctrl+Q : ferme les fenêtres (leur état est enregistré) puis quitte."""
        logger.debug("_on_quit: entrée")
        for fenetre in list(self.get_windows()):
            fenetre.close()
        self.quit()
        logger.debug("_on_quit: fin")

    def boite_a_propos(self) -> Gtk.Widget:
        """Boîte « À propos » (``Adw.AboutDialog`` si libadwaita ≥ 1.5, sinon ``AboutWindow``)."""
        logger.debug("boite_a_propos: entrée")
        classe = getattr(Adw, "AboutDialog", None) or Adw.AboutWindow
        boite = classe(
            application_name="Gnome Connection Manager",
            application_icon="gnome-connection-manager",
            version=__version__,
            developers=DEVELOPPEURS,
            copyright="© 2012 Renzo Bertuzzi L.",
            license_type=Gtk.License.GPL_3_0,
            website=SITE,
            comments=_("A simple ssh connection manager for gnome"),
        )
        logger.debug("boite_a_propos: {}", classe.__name__)
        return boite

    def _on_about(self, _action: Gio.SimpleAction, _param: object) -> None:
        """Aide > À propos."""
        logger.debug("_on_about: entrée")
        boite = self.boite_a_propos()
        fenetre = self.get_active_window()
        if hasattr(boite, "set_transient_for"):  # Adw.AboutWindow (libadwaita < 1.5)
            boite.set_transient_for(fenetre)
            boite.present()
        else:  # Adw.AboutDialog
            boite.present(fenetre)
        logger.debug("_on_about: présentée")

    def _on_preferences(self, _action: Gio.SimpleAction, _param: object) -> None:
        """Ctrl+, : préférences (lot 5, #147)."""
        logger.debug("_on_preferences: pas encore disponible (#147)")


def run(args: argparse.Namespace) -> int:
    """Exécute la boucle GTK ; les arguments sont déjà analysés (pas de reparse)."""
    logger.debug("run: entrée")
    code = Gcm4Application(args).run([])
    logger.debug("run: sortie {}", code)
    return int(code)
