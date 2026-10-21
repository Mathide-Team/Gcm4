"""Chaque texte de gcm4 est traduit dans toutes les langues (décision du 12/10/2026).

Textes de src/gcm4, du lanceur et des métadonnées AppStream de data/ (#274).

L'outillage n'insère jamais de traduction (``scripts/i18n-update.sh``) ;
les textes de la base GTK4 sont traduits à la main, dans le commit qui les
ajoute ou dans un commit dédié. Une entrée vide ou ``fuzzy`` (ignorée à
l'exécution) fait échouer ce test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

LANG = Path(__file__).resolve().parents[1] / "lang"


def _entrees(chemin: Path) -> dict[str, tuple[str, bool]]:
    """Msgid → (msgstr, fuzzy) ; format du dépôt : msgid et msgstr sur une ligne."""
    entrees: dict[str, tuple[str, bool]] = {}
    for bloc in chemin.read_text(encoding="utf-8").split("\n\n"):
        lignes = bloc.splitlines()
        mid = next((ligne[6:] for ligne in lignes if ligne.startswith("msgid ")), None)
        mstr = next((ligne[7:] for ligne in lignes if ligne.startswith("msgstr ")), None)
        if mid and mid != '""' and mstr is not None:
            fuzzy = any(ligne.startswith("#,") and "fuzzy" in ligne for ligne in lignes)
            entrees[mid] = (mstr, fuzzy)
    return entrees


def _msgids_gcm4() -> list[str]:
    """Msgids du modèle dont une référence est dans src/gcm4/ ou data/."""
    ids = []
    for bloc in (LANG / "messages.pot").read_text(encoding="utf-8").split("\n\n"):
        lignes = bloc.splitlines()
        if any(
            ligne.startswith("#:") and ("src/gcm4/" in ligne or "data/" in ligne)
            for ligne in lignes
        ):
            ids += [ligne[6:] for ligne in lignes if ligne.startswith("msgid ")]
    return ids


def test_des_textes_gcm4_existent():
    """Garde-fou : le filtre trouve bien les textes de la base GTK4."""
    assert '"Welcome to Gnome Connection Manager"' in _msgids_gcm4()
    # Lanceur et AppStream (#274).
    assert '"connection;remote;host;session;terminal;gcm4;"' in _msgids_gcm4()
    assert '"Host passwords stored encrypted"' in _msgids_gcm4()


@pytest.mark.parametrize("po", sorted(LANG.glob("*.po")), ids=lambda p: p.stem)
def test_textes_gcm4_traduits(po):
    """Aucun texte de src/gcm4 ou data/ vide ou fuzzy dans cette langue."""
    entrees = _entrees(po)
    manquants = [
        m for m in _msgids_gcm4() if entrees.get(m, ('""', False))[0] == '""' or entrees[m][1]
    ]
    assert manquants == []
