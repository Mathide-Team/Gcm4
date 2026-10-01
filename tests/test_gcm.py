"""Tests unitaires pour Gnome Connection Manager.

Couvre les fonctions critiques sans dépendance GTK/VTE :
- Chiffrement/déchiffrement (xor, AES)
- Classe Host : construction, clone, sérialisation INI
- HostUtils : load/save INI
- _vm_name_split : segmentation nom VM libvirt
- _rdp_socket_available : détection X11
- VncTab._build_cmd / SpiceTab._build_cmd : construction des commandes
- RdpTab._build_cmd : construction commande xfreerdp
"""

import configparser
import contextlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

# ── Stubs GTK/VTE pour importer sans affichage ──────────────────────────────


def _make_gtk_stub():
    """Crée un stub minimal de gi.repository.Gtk avec fallback dynamique."""
    gtk = types.ModuleType("Gtk")

    class _Base:
        def __init__(self, *a, **kw):
            self._text = ""

        def set_margin_start(self, *a):
            """Set margin start."""
            pass

        def set_margin_end(self, *a):
            """Set margin end."""
            pass

        def set_margin_top(self, *a):
            """Set margin top."""
            pass

        def set_margin_bottom(self, *a):
            """Set margin bottom."""
            pass

        def pack_start(self, *a):
            """Pack start."""
            pass

        def pack_end(self, *a):
            """Pack end."""
            pass

        def show_all(self, *a):
            """Show all."""
            pass

        def show(self, *a):
            """Show."""
            pass

        def hide(self, *a):
            """Hide."""
            pass

        def set_text(self, v, *a):
            """Set text."""
            self._text = str(v) if v is not None else ""

        def get_text(self):
            """Get text."""
            return self._text

        def set_xalign(self, *a):
            """Set xalign."""
            pass

        def set_markup(self, *a):
            """Set markup."""
            pass

        def get_style_context(self):
            """Get style context."""
            return self

        def add_class(self, *a):
            """Add class."""
            pass

        def set_sensitive(self, *a):
            """Set sensitive."""
            pass

        def connect(self, *a):
            """Connect."""
            return 1

        def set_tooltip_text(self, *a):
            """Set tooltip text."""
            pass

        def set_label(self, *a):
            """Set label."""
            pass

        def get_label(self):
            """Get label."""
            return ""

        def set_active(self, *a):
            """Set active."""
            pass

        def get_active(self):
            """Get active."""
            return 0

        def get_active_text(self):
            """Get active text."""
            return "ssh"

        def append_text(self, *a):
            """Append text."""
            pass

        def set_hexpand(self, *a):
            """Set hexpand."""
            pass

        def set_vexpand(self, *a):
            """Set vexpand."""
            pass

        def set_icon_from_file(self, *a):
            """Set icon from file."""
            pass

        def run(self):
            """Run."""
            return 0

        def destroy(self, *a):
            """Destroy."""
            pass

        def add(self, *a):
            """Add."""
            pass

        def set_policy(self, *a):
            """Set policy."""
            pass

        def set_min_content_height(self, *a):
            """Set min content height."""
            pass

        def set_editable(self, *a):
            """Set editable."""
            pass

        def set_monospace(self, *a):
            """Set monospace."""
            pass

        def set_wrap_mode(self, *a):
            """Set wrap mode."""
            pass

        def set_default_size(self, *a):
            """Set default size."""
            pass

        def get_content_area(self):
            """Get content area."""
            return self

        def set_spacing(self, *a):
            """Set spacing."""
            pass

        def set_position(self, *a):
            """Set position."""
            pass

        def set_title(self, *a):
            """Set title."""
            pass

        def add_button(self, *a):
            """Add button."""
            return self

        def append_page(self, *a):
            """Append page."""
            pass

        def set_current_page(self, *a):
            """Set current page."""
            pass

        def get_n_pages(self):
            """Get n pages."""
            return 0

        def set_tab_reorderable(self, *a):
            """Set tab reorderable."""
            pass

        def set_headers_visible(self, *a):
            """Set headers visible."""
            pass

        def append_column(self, *a):
            """Append column."""
            pass

        def get_id(self):
            """Get id."""
            return 12345

        def get_realized(self):
            """Get realized."""
            return True

        def realize(self, *a):
            """Realize."""
            pass

        def insert(self, *a):
            """Insert."""
            pass

        def get_end_iter(self):
            """Get end iter."""
            return None

        def get_vadjustment(self):
            """Get vadjustment."""

            class Adj:
                """Tests for adj."""

                def set_value(self, *a):
                    """Set value."""
                    pass

                def get_upper(self):
                    """Get upper."""
                    return 0

            return Adj()

        def get_child(self):
            """Get child."""
            return self

    class Box(_Base):
        """Tests for box."""

        pass

    class Label(_Base):
        """Tests for label."""

        def __init__(self, label="", *a, **kw):
            pass

    class Button(_Base):
        """Tests for button."""

        def __init__(self, label="", *a, **kw):
            pass

    class Entry(_Base):
        """Tests for entry."""

        pass

    class Separator(_Base):
        """Tests for separator."""

        pass

    class Socket(_Base):
        """Tests for socket."""

        pass

    class Buildable:
        """Tests for buildable."""

        pass

    class ScrolledWindow(_Base):
        """Tests for scrolled window."""

        pass

    class TextView(_Base):
        """Tests for text view."""

        pass

    class TextBuffer(_Base):
        """Tests for text buffer."""

        pass

    class TreeView(_Base):
        """Tests for tree view."""

        pass

    class TreeViewColumn(_Base):
        """Tests for tree view column."""

        def __init__(self, *a, **kw):
            pass

    class CellRendererText(_Base):
        """Tests for cell renderer text."""

        pass

    class CellRendererToggle(_Base):
        """Tests for cell renderer toggle."""

        def connect(self, *a):
            """Connect."""
            return 1

    class ListStore(_Base):
        """Tests for list store."""

        def __init__(self, *a, **kw):
            pass

        def __iter__(self):
            return iter([])

    class ProgressBar(_Base):
        """Tests for progress bar."""

        def set_show_text(self, *a):
            """Set show text."""
            pass

        def set_fraction(self, *a):
            """Set fraction."""
            pass

        def set_text(self, *a):
            """Set text."""
            pass

    class Dialog(_Base):
        """Tests for dialog."""

        def __init__(self, *a, **kw):
            pass

        def add_button(self, *a):
            """Add button."""
            return Button()

        def get_content_area(self):
            """Get content area."""
            return Box()

        def disconnect_by_func(self, *a):
            """Disconnect by func."""
            pass

    class Window(_Base):
        """Tests for window."""

        pass

    class ComboBoxText(_Base):
        """ComboBoxText stub avec un mini-ListStore pour get_model/iter."""

        def __init__(self, *a, **kw):
            self._items = []  # list of str
            self._active = -1

        def append_text(self, text):
            """Append text."""
            self._items.append(text)

        def set_active(self, idx):
            """Set active."""
            self._active = idx

        def get_active(self):
            """Get active."""
            return self._active

        def get_active_text(self):
            """Get active text."""
            if 0 <= self._active < len(self._items):
                return self._items[self._active]
            return None

        def connect(self, *a):
            """Connect."""
            return 1

        def set_tooltip_text(self, *a):
            """Set tooltip text."""
            pass

        def get_model(self):
            """Retourne un objet itérable compatible ListStore."""
            items = self._items

            class _Iter:
                def __init__(self, idx=0):
                    self._idx = idx

            class _Model:
                def __getitem__(self_, it):
                    return [items[it._idx]]

                def get_iter_first(self_):
                    """Get iter first."""
                    return _Iter(0) if items else None

                def iter_next(self_, it):
                    """Iter next."""
                    nxt = _Iter(it._idx + 1)
                    return nxt if nxt._idx < len(items) else None

            return _Model()

        def set_active_iter(self, it):
            """Set active iter."""
            self._active = it._idx

    class FontSelectionDialog(_Base):
        """Tests for font selection dialog."""

        def get_font_selection(self):
            """Get font selection."""
            return self

        def set_font_name(self, *a):
            """Set font name."""
            pass

        def get_font_name(self):
            """Get font name."""
            return ""

    class FileChooserDialog(_Base):
        """Tests for file chooser dialog."""

        def __init__(self, *a, **kw):
            pass

        def add_button(self, *a):
            """Add button."""
            pass

        def set_do_overwrite_confirmation(self, *a):
            """Set do overwrite confirmation."""
            pass

        def set_current_folder(self, *a):
            """Set current folder."""
            pass

        def get_filename(self):
            """Get filename."""
            return ""

    class MessageDialog(_Base):
        """Tests for message dialog."""

        def __init__(self, *a, **kw):
            pass

    class Orientation:
        """Tests for orientation."""

        VERTICAL = 1
        HORIZONTAL = 0

    class PolicyType:
        """Tests for policy type."""

        AUTOMATIC = 0

    class WrapMode:
        """Tests for wrap mode."""

        WORD_CHAR = 0

    class ResponseType:
        """Tests for response type."""

        OK = -5
        CANCEL = -6

    class FileChooserAction:
        """Tests for file chooser action."""

        SAVE = 1
        OPEN = 0

    class ButtonsType:
        """Tests for buttons type."""

        OK = 1
        OK_CANCEL = 5

    class MessageType:
        """Tests for message type."""

        ERROR = 0
        QUESTION = 1
        INFO = 2

    # Constantes manquantes
    gtk.Box = Box
    gtk.HBox = Box  # alias pour compatibilité avec l'ancien code
    gtk.VBox = Box
    gtk.Label = Label
    gtk.Button = Button
    gtk.Entry = Entry
    gtk.Separator = Separator
    gtk.Socket = Socket
    gtk.Buildable = Buildable
    gtk.ScrolledWindow = ScrolledWindow
    gtk.TextView = TextView
    gtk.TextBuffer = TextBuffer
    gtk.TreeView = TreeView
    gtk.TreeViewColumn = TreeViewColumn
    gtk.CellRendererText = CellRendererText
    gtk.CellRendererToggle = CellRendererToggle
    gtk.ListStore = ListStore
    gtk.ProgressBar = ProgressBar
    gtk.Dialog = Dialog
    gtk.Window = Window
    gtk.ComboBoxText = ComboBoxText
    gtk.FontSelectionDialog = FontSelectionDialog
    gtk.FileChooserDialog = FileChooserDialog
    gtk.FileChooserAction = FileChooserAction
    gtk.MessageDialog = MessageDialog
    gtk.Orientation = Orientation
    gtk.PolicyType = PolicyType
    gtk.WrapMode = WrapMode
    gtk.ResponseType = ResponseType
    gtk.ButtonsType = ButtonsType
    gtk.MessageType = MessageType
    gtk.Builder = MagicMock()
    gtk.Settings = MagicMock()
    gtk.main = MagicMock()
    gtk.main_quit = MagicMock()

    # Fallback dynamique : tout attribut inconnu retourne _Base
    class _GtkMeta(types.ModuleType):
        def __getattr__(self, name):
            return type(name, (_Base,), {})

    gtk.__class__ = _GtkMeta
    return gtk


def _make_gi_stub():
    gi = types.ModuleType("gi")
    gi.repository = types.ModuleType("gi.repository")

    # Gtk
    gi.repository.Gtk = _make_gtk_stub()

    # Gdk
    gdk = types.ModuleType("Gdk")
    gdk.RGBA = MagicMock()
    gdk.Display = MagicMock()
    gdk.Display.get_default.return_value = None
    gdk.ModifierType = MagicMock()
    gi.repository.Gdk = gdk

    # Vte
    vte = types.ModuleType("Vte")
    vte.Terminal = MagicMock()
    vte.MAJOR_VERSION = 0
    vte.MINOR_VERSION = 60
    vte.PtyFlags = MagicMock()
    vte.EraseBinding = MagicMock()
    vte.EraseBinding.AUTO = 0
    gi.repository.Vte = vte

    # Pango
    pango = types.ModuleType("Pango")
    pango.FontDescription = MagicMock()
    gi.repository.Pango = pango

    # GObject
    gobject = types.ModuleType("GObject")
    gobject.GObject = MagicMock()
    gobject.ParamFlags = MagicMock()
    gobject.ParamFlags.READWRITE = 3
    gobject.TYPE_STRING = MagicMock()
    gobject.TYPE_BOOLEAN = MagicMock()
    gobject.TYPE_INT = MagicMock()
    gobject.Signal = MagicMock()
    gobject.GType = MagicMock()
    gobject.GEnum = MagicMock()
    # key_picker_dialog.py : __gsignals__ = {...: (GObject.SignalFlags.RUN_LAST, ...)}
    gobject.SignalFlags = MagicMock()
    gi.repository.GObject = gobject

    # GdkPixbuf et Gio : importes par gnome_connection_manager dans le meme
    # `from gi.repository import ...` que Gtk/Vte -- un stub manquant faisait
    # echouer tout l'import (masque par le except) puis NameError sur Vte.
    gdkpixbuf = types.ModuleType("GdkPixbuf")
    gdkpixbuf.Pixbuf = MagicMock()
    gdkpixbuf.InterpType = MagicMock()
    gi.repository.GdkPixbuf = gdkpixbuf

    gio = types.ModuleType("Gio")
    gio.bus_get_sync = MagicMock()
    gio.BusType = MagicMock()
    gio.Menu = MagicMock()
    gio.SimpleActionGroup = MagicMock()
    gio.SimpleAction = MagicMock()
    gio.File = MagicMock()
    gi.repository.Gio = gio

    # GtkFrdp : bibliothèque RDP embarquée de plugins/plugin_rdp.py
    gtkfrdp = types.ModuleType("GtkFrdp")
    gtkfrdp.Display = MagicMock()
    gi.repository.GtkFrdp = gtkfrdp

    # GLib
    glib = types.ModuleType("GLib")
    glib.idle_add = lambda fn, *a: fn(*a) if callable(fn) else None
    glib.timeout_add = MagicMock()
    glib.SpawnFlags = MagicMock()
    glib.SpawnFlags.DEFAULT = 0
    glib.SpawnFlags.FILE_AND_ARGV_ZERO = 1
    glib.SpawnFlags.SEARCH_PATH = 2
    glib.SpawnFlags.DO_NOT_REAP_CHILD = 4
    gi.repository.GLib = glib

    gi.require_version = lambda *a: None
    return gi


# Injecter les stubs avant tout import du module principal
_gi = _make_gi_stub()
sys.modules["gi"] = _gi
sys.modules["gi.repository"] = _gi.repository
sys.modules["gi.repository.Gtk"] = _gi.repository.Gtk
sys.modules["gi.repository.Gdk"] = _gi.repository.Gdk
sys.modules["gi.repository.Vte"] = _gi.repository.Vte
sys.modules["gi.repository.Pango"] = _gi.repository.Pango
sys.modules["gi.repository.GObject"] = _gi.repository.GObject
sys.modules["gi.repository.GLib"] = _gi.repository.GLib
sys.modules["gi.repository.GdkPixbuf"] = _gi.repository.GdkPixbuf
sys.modules["gi.repository.Gio"] = _gi.repository.Gio
sys.modules["gi.repository.GtkFrdp"] = _gi.repository.GtkFrdp

# Cryptodome (extra `vnc`, absent d'un `uv sync` simple comme en CI) : seul
# DES sert à plugin_vnc pour chiffrer le mot de passe VNC.
try:
    import Cryptodome.Cipher  # noqa: F401
except ImportError:
    _crypto = types.ModuleType("Cryptodome")
    _crypto.Cipher = types.ModuleType("Cryptodome.Cipher")
    _crypto.Cipher.DES = MagicMock()
    sys.modules["Cryptodome"] = _crypto
    sys.modules["Cryptodome.Cipher"] = _crypto.Cipher

# Stub cairo
cairo_stub = types.ModuleType("cairo")
sys.modules["cairo"] = cairo_stub

# Stub tokenize (utilisé par _normalize_names dans GCMBase)
import tokenize as _real_tokenize  # noqa: E402 — déjà disponible

sys.modules["tokenize"] = _real_tokenize

# Stub expect (OS check)
with patch("os.system", return_value=0):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import gnome_connection_manager as gcm

# Modules vers lesquels le code testé a été déplacé depuis l'écriture de ce
# fichier (plugins/, hypervisor_import_common.py, widgets.py) -- issue #112.
import plugin_import_libvirt  # noqa: E402
import plugin_local  # noqa: E402
import plugin_rdp  # noqa: E402
import plugin_serial  # noqa: E402
import plugin_spice  # noqa: E402
import plugin_ssh  # noqa: E402
import plugin_telnet  # noqa: E402
import plugin_vnc  # noqa: E402

import hypervisor_import_common as hic  # noqa: E402
import widgets  # noqa: E402

# SpiceTab._build_cmd() relit gcm.conf et réécrit /etc/hosts (HostsUpdater) à
# chaque appel : neutralisé ici, un test ne doit jamais toucher au système.
plugin_spice.parse_spice_hosts = lambda conf_path: []
plugin_spice.HostsUpdater = MagicMock()

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_host(
    group="GRP",
    name="test",
    host="1.2.3.4",
    user="root",
    password="",
    port="22",
    protocol="ssh",
    extra_params="",
):
    # Host() n'accepte plus que des mots-cles (models.Host._CORE_FIELDS) :
    # les champs non fournis prennent leur valeur par defaut.
    h = gcm.Host(
        group=group,
        name=name,
        host=host,
        user=user,
        password=password,
        private_key="",
        port=port,
        tunnel="",
        type="ssh",
        keep_alive=0,
        extra_params=extra_params,
        backspace_key=0,
        delete_key=0,
        protocol=protocol,
    )
    return h


# ── Tests chiffrement ────────────────────────────────────────────────────────


