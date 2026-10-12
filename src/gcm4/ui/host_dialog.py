"""Dialogue d'hôte : champs communs, création, modification, duplication (#145).

``Adw.Window`` modale. Seuls les champs **communs** sont édités (inventaire :
``docs/architecture.md`` §2.10) ; l'hôte enregistré part d'une copie de
l'original, donc les options de protocole (``protocol_options``) et toute
clé inconnue sont conservées telles quelles. La zone d'options fournie par
le plugin arrive avec #146.

- Validation à chaque saisie (:func:`gcm4.core.validation.validate_host`) :
  ligne en classe CSS ``error``, message sous le formulaire, « Enregistrer »
  inactif tant qu'il reste une erreur.
- Fermeture (Échap, bouton, gestionnaire de fenêtres) avec des modifications
  non enregistrées : confirmation.
- Le mot de passe n'est jamais journalisé (``Host.password`` est hors
  ``repr`` ; seuls des chemins sont écrits dans le journal).

Compatibilité : uniquement des widgets de libadwaita ≥ 1.2 ;
``Gtk.ColorDialogButton`` (GTK ≥ 4.10) sinon ``Gtk.ColorButton``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from gi.repository import Adw, Gdk, Gtk
from loguru import logger

from gcm4.core.i18n import _
from gcm4.core.model import Host, HostStore, normaliser_chemin
from gcm4.core.validation import (
    ADRESSE,
    NOM,
    PORT,
    FieldError,
    erreur_de_port,
    lire_port,
    validate_host,
)
from gcm4.ui import dialogues
from gcm4.ui.couleurs import rgba_en_hex

CREATION, MODIFICATION, DUPLICATION = "creation", "modification", "duplication"

#: Valeurs stockées de ``auto_close_tab`` (mêmes que GTK3 ``Whost._AUTO_CLOSE_TAB_VALUES``).
FERMETURE_AUTO = ("", "0", "1", "2")

#: Couleurs proposées quand l'hôte n'en a pas (premier plan, fond).
COULEURS_PAR_DEFAUT = ("#ffffff", "#000000")

#: ``valider(nouveau, original)`` enregistre ; vrai si c'est fait (le dialogue se ferme).
Valider = Callable[[Host, Host | None], bool]


def _bouton_couleur() -> Gtk.Widget:
    """Bouton de couleur sans transparence (``ColorDialogButton`` ≥ 4.10)."""
    logger.trace("_bouton_couleur")
    if hasattr(Gtk, "ColorDialogButton"):
        bouton = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
    else:  # GTK < 4.10
        bouton = Gtk.ColorButton(use_alpha=False)
    bouton.set_valign(Gtk.Align.CENTER)
    logger.trace("_bouton_couleur: {}", type(bouton).__name__)
    return bouton


def _rgba(couleur: str, defaut: str) -> Gdk.RGBA:
    """``#rrggbb`` → ``Gdk.RGBA`` (``defaut`` si vide ou illisible)."""
    logger.trace("_rgba: {!r}", couleur)
    rgba = Gdk.RGBA()
    if not (couleur and rgba.parse(couleur)):
        rgba.parse(defaut)
    logger.trace("_rgba: fait")
    return rgba


