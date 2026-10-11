"""Menu principal et raccourcis de gcm4, décrits sans GTK (#134).

Structure reprise de ``Wmain._build_primary_menu`` (GTK3), limitée à la
base sans plugins (#118) : ce qui sert au terminal, au cluster ou aux
outils de plugins arrivera avec eux. ``gcm4.ui`` construit le
``Gio.Menu`` à partir de ces données, qui restent testables sans display.
Libellés : msgids anglais de l'ancienne interface, déjà traduits.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass(frozen=True)
class Entree:
    """Ligne de menu : msgid du libellé et nom d'action (``app.x`` ou ``win.x``)."""

    libelle: str
    action: str


@dataclass(frozen=True)
class SousMenu:
    """Sous-menu : msgid du titre et sections (séparées visuellement)."""

    titre: str
    sections: tuple[tuple[Entree, ...], ...]


MENU_PRINCIPAL: tuple[SousMenu, ...] = (
    SousMenu("File", ((Entree("Quit", "app.quit"),),)),
    SousMenu("Edit", ((Entree("Settings", "app.preferences"),),)),
    SousMenu("View", ((Entree("Show Panel", "win.toggle-panel"),),)),
    SousMenu("Help", ((Entree("About", "app.about"),),)),
)

RACCOURCIS: dict[str, tuple[str, ...]] = {
    "app.quit": ("<Control>q",),
    "app.preferences": ("<Control>comma",),
    "win.toggle-panel": ("F9",),
}


def actions_du_menu() -> list[str]:
    """Toutes les actions citées par le menu, dans l'ordre d'apparition."""
    logger.debug("actions_du_menu: entrée")
    actions = [e.action for sm in MENU_PRINCIPAL for section in sm.sections for e in section]
    logger.debug("actions_du_menu: {}", actions)
    return actions