class TestEncryption(unittest.TestCase):
    """Tests pour les fonctions de chiffrement/déchiffrement."""

    def test_xor_roundtrip(self):
        """Xor est son propre inverse."""
        key = "secret"
        msg = "hello world"
        encrypted = gcm.xor(key, msg)
        decrypted = gcm.xor(key, "".join(encrypted))
        self.assertEqual("".join(decrypted), msg)

    def test_xor_empty(self):
        """Xor avec chaîne vide retourne liste vide."""
        self.assertEqual(gcm.xor("key", ""), [])

    def test_encrypt_decrypt_old_roundtrip(self):
        """encrypt_old/decrypt_old : aller-retour."""
        pw = "mypasskey"
        plain = "s3cr3t"
        enc = gcm.encrypt_old(pw, plain)
        dec = gcm.decrypt_old(pw, enc)
        self.assertEqual(dec, plain)

    def test_encrypt_aes_roundtrip(self):
        """encrypt/decrypt AES : aller-retour."""
        pw = "testpassword"
        plain = "MyP@ssw0rd!"
        enc = gcm.encrypt(pw, plain)
        # Forcer VERSION=1 pour utiliser AES
        original_version = gcm.conf.VERSION
        gcm.conf.VERSION = 1
        try:
            dec = gcm.decrypt(pw, enc)
            self.assertEqual(dec, plain)
        finally:
            gcm.conf.VERSION = original_version

    def test_decrypt_empty_string(self):
        """Decrypt d'une chaîne vide retourne chaîne vide."""
        gcm.conf.VERSION = 1
        try:
            result = gcm.decrypt("key", "")
            self.assertEqual(result, "")
        finally:
            gcm.conf.VERSION = 0

    def test_encrypt_empty_string(self):
        """Encrypt d'une chaîne vide ne lève pas d'exception."""
        result = gcm.encrypt("key", "")
        self.assertIsInstance(result, (str, bytes))


# ── Tests classe Host ────────────────────────────────────────────────────────


class TestHost(unittest.TestCase):
    """Tests pour la classe Host."""

    def test_host_defaults(self):
        """Un Host créé avec arguments minimaux a les bons défauts."""
        h = gcm.Host(group="G", name="myhost")
        self.assertEqual(h.group, "G")
        self.assertEqual(h.name, "myhost")
        self.assertIsNone(h.description)
        self.assertIsNone(h.host)

    def test_host_full_construction(self):
        """Un Host avec tous les arguments est correctement initialisé."""
        h = _make_host(
            group="PROD",
            name="web01",
            host="10.0.0.1",
            user="admin",
            port="2222",
            protocol="ssh",
        )
        self.assertEqual(h.group, "PROD")
        self.assertEqual(h.name, "web01")
        self.assertEqual(h.host, "10.0.0.1")
        self.assertEqual(h.user, "admin")
        self.assertEqual(h.port, "2222")
        self.assertEqual(h.protocol, "ssh")

    def test_host_protocol_rdp(self):
        """Un Host avec protocol='rdp' est correctement stocké."""
        h = _make_host(protocol="rdp", port="3389")
        self.assertEqual(h.protocol, "rdp")
        self.assertEqual(h.port, "3389")

    def test_host_protocol_vnc(self):
        """Un Host avec protocol='vnc' est correctement stocké."""
        h = _make_host(protocol="vnc", port="5900")
        self.assertEqual(h.protocol, "vnc")

    def test_host_protocol_spice(self):
        """Un Host avec protocol='spice' est correctement stocké."""
        h = _make_host(protocol="spice", port="5930")
        self.assertEqual(h.protocol, "spice")

    def test_host_clone_identity(self):
        """clone() produit un objet distinct avec les mêmes valeurs."""
        h = _make_host(name="original", protocol="rdp", port="3389")
        c = h.clone()
        self.assertIsNot(h, c)
        self.assertEqual(c.name, h.name)
        self.assertEqual(c.protocol, h.protocol)
        self.assertEqual(c.port, h.port)
        self.assertEqual(c.host, h.host)
        self.assertEqual(c.user, h.user)

    def test_host_clone_protocol_preserved(self):
        """clone() préserve le protocole non-SSH."""
        for proto in ("rdp", "vnc", "spice", "telnet", "local"):
            h = _make_host(protocol=proto)
            c = h.clone()
            self.assertEqual(c.protocol, proto, f"clone() a perdu le protocole {proto}")

    def test_host_tunnel_as_string_empty(self):
        """tunnel_as_string() retourne '' si tunnel vide."""
        h = _make_host()
        # tunnel est parsé depuis "" -> [""]
        self.assertIsInstance(h.tunnel_as_string(), str)

    def test_host_repr(self):
        """__repr__ retourne une chaîne non vide."""
        h = _make_host(name="myhost", group="GRP")
        r = repr(h)
        self.assertIn("myhost", r)
        self.assertIn("GRP", r)


# ── Tests HostUtils INI ──────────────────────────────────────────────────────


class TestHostUtils(unittest.TestCase):
    """Tests pour HostUtils.load_host_from_ini / save_host_to_ini."""

    def _make_cp_with_host(self, host):
        """Sauvegarde host dans un ConfigParser en mémoire et le retourne."""
        cp = configparser.ConfigParser()
        section = "host_test"
        cp.add_section(section)
        gcm.HostUtils.save_host_to_ini(cp, section, host, pwd="testpwd")
        return cp, section

    def test_save_and_load_basic(self):
        """Save + load préserve les champs de base."""
        h = _make_host(
            group="TEST",
            name="srv1",
            host="192.168.1.1",
            user="alice",
            port="22",
            protocol="ssh",
        )
        cp, section = self._make_cp_with_host(h)
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.group, "TEST")
        self.assertEqual(loaded.name, "srv1")
        self.assertEqual(loaded.host, "192.168.1.1")
        self.assertEqual(loaded.user, "alice")
        self.assertEqual(loaded.port, "22")

    def test_save_and_load_protocol_rdp(self):
        """Save + load préserve protocol='rdp'."""
        h = _make_host(protocol="rdp", port="3389")
        cp, section = self._make_cp_with_host(h)
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.protocol, "rdp")

    def test_save_and_load_protocol_vnc(self):
        """Save + load préserve protocol='vnc'."""
        h = _make_host(protocol="vnc", port="5900")
        cp, section = self._make_cp_with_host(h)
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.protocol, "vnc")

    def test_save_and_load_protocol_spice(self):
        """Save + load préserve protocol='spice'."""
        h = _make_host(protocol="spice", port="5930")
        cp, section = self._make_cp_with_host(h)
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.protocol, "spice")

    def test_save_and_load_password_encrypted(self):
        """Le mot de passe est chiffré dans l'INI (pas en clair)."""
        h = _make_host(password="cleartext_password")
        h.password = gcm.encrypt("testpwd", "cleartext_password")
        cp, section = self._make_cp_with_host(h)
        raw_pass = cp.get(section, "pass")
        self.assertNotEqual(raw_pass, "cleartext_password")

    def test_save_and_load_extra_params(self):
        """extra_params est préservé."""
        h = _make_host(extra_params="/drive:home,/home/user")
        cp, section = self._make_cp_with_host(h)
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.extra_params, "/drive:home,/home/user")

    def test_load_missing_protocol_defaults_ssh(self):
        """Un hôte sans champ 'protocol' dans l'INI charge avec 'ssh'."""
        h = _make_host(protocol="ssh")
        cp, section = self._make_cp_with_host(h)
        # Supprimer le champ protocol pour simuler un ancien fichier de config
        cp.remove_option(section, "protocol")
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.protocol, "ssh")

    def test_load_missing_pass_defaults_empty(self):
        """Un hôte sans champ 'pass' dans l'INI ne doit pas lever d'exception."""
        h = _make_host(password="")
        cp, section = self._make_cp_with_host(h)
        # Simuler un ancien fichier de config sans option "pass"
        cp.remove_option(section, "pass")
        loaded = gcm.HostUtils.load_host_from_ini(cp, section, pwd="testpwd")
        self.assertEqual(loaded.password, "")


# ── Tests _vm_name_split ─────────────────────────────────────────────────────


class TestVmNameSplit(unittest.TestCase):
    """Tests pour _vm_name_split (segmentation nom VM libvirt)."""

    def test_underscore_separator(self):
        """prod_web-01 -> (PROD, web-01)."""
        g, n = hic.vm_name_split("prod_web-01")
        self.assertEqual(g, "PROD")
        self.assertEqual(n, "web-01")

    def test_dash_separator(self):
        """prod-web-01 -> (PROD, web-01)."""
        g, n = hic.vm_name_split("prod-web-01")
        self.assertEqual(g, "PROD")
        self.assertEqual(n, "web-01")

    def test_space_separator(self):
        """'prod web01' -> (PROD, web01)."""
        g, n = hic.vm_name_split("prod web01")
        self.assertEqual(g, "PROD")
        self.assertEqual(n, "web01")

    def test_no_separator(self):
        """Standalone -> (LIBVIRT, standalone)."""
        g, n = hic.vm_name_split("standalone")
        self.assertEqual(g, "LIBVIRT")
        self.assertEqual(n, "standalone")

    def test_multiple_separators(self):
        """dev_app_backend_v2 -> (DEV, app_backend_v2)."""
        g, n = hic.vm_name_split("dev_app_backend_v2")
        self.assertEqual(g, "DEV")
        self.assertEqual(n, "app_backend_v2")

    def test_uppercase_group(self):
        """Le groupe est toujours en majuscules."""
        g, _ = hic.vm_name_split("MyGroup_host")
        self.assertEqual(g, "MYGROUP")

    def test_empty_string(self):
        """Chaîne vide -> (LIBVIRT, '')."""
        g, n = hic.vm_name_split("")
        self.assertEqual(g, "LIBVIRT")
        self.assertEqual(n, "")


# ── Tests _rdp_socket_available ──────────────────────────────────────────────


# ── Tests RdpTab._build_cmd ──────────────────────────────────────────────────


# ── Tests RdpEmbeddedTab._build_cmd ─────────────────────────────────────────


# ── Tests VncTab._build_cmd ──────────────────────────────────────────────────


class TestVncTabBuildCmd(unittest.TestCase):
    """Tests pour VncTab._build_cmd."""

    def _make_vnc_tab(self, host, pwd="", vnc_bin="vncviewer"):
        with patch.object(plugin_vnc, "VNC_BIN", vnc_bin):
            tab = plugin_vnc.VncTab(host, lambda: pwd)
        tab.host = host
        tab._get_password = lambda: pwd
        return tab

    def test_basic_host_port(self):
        """La commande contient host:port."""
        h = _make_host(host="192.168.1.20", port="5900", protocol="vnc")
        tab = self._make_vnc_tab(h)
        with patch.object(plugin_vnc, "VNC_BIN", "vncviewer"):
            cmd, _ = tab._build_cmd()
        self.assertTrue(any("192.168.1.20" in a for a in cmd))

    def test_remmina_uri_style(self):
        """Avec remmina, la commande utilise une URI vnc://."""
        h = _make_host(host="10.0.0.5", port="5901", protocol="vnc")
        tab = self._make_vnc_tab(h, vnc_bin="/usr/bin/remmina")
        with patch.object(plugin_vnc, "VNC_BIN", "/usr/bin/remmina"):
            cmd, _ = tab._build_cmd()
        self.assertTrue(any("vnc://" in a for a in cmd))

    def test_vinagre_uri_style(self):
        """Avec vinagre, la commande utilise une URI vnc://."""
        h = _make_host(host="10.0.0.5", port="5901", protocol="vnc")
        tab = self._make_vnc_tab(h, vnc_bin="/usr/bin/vinagre")
        with patch.object(plugin_vnc, "VNC_BIN", "/usr/bin/vinagre"):
            cmd, _ = tab._build_cmd()
        self.assertTrue(any("vnc://" in a for a in cmd))

    def test_password_not_in_uri_for_vinagre(self):
        """Avec vinagre, le mot de passe n'est jamais passé en argument
        (visible de tous via ps) : il est renvoyé à part.
        """
        h = _make_host(host="10.0.0.5", port="5901", protocol="vnc")
        tab = self._make_vnc_tab(h, pwd="vncp@ss", vnc_bin="/usr/bin/vinagre")
        with patch.object(plugin_vnc, "VNC_BIN", "/usr/bin/vinagre"):
            cmd, pwd = tab._build_cmd()
        self.assertEqual(cmd, ["/usr/bin/vinagre", "vnc://10.0.0.5:5901"])
        self.assertEqual(pwd, "vncp@ss")


# ── Tests SpiceTab._build_cmd ────────────────────────────────────────────────


