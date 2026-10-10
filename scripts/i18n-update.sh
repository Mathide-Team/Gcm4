#!/usr/bin/env bash
# scripts/i18n-update.sh -- maintenance des catalogues gettext (issue #165,
# sur le modèle de Netcross scripts/i18n-update.sh).
#
#   scripts/i18n-update.sh              xgettext -> lang/messages.pot,
#                                       msgmerge lang/*.po (crée les .po
#                                       manquants avec msginit),
#                                       msgfmt --check
#   scripts/i18n-update.sh --check      vérifie sans rien écrire : .pot et .po
#                                       à jour par rapport aux sources (dates
#                                       POT-Creation-Date/PO-Revision-Date
#                                       ignorées), catalogues valides (CI)
#   scripts/i18n-update.sh --compile [DIR]
#                                       msgfmt --check puis compilation en
#                                       DIR/<locale>/LC_MESSAGES/<domaine>.mo
#                                       (défaut : lang, lu par bindtextdomain)
#
# Langues : lang/LINGUAS, nulle part ailleurs. Les nouvelles chaînes arrivent
# avec msgstr "" : aucune traduction automatique n'est insérée.
# Domaine : gcm-lang tant que le renommage (#99) n'est pas tranché ;
# GCM_I18N_DOMAIN permet de compiler sous un autre nom.
# Sources : fichiers Python suivis par git, hors tests/, tools/, scripts/ et
# des sous-projets qui gèrent leurs propres catalogues (SSH-Studio/,
# gtk-frdp/).
#
# Prérequis : gettext (apt-get install gettext / dnf install gettext).

set -euo pipefail
export LC_ALL=C.UTF-8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LANG_DIR="$ROOT/lang"
POT="$LANG_DIR/messages.pot"
DOMAIN="${GCM_I18N_DOMAIN:-gcm-lang}"
MODE="update"
DEST="$LANG_DIR"

case "${1:-}" in
    "") ;;
    --check) MODE="check" ;;
    --compile) MODE="compile"; DEST="${2:-$DEST}" ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
esac

for tool in xgettext msgmerge msgfmt msginit msgfilter; do
    command -v "$tool" >/dev/null || { echo "gettext requis ($tool introuvable)" >&2; exit 2; }
done

linguas() { sed -e 's/#.*//' -e 's/[[:space:]]//g' "$LANG_DIR/LINGUAS" | grep -v '^$'; }

# Contenu comparable : sans les dates de génération et sans les coupures de
# lignes (deux versions de gettext ne coupent pas au même endroit).
normalize() {
    grep -vE '^"(POT-Creation-Date|PO-Revision-Date):' "$1" | msgcat --no-wrap --sort-by-file - 2>/dev/null || true
}

sources() {
    (cd "$ROOT" && git ls-files '*.py' \
        | grep -vE '^(tests|tools|scripts|SSH-Studio|gtk-frdp)/' | sort -u)
}

generate_pot() {
    local out="$1"
    (cd "$ROOT" && sources | xgettext --files-from=- --output="$out" \
        --language=Python --from-code=UTF-8 \
        --keyword=_ --keyword=N_ --keyword=ngettext:1,2 --keyword=pgettext:1c,2 \
        --add-comments=TRANSLATORS: --add-location=file --sort-by-file --no-wrap \
        --package-name="GNOME Connection Manager" \
        --msgid-bugs-address="https://github.com/Mathide-Team/Gcm4/issues" \
        --copyright-holder="Mathilde Deuscher" 2>"$TMP/xgettext.log")
    # xgettext laisse CHARSET dans l'en-tête du modèle ; les .po héritent d'UTF-8.
    sed -i 's/charset=CHARSET/charset=UTF-8/' "$out"
}

merge_po() {  # $1 = .po existant, $2 = .pot, $3 = sortie
    msgmerge --quiet --add-location=file --sort-by-file --no-wrap --previous --output-file="$3" "$1" "$2"
}

