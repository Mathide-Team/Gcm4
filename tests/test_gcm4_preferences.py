"""Préférences générales sans GTK : inventaire de Wconfig, lecture, écriture (#147)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gcm4.core import preferences as p
from gcm4.core.config import ConfigError

ROOT = Path(__file__).resolve().parents[1]


def _options_de_wconfig() -> set[str]:
    """Noms ``conf.X`` utilisés dans la classe GTK3 ``Wconfig``."""
    arbre = ast.parse((ROOT / "gnome_connection_manager.py").read_text(encoding="utf-8"))
    classe = next(
        n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef) and n.name == "Wconfig"
    )
    noms = set()
    for noeud in ast.walk(classe):
        if (
            isinstance(noeud, ast.Attribute)
            and isinstance(noeud.value, ast.Name)
            and noeud.value.id == "conf"
            and noeud.attr.isupper()
        ):
            noms.add(noeud.attr)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
            if noeud.value.startswith("conf.") and noeud.value[5:].isupper():
                noms.add(noeud.value[5:])
    return noms


def test_chaque_option_de_wconfig_est_classee():
    """Critère de #147 : aucune option de Wconfig ne disparaît sans classement."""
    trouvees = _options_de_wconfig()
    assert {"CONFIRM_ON_EXIT", "WORD_SEPARATORS", "THEME_MODE"} <= trouvees  # garde-fou
    classees = {o.nom for o in p.INVENTAIRE}
    assert trouvees - classees == set()


def test_inventaire_coherent():
    """Noms uniques, classement connu, destination renseignée."""
    noms = [o.nom for o in p.INVENTAIRE]
    assert len(noms) == len(set(noms))
    for option in p.INVENTAIRE:
        assert option.classement in p.CLASSEMENTS and option.destination
    pages_5a = {o.nom for o in p.INVENTAIRE if "#147" in o.destination}
    assert pages_5a == {"RESTORE_OPEN_TABS", "CONFIRM_ON_EXIT", "CHECK_UPDATES", "THEME_MODE"}


def test_valeurs_par_defaut_sans_fichier(tmp_path):
    """Fichier absent : valeurs par défaut de GTK3."""
    assert p.load_preferences(str(tmp_path / "absent.conf")) == p.Preferences()


def test_lecture_des_cles_gtk3(tmp_path):
    """Les clés de GTK3 ([options], [window]) sont relues telles quelles."""
    conf = tmp_path / "gcm4.conf"
    conf.write_text(
        "[options]\nconfirm-exit = False\ncheck-updates = False\nrestore-open-tabs = True\n"
        "[window]\ntheme-mode = dark\nshow-panel = False\ntree-font =  Serif 12 \n",
        encoding="utf-8",
    )
    assert p.load_preferences(str(conf)) == p.Preferences(
        confirm_exit=False,
        check_updates=False,
        restore_open_tabs=True,
        theme="dark",
        show_panel=False,
        tree_font="Serif 12",
    )


def test_booleen_invalide_valeur_par_defaut(tmp_path):
    """Valeur illisible : valeur par défaut, pas d'exception."""
    conf = tmp_path / "gcm4.conf"
    conf.write_text("[options]\nconfirm-exit = peut-etre\n", encoding="utf-8")
    assert p.load_preferences(str(conf)).confirm_exit is True


def test_enregistrement_ne_touche_que_la_cle(tmp_path):
    """Une préférence écrite : le reste du fichier (hôtes, autres clés) est conservé."""
    conf = tmp_path / "gcm4.conf"
    conf.write_text(
        "[options]\nfont = Monospace 11\nconfirm-exit = True\n"
        "[host 1]\nname = api\npass = secret\n[window]\nleft-panel-width = 260\n",
        encoding="utf-8",
    )
    p.save_preference(str(conf), "confirm_exit", False)
    p.save_preference(str(conf), "tree_font", "  Sans Bold 10 ")
    p.save_preference(str(conf), "show_panel", False)
    p.save_preference(str(conf), "theme", "dark")
    texte = conf.read_text(encoding="utf-8")
    for ligne in ("font = Monospace 11", "name = api", "pass = secret", "left-panel-width = 260"):
        assert ligne in texte
    relu = p.load_preferences(str(conf))
    assert (relu.confirm_exit, relu.tree_font, relu.show_panel, relu.theme) == (
        False,
        "Sans Bold 10",
        False,
        "dark",
    )
    assert "dark-mode = True" in texte  # compatibilité GTK3 (#135)


def test_preference_inconnue_ou_mal_typee(tmp_path):
    """Nom inconnu ou type inattendu : ValueError, rien n'est écrit."""
    conf = tmp_path / "gcm4.conf"
    with pytest.raises(ValueError):
        p.save_preference(str(conf), "inconnue", True)
    with pytest.raises(ValueError):
        p.save_preference(str(conf), "confirm_exit", "oui")
    assert not conf.exists()


def test_fichier_corrompu_jamais_reecrit(tmp_path):
    """Fichier illisible : ConfigError, contenu intact."""
    conf = tmp_path / "gcm4.conf"
    conf.write_text("pas une section\n= =\n", encoding="utf-8")
    avant = conf.read_bytes()
    with pytest.raises(ConfigError):
        p.save_preference(str(conf), "confirm_exit", False)
    assert conf.read_bytes() == avant


def test_inventaire_documente():
    """docs/architecture.md §2.11 liste chaque option de l'inventaire."""
    doc = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "### 2.11 Préférences" in doc
    for option in p.INVENTAIRE:
        assert f"| `{option.nom}` |" in doc, option.nom
