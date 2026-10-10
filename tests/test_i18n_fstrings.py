"""Aucune f-string passée à `_()` / `N_()` (issue #165).

Une f-string est évaluée avant l'appel : `_()` reçoit le texte déjà
rempli, qui ne figure dans aucun catalogue, donc jamais traduit. De plus,
selon leur version, xgettext extrait ou ignore ces appels, si bien que
`scripts/i18n-update.sh --check` donnerait des résultats différents en
local et en CI. Forme attendue : `_("... {nom} ...").format(nom=valeur)`.
"""

from __future__ import annotations

import ast
import subprocess
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = ("tests/", "tools/", "scripts/", "SSH-Studio/", "gtk-frdp/")


def _fstring_calls(source: str) -> list[int]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(source)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"_", "N_", "ngettext", "pgettext"}
        and any(isinstance(arg, ast.JoinedStr) for arg in node.args)
    ]


class TestPasDeFStringDansGettext(unittest.TestCase):
    """Garde-fou des chaînes traduisibles."""

    def test_sources_sans_fstring_traduite(self):
        """Aucun `_(f"...")` dans les sources scannées par xgettext."""
        files = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
        fautes = {
            f: lines
            for f in files
            if not f.startswith(EXCLUDED)
            and (lines := _fstring_calls((ROOT / f).read_text(encoding="utf-8")))
        }
        self.assertEqual(fautes, {})

    def test_detecteur(self):
        """Le détecteur voit `_(f"...")` et ignore `_("...").format(...)`."""
        self.assertEqual(_fstring_calls('_(f"a {x}")\n_("a {x}").format(x=1)\nf"{x}"\n'), [1])


if __name__ == "__main__":
    unittest.main()
