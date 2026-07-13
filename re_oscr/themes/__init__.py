"""Built-in Retro Escalation theme definitions and startup resolution."""

from .registry import (
    COMMAND_CONSOLE_THEME_ID,
    DEFAULT_THEME_ID,
    ThemeDefinition,
    ThemeResolution,
    available_themes,
    resolve_theme,
)

__all__ = [
    'COMMAND_CONSOLE_THEME_ID',
    'DEFAULT_THEME_ID',
    'ThemeDefinition',
    'ThemeResolution',
    'available_themes',
    'resolve_theme',
]