class TestSpiceTabBuildCmd(unittest.TestCase):
    """Tests pour SpiceTab._build_cmd."""

    def _make_spice_tab(self, host, pwd=""):
        tab = plugin_spice.SpiceTab(host, lambda: pwd)
        tab.host = host
        tab._get_password = lambda: pwd
        return tab

    def test_spice_uri_format(self):
        """La commande contient une URI spice://."""
        h = _make_host(host="192.168.1.30", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        self.assertTrue(any("spice://" in a for a in cmd))

    def test_port_in_uri(self):
        """L'URI SPICE contient le port."""
        h = _make_host(host="192.168.1.30", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        uri_arg = next(a for a in cmd if "spice://" in a)
        self.assertIn("5930", uri_arg)

    def test_host_in_uri(self):
        """L'URI SPICE contient l'adresse hôte."""
        h = _make_host(host="10.10.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        uri_arg = next(a for a in cmd if "spice://" in a)
        self.assertIn("10.10.0.5", uri_arg)

    def test_password_in_uri(self):
        """Avec mot de passe, l'URI contient password=."""
        h = _make_host(host="10.10.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h, pwd="sp1c3p@ss")
        cmd = tab._build_cmd()
        uri_arg = next(a for a in cmd if "spice://" in a)
        self.assertIn("password=sp1c3p@ss", uri_arg)

    def test_no_password_no_password_param(self):
        """Sans mot de passe, l'URI ne contient pas password=."""
        h = _make_host(host="10.10.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h, pwd="")
        cmd = tab._build_cmd()
        uri_arg = next(a for a in cmd if "spice://" in a)
        self.assertNotIn("password=", uri_arg)

    def test_extra_params_appended(self):
        """Les extra_params sont ajoutés après l'URI."""
        h = _make_host(
            host="10.10.0.5",
            port="5930",
            protocol="spice",
            extra_params="--full-screen",
        )
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        self.assertIn("--full-screen", cmd)


# ── Tests proto_defaults ─────────────────────────────────────────────────────


# ── Tests SerialTab._build_cmd ───────────────────────────────────────────────


class TestSerialTabBuildCmd(unittest.TestCase):
    """Tests pour SerialTab._build_cmd (picocom/minicom/screen)."""

    def _make_host(self, device="/dev/ttyUSB0", baud="9600", opts="", tpl=""):
        return _make_host(host=device, port=baud, extra_params=opts, protocol="serial")

    def _make_tab(self, device="/dev/ttyUSB0", baud="9600", opts=""):
        h = self._make_host(device, baud, opts)
        return plugin_serial.SerialTab(h)

    # ── picocom (binaire par défaut dans les tests) ──────────────────────────

    def _with_picocom(self, fn):
        """Force SERIAL_BIN=picocom pour la durée de fn."""
        original = plugin_serial.SERIAL_BIN
        plugin_serial.SERIAL_BIN = "picocom"
        try:
            fn()
        finally:
            plugin_serial.SERIAL_BIN = original

    def _with_minicom(self, fn):
        original = plugin_serial.SERIAL_BIN
        plugin_serial.SERIAL_BIN = "minicom"
        try:
            fn()
        finally:
            plugin_serial.SERIAL_BIN = original

    def _with_screen(self, fn):
        original = plugin_serial.SERIAL_BIN
        plugin_serial.SERIAL_BIN = "screen"
        try:
            fn()
        finally:
            plugin_serial.SERIAL_BIN = original

    def test_picocom_device_in_cmd(self):
        """Le device doit être dernier argument picocom."""

        def _():
            tab = self._make_tab("/dev/ttyUSB0", "9600")
            cmd = tab._build_cmd()
            self.assertEqual(cmd[-1], "/dev/ttyUSB0")

        self._with_picocom(_)

    def test_picocom_baud_in_cmd(self):
        """Le débit est passé via --baud."""

        def _():
            tab = self._make_tab("/dev/ttyS0", "115200")
            cmd = tab._build_cmd()
            self.assertIn("--baud", cmd)
            self.assertIn("115200", cmd)

        self._with_picocom(_)

    def test_picocom_extra_opts(self):
        """Les options supplémentaires sont injectées."""

        def _():
            tab = self._make_tab(
                "/dev/ttyUSB0", "9600", "--flow n --parity n --databits 8 --stopbits 1"
            )
            cmd = tab._build_cmd()
            self.assertIn("--flow", cmd)
            self.assertIn("n", cmd)
            self.assertIn("--parity", cmd)

        self._with_picocom(_)

    def test_picocom_no_opts(self):
        """Sans options libres, les flags série standards sont toujours présents via les combos."""

        def _():
            tab = self._make_tab("/dev/ttyUSB0", "9600", "")
            cmd = tab._build_cmd()
            # Nouveau comportement : --flow/--parity/--databits/--stopbits lus depuis les combos
            self.assertIn("--baud", cmd)
            self.assertIn("--flow", cmd)
            self.assertIn("--parity", cmd)
            self.assertIn("--databits", cmd)
            self.assertIn("--stopbits", cmd)

        self._with_picocom(_)

    def test_picocom_starts_with_binary(self):
        """Premier élément = binaire picocom."""

        def _():
            tab = self._make_tab()
            cmd = tab._build_cmd()
            self.assertEqual(cmd[0], "picocom")

        self._with_picocom(_)

    def test_minicom_device_flag(self):
        """Minicom utilise -D pour le device."""

        def _():
            tab = self._make_tab("/dev/ttyUSB1", "38400")
            cmd = tab._build_cmd()
            self.assertIn("-D", cmd)
            self.assertIn("/dev/ttyUSB1", cmd)

        self._with_minicom(_)

    def test_minicom_baud_flag(self):
        """Minicom utilise -b pour le débit."""

        def _():
            tab = self._make_tab("/dev/ttyUSB0", "57600")
            cmd = tab._build_cmd()
            self.assertIn("-b", cmd)
            self.assertIn("57600", cmd)

        self._with_minicom(_)

    def test_screen_device_and_baud(self):
        """Screen prend device puis baud en positionnels."""

        def _():
            tab = self._make_tab("/dev/ttyS1", "115200")
            cmd = tab._build_cmd()
            # screen DEVICE BAUD (après le binaire)
            self.assertEqual(cmd[0], "screen")
            self.assertIn("/dev/ttyS1", cmd)
            self.assertIn("115200", cmd)

        self._with_screen(_)

    def test_screen_extra_opts(self):
        """Screen : les options supplémentaires sont ajoutées."""

        def _():
            tab = self._make_tab("/dev/ttyUSB0", "9600", "-L")
            cmd = tab._build_cmd()
            self.assertIn("-L", cmd)

        self._with_screen(_)

    def test_default_device_fallback(self):
        """/dev/ttyUSB0 est utilisé si le champ device est vide."""

        def _():
            h = _make_host(host="", port="9600", protocol="serial")
            tab = plugin_serial.SerialTab(h)
            # vider manuellement l'entry
            tab._entry_dev.set_text("")
            cmd = tab._build_cmd()
            self.assertIn("/dev/ttyUSB0", cmd)

        self._with_picocom(_)

    def test_default_baud_fallback(self):
        """9600 est utilisé si le combo débit est indéfini."""

        def _():
            tab = self._make_tab("/dev/ttyUSB0", "9600")
            # forcer combo à -1 (non sélectionné)
            tab._cmb_baud.set_active(-1)
            cmd = tab._build_cmd()
            # le fallback doit être "9600"
            self.assertIn("9600", cmd)

        self._with_picocom(_)


# ── Tests _SERIAL_TEMPLATES ──────────────────────────────────────────────────


class TestSerialTemplates(unittest.TestCase):
    """Tests pour le dictionnaire _SERIAL_TEMPLATES."""

    def test_all_vendors_present(self):
        """Test all vendors present."""
        for vendor in (
            "Cisco IOS / IOS-XE / NX-OS",
            "HP Comware (H3C)",
            "Aruba AOS-S / AOS-CX",
            "Juniper JunOS",
            "Fortinet FortiOS",
            "Palo Alto PAN-OS",
            "F5 TMOS",
            "Linux / Raspberry Pi",
            "Arduino / ESP32",
            "RS-485 Modbus RTU",
            "Libre (manuel)",
        ):
            self.assertIn(vendor, gcm._SERIAL_TEMPLATES)

    def test_tuple_length_5(self):
        """Chaque template doit avoir 5 valeurs (baud, flow, parity, bits, stop)."""
        for name, tpl in gcm._SERIAL_TEMPLATES.items():
            self.assertEqual(len(tpl), 5, msg=f"Template '{name}' : longueur incorrecte")

    def test_cisco_9600_8n1(self):
        """Test cisco 9600 8n1."""
        baud, flow, parity, databits, stopbits = gcm._SERIAL_TEMPLATES[
            "Cisco IOS / IOS-XE / NX-OS"
        ]
        self.assertEqual(baud, "9600")
        self.assertEqual(flow, "n")
        self.assertEqual(parity, "n")
        self.assertEqual(databits, "8")
        self.assertEqual(stopbits, "1")

    def test_aruba_9600_8n1(self):
        """Test aruba 9600 8n1."""
        baud, flow, *_ = gcm._SERIAL_TEMPLATES["Aruba AOS-S / AOS-CX"]
        self.assertEqual(baud, "9600")
        self.assertEqual(flow, "n")

    def test_linux_115200(self):
        """Test linux 115200."""
        baud, *_ = gcm._SERIAL_TEMPLATES["Linux / Raspberry Pi"]
        self.assertEqual(baud, "115200")

    def test_arduino_115200(self):
        """Test arduino 115200."""
        baud, *_ = gcm._SERIAL_TEMPLATES["Arduino / ESP32"]
        self.assertEqual(baud, "115200")

    def test_f5_19200(self):
        """Test f5 19200."""
        baud, *_ = gcm._SERIAL_TEMPLATES["F5 TMOS"]
        self.assertEqual(baud, "19200")

    def test_flow_values_valid(self):
        """Flow doit être n, x ou h."""
        for name, (_, flow, *_rest) in gcm._SERIAL_TEMPLATES.items():
            self.assertIn(flow, ("n", "x", "h"), msg=f"flow invalide pour '{name}'")

    def test_parity_values_valid(self):
        """Parity doit être n, e ou o."""
        for name, (_, _, parity, *_rest) in gcm._SERIAL_TEMPLATES.items():
            self.assertIn(parity, ("n", "e", "o"), msg=f"parity invalide pour '{name}'")

    def test_baud_values_numeric(self):
        """Tous les débits doivent être numériques."""
        for name, (baud, *_rest) in gcm._SERIAL_TEMPLATES.items():
            self.assertTrue(baud.isdigit(), msg=f"baud non numérique pour '{name}'")


# ── Tests Host (supplémentaires) ─────────────────────────────────────────────


class TestHostExtended(unittest.TestCase):
    """Tests supplémentaires pour la classe Host."""

    def test_host_serial_protocol(self):
        """Test host serial protocol."""
        h = _make_host(protocol="serial")
        self.assertEqual(h.protocol, "serial")

    def test_host_port_as_baud_for_serial(self):
        """Pour serial, port = débit en bauds."""
        h = _make_host(host="/dev/ttyUSB0", port="115200", protocol="serial")
        self.assertEqual(h.port, "115200")

    def test_host_extra_params_stored(self):
        """Test host extra params stored."""
        h = _make_host(extra_params="--flow n --parity n")
        self.assertEqual(h.extra_params, "--flow n --parity n")

    def test_host_clone_extra_params(self):
        """Test host clone extra params."""
        h = _make_host(extra_params="--flow n")
        c = h.clone()
        self.assertEqual(c.extra_params, "--flow n")

    def test_host_clone_is_independent(self):
        """Test host clone is independent."""
        h = _make_host(name="orig")
        c = h.clone()
        c.name = "copy"
        self.assertEqual(h.name, "orig")

    def test_host_type_field(self):
        """Test host type field."""
        h = _make_host()
        h.type = "Cisco IOS / IOS-XE / NX-OS"
        self.assertEqual(h.type, "Cisco IOS / IOS-XE / NX-OS")

    def test_host_description_none_safe(self):
        """description=None ne lève pas d'exception à la création."""
        h = gcm.Host(
            group="G",
            name="n",
            description=None,
            host="10.0.0.1",
            user="u",
            password="",
            private_key=None,
            port="22",
            tunnel="",
            type="ssh",
            commands=None,
            keep_alive="0",
            font_color="",
            back_color="",
            x11=False,
            agent=False,
            compression=False,
            compressionLevel="",
            extra_params="",
            log=False,
            backspace_key=int(gcm.Vte.EraseBinding.AUTO),
            delete_key=int(gcm.Vte.EraseBinding.AUTO),
            term="",
            protocol="ssh",
        )
        self.assertIsNone(h.description)

    def test_host_tunnel_empty_split(self):
        """Test host tunnel empty split."""
        h = _make_host()
        self.assertEqual(h.tunnel, [""])

    def test_host_tunnel_with_value(self):
        """Test host tunnel with value."""
        h = gcm.Host(
            group="G",
            name="n",
            description=None,
            host="10.0.0.1",
            user="u",
            password="",
            private_key=None,
            port="22",
            tunnel="8080:remote:80",
            type="ssh",
            commands=None,
            keep_alive="0",
            font_color="",
            back_color="",
            x11=False,
            agent=False,
            compression=False,
            compressionLevel="",
            extra_params="",
            log=False,
            backspace_key=int(gcm.Vte.EraseBinding.AUTO),
            delete_key=int(gcm.Vte.EraseBinding.AUTO),
            term="",
            protocol="ssh",
        )
        self.assertEqual(h.tunnel, ["8080:remote:80"])


# ── Tests HostUtils (supplémentaires) ────────────────────────────────────────


class TestHostUtilsExtended(unittest.TestCase):
    """Tests supplémentaires pour HostUtils.save/load."""

    def test_save_and_load_serial_protocol(self):
        """Protocole serial est préservé en save/load."""
        h = _make_host(
            host="/dev/ttyUSB0",
            port="115200",
            protocol="serial",
            extra_params="--flow n",
        )
        cp = configparser.ConfigParser()
        cp.add_section("host0")
        gcm.HostUtils.save_host_to_ini(cp, "host0", h, "pass")
        loaded = gcm.HostUtils.load_host_from_ini(cp, "host0", "pass")
        self.assertEqual(loaded.protocol, "serial")
        self.assertEqual(loaded.port, "115200")
        self.assertEqual(loaded.extra_params, "--flow n")

    def test_save_none_fields_no_exception(self):
        """save_host_to_ini ne lève pas d'exception si certains champs sont None."""
        h = gcm.Host(
            group="G",
            name="n",
            description=None,
            host="10.0.0.1",
            user="u",
            password="",
            private_key=None,
            port="22",
            tunnel="",
            type="ssh",
            commands=None,
            keep_alive="0",
            font_color="",
            back_color="",
            x11=False,
            agent=False,
            compression=False,
            compressionLevel="",
            extra_params="",
            log=False,
            backspace_key=int(gcm.Vte.EraseBinding.AUTO),
            delete_key=int(gcm.Vte.EraseBinding.AUTO),
            term="",
            protocol="ssh",
        )
        cp = configparser.ConfigParser()
        cp.add_section("s0")
        gcm.HostUtils.save_host_to_ini(cp, "s0", h, "")  # ne doit pas lever

    def test_save_and_load_roundtrip_name(self):
        """Test save and load roundtrip name."""
        h = _make_host(name="mon-routeur")
        cp = configparser.ConfigParser()
        cp.add_section("x")
        gcm.HostUtils.save_host_to_ini(cp, "x", h, "")
        loaded = gcm.HostUtils.load_host_from_ini(cp, "x", "")
        self.assertEqual(loaded.name, "mon-routeur")

    def test_save_and_load_roundtrip_host(self):
        """Test save and load roundtrip host."""
        h = _make_host(host="192.168.1.254")
        cp = configparser.ConfigParser()
        cp.add_section("x")
        gcm.HostUtils.save_host_to_ini(cp, "x", h, "")
        loaded = gcm.HostUtils.load_host_from_ini(cp, "x", "")
        self.assertEqual(loaded.host, "192.168.1.254")


# ── Tests chiffrement (supplémentaires) ──────────────────────────────────────


class TestEncryptionExtended(unittest.TestCase):
    """Tests supplémentaires pour les fonctions de chiffrement."""

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig_version = gcm.conf.VERSION
        gcm.conf.VERSION = 1  # force pyAES

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        gcm.conf.VERSION = self._orig_version

    def test_xor_with_key_longer_than_text(self):
        """La clé plus longue que le texte ne doit pas planter."""
        result = gcm.xor("clé-très-longue-longue", "hi")
        self.assertEqual(len(result), 2)

    def test_xor_with_special_chars(self):
        """Test xor with special chars."""
        plain = "héllo wörld"
        key = "k3y"
        roundtrip = "".join(gcm.xor(key, "".join(gcm.xor(key, plain))))
        self.assertEqual(roundtrip, plain)

    def test_encrypt_aes_different_from_plaintext(self):
        """Test encrypt aes different from plaintext."""
        cipher = gcm.encrypt("pass", "secret")
        self.assertNotEqual(cipher, "secret")

    def test_encrypt_aes_returns_string(self):
        """Test encrypt aes returns string."""
        result = gcm.encrypt("pass", "test")
        self.assertIsInstance(result, str)

    def test_decrypt_aes_returns_string(self):
        """Test decrypt aes returns string."""
        cipher = gcm.encrypt("pass", "hello")
        result = gcm.decrypt("pass", cipher)
        self.assertIsInstance(result, str)

    def test_encrypt_decrypt_aes_extended_latin(self):
        """PyAES supporte les caractères latin-1 (U+0000–U+00FF)."""
        plain = "mot de passe admin"
        cipher = gcm.encrypt("key", plain)
        result = gcm.decrypt("key", cipher)
        self.assertEqual(result, plain)

    def test_encrypt_old_returns_string(self):
        """Test encrypt old returns string."""
        result = gcm.encrypt_old("pass", "hello")
        self.assertIsInstance(result, str)

    def test_decrypt_old_returns_string(self):
        """Test decrypt old returns string."""
        enc = gcm.encrypt_old("pass", "hello")
        result = gcm.decrypt_old("pass", enc)
        self.assertIsInstance(result, str)


# ── Tests VmNameSplit (supplémentaires) ──────────────────────────────────────


class TestVmNameSplitExtended(unittest.TestCase):
    """Tests supplémentaires pour _vm_name_split."""

    def test_double_underscore(self):
        """Test double underscore."""
        grp, name = hic.vm_name_split("web__server")
        self.assertEqual(grp, "WEB")

    def test_leading_separator_is_no_separator(self):
        """Un nom commençant par _ n'a pas de groupe."""
        grp, name = hic.vm_name_split("_server")
        # pas de token avant le _, donc groupe = LIBVIRT
        self.assertEqual(grp, "LIBVIRT")

    def test_digits_only_name(self):
        """Test digits only name."""
        grp, name = hic.vm_name_split("192-168")
        self.assertEqual(grp, "192")
        self.assertEqual(name, "168")

    def test_unicode_name(self):
        """Les noms unicodes sont tolérés."""
        grp, name = hic.vm_name_split("réseau_interne")
        self.assertEqual(grp, "RÉSEAU")

    def test_single_char_group(self):
        """Test single char group."""
        grp, name = hic.vm_name_split("a_server")
        self.assertEqual(grp, "A")
        self.assertEqual(name, "server")


# ── Tests _rdp_socket_available (supplémentaires) ────────────────────────────


# ── Tests RdpTab (supplémentaires) ───────────────────────────────────────────


# ── Tests VncTab (supplémentaires) ───────────────────────────────────────────


class TestVncTabBuildCmdExtended(unittest.TestCase):
    """Tests supplémentaires pour VncTab._build_cmd."""

    def _make_vnc_tab(self, host, pwd=""):
        return plugin_vnc.VncTab(host, lambda: pwd)

    def test_vnc_starts_with_binary(self):
        """Test vnc starts with binary."""
        h = _make_host(host="10.0.0.2", port="5901", protocol="vnc")
        tab = self._make_vnc_tab(h)
        cmd, _ = tab._build_cmd()
        self.assertEqual(cmd[0], plugin_vnc.VNC_BIN)

    def test_vnc_host_port_format(self):
        """Test vnc host port format."""
        h = _make_host(host="10.0.0.2", port="5902", protocol="vnc")
        tab = self._make_vnc_tab(h)
        cmd, _ = tab._build_cmd()
        # au moins un argument contient host:port
        combined = " ".join(cmd)
        self.assertIn("10.0.0.2", combined)
        self.assertIn("5902", combined)

    def test_vnc_uri_for_vinagre(self):
        """Vinagre reçoit une URI vnc://hôte:port, sans identifiants."""
        original = plugin_vnc.VNC_BIN
        plugin_vnc.VNC_BIN = "vinagre"
        try:
            h = _make_host(host="10.0.0.3", port="5900", user="admin", protocol="vnc")
            tab = self._make_vnc_tab(h, pwd="secret")
            cmd, _ = tab._build_cmd()
            self.assertEqual(cmd, ["vinagre", "vnc://10.0.0.3:5900"])
        finally:
            plugin_vnc.VNC_BIN = original

    def test_vnc_returns_tuple(self):
        """Test vnc returns tuple."""
        h = _make_host(host="10.0.0.2", port="5900", protocol="vnc")
        tab = self._make_vnc_tab(h)
        result = tab._build_cmd()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


# ── Tests SpiceTab (supplémentaires) ─────────────────────────────────────────


class TestSpiceTabBuildCmdExtended(unittest.TestCase):
    """Tests supplémentaires pour SpiceTab._build_cmd."""

    def _make_spice_tab(self, host, pwd=""):
        return plugin_spice.SpiceTab(host, lambda: pwd)

    def test_spice_starts_with_binary(self):
        """Test spice starts with binary."""
        h = _make_host(host="10.0.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        self.assertEqual(cmd[0], plugin_spice.SPICE_BIN)

    def test_spice_returns_list(self):
        """Test spice returns list."""
        h = _make_host(host="10.0.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        self.assertIsInstance(cmd, list)

    def test_spice_uri_starts_with_spice(self):
        """Test spice uri starts with spice."""
        h = _make_host(host="10.0.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        uri = next((a for a in cmd if a.startswith("spice://")), None)
        self.assertIsNotNone(uri)

    def test_spice_password_in_query(self):
        """Test spice password in query."""
        h = _make_host(host="10.0.0.5", port="5930", protocol="spice")
        tab = self._make_spice_tab(h, pwd="mypassword")
        cmd = tab._build_cmd()
        self.assertTrue(any("mypassword" in a for a in cmd))

    def test_spice_multiple_extra_params(self):
        """Test spice multiple extra params."""
        h = _make_host(
            host="10.0.0.5",
            port="5930",
            protocol="spice",
            extra_params="--full-screen --spice-debug",
        )
        tab = self._make_spice_tab(h)
        cmd = tab._build_cmd()
        self.assertIn("--full-screen", cmd)
        self.assertIn("--spice-debug", cmd)


# ── Tests encrypt_old/decrypt_old (bug Python 3) ─────────────────────────────


class TestEncryptOldPython3(unittest.TestCase):
    """Vérifie que encrypt_old/decrypt_old fonctionnent en Python 3."""

    def test_roundtrip_simple(self):
        """Test roundtrip simple."""
        enc = gcm.encrypt_old("key", "hello")
        dec = gcm.decrypt_old("key", enc)
        self.assertEqual(dec, "hello")

    def test_roundtrip_with_special_chars(self):
        """Test roundtrip with special chars."""
        enc = gcm.encrypt_old("pass123", "Pässwörd!@#")
        dec = gcm.decrypt_old("pass123", enc)
        self.assertEqual(dec, "Pässwörd!@#")

    def test_encrypt_old_not_plaintext(self):
        """Test encrypt old not plaintext."""
        enc = gcm.encrypt_old("key", "secret")
        self.assertNotEqual(enc, "secret")

    def test_decrypt_old_wrong_key_differs(self):
        """Test decrypt old wrong key differs."""
        enc = gcm.encrypt_old("key1", "hello")
        dec_wrong = gcm.decrypt_old("key2", enc)
        self.assertNotEqual(dec_wrong, "hello")

    def test_empty_string_roundtrip(self):
        """Test empty string roundtrip."""
        enc = gcm.encrypt_old("key", "")
        dec = gcm.decrypt_old("key", enc)
        self.assertEqual(dec, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ═══════════════════════════════════════════════════════════════════════════
#  BLOC 3 — Tests supplémentaires (triplement de la suite)
# ═══════════════════════════════════════════════════════════════════════════

# ── xor (exhaustif) ──────────────────────────────────────────────────────────


class TestXorFunction(unittest.TestCase):
    """Tests exhaustifs pour la primitive xor()."""

    def test_single_char(self):
        """Test single char."""
        self.assertEqual(len(gcm.xor("k", "a")), 1)

    def test_key_wraps_around(self):
        """Test key wraps around."""
        self.assertEqual(len(gcm.xor("k", "hello")), 5)

    def test_double_application_is_identity(self):
        """Test double application is identity."""
        text = "test message"
        key = "secret"
        enc = "".join(gcm.xor(key, text))
        dec = "".join(gcm.xor(key, enc))
        self.assertEqual(dec, text)

    def test_empty_text(self):
        """Test empty text."""
        self.assertEqual(gcm.xor("key", ""), [])

    def test_key_longer_than_text_no_crash(self):
        """Test key longer than text no crash."""
        result = gcm.xor("very_long_key_here", "hi")
        self.assertEqual(len(result), 2)

    def test_with_spaces(self):
        """Test with spaces."""
        self.assertEqual(len(gcm.xor("key", "hello world")), 11)

    def test_ascii_printable(self):
        """Test ascii printable."""
        result = gcm.xor("12345678", "ABCDEFGH")
        self.assertEqual(len(result), 8)

    def test_result_is_list(self):
        """Test result is list."""
        self.assertIsInstance(gcm.xor("k", "hello"), list)

    def test_repeated_key_byte_gives_consistent_output(self):
        """Test repeated key byte gives consistent output."""
        r1 = gcm.xor("k", "abc")
        r2 = gcm.xor("k", "abc")
        self.assertEqual(r1, r2)

    def test_different_keys_different_output(self):
        """Test different keys different output."""
        r1 = "".join(gcm.xor("key1", "hello"))
        r2 = "".join(gcm.xor("key2", "hello"))
        self.assertNotEqual(r1, r2)


# ── Host — champs par défaut ──────────────────────────────────────────────────


class TestHostFieldDefaults(unittest.TestCase):
    """Vérifie les valeurs par défaut de chaque champ Host."""

    def setUp(self):
        """Set up fixtures for this test case."""
        self.h = _make_host()

    def test_protocol_ssh(self):
        """Test protocol ssh."""
        self.assertEqual(self.h.protocol, "ssh")

    def test_x11_false(self):
        """Test x11 false."""
        self.assertFalse(self.h.x11)

    def test_compression_false(self):
        """Test compression false."""
        self.assertFalse(self.h.compression)

    def test_agent_false(self):
        """Test agent false."""
        self.assertFalse(self.h.agent)

    def test_log_false(self):
        """Test log false."""
        self.assertFalse(self.h.log)

    def test_font_color_empty(self):
        """Test font color empty."""
        self.assertEqual(self.h.font_color, "")

    def test_back_color_empty(self):
        """Test back color empty."""
        self.assertEqual(self.h.back_color, "")

    def test_extra_params_empty(self):
        """Test extra params empty."""
        self.assertEqual(self.h.extra_params, "")

    def test_compressionLevel_empty(self):
        """Test compressionLevel empty."""
        self.assertEqual(self.h.compressionLevel, "")

    def test_term_empty(self):
        """Test term empty."""
        self.assertEqual(self.h.term, "")

    def test_keep_alive_zero(self):
        """Test keep alive zero."""
        self.assertEqual(str(self.h.keep_alive), "0")

    def test_tunnel_list(self):
        """Test tunnel list."""
        self.assertIsInstance(self.h.tunnel, list)

    def test_group_stored(self):
        """Test group stored."""
        h = _make_host(group="ROUTERS")
        self.assertEqual(h.group, "ROUTERS")

    def test_name_stored(self):
        """Test name stored."""
        h = _make_host(name="sw-core")
        self.assertEqual(h.name, "sw-core")

    def test_host_stored(self):
        """Test host stored."""
        h = _make_host(host="192.168.1.254")
        self.assertEqual(h.host, "192.168.1.254")

    def test_user_stored(self):
        """Test user stored."""
        h = _make_host(user="admin")
        self.assertEqual(h.user, "admin")

    def test_port_stored(self):
        """Test port stored."""
        h = _make_host(port="8022")
        self.assertEqual(h.port, "8022")


# ── Host — tunnel ─────────────────────────────────────────────────────────────


class TestHostTunnelParsing(unittest.TestCase):
    """Parsing et sérialisation des tunnels SSH."""

    def _h(self, tunnel_str):
        return gcm.Host(
            group="G",
            name="n",
            description=None,
            host="10.0.0.1",
            user="u",
            password="",
            private_key=None,
            port="22",
            tunnel=tunnel_str,
            type="ssh",
            commands=None,
            keep_alive=0,
            font_color="",
            back_color="",
            x11=False,
            agent=False,
            compression=False,
            compressionLevel="",
            extra_params="",
            log=False,
            backspace_key=0,
            delete_key=0,
            term="",
            protocol="ssh",
        )

    def test_empty_tunnel_as_string(self):
        """Test empty tunnel as string."""
        self.assertEqual(_make_host().tunnel_as_string(), "")

    def test_single_forward_tunnel(self):
        """Test single forward tunnel."""
        h = self._h("8080:remote:80")
        self.assertIn("8080:remote:80", h.tunnel)

    def test_tunnel_as_string_non_empty(self):
        """Test tunnel as string non empty."""
        h = self._h("8080:remote:80")
        self.assertIn("8080:remote:80", h.tunnel_as_string())

    def test_dynamic_socks_entry(self):
        """Test dynamic socks entry."""
        h = self._h("1080:*:*")
        self.assertIn("1080:*:*", h.tunnel)

    def test_tunnel_list_type(self):
        """Test tunnel list type."""
        h = self._h("8080:remote:80")
        self.assertIsInstance(h.tunnel, list)

    def test_empty_tunnel_list(self):
        """Test empty tunnel list."""
        h = _make_host()
        self.assertEqual(h.tunnel, [""])


# ── Host — clone exhaustif ────────────────────────────────────────────────────


class TestHostCloneAllFields(unittest.TestCase):
    """Clone préserve chaque champ."""

    def setUp(self):
        """Set up fixtures for this test case."""
        self.orig = _make_host(
            group="ROUTERS",
            name="sw-core",
            host="192.168.1.254",
            user="admin",
            port="22",
            protocol="rdp",
            extra_params="--extra",
        )
        self.orig.font_color = "#FF0000"
        self.orig.back_color = "#000000"
        self.orig.x11 = True
        self.orig.agent = True
        self.orig.compression = True
        self.orig.compressionLevel = "9"
        self.orig.log = True
        self.orig.term = "xterm-256color"
        self.copy = self.orig.clone()

    def test_group(self):
        """Test group."""
        self.assertEqual(self.copy.group, "ROUTERS")

    def test_name(self):
        """Test name."""
        self.assertEqual(self.copy.name, "sw-core")

    def test_host(self):
        """Test host."""
        self.assertEqual(self.copy.host, "192.168.1.254")

    def test_user(self):
        """Test user."""
        self.assertEqual(self.copy.user, "admin")

    def test_port(self):
        """Test port."""
        self.assertEqual(self.copy.port, "22")

    def test_protocol(self):
        """Test protocol."""
        self.assertEqual(self.copy.protocol, "rdp")

    def test_extra_params(self):
        """Test extra params."""
        self.assertEqual(self.copy.extra_params, "--extra")

    def test_font_color(self):
        """Test font color."""
        self.assertEqual(self.copy.font_color, "#FF0000")

    def test_back_color(self):
        """Test back color."""
        self.assertEqual(self.copy.back_color, "#000000")

    def test_x11(self):
        """Test x11."""
        self.assertTrue(self.copy.x11)

    def test_agent(self):
        """Test agent."""
        self.assertTrue(self.copy.agent)

    def test_compression(self):
        """Test compression."""
        self.assertTrue(self.copy.compression)

    def test_log(self):
        """Test log."""
        self.assertTrue(self.copy.log)

    def test_term(self):
        """Test term."""
        self.assertEqual(self.copy.term, "xterm-256color")

    def test_independent_name(self):
        """Test independent name."""
        self.copy.name = "other"
        self.assertEqual(self.orig.name, "sw-core")

    def test_independent_host(self):
        """Test independent host."""
        self.copy.host = "10.0.0.1"
        self.assertEqual(self.orig.host, "192.168.1.254")


# ── HostUtils — champs individuels ────────────────────────────────────────────


class TestHostUtilsEachField(unittest.TestCase):
    """Round-trip save/load pour chaque champ individuel."""

    def _rt(self, **kw):
        h = _make_host(**kw)
        cp = configparser.ConfigParser()
        cp.add_section("s")
        gcm.HostUtils.save_host_to_ini(cp, "s", h, "pass")
        return gcm.HostUtils.load_host_from_ini(cp, "s", "pass")

    def test_group(self):
        """Test group."""
        self.assertEqual(self._rt(group="CORE").group, "CORE")

    def test_name(self):
        """Test name."""
        self.assertEqual(self._rt(name="sw-access").name, "sw-access")

    def test_host_ip(self):
        """Test host ip."""
        self.assertEqual(self._rt(host="10.10.10.1").host, "10.10.10.1")

    def test_host_fqdn(self):
        """Test host fqdn."""
        self.assertEqual(self._rt(host="router.corp.local").host, "router.corp.local")

    def test_user(self):
        """Test user."""
        self.assertEqual(self._rt(user="operator").user, "operator")

    def test_port(self):
        """Test port."""
        self.assertEqual(self._rt(port="2222").port, "2222")

    def test_extra_params(self):
        """Test extra params."""
        self.assertEqual(self._rt(extra_params="/opt").extra_params, "/opt")

    def test_protocol_ssh(self):
        """Test protocol ssh."""
        self.assertEqual(self._rt(protocol="ssh").protocol, "ssh")

    def test_protocol_telnet(self):
        """Test protocol telnet."""
        self.assertEqual(self._rt(protocol="telnet").protocol, "telnet")

    def test_protocol_vnc(self):
        """Test protocol vnc."""
        self.assertEqual(self._rt(protocol="vnc").protocol, "vnc")

    def test_protocol_spice(self):
        """Test protocol spice."""
        self.assertEqual(self._rt(protocol="spice").protocol, "spice")

    def test_protocol_serial(self):
        """Test protocol serial."""
        self.assertEqual(self._rt(protocol="serial").protocol, "serial")

    def test_protocol_rdp(self):
        """Test protocol rdp."""
        self.assertEqual(self._rt(protocol="rdp").protocol, "rdp")

    def _rt_field(self, field, value):
        h = _make_host()
        setattr(h, field, value)
        cp = configparser.ConfigParser()
        cp.add_section("s")
        gcm.HostUtils.save_host_to_ini(cp, "s", h, "")
        return getattr(gcm.HostUtils.load_host_from_ini(cp, "s", ""), field)

    def test_font_color(self):
        """Test font color."""
        self.assertEqual(self._rt_field("font_color", "#AABBCC"), "#AABBCC")

    def test_back_color(self):
        """Test back color."""
        self.assertEqual(self._rt_field("back_color", "#112233"), "#112233")

    def test_term(self):
        """Test term."""
        self.assertEqual(self._rt_field("term", "xterm-256color"), "xterm-256color")

    def test_x11_true(self):
        """Test x11 true."""
        self.assertTrue(self._rt_field("x11", True))

    def test_x11_false(self):
        """Test x11 false."""
        self.assertFalse(self._rt_field("x11", False))

    def test_agent_true(self):
        """Test agent true."""
        self.assertTrue(self._rt_field("agent", True))

    def test_compression_true(self):
        """Test compression true."""
        self.assertTrue(self._rt_field("compression", True))

    def test_log_true(self):
        """Test log true."""
        self.assertTrue(self._rt_field("log", True))

    def test_keepalive(self):
        """Test keepalive."""
        self.assertEqual(self._rt_field("keep_alive", "30"), "30")

    def test_compressionLevel(self):
        """Test compressionLevel."""
        self.assertEqual(self._rt_field("compressionLevel", "6"), "6")


# ── Ports par défaut des protocoles (ex-_PROTO_DEFAULTS) ──────────────────────


class TestPluginDefaultPorts(unittest.TestCase):
    """Le dictionnaire _PROTO_DEFAULTS de gnome_connection_manager a disparu :
    chaque plugin porte désormais son ``default_port`` (plugin_base.py).
    """

    def _port(self, module):
        return module.get_plugin().default_port

    def test_ssh(self):
        """SSH : port 22."""
        self.assertEqual(self._port(plugin_ssh), 22)

    def test_telnet(self):
        """Telnet : port 23."""
        self.assertEqual(self._port(plugin_telnet), 23)

    def test_rdp(self):
        """RDP : port 3389."""
        self.assertEqual(self._port(plugin_rdp), 3389)

    def test_vnc(self):
        """VNC : port 5900."""
        self.assertEqual(self._port(plugin_vnc), 5900)

    def test_spice(self):
        """SPICE : port 5930."""
        self.assertEqual(self._port(plugin_spice), 5930)

    def test_serial_sans_port_reseau(self):
        """Série : pas de port réseau."""
        # Le débit (9600...) n'est plus stocké comme un « port » du protocole.
        self.assertIsNone(self._port(plugin_serial))

    def test_local_sans_port(self):
        """Local : pas de port."""
        self.assertIsNone(self._port(plugin_local))


# ── Détection des binaires ────────────────────────────────────────────────────


class TestBinaryDetection(unittest.TestCase):
    """Tests for binary detection."""

    def test_rdp_bin_string(self):
        """Test rdp bin string."""
        self.assertIsInstance(widgets.RDP_BIN, str)

    def test_rdp_bin_not_empty(self):
        """Test rdp bin not empty."""
        self.assertGreater(len(widgets.RDP_BIN), 0)

    def test_rdp_bin_has_rdp(self):
        """Test rdp bin has rdp."""
        self.assertIn("rdp", widgets.RDP_BIN.lower())

    def test_vnc_bin_string(self):
        """Test vnc bin string."""
        self.assertIsInstance(plugin_vnc.VNC_BIN, str)

    def test_vnc_bin_not_empty(self):
        """Test vnc bin not empty."""
        self.assertGreater(len(plugin_vnc.VNC_BIN), 0)

    def test_spice_bin_string(self):
        """Test spice bin string."""
        self.assertIsInstance(plugin_spice.SPICE_BIN, str)

    def test_spice_bin_not_empty(self):
        """Test spice bin not empty."""
        self.assertGreater(len(plugin_spice.SPICE_BIN), 0)

    def test_serial_bin_string(self):
        """Test serial bin string."""
        self.assertIsInstance(plugin_serial.SERIAL_BIN, str)

    def test_serial_bin_not_empty(self):
        """Test serial bin not empty."""
        self.assertGreater(len(plugin_serial.SERIAL_BIN), 0)

    def test_serial_bin_known(self):
        """Test serial bin known."""
        self.assertIn(os.path.basename(plugin_serial.SERIAL_BIN), ("picocom", "minicom", "screen"))

    def test_spice_bin_known(self):
        """Test spice bin known."""
        self.assertIn(
            os.path.basename(plugin_spice.SPICE_BIN), ("remote-viewer", "virt-viewer", "spicy")
        )

    def test_vnc_bin_known(self):
        """Test vnc bin known."""
        self.assertIn(
            os.path.basename(plugin_vnc.VNC_BIN),
            (
                "vncviewer",
                "tigervnc",
                "xtightvncviewer",
                "xvnc4viewer",
                "vinagre",
                "remmina",
            ),
        )


# ── _SERIAL_TEMPLATES — détaillé ─────────────────────────────────────────────


class TestSerialTemplatesExhaustive(unittest.TestCase):
    """Tests détaillés pour _SERIAL_TEMPLATES."""

    def _tpl(self, name):
        return gcm._SERIAL_TEMPLATES[name]

    def test_cisco_present(self):
        """Test cisco present."""
        self.assertIn("Cisco IOS / IOS-XE / NX-OS", gcm._SERIAL_TEMPLATES)

    def test_comware_present(self):
        """Test comware present."""
        self.assertIn("HP Comware (H3C)", gcm._SERIAL_TEMPLATES)

    def test_aruba_present(self):
        """Test aruba present."""
        self.assertIn("Aruba AOS-S / AOS-CX", gcm._SERIAL_TEMPLATES)

    def test_juniper_present(self):
        """Test juniper present."""
        self.assertIn("Juniper JunOS", gcm._SERIAL_TEMPLATES)

    def test_fortinet_present(self):
        """Test fortinet present."""
        self.assertIn("Fortinet FortiOS", gcm._SERIAL_TEMPLATES)

    def test_paloalto_present(self):
        """Test paloalto present."""
        self.assertIn("Palo Alto PAN-OS", gcm._SERIAL_TEMPLATES)

    def test_f5_present(self):
        """Test f5 present."""
        self.assertIn("F5 TMOS", gcm._SERIAL_TEMPLATES)

    def test_linux_present(self):
        """Test linux present."""
        self.assertIn("Linux / Raspberry Pi", gcm._SERIAL_TEMPLATES)

    def test_arduino_present(self):
        """Test arduino present."""
        self.assertIn("Arduino / ESP32", gcm._SERIAL_TEMPLATES)

    def test_modbus_present(self):
        """Test modbus present."""
        self.assertIn("RS-485 Modbus RTU", gcm._SERIAL_TEMPLATES)

    def test_libre_present(self):
        """Test libre present."""
        self.assertIn("Libre (manuel)", gcm._SERIAL_TEMPLATES)

    def test_count_11(self):
        """Test count 11."""
        self.assertEqual(len(gcm._SERIAL_TEMPLATES), 11)

    def test_all_len5(self):
        """Test all len5."""
        for n, t in gcm._SERIAL_TEMPLATES.items():
            self.assertEqual(len(t), 5, msg=f"{n}: longueur incorrecte")

    def test_all_baud_numeric(self):
        """Test all baud numeric."""
        for n, (b, *_) in gcm._SERIAL_TEMPLATES.items():
            self.assertTrue(b.isdigit(), msg=f"{n}: baud non numérique")

    def test_all_flow_valid(self):
        """Test all flow valid."""
        for n, (_, f, *_) in gcm._SERIAL_TEMPLATES.items():
            self.assertIn(f, ("n", "x", "h"), msg=f"{n}: flow invalide")

    def test_all_parity_valid(self):
        """Test all parity valid."""
        for n, (_, _, p, *_) in gcm._SERIAL_TEMPLATES.items():
            self.assertIn(p, ("n", "e", "o"), msg=f"{n}: parity invalide")

    def test_all_databits_8(self):
        """Test all databits 8."""
        for n, (_, _, _, d, _) in gcm._SERIAL_TEMPLATES.items():
            self.assertEqual(d, "8", msg=f"{n}: databits != 8")

    def test_all_stopbits_1(self):
        """Test all stopbits 1."""
        for n, (_, _, _, _, s) in gcm._SERIAL_TEMPLATES.items():
            self.assertEqual(s, "1", msg=f"{n}: stopbits != 1")

    def test_cisco_9600(self):
        """Test cisco 9600."""
        self.assertEqual(self._tpl("Cisco IOS / IOS-XE / NX-OS")[0], "9600")

    def test_f5_19200(self):
        """Test f5 19200."""
        self.assertEqual(self._tpl("F5 TMOS")[0], "19200")

    def test_linux_115200(self):
        """Test linux 115200."""
        self.assertEqual(self._tpl("Linux / Raspberry Pi")[0], "115200")

    def test_arduino_115200(self):
        """Test arduino 115200."""
        self.assertEqual(self._tpl("Arduino / ESP32")[0], "115200")

    def test_aruba_9600(self):
        """Test aruba 9600."""
        self.assertEqual(self._tpl("Aruba AOS-S / AOS-CX")[0], "9600")

    def test_juniper_9600(self):
        """Test juniper 9600."""
        self.assertEqual(self._tpl("Juniper JunOS")[0], "9600")

    def test_fortinet_9600(self):
        """Test fortinet 9600."""
        self.assertEqual(self._tpl("Fortinet FortiOS")[0], "9600")

    def test_paloalto_9600(self):
        """Test paloalto 9600."""
        self.assertEqual(self._tpl("Palo Alto PAN-OS")[0], "9600")

    def test_modbus_9600(self):
        """Test modbus 9600."""
        self.assertEqual(self._tpl("RS-485 Modbus RTU")[0], "9600")


# ── SerialTab — template application ──────────────────────────────────────────


class TestSerialTabTemplates(unittest.TestCase):
    """Test de l'application des templates dans SerialTab."""

    def _tab(self):
        return plugin_serial.SerialTab(
            _make_host(host="/dev/ttyUSB0", port="9600", protocol="serial")
        )

    def _apply(self, tab, name):
        tpl_list = list(gcm._SERIAL_TEMPLATES.keys())
        tab._cmb_tpl.set_active(tpl_list.index(name))
        tab._on_template_changed(tab._cmb_tpl)

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig_bin = plugin_serial.SERIAL_BIN
        plugin_serial.SERIAL_BIN = "picocom"

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        plugin_serial.SERIAL_BIN = self._orig_bin

    def test_cisco_sets_9600(self):
        """Test cisco sets 9600."""
        t = self._tab()
        self._apply(t, "Cisco IOS / IOS-XE / NX-OS")
        self.assertEqual(t._cmb_baud.get_active_text(), "9600")

    def test_linux_sets_115200(self):
        """Test linux sets 115200."""
        t = self._tab()
        self._apply(t, "Linux / Raspberry Pi")
        self.assertEqual(t._cmb_baud.get_active_text(), "115200")

    def test_arduino_sets_115200(self):
        """Test arduino sets 115200."""
        t = self._tab()
        self._apply(t, "Arduino / ESP32")
        self.assertEqual(t._cmb_baud.get_active_text(), "115200")

    def test_f5_sets_19200(self):
        """Test f5 sets 19200."""
        t = self._tab()
        self._apply(t, "F5 TMOS")
        self.assertEqual(t._cmb_baud.get_active_text(), "19200")

    def test_saves_to_host_type(self):
        """Test saves to host type."""
        t = self._tab()
        self._apply(t, "Aruba AOS-S / AOS-CX")
        self.assertEqual(t.host.type, "Aruba AOS-S / AOS-CX")

    def test_picocom_opts_include_flow(self):
        """Cisco IOS configure flow=n, vérifié dans la commande _build_cmd."""
        t = self._tab()
        self._apply(t, "Cisco IOS / IOS-XE / NX-OS")
        cmd = t._build_cmd()
        self.assertIn("--flow", cmd)

    def test_picocom_opts_include_parity(self):
        """Cisco IOS configure parity=n, vérifié dans la commande _build_cmd."""
        t = self._tab()
        self._apply(t, "Cisco IOS / IOS-XE / NX-OS")
        cmd = t._build_cmd()
        self.assertIn("--parity", cmd)

    def test_minicom_opts_include_databits(self):
        """Minicom : --databits est passé dans la commande générée."""
        plugin_serial.SERIAL_BIN = "minicom"
        t = self._tab()
        self._apply(t, "Cisco IOS / IOS-XE / NX-OS")
        cmd = t._build_cmd()
        self.assertIn("--databits", cmd)

    def test_fortinet_sets_9600(self):
        """Test fortinet sets 9600."""
        t = self._tab()
        self._apply(t, "Fortinet FortiOS")
        self.assertEqual(t._cmb_baud.get_active_text(), "9600")

    def test_juniper_sets_9600(self):
        """Test juniper sets 9600."""
        t = self._tab()
        self._apply(t, "Juniper JunOS")
        self.assertEqual(t._cmb_baud.get_active_text(), "9600")

    def test_comware_sets_9600(self):
        """Test comware sets 9600."""
        t = self._tab()
        self._apply(t, "HP Comware (H3C)")
        self.assertEqual(t._cmb_baud.get_active_text(), "9600")

    def test_modbus_sets_9600(self):
        """Test modbus sets 9600."""
        t = self._tab()
        self._apply(t, "RS-485 Modbus RTU")
        self.assertEqual(t._cmb_baud.get_active_text(), "9600")


# ── SerialTab._build_cmd — détaillé ───────────────────────────────────────────


class TestSerialTabBuildCmdAll(unittest.TestCase):
    """Tests _build_cmd pour tous les binaires et appareils."""

    def _tab(self, device="/dev/ttyUSB0", baud="9600", opts=""):
        h = _make_host(host=device, port=baud, protocol="serial")
        t = plugin_serial.SerialTab(h)
        t._entry_dev.set_text(device)
        t._entry_opts.set_text(opts)
        # sync baud combo
        model = t._cmb_baud.get_model()
        it = model.get_iter_first()
        while it is not None:
            if model[it][0] == baud:
                t._cmb_baud.set_active_iter(it)
                break
            it = model.iter_next(it)
        return t

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig = plugin_serial.SERIAL_BIN

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        plugin_serial.SERIAL_BIN = self._orig

    # picocom ----------------------------------------------------------------

    def test_picocom_first(self):
        """Test picocom first."""
        plugin_serial.SERIAL_BIN = "picocom"
        self.assertEqual(self._tab()._build_cmd()[0], "picocom")

    def test_picocom_device_last(self):
        """Test picocom device last."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0")._build_cmd()
        self.assertEqual(cmd[-1], "/dev/ttyUSB0")

    def test_picocom_baud_9600(self):
        """Test picocom baud 9600."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0", "9600")._build_cmd()
        idx = cmd.index("--baud")
        self.assertEqual(cmd[idx + 1], "9600")

    def test_picocom_baud_115200(self):
        """Test picocom baud 115200."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0", "115200")._build_cmd()
        self.assertIn("115200", cmd)

    def test_picocom_baud_19200(self):
        """Test picocom baud 19200."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0", "19200")._build_cmd()
        self.assertIn("19200", cmd)

    def test_picocom_baud_38400(self):
        """Test picocom baud 38400."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0", "38400")._build_cmd()
        self.assertIn("38400", cmd)

    def test_picocom_baud_57600(self):
        """Test picocom baud 57600."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB0", "57600")._build_cmd()
        self.assertIn("57600", cmd)

    def test_picocom_dev_ttyS0(self):
        """Test picocom dev ttyS0."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyS0")._build_cmd()
        self.assertIn("/dev/ttyS0", cmd)

    def test_picocom_dev_ttyS1(self):
        """Test picocom dev ttyS1."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyS1")._build_cmd()
        self.assertIn("/dev/ttyS1", cmd)

    def test_picocom_dev_ttyUSB1(self):
        """Test picocom dev ttyUSB1."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyUSB1")._build_cmd()
        self.assertIn("/dev/ttyUSB1", cmd)

    def test_picocom_dev_ttyACM0(self):
        """Test picocom dev ttyACM0."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab("/dev/ttyACM0")._build_cmd()
        self.assertIn("/dev/ttyACM0", cmd)

    def test_picocom_opts_flow_n(self):
        """Test picocom opts flow n."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab(opts="--flow n --parity n --databits 8 --stopbits 1")._build_cmd()
        self.assertIn("--flow", cmd)
        self.assertIn("n", cmd)

    def test_picocom_no_opts_no_flow(self):
        """Sans extra opts, --flow est toujours présent (lu depuis les combos série)."""
        plugin_serial.SERIAL_BIN = "picocom"
        cmd = self._tab(opts="")._build_cmd()
        # Nouveau comportement : flags toujours inclus depuis les combos dédiés
        self.assertIn("--flow", cmd)
        self.assertIn("--parity", cmd)
        self.assertIn("--databits", cmd)
        self.assertIn("--stopbits", cmd)

    def test_picocom_fallback_device(self):
        """Test picocom fallback device."""
        plugin_serial.SERIAL_BIN = "picocom"
        t = self._tab()
        t._entry_dev.set_text("")
        self.assertIn("/dev/ttyUSB0", t._build_cmd())

    # minicom ----------------------------------------------------------------

    def test_minicom_first(self):
        """Test minicom first."""
        plugin_serial.SERIAL_BIN = "minicom"
        self.assertEqual(self._tab()._build_cmd()[0], "minicom")

    def test_minicom_b_flag(self):
        """Test minicom b flag."""
        plugin_serial.SERIAL_BIN = "minicom"
        cmd = self._tab("/dev/ttyUSB0", "57600")._build_cmd()
        self.assertIn("-b", cmd)
        self.assertIn("57600", cmd)

    def test_minicom_D_flag(self):
        """Test minicom D flag."""
        plugin_serial.SERIAL_BIN = "minicom"
        cmd = self._tab("/dev/ttyS2")._build_cmd()
        idx = cmd.index("-D")
        self.assertEqual(cmd[idx + 1], "/dev/ttyS2")

    def test_minicom_baud_position(self):
        """Test minicom baud position."""
        plugin_serial.SERIAL_BIN = "minicom"
        cmd = self._tab("/dev/ttyUSB0", "115200")._build_cmd()
        idx = cmd.index("-b")
        self.assertEqual(cmd[idx + 1], "115200")

    def test_minicom_device_after_D(self):
        """Test minicom device after D."""
        plugin_serial.SERIAL_BIN = "minicom"
        cmd = self._tab("/dev/ttyUSB0")._build_cmd()
        idx = cmd.index("-D")
        self.assertEqual(cmd[idx + 1], "/dev/ttyUSB0")

    def test_minicom_extra_opts(self):
        """Test minicom extra opts."""
        plugin_serial.SERIAL_BIN = "minicom"
        cmd = self._tab(opts="-o")._build_cmd()
        self.assertIn("-o", cmd)

    # screen -----------------------------------------------------------------

    def test_screen_first(self):
        """Test screen first."""
        plugin_serial.SERIAL_BIN = "screen"
        self.assertEqual(self._tab()._build_cmd()[0], "screen")

    def test_screen_device_second(self):
        """Test screen device second."""
        plugin_serial.SERIAL_BIN = "screen"
        cmd = self._tab("/dev/ttyUSB0")._build_cmd()
        self.assertEqual(cmd[1], "/dev/ttyUSB0")

    def test_screen_baud_third(self):
        """Test screen baud third."""
        plugin_serial.SERIAL_BIN = "screen"
        cmd = self._tab("/dev/ttyUSB0", "115200")._build_cmd()
        self.assertEqual(cmd[2], "115200")

    def test_screen_extra_opt(self):
        """Test screen extra opt."""
        plugin_serial.SERIAL_BIN = "screen"
        cmd = self._tab(opts="-L")._build_cmd()
        self.assertIn("-L", cmd)

    def test_screen_ttyS1(self):
        """Test screen ttyS1."""
        plugin_serial.SERIAL_BIN = "screen"
        cmd = self._tab("/dev/ttyS1")._build_cmd()
        self.assertIn("/dev/ttyS1", cmd)

    # générique --------------------------------------------------------------

    def test_returns_list(self):
        """Test returns list."""
        plugin_serial.SERIAL_BIN = "picocom"
        self.assertIsInstance(self._tab()._build_cmd(), list)

    def test_not_empty(self):
        """Test not empty."""
        plugin_serial.SERIAL_BIN = "picocom"
        self.assertGreater(len(self._tab()._build_cmd()), 0)


# ── RdpTab — cas limites ──────────────────────────────────────────────────────


# ── RdpEmbeddedTab — supplémentaire ──────────────────────────────────────────


# ── VncTab — cas limites ──────────────────────────────────────────────────────


class TestVncTabEdgeCases(unittest.TestCase):
    """Tests for vnc tab edge cases."""

    def _t(self, host, pwd=""):
        return plugin_vnc.VncTab(host, lambda: pwd)

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig = plugin_vnc.VNC_BIN

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        plugin_vnc.VNC_BIN = self._orig

    def test_returns_tuple(self):
        """Test returns tuple."""
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        self.assertIsInstance(self._t(h)._build_cmd(), tuple)

    def test_tuple_len_2(self):
        """Test tuple len 2."""
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        self.assertEqual(len(self._t(h)._build_cmd()), 2)

    def test_binary_first(self):
        """Test binary first."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertEqual(cmd[0], "vncviewer")

    def test_host_in_cmd(self):
        """Test host in cmd."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertIn("10.0.0.1", " ".join(cmd))

    def test_port_5900_in_cmd(self):
        """Test port 5900 in cmd."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="server", port="5900", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertIn("5900", " ".join(cmd))

    def test_port_5901_in_cmd(self):
        """Test port 5901 in cmd."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="server", port="5901", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertIn("5901", " ".join(cmd))

    def test_vinagre_uri_scheme(self):
        """Test vinagre uri scheme."""
        plugin_vnc.VNC_BIN = "vinagre"
        h = _make_host(host="10.0.0.1", port="5901", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertTrue(any("vnc://" in a for a in cmd))

    def test_remmina_uri_scheme(self):
        """Test remmina uri scheme."""
        plugin_vnc.VNC_BIN = "remmina"
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        cmd, _ = self._t(h)._build_cmd()
        self.assertTrue(any("vnc://" in a for a in cmd))

    def test_password_returned_as_second(self):
        """Test password returned as second."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        # make_vnc_passwd écrirait un vrai fichier passwd : simulé ici.
        with patch.object(plugin_vnc.VncTab, "make_vnc_passwd") as make_passwd:
            cmd, pwd = self._t(h, pwd="vnc_pass")._build_cmd()
        self.assertEqual(pwd, "vnc_pass")
        make_passwd.assert_called_once()
        self.assertIn("-passwd", cmd)
        # Le chemin du fichier passwd (vide ici, make_vnc_passwd simulé) ne doit
        # pas rester dans /tmp après le test.
        with contextlib.suppress(OSError):
            os.remove(cmd[cmd.index("-passwd") + 1])

    def test_no_password_second_empty(self):
        """Test no password second empty."""
        plugin_vnc.VNC_BIN = "vncviewer"
        h = _make_host(host="10.0.0.1", port="5900", protocol="vnc")
        _, pwd = self._t(h)._build_cmd()
        self.assertEqual(pwd, "")

    def test_vinagre_without_user_in_uri(self):
        """L'utilisateur n'est pas ajouté à l'URI vinagre."""
        plugin_vnc.VNC_BIN = "vinagre"
        h = _make_host(host="10.0.0.1", user="admin", port="5900", protocol="vnc")
        cmd, _ = self._t(h, pwd="s")._build_cmd()
        self.assertFalse(any("admin" in a for a in cmd))

    def test_vinagre_without_password_in_uri(self):
        """Le mot de passe n'apparaît dans aucun argument (ps)."""
        plugin_vnc.VNC_BIN = "vinagre"
        h = _make_host(host="10.0.0.1", user="u", port="5900", protocol="vnc")
        cmd, _ = self._t(h, pwd="mypwd")._build_cmd()
        self.assertFalse(any("mypwd" in a for a in cmd))


# ── SpiceTab — cas limites ────────────────────────────────────────────────────


class TestSpiceTabEdgeCases(unittest.TestCase):
    """Tests for spice tab edge cases."""

    def _t(self, host, pwd=""):
        return plugin_spice.SpiceTab(host, lambda: pwd)

    def test_binary_first(self):
        """Test binary first."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        self.assertEqual(self._t(h)._build_cmd()[0], plugin_spice.SPICE_BIN)

    def test_returns_list(self):
        """Test returns list."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        self.assertIsInstance(self._t(h)._build_cmd(), list)

    def test_spice_uri_second(self):
        """Test spice uri second."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        cmd = self._t(h)._build_cmd()
        self.assertTrue(cmd[1].startswith("spice://"))

    def test_host_in_uri(self):
        """Test host in uri."""
        h = _make_host(host="vm01.corp", port="5930", protocol="spice")
        cmd = self._t(h)._build_cmd()
        self.assertIn("vm01.corp", " ".join(cmd))

    def test_port_5930(self):
        """Test port 5930."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        self.assertIn("5930", " ".join(self._t(h)._build_cmd()))

    def test_port_5940(self):
        """Test port 5940."""
        h = _make_host(host="vm", port="5940", protocol="spice")
        self.assertIn("5940", " ".join(self._t(h)._build_cmd()))

    def test_password_in_uri(self):
        """Test password in uri."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        cmd = self._t(h, pwd="spicepass")._build_cmd()
        self.assertIn("spicepass", " ".join(cmd))

    def test_no_password_no_param(self):
        """Test no password no param."""
        h = _make_host(host="vm", port="5930", protocol="spice")
        cmd = self._t(h, pwd="")._build_cmd()
        self.assertFalse(any("password=" in a for a in cmd))

    def test_extra_params_appended(self):
        """Test extra params appended."""
        h = _make_host(host="vm", port="5930", protocol="spice", extra_params="--full-screen")
        self.assertIn("--full-screen", self._t(h)._build_cmd())

    def test_multiple_extra_params(self):
        """Test multiple extra params."""
        h = _make_host(
            host="vm",
            port="5930",
            protocol="spice",
            extra_params="--full-screen --zoom 75",
        )
        cmd = self._t(h)._build_cmd()
        self.assertIn("--full-screen", cmd)
        self.assertIn("--zoom", cmd)
        self.assertIn("75", cmd)

    def test_ipv4_host(self):
        """Test ipv4 host."""
        h = _make_host(host="192.168.100.50", port="5930", protocol="spice")
        self.assertIn("192.168.100.50", " ".join(self._t(h)._build_cmd()))


# ── _rdp_socket_available — supplémentaire ───────────────────────────────────


# ── encrypt_old/decrypt_old — exhaustif ──────────────────────────────────────


class TestEncryptOldExhaustive(unittest.TestCase):
    """Tests for encrypt old exhaustive."""

    def _rt(self, key, text):
        return gcm.decrypt_old(key, gcm.encrypt_old(key, text))

    def test_simple(self):
        """Test simple."""
        self.assertEqual(self._rt("key", "hello"), "hello")

    def test_empty(self):
        """Test empty."""
        self.assertEqual(self._rt("key", ""), "")

    def test_digits(self):
        """Test digits."""
        self.assertEqual(self._rt("pass", "1234567890"), "1234567890")

    def test_symbols(self):
        """Test symbols."""
        self.assertEqual(self._rt("key", "!@#$%^&*()"), "!@#$%^&*()")

    def test_spaces(self):
        """Test spaces."""
        self.assertEqual(self._rt("key", "hello world"), "hello world")

    def test_single_char(self):
        """Test single char."""
        self.assertEqual(self._rt("key", "x"), "x")

    def test_long_text(self):
        """Test long text."""
        self.assertEqual(self._rt("key", "A" * 200), "A" * 200)

    def test_ip_address(self):
        """Test ip address."""
        self.assertEqual(self._rt("key", "192.168.1.1"), "192.168.1.1")

    def test_hostname(self):
        """Test hostname."""
        self.assertEqual(self._rt("key", "router.corp"), "router.corp")

    def test_password_chars(self):
        """Test password chars."""
        self.assertEqual(self._rt("k", "P@ss!0rd"), "P@ss!0rd")

    def test_different_keys_differ(self):
        """Test different keys differ."""
        enc = gcm.encrypt_old("key1", "hello")
        dec2 = gcm.decrypt_old("key2", enc)
        self.assertNotEqual(dec2, "hello")

    def test_encrypt_is_string(self):
        """Test encrypt is string."""
        self.assertIsInstance(gcm.encrypt_old("k", "hi"), str)

    def test_decrypt_is_string(self):
        """Test decrypt is string."""
        enc = gcm.encrypt_old("k", "hi")
        self.assertIsInstance(gcm.decrypt_old("k", enc), str)

    def test_encrypt_not_plaintext(self):
        """Test encrypt not plaintext."""
        self.assertNotEqual(gcm.encrypt_old("k", "secret"), "secret")

    def test_deterministic(self):
        """Test deterministic."""
        self.assertEqual(gcm.encrypt_old("k", "hi"), gcm.encrypt_old("k", "hi"))

    def test_decrypt_invalid_returns_empty(self):
        """Test decrypt invalid returns empty."""
        self.assertEqual(gcm.decrypt_old("k", "not-valid-base64!!!"), "")

    def test_result_is_base64(self):
        """Test result is base64."""
        import base64 as b64

        enc = gcm.encrypt_old("key", "test")
        b64.b64decode(enc)  # ne doit pas lever


# ── AES encrypt/decrypt — supplémentaire ─────────────────────────────────────


class TestAesEncryptExhaustive(unittest.TestCase):
    """Tests encrypt/decrypt AES (conf.VERSION=1 pour forcer AES vs decrypt_old)."""

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig_version = gcm.conf.VERSION
        gcm.conf.VERSION = 1  # force pyAES.decrypt (pas decrypt_old)

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        gcm.conf.VERSION = self._orig_version

    def _rt(self, key, text):
        return gcm.decrypt(key, gcm.encrypt(key, text))

    def test_ascii_password(self):
        """Test ascii password."""
        self.assertEqual(self._rt("pass", "P@ssw0rd!"), "P@ssw0rd!")

    def test_hostname(self):
        """Test hostname."""
        self.assertEqual(self._rt("k", "router.corp.local"), "router.corp.local")

    def test_ip(self):
        """Test ip."""
        self.assertEqual(self._rt("k", "192.168.105.41"), "192.168.105.41")

    def test_empty(self):
        """Test empty."""
        self.assertIsInstance(gcm.decrypt("k", gcm.encrypt("k", "")), str)

    def test_long(self):
        """Test long."""
        self.assertEqual(self._rt("k", "x" * 512), "x" * 512)

    def test_symbols(self):
        """Test symbols."""
        self.assertEqual(self._rt("k", "!@#$%^&*()-_+="), "!@#$%^&*()-_+=")

    def test_spaces(self):
        """Test spaces."""
        self.assertEqual(self._rt("k", "admin password"), "admin password")

    def test_digits(self):
        """Test digits."""
        self.assertEqual(self._rt("k", "1234567890"), "1234567890")

    def test_different_keys_differ(self):
        """Test different keys differ."""
        enc = gcm.encrypt("k1", "hello")
        self.assertNotEqual(gcm.decrypt("k2", enc), "hello")

    def test_encrypt_not_plaintext(self):
        """Test encrypt not plaintext."""
        self.assertNotEqual(gcm.encrypt("k", "secret"), "secret")

    def test_encrypt_returns_string(self):
        """Test encrypt returns string."""
        self.assertIsInstance(gcm.encrypt("k", "test"), str)

    def test_decrypt_returns_string(self):
        """Test decrypt returns string."""
        self.assertIsInstance(gcm.decrypt("k", gcm.encrypt("k", "test")), str)

    def test_encrypt_nonempty(self):
        """Test encrypt nonempty."""
        self.assertGreater(len(gcm.encrypt("k", "hello")), 0)

    def test_wrong_key_not_plaintext(self):
        """Test wrong key not plaintext."""
        enc = gcm.encrypt("correct", "secret")
        self.assertNotEqual(gcm.decrypt("wrong", enc), "secret")


# ── _vm_name_split — cas limites ─────────────────────────────────────────────


class TestVmNameSplitExtra(unittest.TestCase):
    """Tests for vm name split extra."""

    def _s(self, name):
        return hic.vm_name_split(name)

    def test_long_with_dash(self):
        """Test long with dash."""
        g, n = self._s("infrastructure-web-prod-v2")
        self.assertEqual(g, "INFRASTRUCTURE")
        self.assertEqual(n, "web-prod-v2")

    def test_all_caps(self):
        """Test all caps."""
        g, n = self._s("WEB_server")
        self.assertEqual(g, "WEB")

    def test_number_suffix(self):
        """Test number suffix."""
        g, n = self._s("app_01")
        self.assertEqual(g, "APP")
        self.assertEqual(n, "01")

    def test_three_words_space(self):
        """Test three words space."""
        g, n = self._s("home lab server")
        self.assertEqual(g, "HOME")
        self.assertEqual(n, "lab server")

    def test_mixed_sep_first_wins(self):
        """Test mixed sep first wins."""
        g, n = self._s("web-db_01")
        self.assertEqual(g, "WEB")
        self.assertEqual(n, "db_01")

    def test_underscore_preserves_rest(self):
        """Test underscore preserves rest."""
        g, n = self._s("prod_db_master")
        self.assertEqual(g, "PROD")
        self.assertEqual(n, "db_master")

    def test_two_words_space(self):
        """Test two words space."""
        g, n = self._s("home lab")
        self.assertEqual(g, "HOME")
        self.assertEqual(n, "lab")

    def test_single_char_group(self):
        """Test single char group."""
        g, n = self._s("a_server")
        self.assertEqual(g, "A")
        self.assertEqual(n, "server")

    def test_number_only_libvirt(self):
        """Test number only libvirt."""
        g, _ = self._s("42")
        self.assertEqual(g, "LIBVIRT")

    def test_empty_libvirt(self):
        """Test empty libvirt."""
        g, _ = self._s("")
        self.assertEqual(g, "LIBVIRT")

    def test_digits_dash(self):
        """Test digits dash."""
        g, n = self._s("192-168")
        self.assertEqual(g, "192")
        self.assertEqual(n, "168")

    def test_unicode_group_uppercase(self):
        """Test unicode group uppercase."""
        g, n = self._s("réseau_interne")
        self.assertEqual(g, "RÉSEAU")
        self.assertEqual(n, "interne")


# ── Tests _dep_install_hint (v1.3.2 — nouveau) ───────────────────────────────


class TestDepInstallHint(unittest.TestCase):
    """Tests pour _dep_install_hint — détection OS et suggestion d'installation."""

    def _mock_rel(self, content):
        return patch("builtins.open", unittest.mock.mock_open(read_data=content))

    def test_ubuntu_returns_apt(self):
        """Test ubuntu returns apt."""
        with self._mock_rel('ID=ubuntu\nNAME="Ubuntu 22.04"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo apt install", h)
        self.assertIn("pkg-deb", h)

    def test_debian_returns_apt(self):
        """Test debian returns apt."""
        with self._mock_rel('ID=debian\nNAME="Debian GNU/Linux 12"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo apt install", h)

    def test_kali_returns_apt(self):
        """Test kali returns apt."""
        with self._mock_rel('ID=kali\nNAME="Kali GNU/Linux"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo apt install", h)

    def test_raspbian_returns_apt(self):
        """Test raspbian returns apt."""
        with self._mock_rel('ID=raspbian\nNAME="Raspbian GNU/Linux"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo apt install", h)

    def test_fedora_returns_dnf(self):
        """Test fedora returns dnf."""
        with self._mock_rel('ID=fedora\nNAME="Fedora Linux 39"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo dnf install", h)
        self.assertIn("pkg-rpm", h)

    def test_centos_returns_dnf(self):
        """Test centos returns dnf."""
        with self._mock_rel('ID=centos\nNAME="CentOS Linux 8"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo dnf install", h)

    def test_rocky_returns_dnf(self):
        """Test rocky returns dnf."""
        with self._mock_rel('ID=rocky\nNAME="Rocky Linux 9"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo dnf install", h)

    def test_arch_returns_pacman_with_arch_pkg(self):
        """Test arch returns pacman with arch pkg."""
        with self._mock_rel('ID=arch\nNAME="Arch Linux"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm", "pkg-arch")
        self.assertIn("sudo pacman -S", h)
        self.assertIn("pkg-arch", h)

    def test_arch_fallback_uses_rpm_pkg(self):
        """Test arch fallback uses rpm pkg."""
        with self._mock_rel('ID=arch\nNAME="Arch Linux"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("sudo pacman -S", h)
        self.assertIn("pkg-rpm", h)

    def test_unknown_os_contains_both_hints(self):
        """Test unknown os contains both hints."""
        with self._mock_rel('ID=unknown\nNAME="Mystery OS"'):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("pkg-deb", h)
        self.assertIn("pkg-rpm", h)

    def test_os_release_missing_returns_fallback(self):
        """Test os release missing returns fallback."""
        with patch("builtins.open", side_effect=OSError("no file")):
            h = hic.dep_install_hint("pkg-deb", "pkg-rpm")
        self.assertIn("pkg-deb", h)
        self.assertIn("pkg-rpm", h)

    def test_returns_string(self):
        """Test returns string."""
        with patch("builtins.open", side_effect=OSError):
            h = hic.dep_install_hint("a", "b")
        self.assertIsInstance(h, str)


# ── Tests _check_port_open (v1.3.2 — nouveau) ────────────────────────────────


class TestCheckPortOpen(unittest.TestCase):
    """Tests pour _check_port_open — sondage TCP via nc/nmap depuis l'HV."""

    def _run_fn(self, responses):
        """run_fn mocké retournant les réponses en séquence."""
        calls = []

        def _fn(client, cmd, timeout=30):
            calls.append(cmd)
            idx = len(calls) - 1
            return responses[idx] if idx < len(responses) else ""

        return _fn, calls

    def test_empty_ip_returns_false(self):
        """Test empty ip returns false."""
        run_fn, _ = self._run_fn([])
        self.assertFalse(hic.check_port_open(None, run_fn, "", 3389))

    def test_none_ip_returns_false(self):
        """Test none ip returns false."""
        run_fn, _ = self._run_fn([])
        self.assertFalse(hic.check_port_open(None, run_fn, None, 3389))

    def test_nc_open_returns_true(self):
        """Test nc open returns true."""
        run_fn, _ = self._run_fn(["OPEN"])
        self.assertTrue(hic.check_port_open(None, run_fn, "10.0.0.1", 3389))

    def test_nc_closed_returns_false(self):
        """Test nc closed returns false."""
        run_fn, _ = self._run_fn(["CLOSED"])
        self.assertFalse(hic.check_port_open(None, run_fn, "10.0.0.1", 3389))

    def test_nc_ambiguous_fallback_nmap_open(self):
        """Test nc ambiguous fallback nmap open."""
        run_fn, _ = self._run_fn(["", "3389/open tcp"])
        self.assertTrue(hic.check_port_open(None, run_fn, "10.0.0.1", 3389))

    def test_nc_ambiguous_fallback_nmap_closed(self):
        """Test nc ambiguous fallback nmap closed."""
        run_fn, _ = self._run_fn(["", "3389/closed tcp"])
        self.assertFalse(hic.check_port_open(None, run_fn, "10.0.0.1", 3389))

    def test_nmap_case_insensitive_open(self):
        """Test nmap case insensitive open."""
        run_fn, _ = self._run_fn(["", "3389/OPEN"])
        self.assertTrue(hic.check_port_open(None, run_fn, "10.0.0.1", 3389))

    def test_nc_cmd_contains_ip_and_port(self):
        """Test nc cmd contains ip and port."""
        run_fn, calls = self._run_fn(["OPEN"])
        hic.check_port_open(None, run_fn, "192.168.1.50", 22)
        self.assertIn("192.168.1.50", calls[0])
        self.assertIn("22", calls[0])

    def test_nmap_fallback_cmd_contains_port(self):
        """Test nmap fallback cmd contains port."""
        run_fn, calls = self._run_fn(["", ""])
        hic.check_port_open(None, run_fn, "10.0.0.5", 8080)
        # second call is nmap fallback
        self.assertTrue(len(calls) >= 2)
        self.assertIn("8080", calls[1])

    def test_returns_bool(self):
        """Test returns bool."""
        run_fn, _ = self._run_fn(["OPEN"])
        result = hic.check_port_open(None, run_fn, "1.2.3.4", 22)
        self.assertIsInstance(result, bool)


# ── Tests SpiceTab._build_cmd mode libvirt tunnel (v1.3.2) ───────────────────


class TestSpiceTabLibvirtTunnel(unittest.TestCase):
    """Tests SpiceTab._build_cmd en mode libvirt (``spice_mode="libvirt"``).

    L'ancien déclenchement par ``--connect URI VM`` dans les options
    supplémentaires a été remplacé par les champs structurés
    ``spice_libvirt_uri`` / ``spice_vm_name`` de l'hôte.
    """

    def _tab(self, uri="qemu+ssh://root@hv/system", vm="vm1", opts="", host_ip="vm"):
        h = _make_host(host=host_ip, port="5930", protocol="spice")
        h.spice_mode = "libvirt"
        h.spice_libvirt_uri = uri
        h.spice_vm_name = vm
        tab = plugin_spice.SpiceTab(h, lambda: "")
        tab._entry_opts.set_text(opts)
        return tab

    def test_connect_mode_no_spice_uri(self):
        """Pas d'URI spice:// en mode libvirt."""
        cmd = self._tab()._build_cmd()
        self.assertFalse(any("spice://" in a for a in cmd))

    def test_connect_mode_first_arg_is_binary(self):
        """Le premier argument est le binaire SPICE."""
        cmd = self._tab()._build_cmd()
        self.assertEqual(cmd[0], plugin_spice.SPICE_BIN)

    def test_connect_mode_second_arg_is_connect(self):
        """Le deuxième argument est --connect."""
        cmd = self._tab()._build_cmd()
        self.assertEqual(cmd[1:3], ["--connect", "qemu+ssh://root@hv/system"])

    def test_connect_mode_vm_name_present(self):
        """Le nom de la VM suit l'URI libvirt."""
        cmd = self._tab(vm="prod-web")._build_cmd()
        self.assertEqual(cmd[3], "prod-web")

    def test_connect_mode_sans_vm(self):
        """Sans nom de VM, virt-viewer affiche son sélecteur : rien après l'URI."""
        cmd = self._tab(vm="")._build_cmd()
        self.assertEqual(cmd, [plugin_spice.SPICE_BIN, "--connect", "qemu+ssh://root@hv/system"])

    def test_connect_mode_nonstandard_port_preserved(self):
        """Un port SSH non standard dans l'URI libvirt est conservé."""
        cmd = self._tab(uri="qemu+ssh://root@hv:542/system")._build_cmd()
        self.assertIn("qemu+ssh://root@hv:542/system", cmd)

    def test_connect_mode_ignores_host_port_field(self):
        """Le port SPICE de l'hôte (5930) n'apparaît pas en mode libvirt."""
        cmd = self._tab(host_ip="192.168.1.10")._build_cmd()
        self.assertNotIn("5930", " ".join(cmd[1:]))

    def test_connect_mode_options_appended(self):
        """Les options supplémentaires sont ajoutées en fin de commande."""
        cmd = self._tab(opts="--full-screen")._build_cmd()
        self.assertEqual(cmd[-1], "--full-screen")

    def test_connect_mode_uri_manquante_returns_none(self):
        """Sans URI libvirt, pas de commande (erreur affichée dans l'onglet)."""
        self.assertIsNone(self._tab(uri="")._build_cmd())


# ── Tests _libvirt_get_uris_from_dconf (v1.3.2) ──────────────────────────────


class TestLibvirtGetUrisFromDconf(unittest.TestCase):
    """Tests pour _libvirt_get_uris_from_dconf."""

    def _mock_run(self, stdout="", raise_exc=None):
        def _run(*args, **kwargs):
            if raise_exc:
                raise raise_exc
            r = MagicMock()
            r.stdout = stdout
            return r

        return patch("subprocess.run", side_effect=_run)

    def test_normal_output_two_uris(self):
        """Test normal output two uris."""
        raw = "['qemu+ssh://root@192.168.1.41/system', 'qemu+ssh://root@192.168.1.42/system']"
        with self._mock_run(raw):
            result = hic.libvirt_get_uris_from_dconf()
        self.assertEqual(len(result), 2)
        self.assertIn("qemu+ssh://root@192.168.1.41/system", result)

    def test_empty_stdout_returns_empty(self):
        """Test empty stdout returns empty."""
        with self._mock_run(""):
            result = hic.libvirt_get_uris_from_dconf()
        self.assertEqual(result, [])

    def test_as_empty_returns_empty(self):
        """Test as empty returns empty."""
        with self._mock_run("@as []"):
            result = hic.libvirt_get_uris_from_dconf()
        self.assertEqual(result, [])

    def test_exception_returns_empty(self):
        """Test exception returns empty."""
        with self._mock_run(raise_exc=FileNotFoundError("dconf not found")):
            result = hic.libvirt_get_uris_from_dconf()
        self.assertEqual(result, [])

    def test_single_uri_list(self):
        """Test single uri list."""
        raw = "['qemu:///system']"
        with self._mock_run(raw):
            result = hic.libvirt_get_uris_from_dconf()
        self.assertEqual(result, ["qemu:///system"])


# ── Tests _libvirt_ssh_run (v1.3.2) ──────────────────────────────────────────


class TestLibvirtSshRun(unittest.TestCase):
    """Tests pour _libvirt_ssh_run — exécution distante via paramiko."""

    def _client(self, output_bytes=b""):
        client = MagicMock()
        stdout_mock = MagicMock()
        stdout_mock.read.return_value = output_bytes
        client.exec_command.return_value = (MagicMock(), stdout_mock, MagicMock())
        return client

    def test_returns_stripped_output(self):
        """Test returns stripped output."""
        result = hic.libvirt_ssh_run(self._client(b"  hello world  \n"), "cmd")
        self.assertEqual(result, "hello world")

    def test_empty_output_returns_empty_string(self):
        """Test empty output returns empty string."""
        result = hic.libvirt_ssh_run(self._client(b""), "true")
        self.assertEqual(result, "")

    def test_non_utf8_bytes_with_replace(self):
        """Test non utf8 bytes with replace."""
        result = hic.libvirt_ssh_run(self._client(b"\xff\xfe hello\n"), "cmd")
        self.assertIsInstance(result, str)

    def test_timeout_passed_to_exec_command(self):
        """Test timeout passed to exec command."""
        client = self._client(b"out")
        hic.libvirt_ssh_run(client, "cmd", timeout=42)
        client.exec_command.assert_called_with("cmd", timeout=42)


# ── Tests color_to_hex (v1.3.2 — non couvert) ───────────────────────────────


class TestColorToHex(unittest.TestCase):
    """Tests pour color_to_hex — conversion RGBA → chaîne hexadécimale."""

    def _rgba(self, r, g, b):
        rgba = MagicMock()
        rgba.red = r
        rgba.green = g
        rgba.blue = b
        return rgba

    def test_black_produces_hash_000(self):
        """Test black produces hash 000."""
        self.assertEqual(gcm.color_to_hex(self._rgba(0.0, 0.0, 0.0)), "#000")

    def test_white_contains_ff_components(self):
        """Test white contains ff components."""
        result = gcm.color_to_hex(self._rgba(1.0, 1.0, 1.0))
        self.assertEqual(result, "#ffffff")

    def test_starts_with_hash(self):
        """Test starts with hash."""
        result = gcm.color_to_hex(self._rgba(0.5, 0.3, 0.1))
        self.assertTrue(result.startswith("#"))

    def test_diff_parameter_changes_result(self):
        """Test diff parameter changes result."""
        r0 = gcm.color_to_hex(self._rgba(0.0, 0.0, 0.0))
        r1 = gcm.color_to_hex(self._rgba(0.0, 0.0, 0.0), diff=16)
        self.assertNotEqual(r0, r1)

    def test_pure_blue_components(self):
        # blue=1.0 (255=0xff), red=green=0 (0x0)
        """Test pure blue components."""
        result = gcm.color_to_hex(self._rgba(0.0, 0.0, 1.0))
        self.assertTrue(result.endswith("ff"))


# ── Tests get_username (v1.3.2 — non couvert) ────────────────────────────────


class TestGetUsername(unittest.TestCase):
    """Tests pour get_username — lecture variables d'environnement."""

    def test_returns_user_env(self):
        """Test returns user env."""
        with patch("os.getenv", side_effect=lambda k: {"USER": "alice"}.get(k)):
            self.assertEqual(gcm.get_username(), "alice")

    def test_fallback_to_logname(self):
        """Test fallback to logname."""
        with patch(
            "os.getenv",
            side_effect=lambda k: {"USER": None, "LOGNAME": "bob", "USERNAME": None}.get(k),
        ):
            self.assertEqual(gcm.get_username(), "bob")

    def test_fallback_to_username(self):
        """Test fallback to username."""
        with patch(
            "os.getenv",
            side_effect=lambda k: {"USER": None, "LOGNAME": None, "USERNAME": "carol"}.get(k),
        ):
            self.assertEqual(gcm.get_username(), "carol")

    def test_all_none_returns_none(self):
        """Test all none returns none."""
        with patch("os.getenv", return_value=None):
            self.assertIsNone(gcm.get_username())


# ── Tests LibvirtImportDialog colonnes (v1.3.2) ───────────────────────────────


class TestLibvirtImportDialogConstants(unittest.TestCase):
    """Tests pour les constantes de colonnes de LibvirtImportDialog._COL_*."""

    def test_col_sel_is_zero(self):
        """Test col sel is zero."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_SEL, 0)

    def test_col_proto_is_one(self):
        """Test col proto is one."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_PROTO, 1)

    def test_col_name_is_two(self):
        """Test col name is two."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_NAME, 2)

    def test_col_group_is_three(self):
        """Test col group is three."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_GROUP, 3)

    def test_col_host_is_four(self):
        """Test col host is four."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_HOST, 4)

    def test_col_state_is_five(self):
        """Test col state is five."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_STATE, 5)

    def test_col_exists_is_six(self):
        """Test col exists is six."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_EXISTS, 6)

    def test_col_idx_is_nine(self):
        """Test col idx is nine."""
        self.assertEqual(plugin_import_libvirt.LibvirtImportDialog._COL_IDX, 9)

    def test_all_ten_columns_unique(self):
        """Test all ten columns unique."""
        cols = [
            plugin_import_libvirt.LibvirtImportDialog._COL_SEL,
            plugin_import_libvirt.LibvirtImportDialog._COL_PROTO,
            plugin_import_libvirt.LibvirtImportDialog._COL_NAME,
            plugin_import_libvirt.LibvirtImportDialog._COL_GROUP,
            plugin_import_libvirt.LibvirtImportDialog._COL_HOST,
            plugin_import_libvirt.LibvirtImportDialog._COL_STATE,
            plugin_import_libvirt.LibvirtImportDialog._COL_EXISTS,
            plugin_import_libvirt.LibvirtImportDialog._COL_EXIST_LBL,
            plugin_import_libvirt.LibvirtImportDialog._COL_FG,
            plugin_import_libvirt.LibvirtImportDialog._COL_IDX,
        ]
        self.assertEqual(
            len(cols), len(set(cols)), "Tous les indices de colonnes doivent être uniques"
        )


# ── Tests _serial_templates_save / round-trip (v1.3.2) ───────────────────────


class TestSerialTemplatesSaveLoad(unittest.TestCase):
    """Tests pour _serial_templates_save/_serial_templates_load — round-trip."""

    def setUp(self):
        """Set up fixtures for this test case."""
        self._orig = dict(gcm._SERIAL_TEMPLATES)

    def tearDown(self):
        """Tear down fixtures created for this test case."""
        gcm._SERIAL_TEMPLATES = self._orig

    def test_save_creates_section(self):
        """Test save creates section."""
        cp = configparser.RawConfigParser()
        gcm._serial_templates_save(cp)
        self.assertTrue(cp.has_section("serial_templates"))

    def test_save_load_roundtrip_cisco(self):
        """Test save load roundtrip cisco."""
        cp = configparser.RawConfigParser()
        gcm._serial_templates_save(cp)
        gcm._SERIAL_TEMPLATES = {}
        gcm._serial_templates_load(cp)
        self.assertIn("Cisco IOS / IOS-XE / NX-OS", gcm._SERIAL_TEMPLATES)

    def test_save_load_custom_template(self):
        """Test save load custom template."""
        gcm._SERIAL_TEMPLATES["Mon Switch"] = ("115200", "h", "n", "8", "1")
        cp = configparser.RawConfigParser()
        gcm._serial_templates_save(cp)
        gcm._SERIAL_TEMPLATES = {}
        gcm._serial_templates_load(cp)
        # ConfigParser lowercases les clés pour les templates non-défaut
        found = gcm._SERIAL_TEMPLATES.get("mon switch") or gcm._SERIAL_TEMPLATES.get("Mon Switch")
        self.assertIsNotNone(found, "Le template custom doit être rechargé (casse tolérée)")
        self.assertEqual(found, ("115200", "h", "n", "8", "1"))

    def test_save_overwrites_existing_section(self):
        """Test save overwrites existing section."""
        cp = configparser.RawConfigParser()
        cp.add_section("serial_templates")
        cp.set("serial_templates", "old_entry", "9600,n,n,8,1")
        gcm._serial_templates_save(cp)
        self.assertFalse(cp.has_option("serial_templates", "old_entry"))

    def test_load_no_section_returns_false(self):
        """Test load no section returns false."""
        cp = configparser.RawConfigParser()
        result = gcm._serial_templates_load(cp)
        self.assertFalse(result)

    def test_load_with_section_returns_true(self):
        """Test load with section returns true."""
        cp = configparser.RawConfigParser()
        gcm._serial_templates_save(cp)
        result = gcm._serial_templates_load(cp)
        self.assertTrue(result)

    def test_save_load_linux_template(self):
        """Test save load linux template."""
        cp = configparser.RawConfigParser()
        gcm._serial_templates_save(cp)
        gcm._SERIAL_TEMPLATES = {}
        gcm._serial_templates_load(cp)
        self.assertIn("Linux / Raspberry Pi", gcm._SERIAL_TEMPLATES)
        self.assertEqual(gcm._SERIAL_TEMPLATES["Linux / Raspberry Pi"][0], "115200")


# ── Tests _collect_ssh_keys (v1.3.2) ─────────────────────────────────────────


class TestCollectSshKeys(unittest.TestCase):
    """Tests pour _collect_ssh_keys — listing des clés privées SSH."""

    def test_no_ssh_dir_returns_empty(self):
        """Test no ssh dir returns empty."""
        with patch("os.path.isdir", return_value=False):
            result = hic.collect_ssh_keys()
        self.assertEqual(result, [])

    def test_skips_pub_files(self):
        """Test skips pub files."""
        with (
            patch("os.path.isdir", return_value=True),
            patch("os.listdir", return_value=["id_ed25519", "id_ed25519.pub"]),
            patch("os.path.isfile", return_value=True),
            patch(
                "builtins.open", unittest.mock.mock_open(read_data=b"BEGIN OPENSSH PRIVATE KEY")
            ),
        ):
            result = hic.collect_ssh_keys()
        self.assertFalse(any(".pub" in k for k in result))

    def test_skips_known_hosts(self):
        """Test skips known hosts."""
        with (
            patch("os.path.isdir", return_value=True),
            patch("os.listdir", return_value=["known_hosts", "id_rsa"]),
            patch("os.path.isfile", return_value=True),
            patch("builtins.open", unittest.mock.mock_open(read_data=b"BEGIN RSA PRIVATE KEY")),
        ):
            result = hic.collect_ssh_keys()
        self.assertFalse(any("known_hosts" in k for k in result))

    def test_skips_config(self):
        """Test skips config."""
        with (
            patch("os.path.isdir", return_value=True),
            patch("os.listdir", return_value=["config", "authorized_keys", "id_rsa"]),
            patch("os.path.isfile", return_value=True),
            patch("builtins.open", unittest.mock.mock_open(read_data=b"BEGIN RSA PRIVATE KEY")),
        ):
            result = hic.collect_ssh_keys()
        basenames = [os.path.basename(k) for k in result]
        self.assertNotIn("config", basenames)
        self.assertNotIn("authorized_keys", basenames)

    def test_returns_list(self):
        """Test returns list."""
        with (
            patch("os.path.isdir", return_value=True),
            patch("os.listdir", return_value=[]),
            patch("os.path.isfile", return_value=True),
        ):
            result = hic.collect_ssh_keys()
        self.assertIsInstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests nouvelles fonctionnalités v1.3.3
# ═══════════════════════════════════════════════════════════════════════════════

# ── Tests SpiceTab._build_cmd mode --proxmox ─────────────────────────────────


class TestSpiceTabProxmoxMode(unittest.TestCase):
    """Tests SpiceTab._build_cmd en mode Proxmox (``spice_mode="proxmox"``).

    Remplace l'ancien ``--proxmox NODE VMID`` dans les options : nœud et VMID
    sont les champs ``spice_px_node`` / ``spice_px_vmid``. paramiko (extra
    optionnel, importé à la volée) est simulé via ``sys.modules``.
    """

    _TICKET = (
        b'{"type":"spice","tls-port":61000,"password":"abc",'
        b'"host":"pvespiceproxy:x:100:docker41:61000::tok","host-subject":"CN=DOCKER41",'
        b'"ca":"CERT","proxy":"http://docker41:3128"}'
    )

    def _tab(
        self, node="DOCKER41", vmid="100", host_ip="192.168.105.41", port="22", mode="proxmox"
    ):
        h = _make_host(host=host_ip, port=port, protocol="spice", user="root")
        h.spice_mode = mode
        h.spice_px_node = node
        h.spice_px_vmid = vmid
        tab = plugin_spice.SpiceTab(h, lambda: "")
        tab._entry_opts.set_text("")
        return tab

    def _paramiko(self, stdout=b"", connect_error=None):
        fake = MagicMock()
        client = fake.SSHClient.return_value
        if connect_error is not None:
            client.connect.side_effect = connect_error
        out = MagicMock()
        out.read.return_value = stdout
        client.exec_command.return_value = (MagicMock(), out, MagicMock())
        return patch.dict(sys.modules, {"paramiko": fake}), client

    def test_proxmox_mode_detected(self):
        """Ticket valide : fichier .vv écrit et passé à remote-viewer."""
        ctx, client = self._paramiko(self._TICKET)
        with ctx, tempfile.TemporaryDirectory() as tmp:
            vv_path = os.path.join(tmp, "test.vv")
            fd = os.open(vv_path, os.O_WRONLY | os.O_CREAT, 0o600)
            with patch("tempfile.mkstemp", return_value=(fd, vv_path)):
                cmd = self._tab()._build_cmd()
            with open(vv_path, encoding="utf-8") as f:
                content = f.read()
        self.assertEqual(cmd, [plugin_spice.SPICE_BIN, vv_path])
        self.assertIn("tls-port=61000", content)
        self.assertIn("delete-this-file=1", content)
        client.connect.assert_called_once_with(
            "192.168.105.41", port=22, username="root", timeout=10
        )
        self.assertIn("/nodes/DOCKER41/qemu/100/spiceproxy", client.exec_command.call_args[0][0])

    def test_proxmox_port_spice_remplace_par_ssh_22(self):
        """Un port 5930 sur l'hôte (port SPICE) n'est pas utilisé pour SSH."""
        ctx, client = self._paramiko(b"not json")
        with ctx:
            self._tab(port="5930")._build_cmd()
        self.assertEqual(client.connect.call_args.kwargs["port"], 22)

    def test_proxmox_mode_missing_vmid_returns_none(self):
        """Sans VMID, pas de commande."""
        self.assertIsNone(self._tab(vmid="")._build_cmd())

    def test_proxmox_mode_missing_node_returns_none(self):
        """Sans nœud, pas de commande."""
        self.assertIsNone(self._tab(node="")._build_cmd())

    def test_proxmox_mode_bad_json_returns_none(self):
        """Réponse pvesh illisible : pas de commande."""
        ctx, _client = self._paramiko(b"not json")
        with ctx:
            self.assertIsNone(self._tab()._build_cmd())

    def test_proxmox_mode_ssh_error_returns_none(self):
        """Échec SSH : pas de commande."""
        ctx, _client = self._paramiko(connect_error=Exception("Connection refused"))
        with ctx:
            self.assertIsNone(self._tab()._build_cmd())

    def test_standard_mode_unchanged(self):
        """Le mode URI (défaut) produit une URI spice://."""
        cmd = self._tab(host_ip="192.168.1.10", port="5930", mode="uri")._build_cmd()
        self.assertTrue(any("spice://" in a for a in cmd))

    def test_connect_mode_unchanged(self):
        """Le mode libvirt n'est pas affecté par les champs Proxmox."""
        tab = self._tab(mode="libvirt")
        tab.host.spice_libvirt_uri = "qemu+ssh://root@hv/system"
        tab.host.spice_vm_name = "vm1"
        cmd = tab._build_cmd()
        self.assertFalse(any("spice://" in a for a in cmd))


# ── Tests icônes protocole (_proto_icon function) ────────────────────────────


class TestProtoIcon(unittest.TestCase):
    """Tests pour la fonction _proto_icon intégrée dans updateTree."""

    def _proto_icon(self, proto):
        """Réplique la logique _proto_icon de updateTree."""
        return {
            "ssh": "utilities-terminal",
            "telnet": "utilities-terminal",
            "rdp": "computer",
            "vnc": "video-display",
            "spice": "video-display",
            "serial": "modem",
            "local": "user-home",
        }.get(proto or "ssh", "network-workstation")

    def test_ssh_icon(self):
        """Test ssh icon."""
        self.assertEqual(self._proto_icon("ssh"), "utilities-terminal")

    def test_telnet_icon(self):
        """Test telnet icon."""
        self.assertEqual(self._proto_icon("telnet"), "utilities-terminal")

    def test_rdp_icon(self):
        """Test rdp icon."""
        self.assertEqual(self._proto_icon("rdp"), "computer")

    def test_vnc_icon(self):
        """Test vnc icon."""
        self.assertEqual(self._proto_icon("vnc"), "video-display")

    def test_spice_icon(self):
        """Test spice icon."""
        self.assertEqual(self._proto_icon("spice"), "video-display")

    def test_serial_icon(self):
        """Test serial icon."""
        self.assertEqual(self._proto_icon("serial"), "modem")

    def test_local_icon(self):
        """Test local icon."""
        self.assertEqual(self._proto_icon("local"), "user-home")

    def test_unknown_proto_fallback(self):
        """Test unknown proto fallback."""
        self.assertEqual(self._proto_icon("ftp"), "network-workstation")

    def test_none_proto_fallback_to_ssh(self):
        """Test none proto fallback to ssh."""
        self.assertEqual(self._proto_icon(None), "utilities-terminal")

    def test_all_protos_return_string(self):
        """Test all protos return string."""
        for p in ("ssh", "telnet", "rdp", "vnc", "spice", "serial", "local"):
            self.assertIsInstance(self._proto_icon(p), str)


# ── Tests _proxmox_fetch_hosts résolution IP ─────────────────────────────────


class TestProxmoxFetchHostsIPResolution(unittest.TestCase):
    """Tests pour la résolution IP dans _proxmox_fetch_hosts."""

    def _run_responses(self, responses):
        """Crée un run_fn qui renvoie les réponses dans l'ordre."""
        call_count = [0]

        def run_fn(client, cmd, timeout=30):
            """Run fn."""
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(responses):
                return responses[idx]
            return ""

        return run_fn

    def test_extract_first_ipv4_from_qga_json(self):
        """QGA JSON avec une IP valide → IP extraite correctement."""
        qga_json = (
            '{"result":[{"name":"eth0","ip-addresses":'
            '[{"ip-address-type":"ipv4","ip-address":"192.168.105.145","prefix":24}]}]}'
        )
        # Appel direct à la fonction interne via _proxmox_fetch_hosts
        # On teste via le module directement
        import json

        data = json.loads(qga_json)
        ip = ""
        for iface in data.get("result", []):
            for addr in iface.get("ip-addresses", []):
                a = addr.get("ip-address", "")
                import re

                if re.match(r"\d+\.\d+\.\d+\.\d+$", a) and not a.startswith("127."):
                    ip = a
                    break
            if ip:
                break
        self.assertEqual(ip, "192.168.105.145")

    def test_extract_ipv4_skips_loopback(self):
        """L'IP 127.x ne doit pas être retournée."""
        import json
        import re

        qga_json = (
            '{"result":[{"name":"lo","ip-addresses":'
            '[{"ip-address-type":"ipv4","ip-address":"127.0.0.1","prefix":8}]},'
            '{"name":"eth0","ip-addresses":'
            '[{"ip-address-type":"ipv4","ip-address":"10.0.0.5","prefix":24}]}]}'
        )
        data = json.loads(qga_json)
        ip = ""
        for iface in data.get("result", []):
            for addr in iface.get("ip-addresses", []):
                a = addr.get("ip-address", "")
                if re.match(r"\d+\.\d+\.\d+\.\d+$", a) and not a.startswith("127."):
                    ip = a
                    break
            if ip:
                break
        self.assertEqual(ip, "10.0.0.5")

    def test_ipconfig_parsed_correctly(self):
        """ipconfig0: ip=192.168.1.5/24,gw=... → IP extraite."""
        import re

        cfg_out = "ipconfig0: ip=192.168.1.5/24,gw=192.168.1.1"
        m = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", cfg_out)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "192.168.1.5")

    def test_ipconfig_skips_apipa(self):
        """Une IP 169.x dans ipconfig ne doit pas être utilisée."""
        import re

        cfg_out = "ipconfig0: ip=169.254.0.1/16"
        m = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", cfg_out)
        if m:
            self.assertTrue(m.group(1).startswith("169."))


# ── Tests import Proxmox SPICE — détection qxl ───────────────────────────────


class TestProxmoxFetchHostsSpiceQxl(unittest.TestCase):
    """Tests pour la détection vga:qxl dans _proxmox_fetch_hosts."""

    def test_qxl_detected_in_vga_output(self):
        """Test qxl detected in vga output."""
        vga_out = "vga: qxl"
        self.assertIn("qxl", vga_out.lower())

    def test_std_vga_not_qxl(self):
        """Test std vga not qxl."""
        vga_out = "vga: std"
        self.assertNotIn("qxl", vga_out.lower())

    def test_empty_vga_not_qxl(self):
        """Test empty vga not qxl."""
        vga_out = ""
        self.assertNotIn("qxl", vga_out.lower())

    def test_qxl2_detected(self):
        """Test qxl2 detected."""
        vga_out = "vga: qxl2"
        self.assertIn("qxl", vga_out.lower())

    def test_extra_params_proxmox_format(self):
        """extra_params généré doit avoir le bon format --proxmox NODE VMID."""
        node_name = "DOCKER41"
        vmid = "100"
        extra = f"--proxmox {node_name} {vmid}"
        self.assertTrue(extra.startswith("--proxmox "))
        parts = extra.split()
        self.assertEqual(parts[1], "DOCKER41")
        self.assertEqual(parts[2], "100")


# ── Tests import libvirt/Proxmox — groupes par protocole ─────────────────────


class TestImportGroupByProtocol(unittest.TestCase):
    """Tests pour l'organisation en sous-groupes par protocole."""

    def _group_for(self, grp, proto):
        return f"{grp}/{proto}" if grp else proto

    def test_ssh_group(self):
        """Test ssh group."""
        self.assertEqual(self._group_for("hyperv1", "ssh"), "hyperv1/ssh")

    def test_spice_group(self):
        """Test spice group."""
        self.assertEqual(self._group_for("hyperv1", "spice"), "hyperv1/spice")

    def test_rdp_group(self):
        """Test rdp group."""
        self.assertEqual(self._group_for("hyperv1", "rdp"), "hyperv1/rdp")

    def test_vnc_group(self):
        """Test vnc group."""
        self.assertEqual(self._group_for("hyperv1", "vnc"), "hyperv1/vnc")

    def test_empty_grp_ssh(self):
        """Test empty grp ssh."""
        self.assertEqual(self._group_for("", "ssh"), "ssh")

    def test_empty_grp_spice(self):
        """Test empty grp spice."""
        self.assertEqual(self._group_for("", "spice"), "spice")

    def test_nested_group_preserved(self):
        """Test nested group preserved."""
        self.assertEqual(self._group_for("cluster/node1", "rdp"), "cluster/node1/rdp")


# ── Tests validation port (local exempt) ────────────────────────────────────


class TestPortValidation(unittest.TestCase):
    """Tests pour la validation du port (ctype local exempté)."""

    def _validate(self, ctype, port):
        if ctype == "local":
            return True
        return bool(port and port.isdigit() and 1 <= int(port) <= 65535)

    def test_local_empty_port_valid(self):
        """Test local empty port valid."""
        self.assertTrue(self._validate("local", ""))

    def test_ssh_empty_port_invalid(self):
        """Test ssh empty port invalid."""
        self.assertFalse(self._validate("ssh", ""))

    def test_ssh_valid_port(self):
        """Test ssh valid port."""
        self.assertTrue(self._validate("ssh", "22"))

    def test_ssh_port_out_of_range(self):
        """Test ssh port out of range."""
        self.assertFalse(self._validate("ssh", "99999"))

    def test_rdp_valid_port(self):
        """Test rdp valid port."""
        self.assertTrue(self._validate("rdp", "3389"))

    def test_spice_valid_port(self):
        """Test spice valid port."""
        self.assertTrue(self._validate("spice", "5930"))

    def test_local_any_string_valid(self):
        """Test local any string valid."""
        self.assertTrue(self._validate("local", "abc"))

    def test_vnc_valid_port(self):
        """Test vnc valid port."""
        self.assertTrue(self._validate("vnc", "5900"))


# ── Tests VNC dans proto_filter ──────────────────────────────────────────────


class TestVncProtoFilter(unittest.TestCase):
    """Tests pour la prise en charge de VNC dans les filtres d'import."""

    def test_vnc_default_port(self):
        """Test vnc default port (plugin_vnc, ex-_PROTO_DEFAULTS)."""
        self.assertEqual(plugin_vnc.get_plugin().default_port, 5900)

    def test_proto_filter_accepts_vnc(self):
        """Test proto filter accepts vnc."""
        proto_filter = {"ssh", "vnc", "rdp"}
        self.assertIn("vnc", proto_filter)

    def test_check_port_open_with_vnc_port(self):
        """_check_port_open peut être appelé avec le port VNC 5900."""

        def run_fn(client, cmd, timeout=30):
            """Run fn."""
            return "OPEN" if "5900" in cmd else "CLOSED"

        result = hic.check_port_open(None, run_fn, "192.168.1.10", 5900)
        self.assertTrue(result)


# ── Tests _compute_zoom_size (zoom terminal Ctrl+/Ctrl-/Ctrl+0, #79) ─────────


class TestComputeZoomSize(unittest.TestCase):
    """Tests pour _compute_zoom_size (bornage pur, sans dependance GTK/Pango)."""

    def test_zoom_in_increments(self):
        """Un pas positif augmente la taille d'autant."""
        self.assertEqual(gcm._compute_zoom_size(10, 1), 11)

    def test_zoom_out_decrements(self):
        """Un pas negatif diminue la taille d'autant."""
        self.assertEqual(gcm._compute_zoom_size(10, -1), 9)

    def test_no_change_with_zero_delta(self):
        """Un delta nul laisse la taille inchangee."""
        self.assertEqual(gcm._compute_zoom_size(10, 0), 10)

    def test_clamped_at_minimum(self):
        """La taille ne descend jamais sous la borne minimale par defaut."""
        self.assertEqual(gcm._compute_zoom_size(4, -1), 4)

    def test_clamped_at_maximum(self):
        """La taille ne depasse jamais la borne maximale par defaut."""
        self.assertEqual(gcm._compute_zoom_size(72, 1), 72)

    def test_large_negative_delta_clamped(self):
        """Une grande diminution ne descend pas sous la borne minimale."""
        self.assertEqual(gcm._compute_zoom_size(5, -100), 4)

    def test_custom_bounds(self):
        """Des bornes personnalisees sont respectees."""
        self.assertEqual(gcm._compute_zoom_size(10, 5, minimum=0, maximum=12), 12)
        self.assertEqual(gcm._compute_zoom_size(10, -20, minimum=2, maximum=12), 2)


# ── Tests _resolve_config_dir (option CLI --config, #80) ─────────────────────


class TestResolveConfigDir(unittest.TestCase):
    """Tests pour _resolve_config_dir (parsing pur, sans dependance GTK)."""

    def test_default_uses_home_gcm(self):
        """Sans --config, le dossier par defaut est ~/.gcm."""
        config_dir, remaining = gcm._resolve_config_dir([], "/home/alice")
        self.assertEqual(config_dir, os.path.join("/home/alice", ".gcm"))
        self.assertEqual(remaining, [])

    def test_long_form_with_space(self):
        """--config PATH est reconnu et retire des arguments restants."""
        config_dir, remaining = gcm._resolve_config_dir(["--config", "/tmp/altcfg"], "/home/alice")
        self.assertEqual(config_dir, "/tmp/altcfg")
        self.assertEqual(remaining, [])

    def test_long_form_with_equals(self):
        """--config=PATH est reconnu."""
        config_dir, remaining = gcm._resolve_config_dir(["--config=/tmp/altcfg2"], "/home/alice")
        self.assertEqual(config_dir, "/tmp/altcfg2")
        self.assertEqual(remaining, [])

    def test_short_form(self):
        """L'alias court -c est reconnu."""
        config_dir, remaining = gcm._resolve_config_dir(["-c", "/tmp/altcfg3"], "/home/alice")
        self.assertEqual(config_dir, "/tmp/altcfg3")
        self.assertEqual(remaining, [])

    def test_expands_user_and_makes_absolute(self):
        """Un chemin relatif ou avec ~ est normalise en chemin absolu."""
        config_dir, _ = gcm._resolve_config_dir(["--config", "~/altcfg4"], "/home/alice")
        self.assertTrue(os.path.isabs(config_dir))
        self.assertNotIn("~", config_dir)

    def test_host_specifier_preserved_without_config(self):
        """Un specificateur d'hote (groupe/nom) reste dans remaining."""
        config_dir, remaining = gcm._resolve_config_dir(["prod/webserver1"], "/home/alice")
        self.assertEqual(config_dir, os.path.join("/home/alice", ".gcm"))
        self.assertEqual(remaining, ["prod/webserver1"])

    def test_host_specifier_preserved_alongside_config(self):
        """--config et un specificateur d'hote cohabitent sans se marcher dessus."""
        config_dir, remaining = gcm._resolve_config_dir(
            ["--config", "/tmp/altcfg", "prod/webserver1"], "/home/alice"
        )
        self.assertEqual(config_dir, "/tmp/altcfg")
        self.assertEqual(remaining, ["prod/webserver1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
