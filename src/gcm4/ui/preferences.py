"""Préférences de la base GTK4 : pages Général et Apparence (lot 5a, #147).

``Adw.PreferencesWindow`` sans bouton OK : chaque changement est appliqué
tout de suite et enregistré aussitôt (:func:`gcm4.core.preferences.save_preference`,
écriture atomique). Un échec d'écriture (disque plein, fichier corrompu)
n'annule pas le changement en cours de session ; il est signalé par un
toast et journalisé.

- **Général** : confirmation à la fermeture, vérification des mises à jour,
  restauration des onglets ouverts (stockée ; utilisée par les plugins) ;
- **Apparence** : thème (action ``app.theme``, même état que le menu
  Affichage), panneau visible (action ``win.toggle-panel``, comme F9),
  police de l'arbre des hôtes (CSS sur la classe ``gcm-arbre``).

Les options ``[options]`` sont aussi mises à jour dans ``Config.options``
de la fenêtre principale : sinon ``save_config`` (modification de l'arbre)
réécrirait l'ancienne valeur. Sans configuration chargée (fichier
illisible), la page Général est inactive : rien n'est jamais écrit.

Compatibilité : ``Gtk.FontDialogButton`` (GTK ≥ 4.10), sinon ``Gtk.FontButton``.
"""

from __future__ import annotations

from gi.repository import Adw, GLib, Gtk, Pango
from loguru import logger

from gcm4.core import preferences as prefs_core
from gcm4.core.config import ConfigError
from gcm4.core.i18n import N_, _
from gcm4.ui import mises_a_jour

#: Modes du thème, dans l'ordre de la liste déroulante.
MODES = ("system", "light", "dark")

#: Options de la page Général : (attribut de Preferences et d'AppConfig, libellé).
OPTIONS_GENERALES = (
    ("confirm_exit", N_("Confirm on exit")),
    ("check_updates", N_("Check updates")),
    ("restore_open_tabs", N_("Restore open tabs from the previous session on startup")),
)


def css_police(description: str) -> str:
    """Description Pango (``"Sans Bold 11"``) → règle CSS de l'arbre ; vide → ``""``."""
    logger.trace("css_police: {!r}", description)
    if not description.strip():
        logger.trace("css_police: police du système")
        return ""
    desc = Pango.FontDescription.from_string(description)
    regles = []
    famille = desc.get_family()
    if famille:
        regles.append('font-family: "{}";'.format(famille.replace('"', "")))
    if desc.get_size() > 0:
        unite = "px" if desc.get_size_is_absolute() else "pt"
        regles.append(f"font-size: {desc.get_size() / Pango.SCALE:g}{unite};")
    regles.append(f"font-weight: {int(desc.get_weight())};")
    style = {Pango.Style.ITALIC: "italic", Pango.Style.OBLIQUE: "oblique"}.get(
        desc.get_style(), "normal"
    )
    regles.append(f"font-style: {style};")
    resultat = ".gcm-arbre { " + " ".join(regles) + " }\n"
    logger.trace("css_police: {} règle(s)", len(regles))
    return resultat


def _bouton_police() -> Gtk.Widget:
    """Bouton de choix de police (``FontDialogButton`` ≥ 4.10)."""
    logger.trace("_bouton_police")
    if hasattr(Gtk, "FontDialogButton"):
        bouton = Gtk.FontDialogButton(dialog=Gtk.FontDialog(title=_("Select font")))
    else:  # GTK < 4.10
        bouton = Gtk.FontButton(title=_("Select font"))
    bouton.set_valign(Gtk.Align.CENTER)
    logger.trace("_bouton_police: {}", type(bouton).__name__)
    return bouton


def _lire_police(bouton: Gtk.Widget) -> str:
    """Police choisie dans le bouton, en description Pango."""
    logger.trace("_lire_police")
    if hasattr(bouton, "get_font_desc"):
        desc = bouton.get_font_desc()
        resultat = desc.to_string() if desc is not None else ""
    else:
        resultat = bouton.get_font() or ""
    logger.trace("_lire_police: {!r}", resultat)
    return resultat


def _ecrire_police(bouton: Gtk.Widget, description: str) -> None:
    """Affiche ``description`` dans le bouton."""
    logger.trace("_ecrire_police: {!r}", description)
    if hasattr(bouton, "set_font_desc"):
        bouton.set_font_desc(Pango.FontDescription.from_string(description))
    else:
        bouton.set_font(description)
    logger.trace("_ecrire_police: fait")


