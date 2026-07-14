"""Validated Command Console appearance presets shared by settings and theme startup."""

from re import fullmatch


COMMAND_CONSOLE_PALETTES = {
    'command': ('#FF8A2A', '#D4AD3F', '#9A6BC4', '#4FC3CC', '#D94B55'),
    'federation': ('#4D8FD8', '#9CCBFF', '#F4C95D', '#DDEBFF', '#D9545D'),
    'romulan': ('#2F9E6F', '#74D3AE', '#1F6F78', '#D5A94E', '#6B5CA5'),
    'klingon': ('#9E2A2B', '#D3542F', '#A66A3F', '#665A58', '#D89A3D'),
}

COMMAND_CONSOLE_PALETTE_NAMES = {
    'command': 'Command Console Default',
    'federation': 'STO Federation',
    'romulan': 'STO Romulan',
    'klingon': 'STO Klingon',
    'custom': 'Custom',
}

COMMAND_CONSOLE_BACKGROUND_NAMES = {
    'none': 'No background',
    'custom': 'Custom local image',
}

DEFAULT_COMMAND_CONSOLE_PALETTE = COMMAND_CONSOLE_PALETTES['command']
DEFAULT_COMMAND_CONSOLE_BACKGROUND = 'none'


def normalize_hex_colour(value: str) -> str | None:
    """Return an uppercase six-digit hex colour or ``None`` when invalid."""
    candidate = str(value).strip()
    if not candidate.startswith('#'):
        candidate = '#' + candidate
    if fullmatch(r'#[0-9a-fA-F]{6}', candidate) is None:
        return None
    return candidate.upper()


def normalize_custom_palette(values) -> tuple[str, ...]:
    """Return a safe five-colour palette, falling back per invalid entry."""
    candidates = list(values) if isinstance(values, (list, tuple)) else list()
    result = list()
    for index, fallback in enumerate(DEFAULT_COMMAND_CONSOLE_PALETTE):
        normalized = normalize_hex_colour(candidates[index]) if index < len(candidates) else None
        result.append(normalized or fallback)
    return tuple(result)


def resolve_command_console_palette(preset: str, custom_values) -> tuple[str, ...]:
    """Resolve a named preset or a validated custom five-colour palette."""
    if preset in COMMAND_CONSOLE_PALETTES:
        return COMMAND_CONSOLE_PALETTES[preset]
    return normalize_custom_palette(custom_values)


def normalize_background_mode(value: str) -> str:
    """Return a supported background mode, falling back to the flat workspace."""
    if value in COMMAND_CONSOLE_BACKGROUND_NAMES:
        return value
    return DEFAULT_COMMAND_CONSOLE_BACKGROUND
