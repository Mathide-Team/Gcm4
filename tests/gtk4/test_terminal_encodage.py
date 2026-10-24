"""Encodage par hôte des onglets terminal (#85) avec un vrai ``Vte.Terminal``.

Le plugin local lance un faux shell (``SHELL``) qui écrit des octets
ISO-8859-1 et note en hexadécimal les octets reçus. La zone d'options est
celle de ``gcm4.ui.terminal``, commune à telnet et local.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import gi
import pytest

gi.require_version("Vte", "3.91")

from gi.repository import GLib, Gtk, Vte  # noqa: E402

from gcm4.core import registre, terminal  # noqa: E402
from gcm4.core.model import Host  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]

FAUX_SHELL = """#!{python}
import os, sys
trace = open(os.environ["FAUX_SHELL_TRACE"], "a")
os.write(1, b"caf\\xe9 pr\\xeat\\r\\n$ ")
for ligne in sys.stdin.buffer:
    trace.write(ligne.rstrip(b"\\r\\n").hex() + "\\n")
    trace.flush()
    if ligne.strip() == b"exit":
        break
"""


class Journal:
    """Journal du contexte : garde les avertissements."""

    def __init__(self):
        """Aucun avertissement."""
        self.avertissements = []

    def warning(self, message, *args):
        """Avertissement formaté comme loguru."""
        self.avertissements.append(message.format(*args))

    def debug(self, *_args):
        """Ignoré."""


class Contexte:
    """Contexte minimal du contrat v1 (``docs/plugins.md``)."""

    def __init__(self):
        """Journal vide."""
        self.log = Journal()

    def config(self):
        """Section ``[plugin local]`` vide."""
        return {}


@pytest.fixture
def plugin():
    """Plugin local chargé depuis ``plugins/`` du dépôt."""
    candidats = registre.candidats_dossier(RACINE / "plugins")
    etats = {e.name: e for e in registre.decouvrir(lambda _nom: Contexte(), candidats).etats}
    assert etats["local"].erreur is None
    yield etats["local"].plugin
    registre._oublier_paquet("gcm4_plugin_local")


@pytest.fixture
def faux_shell(tmp_path, monkeypatch):
    """Faux shell désigné par ``SHELL`` ; rend le fichier de trace."""
    programme = tmp_path / "faux-shell"
    programme.write_text(FAUX_SHELL.format(python=sys.executable), encoding="utf-8")
    programme.chmod(0o755)
    trace = tmp_path / "trace"
    monkeypatch.setenv("SHELL", str(programme))
    monkeypatch.setenv("FAUX_SHELL_TRACE", str(trace))
    return trace


def _attendre(condition, delai=15.0):
    """Traite les événements GTK jusqu'à ``condition()`` ou ``delai`` secondes."""
    contexte = GLib.MainContext.default()
    fin = time.monotonic() + delai
    while not condition() and time.monotonic() < fin:
        contexte.iteration(False)
        time.sleep(0.005)
    return condition()


def _texte(vte):
    """Texte du terminal, historique compris (API de VTE 0.70 à 0.84)."""
    lignes = vte.get_row_count() + 200
    if hasattr(vte, "get_text_range_format"):
        return vte.get_text_range_format(Vte.Format.TEXT, 0, 0, lignes, 500)[0]
    return vte.get_text_range(0, 0, lignes, 500, None)[0]


def _trace(fichier):
    """Octets reçus par le faux shell, une ligne hexadécimale par ligne saisie."""
    return fichier.read_text(encoding="utf-8").splitlines() if fichier.exists() else []


def _hote(encodage=None, **options):
    """Hôte local de test, ``encoding`` donné ou absent."""
    if encodage is not None:
        options["encoding"] = encodage
    return Host(name="poste", protocol="local", protocol_options={"local": options})


def _afficher(session):
    """Fenêtre 800×600 qui montre l'onglet."""
    fenetre = Gtk.Window(child=session.widget, default_width=800, default_height=600)
    fenetre.present()
    return fenetre


def _enfants(widget):
    """Enfants directs de ``widget``."""
    enfant = widget.get_first_child()
    while enfant is not None:
        yield enfant
        enfant = enfant.get_next_sibling()


