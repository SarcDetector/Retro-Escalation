"""Command Console theme with a validated, user-selectable five-colour palette.

Structural changes from the browser prototype are intentionally outside this milestone. The
theme starts from OSCR's Default tree and only replaces a small set of colour roles.
"""

from copy import deepcopy

from ..appearance import DEFAULT_COMMAND_CONSOLE_PALETTE, normalize_custom_palette
from ..theme import AppTheme


COMMAND_CONSOLE_ACCENTS = DEFAULT_COMMAND_CONSOLE_PALETTE


COMMAND_CONSOLE_OVERRIDES = {
    'app': {
        'bg': '#080d12',
        'fg': '#f4efe6',
        'oscr': '#ff8a2a',
    },
    'defaults': {
        'bg': '#080d12',
        'mbg': '#101820',
        'lbg': '#24323d',
        'oscr': '#ff8a2a',
        'loscr': '#4a2a12',
        'fg': '#f4efe6',
        'mfg': '#bdc9cf',
        'bc': '#607789',
    },
    'plot': {
        'color_cycler': COMMAND_CONSOLE_ACCENTS + (
            '#65b87a', '#e8c96a', '#c383d6', '#7bdce3', '#f07a82',
        ),
        'overview_bar_colours': True,
    },
}


def create_command_console_theme(
        scale: float, accents: tuple[str, ...] | list[str] | None = None) -> AppTheme:
    """Build Command Console from the complete Default theme plus validated overrides."""
    palette = normalize_custom_palette(accents or COMMAND_CONSOLE_ACCENTS)
    default_theme = AppTheme(scale)
    theme_tree = default_theme.get_default_theme()
    overrides = deepcopy(COMMAND_CONSOLE_OVERRIDES)
    overrides['app']['oscr'] = palette[0]
    overrides['defaults']['oscr'] = palette[0]
    overrides['plot']['color_cycler'] = palette + overrides['plot']['color_cycler'][5:]
    for section_name, section_overrides in overrides.items():
        section = theme_tree.get(section_name)
        if not isinstance(section, dict):
            raise ValueError(f'Missing theme section: {section_name}')
        section.update(section_overrides)
    return AppTheme(scale, theme_tree=theme_tree)


def command_console_accents(theme: AppTheme) -> tuple[str, ...]:
    """Return the active five visual rails from a resolved Command Console theme."""
    return tuple(theme['plot']['color_cycler'][:5])
