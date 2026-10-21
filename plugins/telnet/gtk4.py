"""Plugin telnet de gcm4 (contrat v1, ``docs/plugins.md``) : terminal VTE GTK4.

Portage de ``plugins/plugin_telnet.py`` (GTK3, #179) ; la logique sans GTK
est dans :mod:`core` (commande, ``TERM``, commandes après connexion), testée
sans affichage. Chargé en mode source comme ``gcm4_plugin_telnet.gtk4``
(#288).

Écarts avec GTK3, voulus ou en attente de la base :

- le mot de passe passe par un tube (descripteur 3 du script expect), et
  non plus par une frappe simulée 2 s après le lancement ;
- la sortie du serveur reste visible pendant la saisie automatique ;
- police, couleurs par défaut, lignes d'historique et séparateurs de mots
  des préférences globales de GTK3 (``[options]``) ne sont pas lus : le
  contrat v1 ne donne au plugin que sa section ``[plugin telnet]``. Les
  couleurs de l'hôte (``font-color``, ``back-color``) sont appliquées.
"""

from __future__ import annotations

import os
import shutil
import signal
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")  # déjà fixé par gcm4 ; déclare le fichier GTK4 (#178)
gi.require_version("Gdk", "4.0")
gi.require_version("Vte", "3.91")

from gi.repository import Gdk, GLib, Gtk, Vte  # noqa: E402
from loguru import logger  # noqa: E402

from gcm4.core.i18n import N_, _  # noqa: E402
from gcm4.core.model import Host  # noqa: E402
from gcm4.core.plugins import ConnectionPlugin  # noqa: E402

from . import core  # noqa: E402

#: Palette Tango (16 couleurs) appliquée avec les couleurs de l'hôte, comme
#: GTK3 ; GTK3 répétait par erreur ``#729FCF`` en 14ᵉ couleur (magenta
#: clair), corrigé ici en ``#AD7FA8``.
PALETTE = (
    "#000000",
    "#CC0000",
    "#4E9A06",
    "#C4A000",
    "#3465A4",
    "#75507B",
    "#06989A",
    "#D3D7CF",
    "#555753",
    "#EF2929",
    "#8AE234",
    "#FCE94F",
    "#729FCF",
    "#AD7FA8",
    "#34E2E2",
    "#EEEEEC",
)

#: Libellés des liaisons d'effacement, dans l'ordre de ``Vte.EraseBinding``
#: (mêmes chaînes que la page « Avancé » de GTK3, déjà traduites).
LIAISONS = (
    N_("Automatic"),
    N_("ASCII Backspace \t[Ctrl+H 0x08]"),
    N_("ASCII Delete    \t[Ctrl+? 0x7F]"),
    N_("Delete Sequence \t[@7]"),
    N_("TTY Erase"),
)


def _rgba(texte: str) -> Gdk.RGBA | None:
    """``Gdk.RGBA`` de ``texte`` (``#rrggbb``…), ``None`` si illisible."""
    logger.trace("_rgba: {!r}", texte)
    couleur = Gdk.RGBA()
    resultat = couleur if texte and couleur.parse(texte) else None
    logger.trace("_rgba: {}", resultat is not None)
    return resultat


