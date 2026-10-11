"""Tests de l'interface GTK4 de gcm4 (job « Tests GTK4 (Xvfb) »).

Sans GTK4/libadwaita (job Qualité, uv sans PyGObject), ces tests ne sont
pas collectés : ils ne comptent ni comme passés ni comme sautés. Le job
GTK4 définit ``GCM_TESTS_GTK4=1`` : il les collecte toujours, et un GTK
absent y devient une erreur, jamais un saut silencieux (#160).
"""

from __future__ import annotations

import argparse
import os

import pytest


def _gtk4_disponible() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk

        return bool(Gtk.init_check())
    except (ImportError, ValueError):
        return False


# Toujours évalué (pas de court-circuit) : require_version Gtk 4.0 / Adw 1
# est ainsi posé avant tout import de gi.repository par les modules de test.
GTK4_DISPONIBLE = _gtk4_disponible()

if os.environ.get("GCM_TESTS_GTK4") != "1" and not GTK4_DISPONIBLE:
    collect_ignore_glob = ["test_*.py"]


def _pomper(n: int = 60) -> None:
    from gi.repository import GLib

    contexte = GLib.MainContext.default()
    for _ in range(n):
        contexte.iteration(False)


@pytest.fixture
def pomper():
    """Fonction qui traite les événements GTK en attente."""
    return _pomper


@pytest.fixture
def application(tmp_path):
    """Application gcm4 enregistrée et activée, configuration dans ``tmp_path``."""
    from gi.repository import Gio

    from gcm4.ui.application import Gcm4Application

    args = argparse.Namespace(config_dir=str(tmp_path), debug=False, hotes=[])
    app = Gcm4Application(args, flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.activate()
    _pomper()
    yield app
    for fenetre in list(app.get_windows()):
        fenetre.destroy()
    _pomper()
