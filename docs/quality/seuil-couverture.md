# Couverture de tests et seuil bloquant

Issue #128, reprise des mécanismes de Netcross (#224, #246).

## Ce qui est mesuré

`[tool.coverage.run]` dans `pyproject.toml` :

- **périmètre** : le code de l'application (`source = ["."]`), sans `tests/`, les sous-projets vendorisés (`SSH-Studio/`, `gtk-frdp/`), `tools/`, `scripts/`, `rdp/` et `vnc/`. Avec `source`, un module qu'aucun test n'importe compte pour 0 % au lieu d'être ignoré : la mesure ne flatte pas la couverture réelle ;
- **branches** (`branch = true`) en plus des lignes : la couverture d'un `if` dont un seul côté est exécuté est comptée à moitié.

## Référence et seuil

| Date | Commit `dev` | Tests | Couverture (lignes + branches) |
|---|---|---|---|
| 01/10/2026 | b5fa496 | 739 | 19,7 % (2818/13135 lignes, 421/3304 branches) |

Le seuil bloquant `fail_under = 18` laisse moins de 2 points de marge. Il absorbe une PR qui ajoute du code GTK non testable sans Xvfb, et rien de plus.

État à la mesure de référence : le cœur GTK3 `gnome_connection_manager.py` est à 8 %. `ssh_key_manager_dialog.py`, `ssh_config_editor.py`, `snmp_push_core.py` et `netmiko_bulk_core.py` ne sont importés par aucun test (0 %). Les modules sans GTK (`gcm4_core.py` 85 %, `models.py` 86 %, `master_password_core.py` et `*_menu_core.py` 100 %) tirent la moyenne.

**Règle** : relever le seuil quand la base monte, ne jamais le baisser pour faire passer une PR. Le seuil ne s'applique qu'aux exécutions avec `--cov` (la CI, ou en local `uv run pytest --cov`).

## Seuil séparé du cœur (issue #164)

La base GTK4 doit naître très couverte : un second contrôle bloquant s'applique
à `src/gcm4/core/` seul, à **95 %** (lignes + branches, comme le total).

- **job Qualité** (`ci.yml`) : `uv run coverage report --include='src/gcm4/core/*' --fail-under=95`, juste après `pytest --cov`. Une PR qui fait passer le cœur sous 95 % échoue ;
- **commentaire de PR** (`scripts/pr_coverage_comment.py`) : ligne dédiée « Cœur `src/gcm4/core/` » (base, PR, delta) et rappel du seuil avec la marge.

Mesure de référence (18/10/2026, branche `dev`) : **98,9 %** (771/779 instructions,
142/144 branches) — 3,9 points de marge.

À la mesure de référence : `chiffrement.py`, `cli.py`, `menu.py`, `model.py`,
`theme.py` et `window_state.py` sont à 100 % ; `config.py` à 98,7 % ;
`i18n.py` à 84,8 % (lignes 22-29, `locale_dirs()` : recherche des catalogues
compilés) tire vers le bas.

## Où le voir

- **job Qualité** (`ci.yml`) : `pytest --cov`, rapport `term-missing` dans les logs, `coverage.xml` publié en artefact `coverage-report`. L'étape échoue sous le seuil ;
- **commentaire de PR** (`pr-coverage.yml`, `scripts/pr_coverage_comment.py`) : chaque PR vers `dev` reçoit un commentaire unique, mis à jour à chaque push. Il donne la couverture de la base et de la PR, le delta, la ligne du cœur (`src/gcm4/core/`) et les fichiers dont la couverture baisse. La base est mesurée avec la configuration de la PR, pour comparer le même périmètre.

## Suite prévue

- couverture du futur job GTK4 (Xvfb, #127) fusionnée avec `coverage combine`, pour que le code d'interface ne paraisse pas non couvert ;