class TelnetSession:
    """Onglet telnet : un ``Vte.Terminal`` et son défilement ; ``close()`` arrête telnet."""

    def __init__(self, host: Host, lancement: core.Lancement, log) -> None:
        """Construit le terminal et lance ``lancement`` (asynchrone, rien ne bloque).

        Args:
            host: hôte ouvert (couleurs, options ``telnet``).
            lancement: commande à lancer (:func:`core.lancement`).
            log: journal du plugin.
        """
        logger.debug("TelnetSession.__init__: {!r}", host.path)
        self.log = log
        self.pid = 0
        self.fermee = False
        self.code_de_sortie: int | None = None
        #: Envois de commandes pas encore partis : rang → source GLib.
        self._minuteries: dict[int, int] = {}
        options = host.protocol_options.get("telnet", {})
        self.terminal = Vte.Terminal()
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.terminal.set_backspace_binding(
            Vte.EraseBinding(core.liaison(options, core.OPT_RETOUR_ARRIERE))
        )
        self.terminal.set_delete_binding(
            Vte.EraseBinding(core.liaison(options, core.OPT_SUPPRESSION))
        )
        avant, fond = _rgba(host.font_color), _rgba(host.back_color)
        if avant is not None and fond is not None:
            self.terminal.set_colors(avant, fond, [_rgba(c) for c in PALETTE])
        self.terminal.connect("child-exited", self._fin)
        self.widget = Gtk.ScrolledWindow(child=self.terminal)
        self.widget.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._lancer(lancement, core.environnement(options))
        commandes = core.lire_commandes(options.get(core.OPT_COMMANDES, ""))
        for rang, (delai, texte) in enumerate(core.etapes(commandes)):
            self._minuteries[rang] = GLib.timeout_add(delai, self._envoyer, rang, texte)
        logger.debug("TelnetSession.__init__: {} envoi(s) programmé(s)", len(self._minuteries))

    def _lancer(self, lancement: core.Lancement, envv: list[str]) -> None:
        """Lance la commande ; le mot de passe part dans un tube vers le descripteur 3."""
        logger.debug("TelnetSession._lancer: {!r}", lancement)
        fds: list[int] = []
        if lancement.mot_de_passe:
            lecture, ecriture = os.pipe()
            try:
                os.write(ecriture, lancement.mot_de_passe.encode("utf-8") + b"\n")
            finally:
                os.close(ecriture)
            fds = [lecture]
        # VTE prend possession des descripteurs de ``fds`` et les ferme
        # après le lancement, réussi ou non.
        self.terminal.spawn_with_fds_async(
            Vte.PtyFlags.DEFAULT,
            None,
            lancement.argv,
            envv,
            fds,
            [3] * len(fds),
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            self._lance,
        )
        logger.debug("TelnetSession._lancer: demandé")

    def _lance(self, _terminal, pid: int, erreur, *_args) -> None:
        """Fin du lancement asynchrone : garde le pid, ou affiche l'erreur dans le terminal."""
        logger.debug("TelnetSession._lance: pid={}", pid)
        if erreur is not None:
            self.log.warning("telnet: lancement impossible : {}", erreur.message)
            self.terminal.feed(f"{erreur.message}\r\n".encode())
        else:
            self.pid = pid
            if self.fermee:
                logger.debug("TelnetSession._lance: onglet déjà fermé")
                self._arreter()
        logger.debug("TelnetSession._lance: fait")

    def _envoyer(self, rang: int, texte: str) -> bool:
        """Envoie ``texte`` à telnet (commandes après connexion) ; minuterie à usage unique."""
        logger.debug("TelnetSession._envoyer: {} caractère(s)", len(texte))
        self._minuteries.pop(rang, None)
        if not self.fermee and self.code_de_sortie is None:
            self.terminal.feed_child(texte.encode("utf-8"))
        logger.debug("TelnetSession._envoyer: fait")
        return GLib.SOURCE_REMOVE

    def _fin(self, _terminal, statut: int) -> None:
        """Fin de telnet : l'onglet reste ouvert avec « Session ended »."""
        logger.debug("TelnetSession._fin: statut {}", statut)
        self.code_de_sortie = statut
        self.pid = 0
        self._oublier_minuteries()
        self.terminal.feed(("\r\n" + _("Session ended") + "\r\n").encode())
        logger.debug("TelnetSession._fin: fait")

    def _oublier_minuteries(self) -> None:
        """Annule les envois de commandes pas encore partis."""
        logger.debug("TelnetSession._oublier_minuteries: {}", len(self._minuteries))
        for source in self._minuteries.values():
            GLib.source_remove(source)
        self._minuteries.clear()
        logger.debug("TelnetSession._oublier_minuteries: fait")

    def _arreter(self) -> None:
        """Envoie SIGHUP à telnet (ou au script expect), comme à la fermeture d'un terminal."""
        logger.debug("TelnetSession._arreter: pid={}", self.pid)
        if self.pid > 0:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                logger.debug("TelnetSession._arreter: déjà terminé")
        logger.debug("TelnetSession._arreter: fait")

    def close(self) -> None:
        """Onglet fermé : envois annulés, telnet arrêté."""
        logger.debug("TelnetSession.close: entrée")
        self.fermee = True
        self._oublier_minuteries()
        self._arreter()
        logger.debug("TelnetSession.close: fait")


