"""Menu contextuel, actions, raccourcis et activation de l'arbre (#142).

- Clic droit (``Gtk.GestureClick`` bouton 3) sur une ligne ou la zone vide,
  touche Menu et Maj+F10 sur la ligne sélectionnée : ``Gtk.PopoverMenu``
  construit depuis :func:`gcm4.core.menu_arbre.sections`.
- Actions du groupe ``arbre.`` : nouvel hôte, modifier, dupliquer (dialogue
  d'hôte, #145), copier l'adresse, nouveau groupe, renommer, couleur,
  réinitialiser la couleur, supprimer (avec confirmation et décompte), tout
  déplier ou replier.
- Raccourcis de la liste : Suppr (supprimer), F2 (renommer un groupe ou
  modifier un hôte).
- Double-clic ou Entrée (``activate`` de la liste) : un groupe se déplie ou
  se replie ; un hôte déclenche ``win.connect-host`` (délégué au registre
  des plugins, #124).

Chaque modification passe par :meth:`MenuArbre.modifier` : appliquée,
enregistrée, et annulée si l'écriture échoue (rien n'est perdu ni écrit à
moitié).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from loguru import logger

from gcm4.core import menu_arbre
from gcm4.core import preferences as prefs_core
from gcm4.core.config import ConfigError
from gcm4.core.host_tree import Noeud
from gcm4.core.i18n import _
from gcm4.core.model import SEPARATEUR, Host
from gcm4.core.registre import PluginRegistry
from gcm4.ui import dialogues
from gcm4.ui.couleurs import rgba_en_hex
from gcm4.ui.host_dialog import CREATION, DUPLICATION, MODIFICATION, HostDialog

if TYPE_CHECKING:
    from gcm4.ui.host_tree import HostTree

PREFIXE = "arbre"
ACTIONS = (
    "connect",
    "add",
    "edit",
    "copy-address",
    "new-group",
    "rename-group",
    "group-color",
    "group-color-reset",
    "duplicate",
    "delete",
    "expand",
    "collapse",
)


def _dans_l_arbre(
    widget: Gtk.Widget, arbre: Gtk.Widget, x: float, y: float
) -> tuple[float, float]:
    """Point ``x, y`` de ``widget`` dans le repère de ``arbre`` (``compute_point`` ≥ 4.12)."""
    logger.trace("_dans_l_arbre")
    if hasattr(widget, "compute_point"):
        from gi.repository import Graphene

        ok, point = widget.compute_point(arbre, Graphene.Point().init(x, y))
        resultat = (point.x, point.y) if ok else (x, y)
    else:  # GTK < 4.12
        ok, px, py = widget.translate_coordinates(arbre, x, y)
        resultat = (px, py) if ok else (x, y)
    logger.trace("_dans_l_arbre: {}", resultat)
    return resultat


class MenuArbre:
    """Menu contextuel et actions d'un :class:`~gcm4.ui.host_tree.HostTree`."""

    def __init__(self, arbre: HostTree) -> None:
        """Installe actions, gestes, raccourcis et activation sur ``arbre``."""
        logger.debug("MenuArbre.__init__: entrée")
        self.arbre = arbre
        self.cible: Noeud | None = None  # ligne visée par le dernier menu
        self.dialogue: Adw.Dialog | Adw.MessageDialog | None = None  # dernier dialogue (tests)
        self.dialogue_hote: HostDialog | None = None
        self.groupe = Gio.SimpleActionGroup()
        for nom in ACTIONS:
            action = Gio.SimpleAction.new(nom, None)
            action.connect("activate", self._on_action, nom)
            self.groupe.add_action(action)
        arbre.insert_action_group(PREFIXE, self.groupe)
        self.popover = Gtk.PopoverMenu(has_arrow=False, halign=Gtk.Align.START)
        self.popover.set_parent(arbre)
        # Enfant ajouté par set_parent : GTK ne le détache pas lui-même.
        arbre.connect("destroy", lambda *_a: self.popover.unparent())

        clic = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        clic.connect("pressed", self._on_clic_droit)
        arbre.liste.add_controller(clic)
        raccourcis = Gtk.ShortcutController()
        # Déclencheurs partagés avec Préférences > Raccourcis (#148) ; Entrée
        # passe par le signal « activate » de la liste.
        rappels = {
            "Menu|<Shift>F10": self._menu_clavier,
            "Delete|KP_Delete": lambda: self._clavier("delete"),
            "F2": lambda: self._clavier("rename-group", "edit"),
        }
        for declencheur, _libelle in prefs_core.RACCOURCIS_ARBRE:
            rappel = rappels.get(declencheur)
            if rappel is None:
                continue
            raccourcis.add_shortcut(
                Gtk.Shortcut(
                    trigger=Gtk.ShortcutTrigger.parse_string(declencheur),
                    action=Gtk.CallbackAction.new(lambda *_a, r=rappel: r() or True),
                )
            )
        arbre.liste.add_controller(raccourcis)
        arbre.liste.connect("activate", self._on_activate)
        logger.debug("MenuArbre.__init__: prêt")

    def _registre(self) -> PluginRegistry:
        """Registre des plugins de la fenêtre (vide hors fenêtre principale)."""
        logger.trace("_registre: entrée")
        registre = getattr(self.arbre.get_root(), "registre", None)
        resultat = registre if isinstance(registre, PluginRegistry) else PluginRegistry()
        logger.trace("_registre: {}", resultat.protocols())
        return resultat

    # --- ouverture du menu ---------------------------------------------------

    def ouvrir(self, noeud: Noeud | None, x: float, y: float) -> None:
        """Affiche le menu de ``noeud`` (``None`` : zone vide) au point ``x, y`` de l'arbre."""
        logger.debug("ouvrir: {!r}", noeud.chemin if noeud else None)
        self.cible = noeud
        modele = Gio.Menu()
        possible = (
            noeud is not None
            and noeud.host is not None
            and noeud.host.protocol in self._registre()
        )
        for section in menu_arbre.sections(noeud, connexion_possible=possible):
            partie = Gio.Menu()
            for action in section:
                partie.append(_(menu_arbre.LIBELLES[action]), f"{PREFIXE}.{action}")
            modele.append_section(None, partie)
        self.popover.set_menu_model(modele)
        rectangle = Gdk.Rectangle()
        rectangle.x, rectangle.y, rectangle.width, rectangle.height = int(x), int(y), 1, 1
        self.popover.set_pointing_to(rectangle)
        self.popover.popup()
        logger.debug("ouvrir: {} section(s)", modele.get_n_items())

    def _on_clic_droit(self, geste: Gtk.GestureClick, _n: int, x: float, y: float) -> None:
        """Clic droit : la ligne sous le pointeur est sélectionnée, puis le menu s'ouvre."""
        logger.debug("_on_clic_droit: entrée")
        widget = self.arbre.liste.pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget is not None and not isinstance(widget, Gtk.TreeExpander):
            widget = widget.get_parent() if widget is not self.arbre.liste else None
        ligne = widget.get_list_row() if widget is not None else None
        noeud = ligne.get_item().noeud if ligne is not None else None
        if noeud is not None:
            self.arbre.selectionner(noeud.chemin)
        px, py = _dans_l_arbre(self.arbre.liste, self.arbre, x, y)
        geste.set_state(Gtk.EventSequenceState.CLAIMED)
        self.ouvrir(noeud, px, py)
        logger.debug("_on_clic_droit: fait")

    def _noeud_selectionne(self) -> Noeud | None:
        """Nœud de la ligne sélectionnée, ou ``None``."""
        logger.trace("_noeud_selectionne")
        ligne = self.arbre.selection.get_selected_item()
        resultat = ligne.get_item().noeud if ligne is not None else None
        logger.trace("_noeud_selectionne: {!r}", resultat.chemin if resultat else None)
        return resultat

    def _menu_clavier(self) -> None:
        """Touche Menu / Maj+F10 : menu de la ligne sélectionnée, ancré sur elle."""
        logger.debug("_menu_clavier: entrée")
        noeud = self._noeud_selectionne()
        x, y = 12.0, 12.0
        enfant = self.arbre.liste.get_first_child()
        ligne = self.arbre.selection.get_selected_item()
        while enfant is not None and ligne is not None:
            fleche = enfant.get_first_child()
            if isinstance(fleche, Gtk.TreeExpander) and fleche.get_list_row() is ligne:
                ok, bornes = enfant.compute_bounds(self.arbre)
                if ok:
                    x, y = bornes.get_x() + 24, bornes.get_y() + bornes.get_height()
                break
            enfant = enfant.get_next_sibling()
        self.ouvrir(noeud, x, y)
        logger.debug("_menu_clavier: fait")

    def _clavier(self, *actions: str) -> None:
        """Raccourci de la liste : première des ``actions`` qui s'applique à la sélection."""
        logger.debug("_clavier: {}", actions)
        noeud = self._noeud_selectionne()
        disponibles = {a for s in menu_arbre.sections(noeud) for a in s}
        action = next((a for a in actions if a in disponibles), None)
        if noeud is not None and action is not None:
            self.cible = noeud
            self.executer(action)
        logger.debug("_clavier: fait")

    def _on_activate(self, _liste: Gtk.ListView, position: int) -> None:
        """Double-clic / Entrée : groupe déplié ou replié, hôte connecté (``win.connect-host``)."""
        logger.debug("_on_activate: {}", position)
        modele = self.arbre.modele
        ligne = modele.get_item(position) if modele is not None else None
        if ligne is None:
            logger.debug("_on_activate: aucune ligne")
            return
        noeud = ligne.get_item().noeud
        if noeud.est_groupe:
            if ligne.is_expandable():
                ligne.set_expanded(not ligne.get_expanded())
        else:
            self.arbre.activate_action("win.connect-host", GLib.Variant.new_string(noeud.chemin))
        logger.debug("_on_activate: {!r}", noeud.chemin)

    # --- actions -------------------------------------------------------------

    def _on_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None, nom: str) -> None:
        """Entrée de menu choisie."""
        logger.debug("_on_action: {}", nom)
        self.executer(nom)
        logger.debug("_on_action: fait")

    def executer(self, nom: str) -> None:
        """Exécute l'action ``nom`` sur ``self.cible``."""
        logger.debug("executer: {} sur {!r}", nom, self.cible.chemin if self.cible else None)
        getattr(self, "_" + nom.replace("-", "_"))()
        logger.debug("executer: fait")

    def _connect(self) -> None:
        """« Connecter » : même chemin que le double-clic (``win.connect-host``)."""
        logger.debug("_connect: entrée")
        if self.cible is not None and not self.cible.est_groupe:
            self.arbre.activate_action(
                "win.connect-host", GLib.Variant.new_string(self.cible.chemin)
            )
        logger.debug("_connect: fait")

    def modifier(self, operation: Callable[[], None]) -> bool:
        """Applique ``operation`` au store, enregistre, annule si l'écriture échoue.

        Hôtes et groupes sont copiés avant : un échec rétablit exactement
        l'état précédent (le fichier, lui, n'a pas été touché).
        """
        logger.debug("modifier: entrée")
        store = self.arbre.store
        hotes, groupes = copy.deepcopy(store.hosts), copy.deepcopy(store.groups)
        operation()
        try:
            if self.arbre.enregistrer is not None:
                self.arbre.enregistrer()
        except ConfigError as exc:
            logger.warning("modifier: enregistrement impossible ({}), modification annulée", exc)
            store.hosts[:] = hotes
            store.groups.clear()
            store.groups.update(groupes)
            self.arbre.recharger()
            self.arbre._notifier(_("Changes not saved: {error}").format(error=exc))
            logger.debug("modifier: annulé")
            return False
        self.arbre.appliquer_couleurs()
        self.arbre.recharger()
        logger.debug("modifier: enregistré")
        return True

    def _copy_address(self) -> None:
        """Adresse de l'hôte dans le presse-papiers."""
        logger.debug("_copy_address: entrée")
        hote = self.arbre.store.find(self.cible.chemin) if self.cible else None
        if hote is not None:
            self.arbre.get_clipboard().set(hote.host)
            self.arbre._notifier(_("Address copied"))
        logger.debug("_copy_address: fait")

    def _add(self) -> None:
        """Nouvel hôte dans le groupe visé (dialogue d'hôte, mode création)."""
        logger.debug("_add: entrée")
        self.ouvrir_dialogue_hote(CREATION, None, menu_arbre.groupe_de_travail(self.cible))
        logger.debug("_add: fait")

    def _edit(self) -> None:
        """Modifier l'hôte visé."""
        logger.debug("_edit: entrée")
        hote = self.arbre.store.find(self.cible.chemin) if self.cible else None
        if hote is not None:
            self.ouvrir_dialogue_hote(MODIFICATION, hote)
        logger.debug("_edit: fait")

    def _duplicate(self) -> None:
        """Dupliquer l'hôte visé : dialogue prérempli « nom (2) », ajustable avant d'enregistrer."""
        logger.debug("_duplicate: entrée")
        hote = self.arbre.store.find(self.cible.chemin) if self.cible else None
        if hote is not None:
            self.ouvrir_dialogue_hote(DUPLICATION, hote)
        logger.debug("_duplicate: fait")

    def ouvrir_dialogue_hote(self, mode: str, hote: Host | None, groupe: str = "") -> HostDialog:
        """Ouvre le dialogue d'hôte ; l'enregistrement passe par :meth:`modifier`."""
        logger.debug("ouvrir_dialogue_hote: {} {!r}", mode, hote.path if hote else groupe)
        store = self.arbre.store

        def valider(nouveau: Host, original: Host | None) -> bool:
            logger.debug("ouvrir_dialogue_hote.valider: {!r}", nouveau.path)

            def operation() -> None:
                logger.debug("ouvrir_dialogue_hote.operation: entrée")
                if original is None:
                    store.add(nouveau)
                else:
                    store.replace(original, nouveau)
                self._deplier_ancetres(nouveau.group, inclus=True)
                logger.debug("ouvrir_dialogue_hote.operation: fait")

            ok = self.modifier(operation)
            if ok:
                self.arbre.selectionner(nouveau.path)
            logger.debug("ouvrir_dialogue_hote.valider: {}", ok)
            return ok

        racine = self.arbre.get_root()
        self.dialogue_hote = HostDialog(
            racine if isinstance(racine, Gtk.Window) else None,
            store,
            mode,
            valider,
            hote=hote,
            groupe=groupe,
            registre=self._registre(),
        )
        self.dialogue_hote.present()
        logger.debug("ouvrir_dialogue_hote: affiché")
        return self.dialogue_hote

    def _deplier_ancetres(self, chemin: str, inclus: bool = False) -> None:
        """Déplie les groupes parents de ``chemin`` (et ``chemin`` lui-même si ``inclus``)."""
        logger.trace("_deplier_ancetres: {!r}", chemin)
        courant = chemin if inclus else chemin.rpartition(SEPARATEUR)[0]
        while courant:
            groupe = self.arbre.store.groups.get(courant)
            if groupe is not None:
                groupe.collapsed = False
            courant = courant.rpartition(SEPARATEUR)[0]
        logger.trace("_deplier_ancetres: fait")

    def _expand(self) -> None:
        """Tout déplier (état enregistré à la fermeture, comme GTK3)."""
        logger.debug("_expand: entrée")
        for groupe in self.arbre.store.groups.values():
            groupe.collapsed = False
        self.arbre.recharger()
        logger.debug("_expand: fait")

    def _collapse(self) -> None:
        """Tout replier."""
        logger.debug("_collapse: entrée")
        for groupe in self.arbre.store.groups.values():
            groupe.collapsed = True
        self.arbre.recharger()
        logger.debug("_collapse: fait")

    def _group_color_reset(self) -> None:
        """Le groupe reprend la couleur héritée de ses ancêtres."""
        logger.debug("_group_color_reset: entrée")
        groupe = self.arbre.store.groups.get(menu_arbre.groupe_de_travail(self.cible))
        if groupe is not None and groupe.color:
            self.modifier(lambda: setattr(groupe, "color", ""))
        logger.debug("_group_color_reset: fait")

    def _group_color(self) -> None:
        """Choix de couleur (``Gtk.ColorDialog`` ≥ 4.10, sinon ``Gtk.ColorChooserDialog``)."""
        logger.debug("_group_color: entrée")
        chemin = menu_arbre.groupe_de_travail(self.cible)
        groupe = self.arbre.store.groups.get(chemin)
        if groupe is None:
            logger.debug("_group_color: pas de groupe")
            return
        initiale = Gdk.RGBA()
        if not (groupe.color and initiale.parse(groupe.color)):
            initiale.parse("#3584e4")
        racine = self.arbre.get_root()
        if hasattr(Gtk, "ColorDialog"):
            choix = Gtk.ColorDialog(title=_("Group color"), with_alpha=False)
            choix.choose_rgba(racine, initiale, None, self._on_couleur_choisie, chemin)
        else:  # GTK < 4.10
            ancien = Gtk.ColorChooserDialog(
                title=_("Group color"), transient_for=racine, modal=True
            )
            ancien.set_use_alpha(False)
            ancien.set_rgba(initiale)
            ancien.connect("response", self._on_couleur_ancienne, chemin)
            ancien.present()
        logger.debug("_group_color: dialogue ouvert pour {!r}", chemin)

    def _on_couleur_choisie(
        self, choix: Gtk.ColorDialog, resultat: Gio.AsyncResult, chemin: str
    ) -> None:
        """Fin de ``choose_rgba`` : annulation silencieuse, sinon couleur appliquée."""
        logger.debug("_on_couleur_choisie: {!r}", chemin)
        try:
            rgba = choix.choose_rgba_finish(resultat)
        except GLib.Error as exc:  # annulé par l'utilisateur
            logger.debug("_on_couleur_choisie: annulé ({})", exc.message)
            return
        self.appliquer_couleur(chemin, rgba_en_hex(rgba))
        logger.debug("_on_couleur_choisie: fait")

    def _on_couleur_ancienne(
        self, dialogue: Gtk.ColorChooserDialog, reponse: int, chemin: str
    ) -> None:
        """Réponse de ``Gtk.ColorChooserDialog`` (GTK < 4.10)."""
        logger.debug("_on_couleur_ancienne: {}", reponse)
        if reponse == Gtk.ResponseType.OK:
            self.appliquer_couleur(chemin, rgba_en_hex(dialogue.get_rgba()))
        dialogue.destroy()
        logger.debug("_on_couleur_ancienne: fait")

    def appliquer_couleur(self, chemin: str, couleur: str) -> bool:
        """Couleur ``#rrggbb`` du groupe ``chemin``, enregistrée."""
        logger.debug("appliquer_couleur: {!r} {}", chemin, couleur)
        groupe = self.arbre.store.groups.get(chemin)
        resultat = groupe is not None and self.modifier(lambda: setattr(groupe, "color", couleur))
        logger.debug("appliquer_couleur: {}", resultat)
        return resultat

    # --- dialogues -----------------------------------------------------------

    def _saisie_de_groupe(
        self, titre: str, corps: str, valider: str, parent: str, actuel: str | None
    ) -> None:
        """Dialogue de nom de groupe ; bouton actif seulement pour un nom valide."""
        logger.debug("_saisie_de_groupe: {!r} parent={!r}", titre, parent)
        entree = Gtk.Entry(activates_default=True)
        entree.update_property([Gtk.AccessibleProperty.LABEL], [_("Group name")])
        if actuel:
            entree.set_text(actuel.rpartition(SEPARATEUR)[2])

        def rappel(reponse: str) -> None:
            logger.debug("_saisie_de_groupe.rappel: {}", reponse)
            chemin = menu_arbre.chemin_de_groupe(
                self.arbre.store, parent, entree.get_text(), actuel
            )
            if reponse == "valider" and chemin is not None:
                self._enregistrer_groupe(chemin, actuel)
            logger.debug("_saisie_de_groupe.rappel: fait")

        self.dialogue = dialogues.creer(
            self.arbre,
            titre,
            corps,
            [
                ("annuler", _("Cancel"), None),
                ("valider", valider, Adw.ResponseAppearance.SUGGESTED),
            ],
            "valider",
            "annuler",
            rappel,
            extra=entree,
        )

        def verifier(_e: Gtk.Entry) -> None:
            logger.trace("_saisie_de_groupe.verifier")
            chemin = menu_arbre.chemin_de_groupe(
                self.arbre.store, parent, entree.get_text(), actuel
            )
            self.dialogue.set_response_enabled("valider", chemin is not None and chemin != actuel)
            logger.trace("_saisie_de_groupe.verifier: {!r}", chemin)

        entree.connect("changed", verifier)
        verifier(entree)
        logger.debug("_saisie_de_groupe: affiché")

    def _enregistrer_groupe(self, chemin: str, actuel: str | None) -> None:
        """Crée ``chemin`` ou y renomme ``actuel`` ; le groupe est rendu visible et sélectionné."""
        logger.debug("_enregistrer_groupe: {!r} actuel={!r}", chemin, actuel)
        store = self.arbre.store

        def operation() -> None:
            logger.debug("_enregistrer_groupe.operation: entrée")
            if actuel is None:
                store.ensure_group(chemin)
            else:
                store.rename_group(actuel, chemin)
            self._deplier_ancetres(chemin)
            logger.debug("_enregistrer_groupe.operation: fait")

        if self.modifier(operation):
            self.arbre.selectionner(chemin)
        logger.debug("_enregistrer_groupe: fait")

    def _new_group(self) -> None:
        """Nouveau groupe dans le groupe visé (ou à la racine)."""
        logger.debug("_new_group: entrée")
        parent = menu_arbre.groupe_de_travail(self.cible)
        self._saisie_de_groupe(
            _("New Group"),
            _("Parent group: {parent}").format(parent=parent or "/"),
            _("Create"),
            parent,
            None,
        )
        logger.debug("_new_group: fait")

    def _rename_group(self) -> None:
        """Renommer le groupe visé (son contenu suit)."""
        logger.debug("_rename_group: entrée")
        if self.cible is None or not self.cible.est_groupe:
            logger.debug("_rename_group: pas un groupe")
            return
        chemin = self.cible.chemin
        parent = chemin.rpartition(SEPARATEUR)[0]
        self._saisie_de_groupe(
            _("Rename Group"),
            _("Parent group: {parent}").format(parent=parent or "/"),
            _("Rename"),
            parent,
            chemin,
        )
        logger.debug("_rename_group: fait")

    def _delete(self) -> None:
        """Suppression confirmée ; pour un groupe, le dialogue annonce ce qu'il emporte."""
        logger.debug("_delete: entrée")
        noeud = self.cible
        if noeud is None:
            logger.debug("_delete: rien à supprimer")
            return
        store = self.arbre.store
        if noeud.est_groupe:
            compte = menu_arbre.decompte(store, noeud.chemin)
            titre = _("Remove group «{name}»?").format(name=noeud.nom)
            corps = (
                _("This cannot be undone.")
                if compte.vide
                else _(
                    "It contains {hosts} host(s) and {groups} subgroup(s), which will be removed too."
                ).format(hosts=compte.hotes, groups=compte.sous_groupes)
            )
        else:
            titre = _("Remove host «{name}»?").format(name=noeud.nom)
            corps = _("This cannot be undone.")

        def rappel(reponse: str) -> None:
            logger.debug("_delete.rappel: {}", reponse)
            if reponse != "supprimer":
                logger.debug("_delete.rappel: annulé")
                return
            if noeud.est_groupe:
                self.modifier(lambda: store.remove_group(noeud.chemin, avec_contenu=True))
            else:
                hote = store.find(noeud.chemin)
                if hote is not None:
                    self.modifier(lambda: store.remove(hote))
            logger.debug("_delete.rappel: fait")

        self.dialogue = dialogues.creer(
            self.arbre,
            titre,
            corps,
            [
                ("annuler", _("Cancel"), None),
                ("supprimer", _("Remove"), Adw.ResponseAppearance.DESTRUCTIVE),
            ],
            "annuler",
            "annuler",
            rappel,
        )
        logger.debug("_delete: confirmation demandée")
