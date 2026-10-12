"""Arbre des groupes et des hôtes du panneau gauche (#139).

``Gtk.TreeListModel`` + ``Gtk.ListView`` + ``Gtk.TreeExpander`` (fin de
``Gtk.TreeView``, déprécié en GTK 4.10). Une seule source de vérité : le
``HostStore`` du lot 2 ; la structure vient de
:func:`gcm4.core.host_tree.construire`.

- Couleurs de groupe : classes ``gcm-couleur-rrggbb`` sur le libellé
  (feuille chargée par ``Gcm4Application.set_group_colors``).
- Rayures : classe ``gcm-rayures`` sur la liste, sauf si
  ``disable-hosts-stripes`` (``style.css``).
- Groupes repliés : ``Group.collapsed`` suit l'état des lignes ; il est
  enregistré au format GTK3 par la fenêtre (:mod:`gcm4.core.replies`).
"""

from __future__ import annotations

from gi.repository import Gio, GObject, Gtk
from loguru import logger

from gcm4.core.host_tree import Noeud, construire, infobulle
from gcm4.core.i18n import _
from gcm4.core.model import SEPARATEUR, HostStore

ICONE_GROUPE = "folder-symbolic"
# network-workstation-symbolic est absente d'adwaita-icon-theme 50 (icône
# cassée) ; les plugins fourniront la leur (lot 6). tests/gtk4/test_arbre.py
# vérifie que ces icônes existent dans le thème.
ICONE_HOTE = "network-server-symbolic"


class ElementArbre(GObject.Object):
    """Élément du modèle : enveloppe GObject d'un :class:`~gcm4.core.host_tree.Noeud`."""

    __gtype_name__ = "Gcm4ElementArbre"

    def __init__(self, noeud: Noeud) -> None:
        """Enveloppe ``noeud``."""
        logger.trace("ElementArbre.__init__: {!r}", noeud.chemin)
        super().__init__()
        self.noeud = noeud
        logger.trace("ElementArbre.__init__: fait")


def _liste(noeuds: list[Noeud]) -> Gio.ListStore:
    """``Gio.ListStore`` d'``ElementArbre``."""
    logger.trace("_liste: {}", len(noeuds))
    liste = Gio.ListStore(item_type=ElementArbre)
    for noeud in noeuds:
        liste.append(ElementArbre(noeud))
    logger.trace("_liste: fait")
    return liste