class TelnetPlugin(ConnectionPlugin):
    """Protocole ``telnet`` : terminal VTE, saisie automatique par expect."""

    name = "telnet"
    version = "1.0"
    protocols = ("telnet",)

    def default_port(self, protocol: str) -> int | None:
        """Port 23."""
        logger.debug("TelnetPlugin.default_port: {!r}", protocol)
        logger.debug("TelnetPlugin.default_port: {}", core.PORT_DEFAUT)
        return core.PORT_DEFAUT

    def build_host_options_widget(
        self, host: Host, options: dict[str, str], changed: Callable[[], None]
    ) -> Gtk.Widget:
        """Commandes après connexion, touches d'effacement et ``TERM`` (page « Avancé » de GTK3)."""
        logger.debug("TelnetPlugin.build_host_options_widget: {!r}", host.path)
        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        texte = core.lire_commandes(options.get(core.OPT_COMMANDES, ""))
        case = Gtk.CheckButton(label=_("Send commands after login"), active=bool(texte))
        vue = Gtk.TextView(monospace=True, sensitive=bool(texte))
        vue.get_buffer().set_text(texte)
        defilement = Gtk.ScrolledWindow(child=vue, min_content_height=80)
        defilement.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        aide = Gtk.Label(xalign=0, wrap=True)
        aide.set_markup(
            _("<span size='smaller'>Use ##D=milliseconds to add a delay.\nEx: ##D=1000</span>")
        )

        def commandes(*_args) -> None:
            """Case ou texte modifié : ``commands`` vide quand la case est décochée (GTK3)."""
            logger.debug("TelnetPlugin.build_host_options_widget.commandes: entrée")
            vue.set_sensitive(case.get_active())
            tampon = vue.get_buffer()
            brut = tampon.get_text(tampon.get_start_iter(), tampon.get_end_iter(), False)
            options[core.OPT_COMMANDES] = core.ecrire_commandes(brut) if case.get_active() else ""
            changed()
            logger.debug("TelnetPlugin.build_host_options_widget.commandes: fait")

        case.connect("toggled", commandes)
        vue.get_buffer().connect("changed", commandes)
        for enfant in (case, defilement, aide):
            boite.append(enfant)

        grille = Gtk.Grid(column_spacing=12, row_spacing=6)
        libelles = Gtk.StringList.new([_(texte_liaison) for texte_liaison in LIAISONS])
        for ligne, (cle, titre) in enumerate(
            ((core.OPT_RETOUR_ARRIERE, _("Backspace:")), (core.OPT_SUPPRESSION, _("Delete:")))
        ):
            liste = Gtk.DropDown(model=libelles, hexpand=True)
            liste.set_selected(core.liaison(options, cle))

            def choisi(widget, _param, cle=cle) -> None:
                """Liaison choisie, enregistrée en entier comme GTK3."""
                logger.debug("TelnetPlugin.build_host_options_widget.choisi: {}", cle)
                options[cle] = str(widget.get_selected())
                changed()
                logger.debug("TelnetPlugin.build_host_options_widget.choisi: fait")

            liste.connect("notify::selected", choisi)
            grille.attach(Gtk.Label(label=titre, xalign=0), 0, ligne, 1, 1)
            grille.attach(liste, 1, ligne, 1, 1)

        term = Gtk.Entry(text=options.get(core.OPT_TERM, ""), placeholder_text=core.TERM_DEFAUT)

        def saisie(*_args) -> None:
            """``TERM`` saisi."""
            logger.debug("TelnetPlugin.build_host_options_widget.saisie: entrée")
            options[core.OPT_TERM] = term.get_text().strip()
            changed()
            logger.debug("TelnetPlugin.build_host_options_widget.saisie: fait")

        term.connect("changed", saisie)
        grille.attach(Gtk.Label(label=_("TERM"), xalign=0), 0, 2, 1, 1)
        grille.attach(term, 1, 2, 1, 1)
        boite.append(grille)
        logger.debug("TelnetPlugin.build_host_options_widget: fait")
        return boite

    def open(self, host: Host) -> TelnetSession:
        """Lance telnet (ou expect) dans un terminal.

        Raises:
            FileNotFoundError: ``telnet``, ou ``expect`` pour la saisie
                automatique, est introuvable dans ``PATH``.
            ValueError: paramètres supplémentaires mal formés.
        """
        logger.debug("TelnetPlugin.open: {!r}", host.path)
        telnet = shutil.which("telnet")
        if telnet is None:
            logger.debug("TelnetPlugin.open: telnet absent")
            raise FileNotFoundError(_("{program} not found").format(program="telnet"))
        try:
            lancement = core.lancement(
                host.host,
                host.port,
                host.user,
                host.password,
                host.extra_params,
                telnet,
                shutil.which("expect"),
            )
        except FileNotFoundError as exc:
            logger.debug("TelnetPlugin.open: {} absent", exc.args[0])
            raise FileNotFoundError(_("{program} not found").format(program=exc.args[0])) from None
        session = TelnetSession(host, lancement, self.context.log)
        logger.debug("TelnetPlugin.open: session ouverte")
        return session


PLUGIN = TelnetPlugin
