#!/usr/bin/env bash
# scripts/smoke-test-packages.sh -- test de fumée du paquet gcm4 installé (#156).
#
# Sur le modèle de Netcross : le paquet est vérifié tel que l'utilisateur le
# reçoit, dans un système propre (conteneur du job « Paquets »).
#
#   deb : scripts/smoke-test-packages.sh deb build-deb/dist/gcm4_*.deb
#         installe le .deb avec apt (dépendances résolues), puis vérifie :
#         1. aucune dépendance de plugin (VTE, gtk-vnc, spice, freerdp) ;
#         2. le lanceur /usr/bin/gcm4 (exécutable, /usr/bin/python3) ;
#         3. « gcm4 --version » donne la version du paquet ;
#         4. chaque module de /usr/share/gcm4 s'importe avec /usr/bin/python3 ;
#         5. le lanceur .desktop, le metainfo et les icônes sont installés ;
#         6. un catalogue .mo par langue de lang/LINGUAS, réellement chargé
#            par gcm4.core.i18n depuis /usr/share/locale ;
#         7. gcm4 démarre sous Xvfb, présente sa fenêtre, et son journal
#            debug ne contient ni erreur ni trace d'exception.
#   rpm : paquet .rpm, issue #157.
#
# Prérequis du système de test : apt, xvfb (xvfb-run), dbus (dbus-run-session),
# et aucune règle dpkg path-exclude sur /usr/share/locale (images minimales).
# Sortie non nulle au premier écart.

set -euo pipefail

MODE="${1:?usage: $0 deb <paquet>}"
PKG="${2:?usage: $0 deb <paquet>}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="io.github.MathildeDec.gcm4"
PREFIX="/usr/share/gcm4"
DOMAIN="gcm-lang"
ICON_SIZES=(16x16 22x22 24x24 32x32 48x48 64x64 128x128)
# Dépendances propres aux plugins de connexion : jamais dans la base.
PLUGIN_DEPS_RE='vte|gtk-?vnc|spice|freerdp|expect|paramiko'
# Délai laissé à gcm4 pour démarrer sous Xvfb avant d'être arrêté.
LAUNCH_SECONDS="${GCM4_SMOKE_LAUNCH_SECONDS:-20}"

fail() { echo "ECHEC : $*" >&2; exit 1; }

linguas() { sed -e 's/#.*//' -e 's/[[:space:]]//g' "$ROOT/lang/LINGUAS" | grep -v '^$'; }

