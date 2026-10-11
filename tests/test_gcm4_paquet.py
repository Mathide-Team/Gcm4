"""Paquet src/gcm4 : point d'entrée et ligne de commande (issue #133).

Sans display ni GTK : ``gcm4 --version`` et ``--help`` sont utilisés par
le test de fumée des paquets ; GTK absent donne un message d'installation
et un code non nul, sans trace Python.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

import gcm4
from gcm4 import app
from gcm4.core import cli

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "gcm4"


def _gcm4(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "GCM_DEBUG")
    }
    env["GCM_LOG_LEVEL"] = "WARNING"
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "gcm4", *args], capture_output=True, text=True, env=env, timeout=60
    )


def test_version_sans_display():
    """``gcm4 --version`` répond sans display, sur stdout, code 0."""
    r = _gcm4("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == f"gcm4 {gcm4.__version__}"
    assert r.stderr == ""


def test_version_lue_dans_les_metadonnees():
    """La version est celle de pyproject.toml (importlib.metadata)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert gcm4.__version__ == data["project"]["version"]


def test_aide_sans_display():
    """``gcm4 --help`` liste les options de #133."""
    r = _gcm4("--help")
    assert r.returncode == 0, r.stderr
    for option in ("--version", "--debug", "--config", "GROUPE/NOM"):
        assert option in r.stdout


def test_gtk_absent_message_d_installation(tmp_path):
    """Sans PyGObject : commande d'installation, code CODE_GTK_ABSENT, aucune trace."""
    faux = tmp_path / "faux" / "gi"
    faux.mkdir(parents=True)
    (faux / "__init__.py").write_text('raise ImportError("gi simulé absent")\n', encoding="utf-8")
    r = _gcm4(
        "-c",
        str(tmp_path / "conf"),
        env_extra={
            "PYTHONPATH": os.pathsep.join([str(faux.parent), str(ROOT / "src"), str(ROOT)])
        },
    )
    assert r.returncode == app.CODE_GTK_ABSENT
    assert "Installez-les avec" in r.stderr
    assert "Traceback" not in r.stderr


def test_config_par_defaut_dans_le_home(tmp_path):
    """Sans ``-c``, configuration dans ``~/.gcm`` (décision D3 de #118)."""
    args = cli.parse_args([], home=str(tmp_path))
    assert args.config_dir == str(tmp_path / ".gcm")
    assert args.hotes == [] and args.debug is False


def test_config_relative_rendue_absolue(tmp_path, monkeypatch):
    """``-c conf`` relatif devient un chemin absolu."""
    monkeypatch.chdir(tmp_path)
    assert cli.parse_args(["-c", "conf"]).config_dir == str(tmp_path / "conf")


def test_hotes_et_debug():
    """Les arguments ``groupe/nom`` sont conservés, ``--debug`` reconnu."""
    args = cli.parse_args(["--debug", "lab/web", "prod/db"], home="/x")
    assert args.debug is True
    assert args.hotes == ["lab/web", "prod/db"]


def test_option_inconnue_refusee():
    """Une option inconnue est refusée par argparse (code 2)."""
    with pytest.raises(SystemExit) as exc:
        cli.parse_args(["--inexistante"])
    assert exc.value.code == 2


def test_commande_declaree():
    """``[project.scripts] gcm4 = "gcm4.app:main"`` et Python 3.12 minimum (D4)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["gcm4"] == "gcm4.app:main"
    assert data["project"]["requires-python"].startswith(">=3.12")


def _imports(path: Path) -> list[str]:
    noms = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            noms += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms.append(n.module)
    return noms


def test_aucun_gi_hors_de_ui():
    """Aucun fichier de src/gcm4 hors ``ui/`` n'importe ``gi`` (cœur et point d'entrée)."""
    fautes = [
        f"{p.relative_to(ROOT)} : {m}"
        for p in sorted(SRC.rglob("*.py"))
        if "ui" not in p.relative_to(SRC).parts
        for m in _imports(p)
        if m == "gi" or m.startswith("gi.")
    ]
    assert fautes == []


def test_require_version_uniquement_dans_ui_init():
    """``gi.require_version`` n'apparaît que dans ``src/gcm4/ui/__init__.py``."""
    fichiers = sorted(
        str(p.relative_to(ROOT))
        for p in SRC.rglob("*.py")
        if "require_version" in p.read_text(encoding="utf-8")
    )
    assert fichiers == ["src/gcm4/ui/__init__.py"]
