"""Thème appliqué à chaud et conservé après redémarrage (#135)."""

from __future__ import annotations

import argparse
import configparser

from gi.repository import Adw, Gio, GLib

import gcm4.ui  # noqa: F401  (require_version Gtk 4.0 / Adw 1 avant gi.repository)
from gcm4.ui.application import Gcm4Application


def _schema():
    return Adw.StyleManager.get_default().get_color_scheme()


def test_changement_de_theme_a_chaud(application, tmp_path, pomper):
    """app.theme → dark : schéma FORCE_DARK appliqué tout de suite, enregistré dans gcm.conf."""
    action = application.lookup_action("theme")
    assert action.get_state().get_string() == "system"
    application.activate_action("theme", GLib.Variant("s", "dark"))
    pomper()
    assert action.get_state().get_string() == "dark"
    assert _schema() == Adw.ColorScheme.FORCE_DARK
    cp = configparser.RawConfigParser()
    cp.read(tmp_path / "gcm.conf", encoding="utf-8")
    assert cp.get("window", "theme-mode") == "dark"
    application.activate_action("theme", GLib.Variant("s", "light"))
    pomper()
    assert _schema() == Adw.ColorScheme.FORCE_LIGHT


def test_mode_inconnu_ignore(application, pomper):
    """Une cible inconnue ne change ni l'état ni le schéma."""
    application.activate_action("theme", GLib.Variant("s", "system"))
    pomper()
    application.activate_action("theme", GLib.Variant("s", "violet"))
    pomper()
    assert application.lookup_action("theme").get_state().get_string() == "system"
    assert _schema() == Adw.ColorScheme.DEFAULT


def test_theme_conserve_apres_redemarrage(tmp_path, pomper):
    """Thème enregistré → appliqué au démarrage suivant."""
    (tmp_path / "gcm.conf").write_text("[window]\ntheme-mode = dark\n", encoding="utf-8")
    app = Gcm4Application(
        argparse.Namespace(config_dir=str(tmp_path), debug=False, hotes=[]),
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)
    pomper()
    try:
        assert app.lookup_action("theme").get_state().get_string() == "dark"
        assert _schema() == Adw.ColorScheme.FORCE_DARK
    finally:
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)


def test_css_et_couleurs_de_groupe(application):
    """style.css chargé ; set_group_colors génère les classes gcm-couleur-*."""
    assert "tab:checked" in application.css_principal.to_string()
    application.set_group_colors(["#FF8800", "invalide"])
    css = application.css_couleurs.to_string()
    assert ".gcm-couleur-ff8800" in css and "invalide" not in css
