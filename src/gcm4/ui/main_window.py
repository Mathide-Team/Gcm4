"""Fenêtre principale de gcm4 (#134).

``Adw.HeaderBar`` avec menu principal, ``Gtk.Paned`` : panneau gauche
(arbre des hôtes du lot 3, #139) et ``Gtk.Notebook`` à droite avec une page
d'accueil. Taille et largeur du panneau restaurées depuis ``gcm4.conf`` et
enregistrées à la fermeture.
"""

from __future__ import annotations

from gi.repository import Adw, Gio, GLib, Gtk
from loguru import logger

from gcm4.core import chemins, menu, window_state
from gcm4.core.chiffrement import ChiffrementGcm
from gcm4.core.config import ConfigError, load_config, update_keys
from gcm4.core.i18n import _
from gcm4.core.replies import ecrire_replies
from gcm4.ui.host_tree import HostTree

LARGEUR_DEFAUT = 1000
HAUTEUR_DEFAUT = 650


def construire_menu() -> Gio.Menu:
    """``Gio.Menu`` du menu principal, depuis ``gcm4.core.menu``."""
    logger.debug("construire_menu: entrée")
    racine = Gio.Menu()
    for sous_menu in menu.MENU_PRINCIPAL:
        contenu = Gio.Menu()
        for section in sous_menu.sections:
            bloc = Gio.Menu()
            for entree in section:
                ligne = Gio.MenuItem.new(_(entree.libelle), None)
                if entree.cible is None:
                    ligne.set_detailed_action(entree.action)
                else:
                    ligne.set_action_and_target_value(
                        entree.action, GLib.Variant("s", entree.cible)
                    )
                bloc.append_item(ligne)
            contenu.append_section(None, bloc)
        racine.append_submenu(_(sous_menu.titre), contenu)
    logger.debug("construire_menu: {} sous-menu(s)", racine.get_n_items())
    return racine


class MainWindow(Adw.ApplicationWindow):
    """Fenêtre principale : en-tête, panneau gauche, onglets."""

    def __init__(self, application: Adw.Application, config_dir: str) -> None:
        """Construit la fenêtre et restaure son état depuis ``config_dir/gcm4.conf``."""
        logger.debug("MainWindow.__init__: config_dir={}", config_dir)
        super().__init__(application=application, title="Gnome Connection Manager")
        self.config_file = chemins.fichier_conf(config_dir)
        self.etat = window_state.load_window_state(self.config_file)

        entete = Adw.HeaderBar()
        self.bouton_menu = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=construire_menu()
        )
        self.bouton_menu.set_tooltip_text(_("Menu"))
        entete.pack_end(self.bouton_menu)

        self.panneau = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panneau.set_size_request(120, -1)
        self.config = None
        self.arbre: HostTree | None = None
        try:
            self.config = load_config(self.config_file, ChiffrementGcm(config_dir))
        except ConfigError as exc:
            # Rien n'est chargé : aucune écriture ne pourra écraser le fichier.
            logger.warning("MainWindow.__init__: configuration non chargée ({})", exc)
            self.erreur_config = Adw.StatusPage(
                icon_name="dialog-warning-symbolic",
                title=_("Configuration not loaded"),
                description=str(exc),
            )
            self.erreur_config.set_vexpand(True)
            self.panneau.append(self.erreur_config)
        else:
            self.arbre = HostTree(
                self.config.store, rayures=not self.config.options.disable_hosts_stripes
            )
            self.panneau.append(self.arbre)
            couleurs = [g.color for g in self.config.store.groups.values() if g.color]
            if hasattr(application, "set_group_colors"):
                application.set_group_colors(couleurs)
        self.onglets = Gtk.Notebook(scrollable=True)
        self.page_accueil = Adw.StatusPage(
            icon_name="network-server-symbolic",
            title=_("Welcome to Gnome Connection Manager"),
            description=_("Hosts and groups will appear in the left panel."),
        )
        self.onglets.append_page(self.page_accueil, Gtk.Label(label=_("Home")))

        self.separateur = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.separateur.set_start_child(self.panneau)
        self.separateur.set_end_child(self.onglets)
        self.separateur.set_resize_start_child(False)
        self.separateur.set_position(self.etat.panel_width)

        corps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        corps.append(entete)
        corps.append(self.separateur)
        self.separateur.set_vexpand(True)
        self.set_content(corps)

        self.set_default_size(
            self.etat.width if self.etat.width > 0 else LARGEUR_DEFAUT,
            self.etat.height if self.etat.height > 0 else HAUTEUR_DEFAUT,
        )
        action = Gio.SimpleAction.new_stateful(
            "toggle-panel", None, GLib.Variant.new_boolean(self.etat.show_panel)
        )
        action.connect("change-state", self._on_toggle_panel)
        self.add_action(action)
        self.panneau.set_visible(self.etat.show_panel)
        self.connect("close-request", self._on_close_request)
        logger.debug("MainWindow.__init__: prête ({})", self.etat)

    def _on_toggle_panel(self, action: Gio.SimpleAction, valeur: GLib.Variant) -> None:
        """F9 / Affichage > Panneau : montre ou cache le panneau gauche."""
        logger.debug("_on_toggle_panel: {}", valeur.get_boolean())
        action.set_state(valeur)
        self.panneau.set_visible(valeur.get_boolean())
        self.etat.show_panel = valeur.get_boolean()
        logger.debug("_on_toggle_panel: fait")

    def etat_courant(self) -> window_state.WindowState:
        """État actuel (taille, panneau) à enregistrer."""
        logger.debug("etat_courant: entrée")
        largeur, hauteur = self.get_default_size()
        etat = window_state.WindowState(
            width=self.get_width() or largeur,
            height=self.get_height() or hauteur,
            panel_width=self.separateur.get_position(),
            show_panel=self.panneau.get_visible(),
        )
        logger.debug("etat_courant: {}", etat)
        return etat

    def _on_close_request(self, _fenetre: Gtk.Window) -> bool:
        """Enregistre l'état ; une erreur d'écriture n'empêche pas la fermeture."""
        logger.debug("_on_close_request: entrée")
        try:
            window_state.save_window_state(self.config_file, self.etat_courant())
            if self.config is not None:
                groupes = self.config.store.groups
                replies = ecrire_replies((p for p, g in groupes.items() if g.collapsed), groupes)
                update_keys(self.config_file, "window", {"collapsed-folders": replies})
        except ConfigError as exc:
            # gcm4.conf corrompu ou disque plein : le fichier reste intact,
            # seule la géométrie de cette session est perdue.
            logger.warning("_on_close_request: état non enregistré ({})", exc)
        logger.debug("_on_close_request: fermeture autorisée")
        return False