same() { diff -q <(normalize "$1") <(normalize "$2") >/dev/null; }

check_all() {
    local rc=0 po loc
    for loc in $(linguas); do
        po="$LANG_DIR/$loc.po"
        if [ ! -f "$po" ]; then echo "manquant : lang/$loc.po (lancer scripts/i18n-update.sh)" >&2; rc=1; continue; fi
        # Les en-têtes Last-Translator/Language-Team laissés à leur valeur
        # par défaut ne sont que des avertissements : on ne les affiche pas.
        msgfmt --check --output-file=/dev/null "$po" 2> >(grep -v 'still has the initial default value' >&2) \
            || { echo "invalide : lang/$loc.po" >&2; rc=1; }
    done
    for po in "$LANG_DIR"/*.po; do
        [ -e "$po" ] || continue
        loc="$(basename "$po" .po)"
        linguas | grep -qx "$loc" || { echo "lang/$loc.po absent de lang/LINGUAS" >&2; rc=1; }
    done
    return $rc
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

case "$MODE" in
update)
    generate_pot "$TMP/messages.pot"
    if [ -f "$POT" ] && same "$POT" "$TMP/messages.pot"; then
        echo "lang/messages.pot inchangé"
    else
        cp "$TMP/messages.pot" "$POT"; echo "lang/messages.pot mis à jour ($(grep -c '^msgid ' "$POT") entrées)"
    fi
    for loc in $(linguas); do
        po="$LANG_DIR/$loc.po"
        if [ ! -f "$po" ]; then
            msginit --no-translator --no-wrap --locale="$loc" --input="$POT" --output-file="$po" 2>/dev/null
            sed -i 's/charset=ASCII/charset=UTF-8/' "$po"
            # msginit recopie les msgid pour l'anglais : ce seraient de fausses
            # traductions. Tout repart vide.
            msgfilter --keep-header --no-wrap --input="$po" --output-file="$po" true
            if grep -q 'nplurals=INTEGER' "$po"; then
                echo "lang/$loc.po créé : msginit ne connaît pas les pluriels de '$loc'," \
                     "renseigner l'en-tête Plural-Forms avant de relancer" >&2
                exit 1
            fi
            echo "lang/$loc.po créé"
        fi
        merge_po "$po" "$POT" "$TMP/$loc.po"
        if ! same "$po" "$TMP/$loc.po"; then
            cp "$TMP/$loc.po" "$po"; echo "lang/$loc.po mis à jour"
        fi
    done
    check_all
    ;;
check)
    rc=0
    generate_pot "$TMP/messages.pot"
    if [ ! -f "$POT" ] || ! diff -u <(normalize "$POT") <(normalize "$TMP/messages.pot") >"$TMP/pot.diff"; then
        echo "::error::lang/messages.pot n'est plus à jour avec les sources : lancer scripts/i18n-update.sh" >&2
        head -60 "$TMP/pot.diff" >&2 || true
        rc=1
    fi
    for loc in $(linguas); do
        po="$LANG_DIR/$loc.po"
        [ -f "$po" ] || continue
        merge_po "$po" "$TMP/messages.pot" "$TMP/$loc.po"
        if ! same "$po" "$TMP/$loc.po"; then
            echo "::error::lang/$loc.po n'est plus synchronisé avec messages.pot" >&2
            rc=1
        fi
    done
    check_all || rc=1
    [ $rc -eq 0 ] && echo "catalogues à jour : $(linguas | wc -l) langue(s)"
    exit $rc
    ;;
compile)
    check_all
    for loc in $(linguas); do
        mkdir -p "$DEST/$loc/LC_MESSAGES"
        msgfmt --check --output-file="$DEST/$loc/LC_MESSAGES/$DOMAIN.mo" "$LANG_DIR/$loc.po" \
            2> >(grep -v 'still has the initial default value' >&2)
    done
    echo "$(linguas | wc -l) catalogue(s) compilé(s) dans $DEST"
    ;;
esac
