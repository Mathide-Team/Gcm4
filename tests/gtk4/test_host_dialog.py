"""Dialogue d'hôte sous Xvfb : création, modification, duplication, annulation (#145)."""

from __future__ import annotations

import configparser

from gi.repository import Gdk
from loguru import logger

import gcm4.ui  # noqa: F401  (require_version avant gi.repository)
from gcm4.core.chiffrement import ChiffrementGcm
from gcm4.core.config import ConfigError, load_config
from gcm4.ui.host_dialog import CREATION, DUPLICATION, MODIFICATION, HostDialog


def _relire(dossier):
    return load_config(str(dossier / "gcm4.conf"), ChiffrementGcm(str(dossier)))


def _brut(dossier):
    cp = configparser.RawConfigParser()
    cp.read(dossier / "gcm4.conf", encoding="utf-8")
    return {cp.get(s, "name"): dict(cp.items(s)) for s in cp.sections() if s.startswith("host ")}


def _ouvrir(arbre, action, chemin):
    noeud = arbre.ligne(chemin).get_item().noeud if chemin else None
    arbre.menu.cible = noeud
    arbre.menu.executer(action)
    return arbre.menu.dialogue_hote


def test_creation_dans_le_groupe_vise(app_fixture, pomper):
    """Nouvel hôte dans LAB : vierge sans message, invalide tant que nom et adresse manquent, puis écrit."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "add", "LAB/bases")
    pomper()
    assert d.mode == CREATION and d.get_title() and d.groupe.get_text() == "LAB/bases"
    assert not d.bouton_enregistrer.get_sensitive() and not d.message.get_visible()
    assert not d.enregistrer()
    d.nom.set_text("neuf")
    assert d.message.get_visible() and d.adresse.has_css_class("error")
    d.adresse.set_text("10.9.9.9")
    d.port.set_text("2200")
    d.utilisateur.set_text("root")
    d.mot_de_passe.set_text("S3cret-unique")
    assert d.bouton_enregistrer.get_sensitive() and not d.message.get_visible()
    assert d.enregistrer()
    pomper()
    assert not d.get_visible()
    h = _relire(dossier).store.find("LAB/bases/neuf")
    assert (h.host, h.port, h.user, h.password) == ("10.9.9.9", 2200, "root", "S3cret-unique")
    assert arbre.chemin_selectionne() == "LAB/bases/neuf"


def test_erreurs_sur_les_champs(app_fixture, pomper):
    """Doublon, « / », port invalide : classe error sur le champ, Enregistrer inactif."""
    app, _ = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "add", "LAB")
    d.adresse.set_text("h")
    for nom in ("web", "a/b", ""):
        d.nom.set_text(nom)
        assert d.nom.has_css_class("error") and not d.bouton_enregistrer.get_sensitive(), nom
    d.nom.set_text("libre")
    assert not d.nom.has_css_class("error")
    for port in ("abc", "0", "70000"):
        d.port.set_text(port)
        assert d.port.has_css_class("error") and "65535" in d.message.get_label(), port
        assert not d.bouton_enregistrer.get_sensitive()
    d.port.set_text("")
    assert d.bouton_enregistrer.get_sensitive()
    d.enregistre = True
    d.close()


def test_modification_garde_les_options_de_protocole(app_fixture, pomper):
    """PROD/eu/api modifié et déplacé, sans plugin : options proto-a (tunnel, x11) et mot de passe intacts."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    avant = _brut(dossier)["api"]
    mdp = _relire(dossier).store.find("PROD/eu/api").password
    rang = [h.path for h in arbre.store.hosts].index("PROD/eu/api")
    arbre.menu.executer("expand")
    pomper()
    d = _ouvrir(arbre, "edit", "PROD/eu/api")
    assert d.mode == MODIFICATION and d.nom.get_text() == "api" and d.port.get_text() == "2222"
    assert d.mot_de_passe.get_text()  # déchiffré, éditable
    assert d.protocole.get_subtitle() and d.protocole.get_sensitive()  # proto-a inconnu, conservé
    assert d.bouton_enregistrer.get_sensitive() and not d.modifie()
    d.description.set_text("Passerelle")
    d.groupe.set_text("PROD")
    assert d.enregistrer()
    pomper()
    relu = _relire(dossier)
    h = relu.store.find("PROD/api")
    assert relu.store.find("PROD/eu/api") is None
    assert arbre.store.hosts[rang].path == "PROD/api"  # même rang en mémoire
    assert h.description == "Passerelle" and h.protocol == "proto-a" and h.password == mdp
    apres = _brut(dossier)["api"]
    for cle in ("tunnel", "x11", "port", "user", "protocol"):
        assert apres[cle] == avant[cle], cle


def test_modification_nom_inchange_n_est_pas_un_doublon(app_fixture, pomper):
    """Modifier sans renommer : pas d'erreur de doublon."""
    app, _ = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "edit", "LAB/web")
    assert d.erreurs == [] and d.bouton_enregistrer.get_sensitive()
    d.nom.set_text("db")  # db est dans LAB/bases : libre dans LAB
    assert d.erreurs == []
    d.groupe.set_text("LAB/bases")
    assert d.nom.has_css_class("error")
    d.enregistre = True
    d.close()