class PreferencesWindow(Adw.PreferencesWindow):
    """Pages Général et Apparence ; chaque changement est appliqué et enregistré."""

    def __init__(self, application: Adw.Application, fenetre: Gtk.Window | None) -> None:
        """Construit les pages depuis le fichier de configuration de l'application.

        Args:
            application: ``Gcm4Application`` (``config_file``, action ``theme``,
                :meth:`appliquer_police_arbre`).
            fenetre: fenêtre principale (``config``, action ``toggle-panel``),
                ou ``None``.
        """
        logger.debug("PreferencesWindow.__init__: entrée")
        super().__init__(
            title=_("Settings"), modal=True, transient_for=fenetre, application=application
        )
        self.set_search_enabled(False)  # sept réglages : la recherche n'apporte rien
        self.application = application
        self.fenetre = fenetre
        self.config_file: str = application.config_file
        self.valeurs = prefs_core.load_preferences(self.config_file)
        etat_panneau = self._etat_action(fenetre, "toggle-panel")
        if etat_panneau is not None:  # la fenêtre fait foi (F9 non encore enregistré)
            self.valeurs.show_panel = etat_panneau.get_boolean()
        etat_theme = self._etat_action(application, "theme")
        if etat_theme is not None:
            self.valeurs.theme = etat_theme.get_string()
        self.erreur: str | None = None  # dernier échec d'écriture (tests)
        self.add(self._page_generale())
        self.add(self._page_apparence())
        logger.debug("PreferencesWindow.__init__: prête")

    @staticmethod
    def _etat_action(groupe: object, nom: str) -> GLib.Variant | None:
        """État de l'action ``nom`` de ``groupe`` (fenêtre ou application), sinon ``None``."""
        logger.trace("_etat_action: {}", nom)
        action = groupe.lookup_action(nom) if hasattr(groupe, "lookup_action") else None
        etat = action.get_state() if action is not None else None
        logger.trace("_etat_action: {}", etat)
        return etat

    # --- construction ----------------------------------------------------------

    def _page_generale(self) -> Adw.PreferencesPage:
        """Page Général : interrupteurs des options de la base."""
        logger.debug("_page_generale: entrée")
        page = Adw.PreferencesPage(title=_("General"), icon_name="preferences-system-symbolic")
        groupe = Adw.PreferencesGroup()
        self.interrupteurs: dict[str, Gtk.Switch] = {}
        config = getattr(self.fenetre, "config", None)
        for nom, libelle in OPTIONS_GENERALES:
            interrupteur = Gtk.Switch(valign=Gtk.Align.CENTER)
            valeur = getattr(config.options, nom) if config is not None else None
            interrupteur.set_active(getattr(self.valeurs, nom) if valeur is None else bool(valeur))
            ligne = Adw.ActionRow(title=_(libelle))
            ligne.add_suffix(interrupteur)
            ligne.set_activatable_widget(interrupteur)
            interrupteur.connect("notify::active", self._on_option, nom)
            groupe.add(ligne)
            self.interrupteurs[nom] = interrupteur
        if config is None:  # configuration illisible : jamais d'écriture
            groupe.set_sensitive(False)
        page.add(groupe)
        logger.debug("_page_generale: fait")
        return page

    def _page_apparence(self) -> Adw.PreferencesPage:
        """Page Apparence : thème, panneau, police de l'arbre."""
        logger.debug("_page_apparence: entrée")
        page = Adw.PreferencesPage(
            title=_("Appearance"), icon_name="applications-graphics-symbolic"
        )
        groupe = Adw.PreferencesGroup()

        self.theme = Adw.ComboRow(title=_("Theme"))
        self.theme.set_model(Gtk.StringList.new([_("System"), _("Light"), _("Dark")]))
        mode = self.valeurs.theme if self.valeurs.theme in MODES else "system"
        self.theme.set_selected(MODES.index(mode))
        self.theme.connect("notify::selected", self._on_theme)
        groupe.add(self.theme)

        self.panneau = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.valeurs.show_panel)
        ligne = Adw.ActionRow(title=_("Show Panel"))
        ligne.add_suffix(self.panneau)
        ligne.set_activatable_widget(self.panneau)
        self.panneau.connect("notify::active", self._on_panneau)
        groupe.add(ligne)

        self.police_systeme = Gtk.Switch(
            valign=Gtk.Align.CENTER, active=not self.valeurs.tree_font
        )
        ligne = Adw.ActionRow(title=_("Use system font"))
        ligne.add_suffix(self.police_systeme)
        ligne.set_activatable_widget(self.police_systeme)
        groupe.add(ligne)
        self.police = _bouton_police()
        _ecrire_police(self.police, self.valeurs.tree_font or "Sans 11")
        self.ligne_police = Adw.ActionRow(title=_("Tree font"))
        self.ligne_police.add_suffix(self.police)
        self.ligne_police.set_activatable_widget(self.police)
        self.ligne_police.set_sensitive(bool(self.valeurs.tree_font))
        groupe.add(self.ligne_police)
        self.police_systeme.connect("notify::active", self._on_police)
        signal = "notify::font-desc" if hasattr(self.police, "get_font_desc") else "font-set"
        self.police.connect(signal, self._on_police)
        page.add(groupe)
        logger.debug("_page_apparence: fait")
        return page

    # --- application immédiate ---------------------------------------------------

    def _enregistrer(self, nom: str, valeur: bool | str) -> bool:
        """Écrit la préférence ; un échec est signalé (toast) sans annuler le changement."""
        logger.debug("_enregistrer: {}", nom)
        try:
            prefs_core.save_preference(self.config_file, nom, valeur)
        except ConfigError as exc:
            logger.warning("_enregistrer: {} non enregistrée ({})", nom, exc)
            self.erreur = str(exc)
            message = _("Preferences not saved: {error}").format(error=exc)
            if hasattr(self, "add_toast"):
                self.add_toast(Adw.Toast(title=message, timeout=5))
            logger.debug("_enregistrer: échec signalé")
            return False
        setattr(self.valeurs, nom, valeur)
        logger.debug("_enregistrer: fait")
        return True

    def _on_option(self, interrupteur: Gtk.Switch, _pspec: object, nom: str) -> None:
        """Interrupteur de la page Général : modèle en mémoire puis fichier."""
        logger.debug("_on_option: entrée")
        valeur = interrupteur.get_active()
        logger.debug("_on_option: {} = {}", nom, valeur)
        config = getattr(self.fenetre, "config", None)
        if config is None:
            logger.debug("_on_option: aucune configuration chargée")
            return
        setattr(config.options, nom, valeur)  # save_config réécrit [options] depuis le modèle
        if self._enregistrer(nom, valeur) and nom == "check_updates" and valeur:
            # Activer l'option vaut accord explicite (#245).
            mises_a_jour.enregistrer_accord(self.config_file, True)
        logger.debug("_on_option: fait")

    def _on_theme(self, ligne: Adw.ComboRow, _pspec: object) -> None:
        """Thème : l'action ``app.theme`` l'applique et l'enregistre (comme le menu)."""
        logger.debug("_on_theme: entrée")
        choisi = ligne.get_selected()
        logger.debug("_on_theme: {}", choisi)
        if choisi >= len(MODES):
            logger.debug("_on_theme: aucune sélection")
            return
        mode = MODES[choisi]
        self.application.change_action_state("theme", GLib.Variant("s", mode))
        self.valeurs.theme = mode
        logger.debug("_on_theme: {}", mode)

    def _on_panneau(self, interrupteur: Gtk.Switch, _pspec: object) -> None:
        """Panneau visible : même action que F9, puis enregistrement."""
        logger.debug("_on_panneau: entrée")
        valeur = interrupteur.get_active()
        logger.debug("_on_panneau: {}", valeur)
        if self.fenetre is not None and self.fenetre.lookup_action("toggle-panel") is not None:
            self.fenetre.change_action_state("toggle-panel", GLib.Variant.new_boolean(valeur))
        self._enregistrer("show_panel", valeur)
        logger.debug("_on_panneau: fait")

    def _on_police(self, *_args: object) -> None:
        """Police de l'arbre : appliquée tout de suite, puis enregistrée."""
        logger.debug("_on_police: entrée")
        systeme = self.police_systeme.get_active()
        self.ligne_police.set_sensitive(not systeme)
        description = "" if systeme else _lire_police(self.police)
        appliquer = getattr(self.application, "appliquer_police_arbre", None)
        if callable(appliquer):
            appliquer(description)
        self._enregistrer("tree_font", description)
        logger.debug("_on_police: {!r}", description)