check_deb() {
    local sudo="${SUDO-sudo}"
    [ "$(id -u)" -eq 0 ] && sudo=""
    # Images minimales (conteneurs Ubuntu) : dpkg y ignore les .mo, un poste
    # de travail non. Le test 6 serait faux : on refuse de commencer.
    if grep -hsE '^path-exclude=/usr/share/locale/' /etc/dpkg/dpkg.cfg.d/* | grep -q .; then
        fail "dpkg exclut /usr/share/locale (système minimal) : retirer la règle path-exclude de /etc/dpkg/dpkg.cfg.d/ avant le test"
    fi
    $sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$(readlink -f "$PKG")" >/dev/null

    # 1. dépendances
    local depends
    depends="$(dpkg-query -W -f='${Depends}' gcm4)"
    if grep -Eiq "$PLUGIN_DEPS_RE" <<<"$depends"; then
        fail "dépendance de plugin dans le paquet de la base : $depends"
    fi
    for d in python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-loguru; do
        grep -Eq "(^|, )$d( |,|$)" <<<"$depends" || fail "dépendance $d absente : $depends"
    done
    echo "dépendances : $depends"

    # 2. lanceur
    [ -x /usr/bin/gcm4 ] || fail "lanceur /usr/bin/gcm4 absent ou non exécutable"
    head -n 1 /usr/bin/gcm4 | grep -qx '#!/usr/bin/python3' || fail "/usr/bin/gcm4 n'utilise pas /usr/bin/python3"
    command -v gcm4 >/dev/null || fail "gcm4 introuvable dans le PATH"

    # 3. version : celle du paquet, lue dans le .dist-info installé
    local version attendu home
    version="$(dpkg-query -W -f='${Version}' gcm4)"
    attendu="gcm4 $version"
    home="$(mktemp -d)"
    [ "$(HOME="$home" gcm4 --version)" = "$attendu" ] \
        || fail "gcm4 --version : « $(HOME="$home" gcm4 --version) » au lieu de « $attendu »"
    echo "--version : $attendu"

    # 4. imports (interface comprise : ses dépendances sont celles du paquet)
    /usr/bin/python3 - "$PREFIX" <<'PY'
import importlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))

# Modules à dépendance optionnelle : leur import peut légitimement échouer
# si la dépendance n'est pas installée. D1 de #118 : le paquet de base
# n'embarque pas les dépendances des plugins ; #223 : VTE GTK4 (Vte-3.91)
# est absent de Rocky Linux 9 et 10 — l'import de gcm4.ui.terminal échoue
# alors dans le plugin, signalé en erreur dans Préférences > Extensions,
# sans empêcher gcm4 de démarrer (la base ne l'importe jamais). La
# fonctionnalité est couverte ailleurs : job GTK4 (tests/gtk4/
# test_plugin_local.py, VTE installé).
OPTIONNELS = {"gcm4.ui.terminal": "VTE GTK4 (Vte-3.91), absent du paquet de base (D1 #118, #223)"}

mods, errors, optionnels = [], [], []
for py in sorted(root.rglob("*.py")):
    rel = py.relative_to(root).with_suffix("")
    name = ".".join(rel.parts[:-1] if rel.name == "__init__" else rel.parts)
    if name.endswith("__main__"):
        continue  # lancerait l'application
    mods.append(name)
    try:
        module = importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001 -- on veut tout lister
        if name in OPTIONNELS:
            optionnels.append(f"{name}: {OPTIONNELS[name]}")
            continue
        errors.append(f"{name}: {exc!r}")
        continue
    if not str(getattr(module, "__file__", "")).startswith(str(root)):
        errors.append(f"{name}: importé depuis {module.__file__}, hors de {root}")
if optionnels:
    print("modules optionnels non importés (attendu sans leur dépendance) :")
    print("  " + "\n  ".join(optionnels))
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(f"imports : {len(errors)} module(s) en échec sur {len(mods)}")
print(f"imports : {len(mods)} modules OK")
PY

    # 5. intégration au bureau
    local desktop="/usr/share/applications/$APP_ID.desktop"
    [ -f "$desktop" ] || fail "$desktop absent"
    grep -qx 'Exec=gcm4' "$desktop" || fail "$desktop : Exec=gcm4 absent"
    grep -qx "Icon=$APP_ID" "$desktop" || fail "$desktop : Icon=$APP_ID absent"
    [ -f "/usr/share/metainfo/$APP_ID.metainfo.xml" ] || fail "metainfo absent"
    for s in "${ICON_SIZES[@]}"; do
        [ -f "/usr/share/icons/hicolor/$s/apps/$APP_ID.png" ] || fail "icône $s absente"
    done
    echo "bureau : lanceur, metainfo et ${#ICON_SIZES[@]} icônes installés"

    # 6. traductions
    local n=0
    for loc in $(linguas); do
        [ -f "/usr/share/locale/$loc/LC_MESSAGES/$DOMAIN.mo" ] || fail "catalogue $loc absent"
        n=$((n + 1))
    done
    /usr/bin/python3 - "$PREFIX" "$DOMAIN" $(linguas) <<'PY'
import gettext, os, sys
sys.path.insert(0, sys.argv[1])
domain, locales = sys.argv[2], sys.argv[3:]
from gcm4.core import i18n
for loc in locales:
    os.environ["LANGUAGE"] = loc
    attendu = gettext.translation(domain, "/usr/share/locale", [loc])
    obtenu = i18n.install()
    if type(obtenu) is gettext.NullTranslations or obtenu._catalog != attendu._catalog:
        sys.exit(f"traductions : {loc} non chargé par gcm4.core.i18n depuis /usr/share/locale")
os.environ["LANGUAGE"] = "fr_FR"
i18n.install()
if i18n._("Cancel") != "Annuler":
    sys.exit(f"traductions : « Cancel » donne « {i18n._('Cancel')} » en fr_FR")
PY
    echo "traductions : $n catalogues installés et chargés"

    # 7. démarrage réel, sans plugin
    local journal="$home/.config/gcm4/log/gcm-app.log" code=0
    HOME="$home" timeout -k 5 "$LAUNCH_SECONDS" dbus-run-session -- xvfb-run -a gcm4 --debug \
        >"$home/sortie.txt" 2>&1 || code=$?
    # 124 : toujours en marche à l'échéance, arrêté par timeout (attendu).
    [ "$code" -eq 124 ] || { cat "$home/sortie.txt" >&2; fail "gcm4 s'est arrêté seul (code $code)"; }
    [ -f "$journal" ] || { cat "$home/sortie.txt" >&2; fail "journal debug $journal absent"; }
    grep -q "_on_activate: fenêtre présentée" "$journal" \
        || { tail -n 30 "$journal" >&2; fail "fenêtre principale non présentée"; }
    if grep -Eq '\| (ERROR|CRITICAL) +\||Traceback' "$journal" "$home/sortie.txt"; then
        grep -E '\| (ERROR|CRITICAL) +\||Traceback' -A5 "$journal" "$home/sortie.txt" >&2
        fail "erreur ou exception au démarrage"
    fi
    echo "démarrage : fenêtre présentée en moins de ${LAUNCH_SECONDS} s, journal sans erreur"
    rm -rf "$home"
}

case "$MODE" in
    deb) check_deb ;;
    rpm) fail "paquet .rpm : issue #157" ;;
    *) fail "mode inconnu : $MODE" ;;
esac
echo "test de fumée $MODE : OK"
