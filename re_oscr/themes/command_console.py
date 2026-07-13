"""Initial palette-only Command Console theme.

Structural changes from the browser prototype are intentionally outside this milestone. The
theme starts from OSCR's Default tree and only replaces a small set of colour roles.
"""

from ..theme import AppTheme


COMMAND_CONSOLE_ACCENTS = (
    '#ff8a2a',  # orange
    '#d4ad3f',  # gold
    '#9a6bc4',  # purple
    '#4fc3cc',  # cyan
    '#d94b55',  # red
)


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
    },
}


def create_command_console_theme(scale: float) -> AppTheme:
    """Build Command Console from the complete Default theme plus validated overrides."""
    default_theme = AppTheme(scale)
    theme_tree = default_theme.get_default_theme()
    for section_name, section_overrides in COMMAND_CONSOLE_OVERRIDES.items():
        section = theme_tree.get(section_name)
        if not isinstance(section, dict):
            raise ValueError(f'Missing theme section: {section_name}')
        section.update(section_overrides)
    return AppTheme(scale, theme_tree=theme_tree)
