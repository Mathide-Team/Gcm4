PKG_NAME    = gnome-connection-manager
PKG_VERSION = 1.3.3
PKG_MAINTAINER = "MathildeDec <mathilde.deuscher@gmail.com>"
PKG_DESCRIPTION = "Multi-protocol tabbed connection manager (SSH/RDP/VNC/SPICE/Serial)"
PKG_VENDOR  = MathildeDec
PKG_URL     = https://github.com/MathildeDec/gnome-connection-manager
PKG_ARCH    = all
PKG_ARCH_RPM = noarch
PKG_LICENSE = GPLv3
PKG_DEB     = $(PKG_NAME)_$(PKG_VERSION)_$(PKG_ARCH).deb
PKG_RPM     = $(PKG_NAME)-$(PKG_VERSION).$(PKG_ARCH_RPM).rpm
PKG_OPENSUSE = $(PKG_NAME)-opensuse-$(PKG_VERSION).$(PKG_ARCH_RPM).rpm

TMPINSTALLDIR = /tmp/$(PKG_NAME)-fpm-install

FPM_COMMON = -s dir -n $(PKG_NAME) -v $(PKG_VERSION) -C $(TMPINSTALLDIR) \
	--maintainer $(PKG_MAINTAINER) \
	--description "$$(printf '$(PKG_DESCRIPTION)')" \
	--license $(PKG_LICENSE) --vendor $(PKG_VENDOR) \
	--category net --url $(PKG_URL)

# ── Cibles principales ────────────────────────────────────────────────────────
.PHONY: all deb rpm opensuse install translate i18n-update i18n-check i18n-report test lint validate clean help

all:  test lint deb rpm opensuse translate validate

help:
	@echo "Cibles disponibles :"
	@echo "  make          → deb + rpm (défaut)"
	@echo "  make deb      → paquet .deb (Debian/Ubuntu)"
	@echo "  make rpm      → paquet .rpm (Fedora/RHEL/CentOS)"
	@echo "  make opensuse → paquet .rpm (openSUSE — dépendances zypper)"
	@echo "  make translate → compile tous les .po → .mo"
	@echo "  make i18n-update → extrait les chaînes et met à jour lang/*.po"
	@echo "  make i18n-check  → échoue si lang/messages.pot ou un .po est périmé"
	@echo "  make i18n-report → taux de traduction par langue"
	@echo "  make test     → lance la suite pytest"
	@echo "  make lint     → ruff + flake8"
	@echo "  make validate → valide .po (msgfmt) + .glade/.xml/.json"
	@echo "  make clean    → supprime les paquets et répertoires temporaires"

# ── Compilation des traductions ───────────────────────────────────────────────
translate:
	@echo "Compilation des fichiers .po → .mo (langues de lang/LINGUAS)…"
	@scripts/i18n-update.sh --compile lang

# Catalogues gettext (issue #165) : extraction + fusion, puis vérification
# sans écriture (même contrôle que la CI).
i18n-update:
	@scripts/i18n-update.sh

i18n-check:
	@scripts/i18n-update.sh --check

i18n-report:
	@uv run python scripts/i18n_report.py

# ── Installation dans un répertoire temporaire ────────────────────────────────
install: translate
	mkdir -p $(DESTDIR)/usr/share/$(PKG_NAME)
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/usr/share/doc/$(PKG_NAME)
	echo "$(PKG_NAME) ($(PKG_VERSION)) all; urgency=low" \
		> $(DESTDIR)/usr/share/doc/$(PKG_NAME)/changelog
	git log --no-merges --format="* %s" \
		>> $(DESTDIR)/usr/share/doc/$(PKG_NAME)/changelog
	gzip -9 $(DESTDIR)/usr/share/doc/$(PKG_NAME)/changelog
	cp gnome-connection-manager.desktop $(DESTDIR)/usr/share/applications/
	cp LICENSE $(DESTDIR)/usr/share/doc/$(PKG_NAME)/copyright
	cp -r lang gnome_connection_manager.py \
		icon.png pyAES.py ssh.expect urlregex.py style.css \
		$(DESTDIR)/usr/share/$(PKG_NAME)/

# ── Paquet .deb (Debian / Ubuntu) ────────────────────────────────────────────
deb:
	rm -rf $(TMPINSTALLDIR) $(PKG_DEB)
	chmod -R g-w *
	$(MAKE) install DESTDIR=$(TMPINSTALLDIR)
	fpm -t deb -p $(PKG_DEB) $(FPM_COMMON) \
		-a $(PKG_ARCH) \
		-d python3 \
		-d python3-gi \
		-d gir1.2-vte-2.91 \
		-d gir1.2-gtk-3.0 \
		-d gir1.2-gtk-vnc-2.0 \
		-d gir1.2-spiceclientgtk-3.0 \
		-d "freerdp2-x11 | freerdp3-x11" \
		-d expect \
		-d python3-paramiko \
		--after-install postinst \
		--deb-priority optional \
		usr
	@echo "\033[92mOK: $(PKG_DEB)\033[0m"