class HostTree(Gtk.ScrolledWindow):
    """Panneau gauche : arbre des groupes et des hôtes."""

    __gtype_name__ = "Gcm4HostTree"

    def __init__(self, store: HostStore, rayures: bool = True) -> None:
        """Arbre de ``store`` ; ``rayures`` : alternance de fond des lignes."""
        logger.debug("HostTree.__init__: rayures={}", rayures)
        super().__init__(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.store = store
        fabrique = Gtk.SignalListItemFactory()
        fabrique.connect("setup", self._on_setup)
        fabrique.connect("bind", self._on_bind)
        fabrique.connect("unbind", self._on_unbind)
        self.selection = Gtk.SingleSelection(autoselect=False, can_unselect=True)
        self.liste = Gtk.ListView(model=self.selection, factory=fabrique)
        self.liste.add_css_class("gcm-arbre")
        self.liste.add_css_class("navigation-sidebar")
        if rayures:
            self.liste.add_css_class("gcm-rayures")
        self.liste.update_property([Gtk.AccessibleProperty.LABEL], [_("Hosts")])
        self.set_child(self.liste)
        self.modele: Gtk.TreeListModel | None = None
        self.recharger()
        logger.debug("HostTree.__init__: prêt")

    # --- modèle ------------------------------------------------------------

    def recharger(self) -> None:
        """Reconstruit l'arbre depuis le ``HostStore`` et restaure les groupes repliés."""
        logger.debug("recharger: entrée")
        self.modele = Gtk.TreeListModel.new(
            _liste(construire(self.store)), False, False, self._enfants
        )
        self.selection.set_model(self.modele)
        self._deplier(None)
        logger.debug("recharger: {} ligne(s) visibles", self.modele.get_n_items())

    def _enfants(self, element: ElementArbre) -> Gio.ListModel | None:
        """Enfants d'un groupe (``None`` pour un hôte ou un groupe vide : pas de flèche)."""
        logger.trace("_enfants: {!r}", element.noeud.chemin)
        noeud = element.noeud
        resultat = _liste(noeud.enfants) if noeud.est_groupe and noeud.enfants else None
        logger.trace("_enfants: {}", resultat is not None)
        return resultat

    def _deplier(self, ligne: Gtk.TreeListRow | None) -> None:
        """Déplie les groupes non repliés sous ``ligne`` (``None`` : racine)."""
        logger.trace("_deplier: entrée")
        assert self.modele is not None
        if ligne is None:
            enfants = [
                self.modele.get_child_row(i) for i in range(self.modele.get_model().get_n_items())
            ]
        else:
            enfants = [ligne.get_child_row(i) for i in range(ligne.get_children().get_n_items())]
        for enfant in enfants:
            if enfant is None:
                continue
            enfant.connect("notify::expanded", self._on_expanded)
            noeud = enfant.get_item().noeud
            groupe = self.store.groups.get(noeud.chemin) if noeud.est_groupe else None
            if groupe is not None and enfant.is_expandable() and not groupe.collapsed:
                enfant.set_expanded(True)
        logger.trace("_deplier: {} enfant(s)", len(enfants))

    def _on_expanded(self, ligne: Gtk.TreeListRow, _pspec: GObject.ParamSpec) -> None:
        """Ligne dépliée ou repliée : ``Group.collapsed`` mis à jour ; enfants restaurés."""
        logger.debug("_on_expanded: entrée")
        noeud = ligne.get_item().noeud
        parent = ligne.get_parent()
        # Ligne détachée : GTK remet profondeur et parent à zéro avant de
        # notifier ; un sous-groupe (« a/b ») sans parent est donc en cours de
        # destruction.
        detachee = SEPARATEUR in noeud.chemin and parent is None
        if not ligne.get_expanded() and (
            detachee or (parent is not None and not parent.get_expanded())
        ):
            # Ligne détruite parce que son parent se replie : l'état propre du
            # sous-groupe est conservé et sera restauré au prochain dépliage.
            logger.debug("_on_expanded: {!r} masqué par son parent, état conservé", noeud.chemin)
            return
        groupe = self.store.groups.get(noeud.chemin)
        if groupe is not None:
            groupe.collapsed = not ligne.get_expanded()
        if ligne.get_expanded():
            self._deplier(ligne)
        logger.debug("_on_expanded: {!r} replié={}", noeud.chemin, not ligne.get_expanded())

    # --- lignes ------------------------------------------------------------

    def _on_setup(self, _fabrique: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        """Widgets d'une ligne : flèche, icône, libellé."""
        logger.trace("_on_setup")
        boite = Gtk.Box(spacing=6)
        boite.append(Gtk.Image())
        boite.append(Gtk.Label(xalign=0, ellipsize=3))  # Pango.EllipsizeMode.END
        item.set_child(Gtk.TreeExpander(child=boite))
        logger.trace("_on_setup: fait")

    def _on_bind(self, _fabrique: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        """Remplit une ligne avec son nœud (texte, icône, couleur, info-bulle)."""
        logger.trace("_on_bind")
        ligne: Gtk.TreeListRow = item.get_item()
        noeud: Noeud = ligne.get_item().noeud
        fleche: Gtk.TreeExpander = item.get_child()
        fleche.set_list_row(ligne)
        boite = fleche.get_child()
        icone, libelle = boite.get_first_child(), boite.get_last_child()
        icone.set_from_icon_name(ICONE_GROUPE if noeud.est_groupe else ICONE_HOTE)
        libelle.set_text(noeud.nom)
        classe = noeud.classe_css
        if classe:
            libelle.add_css_class(classe)
        libelle.gcm_classe = classe  # retirée à l'unbind (widgets recyclés)
        if noeud.host is not None:
            boite.set_tooltip_markup(infobulle(noeud.host))
        else:
            boite.set_tooltip_markup(None)
        logger.trace("_on_bind: {!r}", noeud.chemin)

    def _on_unbind(self, _fabrique: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        """Retire la classe de couleur avant recyclage du widget."""
        logger.trace("_on_unbind")
        libelle = item.get_child().get_child().get_last_child()
        classe = getattr(libelle, "gcm_classe", None)
        if classe:
            libelle.remove_css_class(classe)
        libelle.gcm_classe = None
        logger.trace("_on_unbind: fait")

    # --- consultation (tests, lots suivants) --------------------------------

    def lignes_visibles(self) -> list[tuple[int, str]]:
        """``(profondeur, chemin)`` des lignes visibles, dans l'ordre d'affichage."""
        logger.debug("lignes_visibles: entrée")
        assert self.modele is not None
        resultat = []
        for i in range(self.modele.get_n_items()):
            ligne = self.modele.get_item(i)
            resultat.append((ligne.get_depth(), ligne.get_item().noeud.chemin))
        logger.debug("lignes_visibles: {}", len(resultat))
        return resultat

    def ligne(self, chemin: str) -> Gtk.TreeListRow | None:
        """Ligne visible de ``chemin``, ou ``None``."""
        logger.debug("ligne: {!r}", chemin)
        assert self.modele is not None
        for i in range(self.modele.get_n_items()):
            ligne = self.modele.get_item(i)
            if ligne.get_item().noeud.chemin == chemin:
                logger.debug("ligne: trouvée")
                return ligne
        logger.debug("ligne: absente")
        return None
