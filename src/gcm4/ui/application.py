"""Application libadwaita de gcm4 : instance unique, actions, À propos (#133, #134)."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable

from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from loguru import logger

from gcm4 import __version__
from gcm4.core import chemins, menu, theme
from gcm4.core import preferences as prefs_core
from gcm4.core.config import ConfigError
from gcm4.core.i18n import _
from gcm4.core.registre import Candidat, PluginRegistry, decouvrir
from gcm4.ui import mises_a_jour
from gcm4.ui.contexte import ContexteApplication
from gcm4.ui.main_window import MainWindow
from gcm4.ui.preferences import PreferencesWindow, css_police

APPLICATION_ID = "io.github.MathildeDec.gcm4"
SITE = "https://github.com/Mathide-Team/Gcm4"
#: Règles CSS encore utiles de l'ancienne interface (audit dans le fichier).
STYLE_CSS = os.path.join(os.path.dirname(__file__), "style.css")
DEVELOPPEURS = ["Renzo Bertuzzi L. <kuthulu@gmail.com>", "MathildeDec"]


class Gcm4Application(Adw.Application):
    """Application unique : une deuxième exécution active la fenêtre existante."""

    def __init__(
        self,
        args: argparse.Namespace,
        flags: Gio.ApplicationFlags | None = None,
        candidats: Iterable[Candidat] | None = None,
    ) -> None:
        """Garde les arguments déjà analysés par ``gcm4.core.cli``.

        Args:
            args: options de ``gcm4.core.cli`` (``config_dir``, ``debug``, ``hotes``).
            flags: drapeaux ``Gio`` ; par défaut ``HANDLES_COMMAND_LINE``.
            candidats: plugins à charger ; par défaut, points d'entrée puis
                dossier source (``gcm4.core.registre``). Les tests y passent
                le plugin démo.
        """
        logger.debug("Gcm4Application.__init__: config_dir={}", args.config_dir)
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE if flags is None else flags,
        )
        self.args = args
        self._candidats = None if candidats is None else list(candidats)
        #: Plugins chargés au démarrage ; vide jusque-là (mode zéro plugin).
        self.registre = PluginRegistry()
        self.config_file = chemins.fichier_conf(args.config_dir)
        self.css_principal: Gtk.CssProvider | None = None
        self.css_couleurs: Gtk.CssProvider | None = None
        self.css_police: Gtk.CssProvider | None = None
        self.preferences: Gtk.Window | None = None  # fenêtre des préférences ouverte (#147)
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
        for action, touches in menu.RACCOURCIS.items():
            self.set_accels_for_action(action, list(touches))
        mode = theme.load_theme(self.config_file)
        action_theme = Gio.SimpleAction.new_stateful(
            "theme", GLib.VariantType.new("s"), GLib.Variant("s", mode)
        )
        action_theme.connect("change-state", self._on_theme)
        self.add_action(action_theme)
        self.appliquer_theme(mode)
        self._charger_css()
        # Aucun plugin ne peut empêcher le démarrage : ses erreurs restent dans le registre.
        self.registre = decouvrir(lambda nom: ContexteApplication(self, nom), self._candidats)
        logger.debug("_on_startup: fin")

    def appliquer_theme(self, mode: str) -> None:
        """Applique ``mode`` (``system`` / ``light`` / ``dark``) à chaud avec ``Adw.StyleManager``."""
        logger.debug("appliquer_theme: {}", mode)
        schema = getattr(Adw.ColorScheme, theme.SCHEMAS[mode])
        Adw.StyleManager.get_default().set_color_scheme(schema)
        logger.debug("appliquer_theme: fait")

    def _on_theme(self, action: Gio.SimpleAction, valeur: GLib.Variant) -> None:
        """Menu Affichage > thème : applique, puis enregistre dans gcm4.conf."""
        logger.debug("_on_theme: entrée")
        mode = valeur.get_string()
        logger.debug("_on_theme: {}", mode)
        if mode not in theme.MODES:
            logger.warning("_on_theme: mode inconnu {!r}", mode)
            return
        action.set_state(valeur)
        self.appliquer_theme(mode)
        try:
            theme.save_theme(self.config_file, mode)
        except ConfigError as exc:
            logger.warning("_on_theme: thème non enregistré ({})", exc)
        logger.debug("_on_theme: fait")

    def _charger_css(self) -> None:
        """Feuille de style de la base et feuille des couleurs de groupe (vide au départ)."""
        logger.debug("_charger_css: {}", STYLE_CSS)
        ecran = Gdk.Display.get_default()
        if ecran is None:
            logger.warning("_charger_css: aucun écran, CSS non chargé")
            return
        self.css_principal = Gtk.CssProvider()
        self.css_principal.load_from_path(STYLE_CSS)
        self.css_couleurs = Gtk.CssProvider()
        self.css_police = Gtk.CssProvider()
        for fournisseur in (self.css_principal, self.css_couleurs, self.css_police):
            Gtk.StyleContext.add_provider_for_display(
                ecran, fournisseur, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self.appliquer_police_arbre(prefs_core.load_preferences(self.config_file).tree_font)
        logger.debug("_charger_css: fait")

    @staticmethod
    def _charger(fournisseur: Gtk.CssProvider, css: str) -> None:
        """Remplace le contenu d'une feuille de style (GTK 4.8 à 4.12+)."""
        logger.trace("_charger: {} octet(s)", len(css))
        if hasattr(fournisseur, "load_from_string"):  # GTK ≥ 4.12
            fournisseur.load_from_string(css)
        else:  # GTK 4.8 (Debian 12)
            fournisseur.load_from_data(css, -1)
        logger.trace("_charger: fait")

    def appliquer_police_arbre(self, description: str) -> None:
        """Police de l'arbre des hôtes (#147) ; vide : police du système."""
        logger.debug("appliquer_police_arbre: {!r}", description)
        if self.css_police is None:
            logger.debug("appliquer_police_arbre: CSS non chargé")
            return
        self._charger(self.css_police, css_police(description))
        logger.debug("appliquer_police_arbre: fait")

    def set_group_colors(self, couleurs: Iterable[str]) -> None:
        """Recharge les classes ``gcm-couleur-rrggbb`` (arbre des hôtes, #121)."""
        logger.debug("set_group_colors")
        if self.css_couleurs is None:
            logger.debug("set_group_colors: CSS non chargé")
            return
        self._charger(self.css_couleurs, theme.colors_css(couleurs))
        logger.debug("set_group_colors: fait")

    def _on_command_line(self, _app: Adw.Application, _ligne: Gio.ApplicationCommandLine) -> int:
        """Ligne de commande (déjà analysée) : active la fenêtre, y compris d'une 2e instance."""
        logger.debug("_on_command_line: entrée")
        self.activate()
        logger.debug("_on_command_line: sortie 0")
        return 0

    def _on_activate(self, _app: Adw.Application) -> None:
        """Présente la fenêtre principale, créée au premier appel."""
        logger.debug("_on_activate: entrée")
        fenetre = self.get_active_window()
        if fenetre is None:
            fenetre = MainWindow(self, self.args.config_dir)
            fenetre.present()
            fenetre.restaurer_onglets()  # une fois, à la création (#246)
            mises_a_jour.au_demarrage(fenetre)  # jamais sans accord (#245)
        else:
            fenetre.present()
        logger.debug("_on_activate: fenêtre présentée")

    def _on_quit(self, _action: Gio.SimpleAction, _param: object) -> None:
        """Ctrl+Q : ferme les fenêtres (leur état est enregistré) puis quitte.

        Une fenêtre qui demande confirmation (connexions ouvertes, #147)
        garde l'application ouverte : elle quittera après la réponse.
        """
        logger.debug("_on_quit: entrée")
        for fenetre in list(self.get_windows()):
            fenetre.close()
        if any(getattr(f, "confirmation_fermeture", None) for f in self.get_windows()):
            logger.debug("_on_quit: confirmation demandée, pas encore quitté")
            return
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
        """Édition > Préférences (Ctrl+,) : pages Général et Apparence (#147)."""
        logger.debug("_on_preferences: entrée")
        fenetre = self.get_active_window()
        if isinstance(fenetre, PreferencesWindow):
            fenetre.present()
            logger.debug("_on_preferences: déjà ouverte")
            return
        principale = next((f for f in self.get_windows() if isinstance(f, MainWindow)), None)
        self.preferences = PreferencesWindow(self, principale)
        self.preferences.present()
        logger.debug("_on_preferences: présentée")


def run(args: argparse.Namespace) -> int:
    """Exécute la boucle GTK ; les arguments sont déjà analysés (pas de reparse)."""
    logger.debug("run: entrée")
    code = Gcm4Application(args).run([])
    logger.debug("run: sortie {}", code)
    return int(code)