# ── Paquet .rpm (Fedora / RHEL / CentOS) ─────────────────────────────────────
rpm:
	rm -rf $(TMPINSTALLDIR) $(PKG_RPM)
	chmod -R g-w *
	$(MAKE) install DESTDIR=$(TMPINSTALLDIR)
	fpm -t rpm -p $(PKG_RPM) $(FPM_COMMON) \
		-a $(PKG_ARCH_RPM) \
		-d python3 \
		-d python3-gobject \
		-d vte291 \
		-d gtk-vnc2 \
		-d spice-gtk3 \
		-d freerdp \
		-d expect \
		-d python3-paramiko \
		--after-install postinst \
		usr
	@echo "\033[92mOK: $(PKG_RPM)\033[0m"

# ── Paquet .rpm (openSUSE / SLES) ────────────────────────────────────────────
# Les noms de paquets openSUSE diffèrent de Fedora :
#   python3-gobject → python3-gobject (identique)
#   vte291          → typelib-1_0-Vte-2.91 + libvte-2_91-0
#   expect          → expect (identique)
opensuse:
	rm -rf $(TMPINSTALLDIR) $(PKG_OPENSUSE)
	chmod -R g-w *
	$(MAKE) install DESTDIR=$(TMPINSTALLDIR)
	fpm -t rpm -p $(PKG_OPENSUSE) $(FPM_COMMON) \
		-a $(PKG_ARCH_RPM) \
		--rpm-dist "opensuse" \
		-d python3 \
		-d python3-gobject \
		-d "typelib-1_0-Vte-2.91" \
		-d "typelib-1_0-GtkVnc-2.0" \
		-d "typelib-1_0-SpiceClientGtk-3.0" \
		-d freerdp \
		-d expect \
		-d python3-paramiko \
		--after-install postinst \
		usr
	@echo "\033[92mOK: $(PKG_OPENSUSE) (openSUSE)\033[0m"

# ── Tests unitaires ───────────────────────────────────────────────────────────
test:
	python3 -m pytest tests/ -v

# ── Lint (ruff + flake8) ──────────────────────────────────────────────────────
# session-35 (2026-09-14) : la cible ne couvrait que gnome_connection_manager.py,
# gcm4_core.py et tests/ — les plugins/, models.py, netmiko_bulk_core.py,
# utils.py et widgets.py n'étaient jamais vérifiés. Élargi à tout le dépôt
# (respecte l'exclude de pyproject.toml, dont SSH-Studio/gtk-frdp, vendorisés
# et hors périmètre GCM).
# session-36 (2026-09-16) : `ruff check .` passe désormais sans aucune erreur
# (les 423 erreurs pré-existantes de tests/test_gcm.py, docstrings manquantes,
# ont été comblées). `make lint` échoue néanmoins toujours aujourd'hui, pour
# une raison distincte nouvellement découverte : flake8 n'a jamais été
# configuré pour ce dépôt (pas de .flake8/setup.cfg avant cette session) et
# tournait donc avec sa limite par défaut de 79 caractères au lieu des 99
# déclarés partout ailleurs — corrigé (.flake8 ajouté), mais 182 erreurs
# flake8 réelles restent sur gnome_connection_manager.py (97 lignes >99
# caractères + 85 constats de code légué déjà ignorés par ruff pour ce
# fichier), non corrigées cette session (hors périmètre de la demande
# « erreurs ruff », voir docs/sessions/session-36.md).
lint:
	ruff check .
	flake8 gnome_connection_manager.py

# ── Validation .po (+ .xml/.glade/.json si le dépôt en contient un jour) ─────
# session-30 (2026-09-10) : cette cible appelait tools/validate_xml_json.py
# sur gnome-connection-manager.glade, fichier absent du dépôt depuis la
# suppression de tout .glade/.ui (session-08, cf. CLAUDE.md) — `make validate`
# et donc `make check` échouaient silencieusement à chaque exécution
# (`[Errno 2] No such file or directory`), sans rapport avec les 423 erreurs
# ruff pré-existantes déjà documentées pour `make lint`. Corrigé en retirant
# l'appel obsolète ; tools/validate_xml_json.py reste disponible tel quel
# (générique .xml/.glade/.json) pour un futur fichier de ce type, il suffira
# de l'invoquer de nouveau ici. Voir docs/gcm4-rename.md.
validate:
	@echo "Validation des fichiers .po…"
	@python3 tools/validate_po.py lang/*.po && echo "\033[92m  .po OK\033[0m"

# ── Nettoyage ─────────────────────────────────────────────────────────────────
clean:
	rm -rf $(TMPINSTALLDIR)
	rm -f $(PKG_DEB) $(PKG_RPM)
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── Aide au développeur ───────────────────────────────────────────────────────
check-gitignore:
	@if [ -n "$$(git status -uno -s)" ]; then \
		echo "ERROR: des fichiers trackés ont des modifications non commitées" >&2; \
		git status -uno -s; \
		exit 1; \
	fi

check: validate lint test check-gitignore
