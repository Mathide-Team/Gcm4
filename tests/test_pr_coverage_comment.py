"""Tests de scripts/pr_coverage_comment.py (issue #128), sans réseau."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "pr_coverage_comment", ROOT / "scripts" / "pr_coverage_comment.py"
)
pcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pcc)


def _rapport(pct, lignes=(50, 100), branches=(5, 10), fichiers=None):
    """Rapport coverage.py JSON minimal."""
    return {
        "totals": {
            "percent_covered": pct,
            "covered_lines": lignes[0],
            "num_statements": lignes[1],
            "covered_branches": branches[0],
            "num_branches": branches[1],
        },
        "files": {nom: {"summary": {"percent_covered": v}} for nom, v in (fichiers or {}).items()},
    }


def test_seuil_lu_dans_le_pyproject_du_depot():
    """Le fail_under du dépôt est lu et plausible."""
    seuil = pcc.lire_seuil()
    assert seuil is not None and 0 < seuil <= 100


def test_seuil_absent_ou_fichier_illisible(tmp_path):
    """Section absente ou fichier introuvable : aucun seuil."""
    vide = tmp_path / "pyproject.toml"
    vide.write_text("[tool.ruff]\nline-length = 99\n", encoding="utf-8")
    assert pcc.lire_seuil(str(vide)) is None
    assert pcc.lire_seuil(str(tmp_path / "absent.toml")) is None


def test_seuil_hors_section_ignore(tmp_path):
    """Un fail_under hors de [tool.coverage.report] est ignoré."""
    f = tmp_path / "pyproject.toml"
    f.write_text("[autre]\nfail_under = 99\n[tool.coverage.report]\nprecision = 1\n")
    assert pcc.lire_seuil(str(f)) is None


def test_commentaire_totaux_et_delta():
    """Totaux, delta et marge au seuil dans le tableau."""
    corps = pcc.construire_commentaire(
        _rapport(21.04, (60, 100), (6, 10)), _rapport(19.7, (55, 100), (5, 10)), 18.0
    )
    assert corps.startswith(pcc.MARQUEUR)
    assert "| Couverture | 19.7 % | 21.0 % | +1.3 pt |" in corps
    assert "| Instructions couvertes | 55/100 | 60/100 | +5 |" in corps
    assert "| Branches couvertes | 5/10 | 6/10 | +1 |" in corps
    assert "marge 3.0 pt" in corps


def test_commentaire_sous_le_seuil():
    """Une PR sous le seuil est signalée en gras."""
    corps = pcc.construire_commentaire(_rapport(17.0), _rapport(19.7), 18.0)
    assert "**Sous le seuil bloquant** de 18.0 %" in corps


def test_commentaire_sans_seuil():
    """Sans seuil configuré, le commentaire le dit."""
    assert "Aucun seuil bloquant" in pcc.construire_commentaire(_rapport(1), _rapport(1), None)


def test_fichiers_en_baisse_tries_et_nouveaux_ignores():
    """Baisses triées ; fichiers nouveaux ou stables absents."""
    pr = _rapport(10, fichiers={"a.py": 50.0, "b.py": 10.0, "c.py": 90.0, "neuf.py": 0.0})
    base = _rapport(10, fichiers={"a.py": 60.0, "b.py": 40.0, "c.py": 90.02})
    assert pcc.fichiers_en_baisse(pr, base) == [("b.py", 40.0, 10.0), ("a.py", 60.0, 50.0)]
    corps = pcc.construire_commentaire(pr, base, None)
    assert "### Fichiers dont la couverture baisse" in corps
    assert "| `b.py` | 40.0 % | 10.0 % |" in corps
    assert "neuf.py" not in corps and "c.py" not in corps


def test_liste_des_baisses_tronquee():
    """Au-delà de MAX_FICHIERS, la liste est tronquée."""
    noms = {f"f{i}.py": 10.0 for i in range(pcc.MAX_FICHIERS + 3)}
    pr = _rapport(1, fichiers=noms)
    base = _rapport(1, fichiers=dict.fromkeys(noms, 20.0))
    assert "… et 3 autre(s)" in pcc.construire_commentaire(pr, base, None)


def test_publier_met_a_jour_le_commentaire_existant(monkeypatch):
    """Le commentaire portant le marqueur est modifié (PATCH)."""
    appels = []

    def faux(chemin, token, methode="GET", corps=None):
        """Remplace l'appel réseau."""
        appels.append((methode, chemin))
        if methode == "GET":
            return [{"id": 1, "body": "autre"}, {"id": 7, "body": pcc.MARQUEUR, "html_url": "u7"}]
        return {"html_url": "x"}

    monkeypatch.setattr(pcc, "_appel_api", faux)
    assert "mis à jour (u7)" in pcc.publier("o/r", 5, "corps", "t")
    assert appels[-1] == ("PATCH", "/repos/o/r/issues/comments/7")


def test_publier_cree_sinon(monkeypatch):
    """Sans commentaire existant, un commentaire est créé."""

    def faux(chemin, token, methode="GET", corps=None):
        """Remplace l'appel réseau."""
        return [] if methode == "GET" else {"html_url": "neuf"}

    monkeypatch.setattr(pcc, "_appel_api", faux)
    assert pcc.publier("o/r", 5, "corps", "t") == "commentaire créé (neuf)"


@pytest.fixture
def rapports(tmp_path):
    """Deux rapports JSON minimaux et les arguments de main()."""
    pr, base = tmp_path / "pr.json", tmp_path / "base.json"
    pr.write_text(json.dumps(_rapport(20.0)))
    base.write_text(json.dumps(_rapport(19.0)))
    return ["--pr-json", str(pr), "--base-json", str(base), "--pr-number", "3"]


def test_main_dry_run(rapports, capsys):
    """--dry-run affiche le commentaire sans appel réseau."""
    assert pcc.main(rapports + ["--dry-run"]) == 0
    assert "+1.0 pt" in capsys.readouterr().out


def test_main_sans_environnement_github(rapports, monkeypatch):
    """Sans GITHUB_TOKEN/GITHUB_REPOSITORY : code 2."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert pcc.main(rapports) == 2
