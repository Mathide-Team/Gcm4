"""Workflow .github/workflows/i18n.yml : PR automatique des catalogues (issue #167)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "i18n.yml").read_text(encoding="utf-8")


def _section(name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\n(.*?)(?=^\S|\Z)", WORKFLOW, re.M | re.S)
    return match.group(1) if match else ""


class TestWorkflowI18n(unittest.TestCase):
    """Déclenchement, unicité de la PR, absence de traduction automatique."""

    def test_declenche_par_un_push_sur_dev_touchant_le_code_ou_lang(self):
        """Push sur dev, filtré sur le code Python et lang/."""
        on = _section('"on"')
        self.assertRegex(on, r"push:\n\s+branches: \[dev\]")
        self.assertIn('"**.py"', on)
        self.assertIn('"lang/**"', on)

    def test_une_seule_pr_a_jour(self):
        """Concurrency avec annulation, branche fixe, PR existante réutilisée."""
        concurrency = _section("concurrency")
        self.assertIn("group: i18n-mise-a-jour-catalogues", concurrency)
        self.assertIn("cancel-in-progress: true", concurrency)
        self.assertIn("BRANCHE_I18N: i18n/mise-a-jour-catalogues", WORKFLOW)
        self.assertIn("gh pr list --head", WORKFLOW)

    def test_regeneration_par_le_script_et_sans_force_push(self):
        """Même script qu'en local ; jamais de push forcé."""
        self.assertIn("scripts/i18n-update.sh\n", WORKFLOW)
        self.assertIn("scripts/i18n-update.sh --compile lang", WORKFLOW)
        self.assertNotRegex(WORKFLOW, r"push\s+(-f|--force)")

    def test_aucune_traduction_automatique(self):
        """Ni msgen, ni outil de traduction machine ; msgstr vides annoncés."""
        for outil in ("msgen", "translate-shell", "trans ", "deepl", "googletrans"):
            self.assertNotIn(outil, WORKFLOW.lower().replace("translate-toolkit", ""))
        self.assertIn('msgstr ""', WORKFLOW)

    def test_le_script_ne_traduit_pas_non_plus(self):
        """scripts/i18n-update.sh vide les msgstr que msginit recopie."""
        script = (ROOT / "scripts" / "i18n-update.sh").read_text(encoding="utf-8")
        self.assertIn("msgfilter --keep-header", script)
        self.assertNotIn("msgen", script)


if __name__ == "__main__":
    unittest.main()