def test_duplication_original_intact(app_fixture, pomper):
    """Dupliquer web : « web (2) » proposé, renommé « web-bis » ; l'original et ses options restent."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "duplicate", "LAB/web")
    assert d.mode == DUPLICATION and d.nom.get_text() == "web (2)"
    d.nom.set_text("web")
    assert not d.bouton_enregistrer.get_sensitive()
    d.nom.set_text("web-bis")
    assert d.enregistrer()
    pomper()
    brut = _brut(dossier)
    assert brut["web"]["resolution"] == brut["web-bis"]["resolution"] == "1280x800"
    assert brut["web-bis"]["group"] == "LAB"


def test_annulation_avec_et_sans_modification(app_fixture, pomper):
    """Sans modification : fermeture directe. Avec : confirmation ; continuer garde, abandonner ferme sans écrire."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "edit", "LAB/web")
    pomper()
    d.close()
    pomper()
    assert not d.get_visible() and d.confirmation is None
    contenu = (dossier / "gcm4.conf").read_bytes()
    d = _ouvrir(arbre, "edit", "LAB/web")
    d.description.set_text("brouillon")
    d.close()
    pomper()
    assert d.get_visible() and d.confirmation is not None
    d.confirmation.emit("response", "continuer")
    pomper()
    assert d.get_visible() and d.description.get_text() == "brouillon"
    d.close()
    pomper()
    d.confirmation.emit("response", "abandonner")
    pomper()
    assert not d.get_visible()
    assert (dossier / "gcm4.conf").read_bytes() == contenu


def test_couleurs_espace_de_travail_fermeture(app_fixture, pomper):
    """Couleurs choisies (hex), espace de travail, fermeture « Toujours », commandes : écrits."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "edit", "LAB/web")
    assert d.couleurs_par_defaut.get_active()
    d.couleurs_par_defaut.set_active(False)
    rouge = Gdk.RGBA()
    rouge.parse("#ff0000")
    d.premier_plan.set_rgba(rouge)
    d.espace_de_travail.set_active(True)
    d.fermeture.set_selected(2)
    d.avant.set_text("echo {name}")
    d.apres.set_text("logger fin")
    d.parametres.set_text("-v")
    assert d.enregistrer()
    pomper()
    h = _relire(dossier).store.find("LAB/web")
    assert (h.font_color, h.back_color) == ("#ff0000", "#000000")
    assert h.workspace and h.auto_close_tab == "1"
    assert (h.pre_connect_command, h.post_connect_command, h.extra_params) == (
        "echo {name}",
        "logger fin",
        "-v",
    )


def test_creation_sans_plugin(app_fixture, pomper):
    """Zéro plugin : protocole non modifiable en création, l'hôte s'enregistre quand même."""
    app, dossier = app_fixture
    arbre = app.get_active_window().arbre
    d = _ouvrir(arbre, "add", None)
    assert not d.protocole.get_sensitive() and d.protocole.get_subtitle()
    d.nom.set_text("racine")
    d.adresse.set_text("h")
    assert d.enregistrer()
    pomper()
    assert _relire(dossier).store.find("racine") is not None


def test_protocoles_du_registre(app_fixture, pomper):
    """Protocoles fournis par le registre : liste triée, choix enregistré dans l'hôte lu."""
    app, _ = app_fixture
    fenetre = app.get_active_window()
    retenus = []
    d = HostDialog(
        fenetre,
        fenetre.arbre.store,
        CREATION,
        lambda h, _o: retenus.append(h) or True,
        protocoles=("zeta", "alpha", ""),
    )
    assert d.protocole.get_model().get_n_items() == 2 and d.protocole.get_sensitive()
    d.protocole.set_selected(1)
    d.nom.set_text("x")
    d.adresse.set_text("h")
    assert d.enregistrer() and retenus[0].protocol == "zeta"


def test_echec_d_ecriture_garde_le_dialogue(app_fixture, pomper):
    """Écriture impossible : dialogue ouvert, saisie conservée, arbre rétabli."""
    app, _ = app_fixture
    arbre = app.get_active_window().arbre
    arbre.notifier = lambda _m: None

    def echoue():
        raise ConfigError("lecture seule")

    arbre.enregistrer = echoue
    d = _ouvrir(arbre, "edit", "LAB/web")
    d.description.set_text("perdu ?")
    assert not d.enregistrer()
    pomper()
    assert d.get_visible() and d.description.get_text() == "perdu ?"
    assert arbre.store.find("LAB/web").description == ""
    d.enregistre = True
    d.close()


def test_mot_de_passe_jamais_journalise(app_fixture, pomper):
    """Journal TRACE pendant création et modification : le mot de passe n'y figure pas."""
    app, _ = app_fixture
    arbre = app.get_active_window().arbre
    lignes = []
    sink = logger.add(lambda m: lignes.append(str(m)), level="TRACE")
    logger.enable("gcm4")
    try:
        d = _ouvrir(arbre, "add", "LAB")
        d.nom.set_text("secret")
        d.adresse.set_text("h")
        d.mot_de_passe.set_text("Mdp-Tres-Secret-42")
        assert d.enregistrer()
        pomper()
        d = _ouvrir(arbre, "edit", "LAB/secret")
        d.description.set_text("x")
        assert d.enregistrer()
        pomper()
    finally:
        logger.disable("gcm4")
        logger.remove(sink)
    assert lignes and not any("Mdp-Tres-Secret-42" in ligne for ligne in lignes)
