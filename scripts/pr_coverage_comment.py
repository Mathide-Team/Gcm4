#!/usr/bin/env python3
r"""pr_coverage_comment.py -- publie le commentaire de couverture d'une PR.

Issue #128 (repris de Netcross, scripts/pr_coverage_comment.py, #224) : le
workflow .github/workflows/pr-coverage.yml exécute pytest --cov deux fois
(ref de fusion de la PR, puis SHA de base de `dev`) et passe les deux
rapports JSON de coverage.py à ce script. Celui-ci publie, ou met à jour,
un commentaire unique sur la PR : couverture totale, delta par rapport à la
base, et fichiers dont la couverture baisse.

Appel :
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \\
    python3 scripts/pr_coverage_comment.py \\
        --pr-json coverage-pr.json --base-json coverage-base.json \\
        --pr-number 123

Bibliothèque standard (urllib) plus loguru, dépendance du projet : le
workflow le lance par ``uv run``. Le seuil bloquant (``fail_under`` de pyproject.toml) est
appliqué par ci.yml ; ce script le rappelle et signale une PR qui passe
dessous.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

from loguru import logger

# Marqueur HTML invisible : identifie le commentaire à mettre à jour plutôt
# qu'à dupliquer d'un push à l'autre.
MARQUEUR = "<!-- gcm4:couverture-pr -->"

API = "https://api.github.com"

PYPROJECT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyproject.toml"
)

# Au-delà, la liste des fichiers en baisse est tronquée (commentaire lisible).
MAX_FICHIERS = 15


def lire_seuil(chemin: str = PYPROJECT) -> float | None:
    """``fail_under`` de la section [tool.coverage.report], ou None.

    Lecture par expression régulière plutôt que tomllib (Python >= 3.11) :
    le projet accepte encore Python 3.10.
    """
    logger.debug("lire_seuil() | chemin={}", chemin)
    try:
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
    except OSError as exc:
        logger.warning("pyproject.toml illisible ({}) : aucun seuil", exc)
        return None
    section = re.search(r"^\[tool\.coverage\.report\]\s*$(.*?)(?=^\[|\Z)", texte, re.M | re.S)
    if section is None:
        logger.debug("lire_seuil() -> None (section absente)")
        return None
    valeur = re.search(r"^fail_under\s*=\s*([0-9.]+)\s*$", section.group(1), re.M)
    seuil = float(valeur.group(1)) if valeur else None
    logger.debug("lire_seuil() -> {}", seuil)
    return seuil


def _lire_rapport(chemin: str) -> dict:
    """Charge un rapport JSON de coverage.py."""
    logger.debug("_lire_rapport() | chemin={}", chemin)
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _pct(valeur: float) -> str:
    """76.7421... -> '76.7 %'."""
    return f"{valeur:.1f} %"


def _delta(pr: float, base: float) -> str:
    """Différence en points de pourcentage, signée, 1 décimale."""
    return f"{pr - base:+.1f} pt"


def _ligne_seuil(pourcentage_pr: float, seuil: float | None) -> str:
    """Phrase de rappel du seuil bloquant."""
    if seuil is None:
        return "Aucun seuil bloquant configuré (`fail_under` absent de pyproject.toml)."
    if pourcentage_pr < seuil:
        return (
            f"**Sous le seuil bloquant** de {_pct(seuil)} (`fail_under`) : "
            "le job Qualité de la CI échouera."
        )
    return f"Seuil bloquant : {_pct(seuil)} (`fail_under`), marge {pourcentage_pr - seuil:.1f} pt."


def fichiers_en_baisse(rapport_pr: dict, rapport_base: dict, tolerance: float = 0.05) -> list:
    """Fichiers présents des deux côtés dont la couverture baisse.

    Returns:
        list[tuple[str, float, float]]: (fichier, base %, PR %), triés par
        baisse décroissante. Un fichier nouveau ou supprimé n'y figure pas :
        le total le reflète déjà.
    """
    logger.debug("fichiers_en_baisse() | tolerance={}", tolerance)
    base = rapport_base.get("files", {})
    resultat = []
    for nom, donnees in rapport_pr.get("files", {}).items():
        if nom not in base:
            continue
        avant = base[nom]["summary"]["percent_covered"]
        apres = donnees["summary"]["percent_covered"]
        if apres < avant - tolerance:
            resultat.append((nom, avant, apres))
    resultat.sort(key=lambda x: x[2] - x[1])
    logger.debug("fichiers_en_baisse() -> {} fichier(s)", len(resultat))
    return resultat


def construire_commentaire(
    rapport_pr: dict, rapport_base: dict, seuil: float | None = None
) -> str:
    """Corps Markdown du commentaire de couverture."""
    logger.debug("construire_commentaire() | seuil={}", seuil)
    pr = rapport_pr["totals"]
    base = rapport_base["totals"]
    b_pr, b_base = pr.get("covered_branches", 0), base.get("covered_branches", 0)
    lignes = [
        MARQUEUR,
        "## Couverture de tests (delta vs `dev`)",
        "",
        "| Métrique | Base (`dev`) | PR | Δ |",
        "|---|---|---|---|",
        f"| Couverture | {_pct(base['percent_covered'])} | {_pct(pr['percent_covered'])} | "
        f"{_delta(pr['percent_covered'], base['percent_covered'])} |",
        f"| Instructions couvertes | {base['covered_lines']}/{base['num_statements']} | "
        f"{pr['covered_lines']}/{pr['num_statements']} | "
        f"{pr['covered_lines'] - base['covered_lines']:+d} |",
        f"| Branches couvertes | {b_base}/{base.get('num_branches', 0)} | "
        f"{b_pr}/{pr.get('num_branches', 0)} | {b_pr - b_base:+d} |",
        "",
        _ligne_seuil(pr["percent_covered"], seuil),
    ]
    baisses = fichiers_en_baisse(rapport_pr, rapport_base)
    if baisses:
        lignes += ["", "### Fichiers dont la couverture baisse", "", "| Fichier | Base | PR |"]
        lignes.append("|---|---|---|")
        for nom, avant, apres in baisses[:MAX_FICHIERS]:
            lignes.append(f"| `{nom}` | {_pct(avant)} | {_pct(apres)} |")
        if len(baisses) > MAX_FICHIERS:
            lignes.append(f"| … et {len(baisses) - MAX_FICHIERS} autre(s) | | |")
    logger.debug("construire_commentaire() -> {} ligne(s)", len(lignes))
    return "\n".join(lignes)


def _appel_api(chemin: str, token: str, methode: str = "GET", corps: str | None = None):
    """Appel REST GitHub minimal (urllib, pas de dépendance tierce)."""
    logger.debug("_appel_api() | {} {}", methode, chemin)
    requete = urllib.request.Request(
        f"{API}{chemin}",
        data=corps.encode() if corps else None,
        method=methode,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(requete) as reponse:  # noqa: S310 (URL fixe api.github.com)
        return json.loads(reponse.read())


def publier(repo: str, pr: int, corps: str, token: str) -> str:
    """Met à jour le commentaire existant (marqueur) ou en crée un."""
    logger.debug("publier() | repo={} pr={}", repo, pr)
    commentaires = _appel_api(f"/repos/{repo}/issues/{pr}/comments?per_page=100", token)
    for c in commentaires:
        if MARQUEUR in c.get("body", ""):
            _appel_api(
                f"/repos/{repo}/issues/comments/{c['id']}",
                token,
                methode="PATCH",
                corps=json.dumps({"body": corps}),
            )
            return f"commentaire existant mis à jour ({c['html_url']})"
    cree = _appel_api(
        f"/repos/{repo}/issues/{pr}/comments",
        token,
        methode="POST",
        corps=json.dumps({"body": corps}),
    )
    return f"commentaire créé ({cree['html_url']})"


def main(argv: list[str]) -> int:
    """Point d'entrée : 0 si publié, 2 si l'environnement GitHub manque."""
    parseur = argparse.ArgumentParser(description="Commentaire de couverture d'une PR")
    parseur.add_argument("--pr-json", required=True, help="rapport coverage.py de la PR")
    parseur.add_argument("--base-json", required=True, help="rapport coverage.py de la base")
    parseur.add_argument("--pr-number", required=True, type=int)
    parseur.add_argument(
        "--dry-run", action="store_true", help="affiche le commentaire sans le publier"
    )
    arguments = parseur.parse_args(argv)
    # Traces DEBUG seulement sur demande (même variable que l'application,
    # issue #130) : les logs CI restent lisibles.
    niveau = "DEBUG" if os.environ.get("GCM_DEBUG", "") in {"1", "true", "yes", "on"} else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=niveau)
    logger.debug("main() | pr={} dry_run={}", arguments.pr_number, arguments.dry_run)

    corps = construire_commentaire(
        _lire_rapport(arguments.pr_json), _lire_rapport(arguments.base_json), lire_seuil()
    )
    if arguments.dry_run:
        print(corps)
        return 0
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        logger.error("GITHUB_TOKEN et GITHUB_REPOSITORY sont requis")
        return 2
    print(publier(repo, arguments.pr_number, corps, token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