def test_iso_8859_1_affiche_et_saisi(plugin, faux_shell):
    """ISO-8859-1 : sortie du shell lue correctement, saisie et commandes converties."""
    session = plugin.open(_hote("iso-8859-1", commands="é"))
    assert session.encodage == "ISO-8859-1"
    assert session.terminal.get_encoding() == "ISO-8859-1"
    fenetre = _afficher(session)
    assert _attendre(lambda: "café prêt" in _texte(session.terminal))
    assert _attendre(lambda: _trace(faux_shell) == ["e9"])
    session.terminal.feed_child("à\r".encode())
    assert _attendre(lambda: _trace(faux_shell) == ["e9", "e0"])
    session.terminal.feed_child(b"exit\r")
    assert _attendre(lambda: session.code_de_sortie is not None)
    assert _attendre(lambda: "Session ended" in _texte(session.terminal))
    fenetre.destroy()


def test_utf_8_par_defaut(plugin, faux_shell):
    """Sans option : UTF-8, ``set_encoding`` n'est pas appelé, les octets ISO-8859-1 sont illisibles."""
    session = plugin.open(_hote())
    assert session.encodage == "UTF-8" and session.terminal.get_encoding() == "UTF-8"
    fenetre = _afficher(session)
    assert _attendre(lambda: "$ " in _texte(session.terminal))
    assert "café" not in _texte(session.terminal)
    session.close()
    assert _attendre(lambda: session.code_de_sortie is not None)
    fenetre.destroy()


def test_encodage_inconnu(plugin, faux_shell):
    """Valeur inconnue dans la configuration : UTF-8, l'onglet s'ouvre."""
    session = plugin.open(_hote("BIDON"))
    assert session.encodage == "UTF-8"
    assert plugin.context.log.avertissements == []
    session.close()
    assert _attendre(lambda: session.code_de_sortie is not None)


def test_encodage_refuse_par_vte(plugin, faux_shell, monkeypatch):
    """VTE refuse l'encodage (sans ICU, ou nom absent) : UTF-8, avertissement et message dans l'onglet."""
    monkeypatch.setattr(terminal, "ENCODAGES", (*terminal.ENCODAGES, "BIDON"))
    session = plugin.open(_hote("bidon"))
    assert session.encodage == "UTF-8" and session.terminal.get_encoding() == "UTF-8"
    assert len(plugin.context.log.avertissements) == 1
    assert "local: encodage BIDON refusé" in plugin.context.log.avertissements[0]
    fenetre = _afficher(session)
    assert _attendre(
        lambda: "Encoding BIDON is not available, UTF-8 is used." in _texte(session.terminal)
    )
    session.close()
    assert _attendre(lambda: session.code_de_sortie is not None)
    fenetre.destroy()


def test_message_dans_l_encodage_de_l_onglet(tmp_path):
    """Les messages de gcm4 (ici l'erreur de lancement) sont encodés comme l'onglet."""
    from gcm4.ui.terminal import SessionTerminal

    journal = Journal()
    absent = str(tmp_path / "absenté")
    session = SessionTerminal(
        _hote("ISO-8859-15"), "local", terminal.Lancement([absent]), journal, 0
    )
    fenetre = _afficher(session)
    assert _attendre(lambda: bool(journal.avertissements))
    assert _attendre(lambda: "absenté" in _texte(session.terminal))
    fenetre.destroy()


def test_zone_d_options_encodage(plugin):
    """Liste des encodages : valeur de l'hôte sélectionnée, UTF-8 n'est pas écrit."""
    options = {"encoding": "koi8-r"}
    appels = []
    zone = plugin.build_host_options_widget(_hote(), options, lambda: appels.append(1))
    grille = list(_enfants(zone))[-1]
    assert grille.get_child_at(0, 3).get_label() == "Encoding:"
    liste = grille.get_child_at(1, 3)
    assert liste.get_model().get_n_items() == len(terminal.ENCODAGES)
    assert liste.get_model().get_string(liste.get_selected()) == "KOI8-R"
    assert options == {"encoding": "koi8-r"} and appels == []
    liste.set_selected(terminal.ENCODAGES.index("ISO-8859-15"))
    assert options["encoding"] == "ISO-8859-15"
    liste.set_selected(0)
    assert options["encoding"] == "" and len(appels) == 2


def test_zone_d_options_sans_encodage(plugin):
    """Sans option : UTF-8 sélectionné, rien écrit tant que rien ne change."""
    options = {}
    zone = plugin.build_host_options_widget(_hote(), options, lambda: None)
    liste = list(_enfants(zone))[-1].get_child_at(1, 3)
    assert liste.get_selected() == 0
    assert options == {}
