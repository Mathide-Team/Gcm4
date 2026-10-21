# Publication et vérification locale

Issue #162.

## `make ci`

Rejoue localement les étapes des jobs Qualité, Types, i18n, Intégration au
bureau et documentation de `.github/workflows/ci.yml`, dans le même ordre :
ruff, flake8, format, imports circulaires, pytest avec couverture, mypy,
validation et fraîcheur des catalogues, lanceur et AppStream, MkDocs. `tests/test_make_ci.py` échoue si une étape est
ajoutée à la CI sans l'être à `make ci`.

Le hook pre-commit (`.pre-commit-config.yaml`, #90) reste plus léger
(ruff, format, imports circulaires) : `make ci` est la vérification
complète avant de pousser.

## Intégration au bureau

Issue #155. Fichiers de `data/`, nommés d'après l'identifiant de
l'application (`APPLICATION_ID`, `io.github.MathildeDec.gcm4`) :

- `io.github.MathildeDec.gcm4.desktop` : lanceur (`Exec=gcm4`) et action
  « gcm4 (debug mode) » (`gcm4 --debug`). gcm4 est une application à
  instance unique : si gcm4 tourne déjà, l'action présente la fenêtre
  existante sans activer le mode debug (#275).
- `io.github.MathildeDec.gcm4.metainfo.xml` : métadonnées AppStream
  (logithèques). La balise `<release>` suit la version de `pyproject.toml`.
- `icons/hicolor/<taille>/apps/io.github.MathildeDec.gcm4.png` : 16 à 128
  pixels, produites par `make icons` (`scripts/generer-icones.sh`) depuis
  `icon.png` (128×128, jamais agrandie) et versionnées.

`GLib.set_prgname(APPLICATION_ID)` (`Gcm4Application.__init__`) donne à la
fenêtre la classe `io.github.MathildeDec.gcm4` (`WM_CLASS` sous X11,
`app_id` sous Wayland) : c'est ce qui rattache la fenêtre à son lanceur
(`StartupWMClass`). Sans cet appel, la classe était `python3`.

`make check-desktop` (`scripts/check-desktop.sh`, job CI « Intégration au
bureau ») valide le lanceur (`desktop-file-validate`, tout constat fait
échouer), les métadonnées (`appstreamcli validate --no-net`) et les tailles
des icônes. `tests/test_integration_bureau.py` vérifie sans ces outils la
cohérence entre fichiers, identifiant, nom affiché et version.

Restent hors de cette issue : l'installation de ces fichiers par les
paquets (#156, #157) et la traduction du lanceur et des métadonnées (#274).

## Paquets

- `make deb`, `make rpm`, `make opensuse` (fpm) emballent l'arborescence
  produite par `make install` : tous les modules `.py` de la racine,
  `plugins/` hors tests, les traductions compilées, l'icône et le
  `.desktop`.
- `tests/test_paquet_contenu.py` lance `make install` et vérifie que chaque
  module local importé, même dans une fonction, est installé. Avant cette
  issue, seuls trois modules étaient copiés et l'application installée ne
  démarrait pas.
- `python3-loguru` est une dépendance de chaque paquet. Les versions des
  distributions peuvent être plus anciennes que la 0.7.3 de
  `pyproject.toml` (Debian bookworm, Ubuntu jammy) : à vérifier au premier
  test d'installation réel (#156, #157).

## Release

`.github/workflows/release.yml` :

- sur tag `v*` (ex. `v1.3.4`) : construit les trois paquets avec
  `PKG_VERSION` tiré du tag, vérifie leur contenu, les publie en artefact
  et les attache à la release du tag ;
- `workflow_dispatch` : même construction sans tag (artefacts seulement),
  version optionnelle.

`guard-main.yml` est conservé : les PR vers `main` viennent de `dev`.

## Protections de main et de dev

- **dev** : contrôles requis Qualité, Types, i18n et Tests GTK4 (Xvfb), et
  branche **à jour exigée** (`.github/branch-protection/dev.json`) : une PR
  en retard se met à jour avec `gh pr update-branch`.
- **main** : on n'y fusionne que dev (contrôle « Garde : PR vers main doit
  venir de dev »), avec Qualité. La branche à jour n'y est **pas** exigée,
  depuis le 12/10/2026. Chaque release crée sur main un commit de fusion
  absent de dev ; avec cette exigence, la release suivante était déclarée
  en retard, et il fallait une PR main → dev (#215, #220) que la
  protection de dev refusait de faire automatiquement.

## Tag de pré-version

`vX.Y.Z-rcN` donne la version de paquet `X.Y.Z~rcN`, qui reste inférieure à
`X.Y.Z` pour dpkg et rpm, et une release marquée pré-version (#211, essai
`v1.3.4-rc1`). GitHub remplace `~` par `.` dans le **nom** des fichiers
attachés, pas dans les métadonnées des paquets.
