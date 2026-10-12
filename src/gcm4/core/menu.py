"""Menu principal et raccourcis de gcm4, décrits sans GTK (#134).

Structure reprise de ``Wmain._build_primary_menu`` (GTK3), limitée à la
base sans plugins (#118) : ce qui sert au terminal, au cluster ou aux
outils de plugins arrivera avec eux. ``gcm4.ui`` construit le
``Gio.Menu`` à partir de ces données, qui restent testables sans display.
Libellés : msgids anglais de l'ancienne interface, marqués ``N_`` pour
l'extraction (traduits à l'affichage par ``gcm4.ui``).
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from gcm4.core.i18n import N_


@dataclass(frozen=True)
class Entree:
    """Ligne de menu : msgid du libellé, nom d'action (``app.x`` ou ``win.x``).

    ``cible`` : valeur de l'action à état (entrée radio), ``None`` sinon.
    """

    libelle: str
    action: str
    cible: str | None = None


@dataclass(frozen=True)
class SousMenu:
    """Sous-menu : msgid du titre et sections (séparées visuellement)."""

    titre: str
    sections: tuple[tuple[Entree, ...], ...]


MENU_PRINCIPAL: tuple[SousMenu, ...] = (
    SousMenu(N_("File"), ((Entree(N_("Quit"), "app.quit"),),)),
    SousMenu(N_("Edit"), ((Entree(N_("Settings"), "app.preferences"),),)),
    SousMenu(
        N_("View"),
        (
            (Entree(N_("Show Panel"), "win.toggle-panel"), Entree(N_("Search"), "win.search")),
            # Thème (#135) : action à état app.theme, une entrée radio par mode.
            (
                Entree(N_("System"), "app.theme", "system"),
                Entree(N_("Light"), "app.theme", "light"),
                Entree(N_("Dark"), "app.theme", "dark"),
            ),
        ),
    ),
    SousMenu(N_("Help"), ((Entree(N_("About"), "app.about"),),)),
)

RACCOURCIS: dict[str, tuple[str, ...]] = {
    "app.quit": ("<Control>q",),
    "app.preferences": ("<Control>comma",),
    "win.toggle-panel": ("F9",),
    "win.search": ("<Control>f",),
}


def actions_du_menu() -> list[str]:
    """Toutes les actions citées par le menu, dans l'ordre d'apparition."""
    logger.debug("actions_du_menu: entrée")
    actions = list(
        dict.fromkeys(
            e.action for sm in MENU_PRINCIPAL for section in sm.sections for e in section
        )
    )
    logger.debug("actions_du_menu: {}", actions)
    return actions