class HostDialog(Adw.Window):
    """Création, modification ou duplication d'un hôte."""

    def __init__(
        self,
        parent: Gtk.Window | None,
        store: HostStore,
        mode: str,
        valider: Valider,
        hote: Host | None = None,
        groupe: str = "",
        protocoles: Sequence[str] = (),
    ) -> None:
        """Construit le formulaire.

        Args:
            parent: fenêtre principale (le dialogue lui est modal).
            store: hôtes et groupes (unicité du nom, liste des groupes).
            mode: :data:`CREATION`, :data:`MODIFICATION` ou :data:`DUPLICATION`.
            valider: enregistre l'hôte saisi (voir :data:`Valider`).
            hote: hôte modifié ou dupliqué (ignoré en création).
            groupe: groupe proposé en création.
            protocoles: protocoles gérés par les plugins installés (#124).
        """
        logger.debug(
            "HostDialog.__init__: {} {!r}", mode, hote.path if hote is not None else groupe
        )
        if mode not in (CREATION, MODIFICATION, DUPLICATION):
            raise ValueError(mode)
        if mode != CREATION and hote is None:
            raise ValueError(f"{mode} sans hôte")
        titres = {
            CREATION: _("New Host"),
            MODIFICATION: _("Edit Host"),
            DUPLICATION: _("Duplicate Host"),
        }
        super().__init__(
            title=titres[mode],
            modal=True,
            transient_for=parent,
            default_width=520,
            default_height=640,
        )
        self.store, self.mode, self._valider = store, mode, valider
        self.original = hote if mode == MODIFICATION else None
        if mode == CREATION:
            self.base = Host(name="", group=normaliser_chemin(groupe))
        else:
            assert hote is not None
            self.base = hote.clone()
            if mode == DUPLICATION:
                self.base.name = store.nom_de_copie(hote)
        self.enregistre = False  # vrai après l'enregistrement : fermeture sans confirmation
        self.confirmation: Adw.Dialog | Adw.MessageDialog | None = None  # tests
        self.erreurs: list[FieldError] = []
        self._construire(titres[mode], protocoles)
        self._remplir()
        self.initial = self.lire()
        self.verifier()
        self.connect("close-request", self._on_close_request)
        logger.debug("HostDialog.__init__: prêt")

    # --- construction ----------------------------------------------------------

    def _construire(self, titre: str, protocoles: Sequence[str]) -> None:
        """Barre d'en-tête, trois groupes de lignes, zone d'erreurs."""
        logger.debug("_construire: entrée")
        entete = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        entete.set_title_widget(Adw.WindowTitle(title=titre))
        annuler = Gtk.Button(label=_("Cancel"))
        annuler.connect("clicked", lambda _b: self.close())
        entete.pack_start(annuler)
        self.bouton_enregistrer = Gtk.Button(label=_("Save"))
        self.bouton_enregistrer.add_css_class("suggested-action")
        self.bouton_enregistrer.connect("clicked", lambda _b: self.enregistrer())
        entete.pack_end(self.bouton_enregistrer)

        page = Adw.PreferencesPage()
        connexion = Adw.PreferencesGroup(title=_("Connection"))
        self.nom = self._ligne(connexion, _("Name"))
        self.groupe = self._ligne(connexion, _("Group"))
        self.groupe.set_tooltip_text(_("To create subgroups use format group1/group2/group3"))
        self.groupe.add_suffix(self._liste_des_groupes())
        self.adresse = self._ligne(connexion, _("Host"))
        self.port = self._ligne(connexion, _("Port"))
        self.port.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self.utilisateur = self._ligne(connexion, _("User"))
        self.mot_de_passe = Adw.PasswordEntryRow(title=_("Password"))
        self.mot_de_passe.set_tooltip_text(
            _("Leave blank for passwordless/public key authentication")
        )
        self.mot_de_passe.connect("changed", lambda _e: self.verifier())
        connexion.add(self.mot_de_passe)
        self.protocole = Adw.ComboRow(title=_("Protocol"))
        self._protocoles = sorted({p for p in protocoles if p})
        if self.base.protocol and self.base.protocol not in self._protocoles:
            self._protocoles.append(self.base.protocol)
            self.protocole.set_subtitle(
                _("No extension handles this protocol: its options are kept.")
            )
        if not self._protocoles:
            self.protocole.set_sensitive(False)
            self.protocole.set_subtitle(_("No extension is installed."))
        self.protocole.set_model(Gtk.StringList.new(self._protocoles))
        self.protocole.connect("notify::selected", lambda *_a: self.verifier())
        connexion.add(self.protocole)
        page.add(connexion)

        affichage = Adw.PreferencesGroup(title=_("Display"))
        self.description = self._ligne(affichage, _("Description"))
        self.couleurs_par_defaut = self._interrupteur(affichage, _("Default colors"))
        self.couleurs_par_defaut.connect("notify::active", lambda *_a: self._couleurs_actives())
        self.premier_plan = _bouton_couleur()
        self.fond = _bouton_couleur()
        for titre_couleur, bouton in (
            (_("Foreground color"), self.premier_plan),
            (_("Background color"), self.fond),
        ):
            ligne = Adw.ActionRow(title=titre_couleur)
            ligne.add_suffix(bouton)
            ligne.set_activatable_widget(bouton)
            bouton.connect("notify::rgba", lambda *_a: self.verifier())
            affichage.add(ligne)
        self.espace_de_travail = self._interrupteur(
            affichage,
            _("Workspace"),
            _("Include this host in the workspace (Tools > Open Workspace)"),
        )
        self.fermeture = Adw.ComboRow(title=_("Close console"))
        self.fermeture.set_model(
            Gtk.StringList.new(
                [_("Use global preference"), _("Never"), _("Always"), _("Only on clean exit")]
            )
        )
        self.fermeture.connect("notify::selected", lambda *_a: self.verifier())
        affichage.add(self.fermeture)
        page.add(affichage)

        commandes = Adw.PreferencesGroup(title=_("Commands"))
        self.avant = self._ligne(commandes, _("Before connecting"))
        self.avant.set_tooltip_text(
            _(
                "Shell command run locally, in the background, right before this "
                "connection opens (any protocol). Leave blank to disable. "
                "Placeholders: {name} {address} {group} {protocol}"
            )
        )
        self.apres = self._ligne(commandes, _("After disconnecting"))
        self.apres.set_tooltip_text(
            _(
                "Shell command run locally, in the background, right after this "
                "connection ends, by the protocols that support it. Leave blank to "
                "disable. Placeholders: {name} {address} {group} {protocol}"
            )
        )
        self.parametres = self._ligne(commandes, _("Extra parameters"))
        page.add(commandes)

        self.message = Gtk.Label(wrap=True, xalign=0, visible=False)
        self.message.add_css_class("error")
        self.message.set_margin_start(12)
        self.message.set_margin_end(12)
        self.message.set_margin_bottom(12)
        self.message.update_property([Gtk.AccessibleProperty.LABEL], [_("Errors")])

        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boite.append(entete)
        page.set_vexpand(True)
        boite.append(page)
        boite.append(self.message)
        self.set_content(boite)

        raccourcis = Gtk.ShortcutController(scope=Gtk.ShortcutScope.MANAGED)
        raccourcis.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
                action=Gtk.CallbackAction.new(lambda *_a: self.close() or True),
            )
        )
        raccourcis.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string("<Control>s"),
                action=Gtk.CallbackAction.new(lambda *_a: self.enregistrer() or True),
            )
        )
        self.add_controller(raccourcis)
        logger.debug("_construire: fait")

    def _ligne(self, groupe: Adw.PreferencesGroup, titre: str) -> Adw.EntryRow:
        """``Adw.EntryRow`` revalidée à chaque saisie ; Entrée enregistre si c'est valide."""
        logger.trace("_ligne: {!r}", titre)
        ligne = Adw.EntryRow(title=titre)
        ligne.connect("changed", lambda _e: self.verifier())
        ligne.connect("entry-activated", lambda _e: self.enregistrer())
        groupe.add(ligne)
        logger.trace("_ligne: fait")
        return ligne

    def _interrupteur(
        self, groupe: Adw.PreferencesGroup, titre: str, sous_titre: str = ""
    ) -> Gtk.Switch:
        """Ligne avec ``Gtk.Switch`` (``Adw.SwitchRow`` exige libadwaita 1.4)."""
        logger.trace("_interrupteur: {!r}", titre)
        interrupteur = Gtk.Switch(valign=Gtk.Align.CENTER)
        ligne = Adw.ActionRow(title=titre, subtitle=sous_titre)
        ligne.add_suffix(interrupteur)
        ligne.set_activatable_widget(interrupteur)
        interrupteur.connect("notify::active", lambda *_a: self.verifier())
        groupe.add(ligne)
        logger.trace("_interrupteur: fait")
        return interrupteur

    def _liste_des_groupes(self) -> Gtk.MenuButton:
        """Bouton listant les groupes existants ; un clic remplit le champ Groupe."""
        logger.debug("_liste_des_groupes: {} groupe(s)", len(self.store.groups))
        liste = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        liste.add_css_class("navigation-sidebar")
        for chemin in sorted(self.store.groups, key=str.casefold):
            etiquette = Gtk.Label(label=chemin, xalign=0)
            etiquette.set_margin_start(6)
            etiquette.set_margin_end(6)
            liste.append(etiquette)
        defilement = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_height=True,
            max_content_height=320,
        )
        defilement.set_child(liste)
        self.popover_groupes = Gtk.Popover(child=defilement)
        bouton = Gtk.MenuButton(
            icon_name="pan-down-symbolic", valign=Gtk.Align.CENTER, popover=self.popover_groupes
        )
        bouton.add_css_class("flat")
        bouton.set_tooltip_text(_("Existing groups"))
        bouton.update_property([Gtk.AccessibleProperty.LABEL], [_("Existing groups")])
        liste.connect("row-activated", self._on_groupe_choisi)
        self.liste_groupes = liste
        logger.debug("_liste_des_groupes: fait")
        return bouton

    def _on_groupe_choisi(self, _liste: Gtk.ListBox, ligne: Gtk.ListBoxRow) -> None:
        """Groupe existant choisi dans la liste."""
        logger.debug("_on_groupe_choisi: entrée")
        etiquette = ligne.get_child()
        if isinstance(etiquette, Gtk.Label):
            self.groupe.set_text(etiquette.get_label())
        self.popover_groupes.popdown()
        logger.debug("_on_groupe_choisi: {!r}", self.groupe.get_text())

    # --- valeurs ---------------------------------------------------------------

    def _remplir(self) -> None:
        """Champs ← ``self.base``."""
        logger.debug("_remplir: entrée")
        h = self.base
        self.nom.set_text(h.name)
        self.groupe.set_text(h.group)
        self.adresse.set_text(h.host)
        self.port.set_text("" if h.port is None else str(h.port))
        self.utilisateur.set_text(h.user)
        self.mot_de_passe.set_text(h.password)
        if h.protocol in self._protocoles:
            self.protocole.set_selected(self._protocoles.index(h.protocol))
        self.description.set_text(h.description)
        defaut = not h.font_color and not h.back_color
        self.couleurs_par_defaut.set_active(defaut)
        self.premier_plan.set_rgba(_rgba(h.font_color, COULEURS_PAR_DEFAUT[0]))
        self.fond.set_rgba(_rgba(h.back_color, COULEURS_PAR_DEFAUT[1]))
        self._couleurs_actives()
        self.espace_de_travail.set_active(h.workspace)
        self.fermeture.set_selected(
            FERMETURE_AUTO.index(h.auto_close_tab) if h.auto_close_tab in FERMETURE_AUTO else 0
        )
        self.avant.set_text(h.pre_connect_command)
        self.apres.set_text(h.post_connect_command)
        self.parametres.set_text(h.extra_params)
        logger.debug("_remplir: fait")

    def _couleurs_actives(self) -> None:
        """Boutons de couleur utilisables seulement sans « couleurs par défaut »."""
        logger.trace("_couleurs_actives")
        actif = not self.couleurs_par_defaut.get_active()
        for bouton in (self.premier_plan, self.fond):
            ligne = bouton.get_ancestor(Adw.ActionRow)
            (ligne or bouton).set_sensitive(actif)
        logger.trace("_couleurs_actives: {}", actif)

    def lire(self) -> Host:
        """Hôte saisi : copie de la base (options de protocole comprises) + champs communs."""
        logger.trace("lire")
        h = self.base.clone()
        h.name = self.nom.get_text().strip()
        h.group = normaliser_chemin(self.groupe.get_text())
        h.host = self.adresse.get_text().strip()
        try:
            h.port = lire_port(self.port.get_text())
        except ValueError:
            logger.trace("lire: port non numérique (erreur affichée sur le champ)")
            h.port = None
        h.user = self.utilisateur.get_text().strip()
        h.password = self.mot_de_passe.get_text()
        choisi = self.protocole.get_selected()
        if self._protocoles and choisi != Gtk.INVALID_LIST_POSITION:
            h.protocol = self._protocoles[choisi]
        h.description = self.description.get_text().strip()
        if self.couleurs_par_defaut.get_active():
            h.font_color = h.back_color = ""
        else:
            h.font_color = rgba_en_hex(self.premier_plan.get_rgba())
            h.back_color = rgba_en_hex(self.fond.get_rgba())
        h.workspace = self.espace_de_travail.get_active()
        h.auto_close_tab = FERMETURE_AUTO[min(self.fermeture.get_selected(), 3)]
        h.pre_connect_command = self.avant.get_text().strip()
        h.post_connect_command = self.apres.get_text().strip()
        h.extra_params = self.parametres.get_text().strip()
        logger.trace("lire: {!r}", h.path)
        return h

    def modifie(self) -> bool:
        """Vrai si la saisie diffère de l'état d'ouverture."""
        logger.trace("modifie")
        resultat = self.lire() != self.initial
        logger.trace("modifie: {}", resultat)
        return resultat

    # --- validation et enregistrement -----------------------------------------

    def verifier(self) -> bool:
        """Revalide ; marque les champs en erreur ; « Enregistrer » actif si tout est valide."""
        logger.trace("verifier")
        if not hasattr(self, "initial"):
            logger.trace("verifier: remplissage initial en cours")
            return False
        hote = self.lire()
        erreurs = validate_host(hote, self.store, self.original)
        erreur_port = erreur_de_port(self.port.get_text())
        if erreur_port is not None and all(e.champ != PORT for e in erreurs):
            erreurs.append(erreur_port)
        self.erreurs = erreurs
        par_champ = {e.champ: e.message for e in erreurs}
        for champ, ligne in ((NOM, self.nom), (ADRESSE, self.adresse), (PORT, self.port)):
            if champ in par_champ:
                ligne.add_css_class("error")
                ligne.set_tooltip_text(par_champ[champ])
            else:
                ligne.remove_css_class("error")
                ligne.set_tooltip_text(None)
        # Création : pas de message avant la première saisie (formulaire vide).
        vierge = self.mode == CREATION and not self.modifie()
        self.message.set_label("\n".join(e.message for e in erreurs))
        self.message.set_visible(bool(erreurs) and not vierge)
        self.bouton_enregistrer.set_sensitive(not erreurs)
        logger.trace("verifier: {} erreur(s)", len(erreurs))
        return not erreurs

    def enregistrer(self) -> bool:
        """Enregistre si la saisie est valide ; ferme le dialogue si c'est fait."""
        logger.debug("enregistrer: {}", self.mode)
        if not self.verifier():
            logger.debug("enregistrer: saisie invalide")
            return False
        hote = self.lire()
        if not self._valider(hote, self.original):
            logger.debug("enregistrer: refusé par l'appelant")
            return False
        self.enregistre = True
        self.close()
        logger.debug("enregistrer: {!r}", hote.path)
        return True

    def _on_close_request(self, _fenetre: Adw.Window) -> bool:
        """Modifications non enregistrées : confirmation avant de fermer."""
        logger.debug("_on_close_request: entrée")
        if self.enregistre or not self.modifie():
            logger.debug("_on_close_request: fermeture")
            return False

        def rappel(reponse: str) -> None:
            logger.debug("_on_close_request.rappel: {}", reponse)
            if reponse == "abandonner":
                self.enregistre = True
                self.close()
            logger.debug("_on_close_request.rappel: fait")

        self.confirmation = dialogues.creer(
            self,
            _("Discard changes?"),
            _("The changes to this host have not been saved."),
            [
                ("continuer", _("Keep Editing"), None),
                ("abandonner", _("Discard"), Adw.ResponseAppearance.DESTRUCTIVE),
            ],
            "continuer",
            "continuer",
            rappel,
        )
        logger.debug("_on_close_request: confirmation demandée")
        return True
