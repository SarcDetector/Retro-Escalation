"""Allow-listed startup theme registry with a guaranteed Legacy fallback."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtCore import QDir

from ..theme import AppTheme
from .command_console import create_command_console_theme


DEFAULT_THEME_ID = 'default'
COMMAND_CONSOLE_THEME_ID = 'command_console'
THEME_ASSET_PREFIX = 'theme_assets_folder'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThemeDefinition:
    theme_id: str
    display_name: str
    factory: Callable[[float], AppTheme]
    asset_directory: str | None = None


@dataclass(frozen=True)
class ThemeResolution:
    theme: AppTheme
    definition: ThemeDefinition
    requested_theme_id: str
    fallback_used: bool


def _create_default_theme(scale: float) -> AppTheme:
    return AppTheme(scale)


THEME_REGISTRY = {
    DEFAULT_THEME_ID: ThemeDefinition(
        theme_id=DEFAULT_THEME_ID,
        display_name='Legacy',
        factory=_create_default_theme,
    ),
    COMMAND_CONSOLE_THEME_ID: ThemeDefinition(
        theme_id=COMMAND_CONSOLE_THEME_ID,
        display_name='Command Console',
        factory=create_command_console_theme,
        asset_directory='command_console',
    ),
}


def available_themes() -> tuple[ThemeDefinition, ...]:
    """Return public themes in stable Settings-selector order."""
    return tuple(THEME_REGISTRY.values())


def _configure_asset_path(definition: ThemeDefinition, app_dir: Path) -> None:
    if definition.asset_directory is None:
        return
    asset_path = app_dir / 'theme_assets' / definition.asset_directory
    if not asset_path.is_dir():
        raise FileNotFoundError(f'Theme asset directory does not exist: {asset_path}')
    QDir.addSearchPath(THEME_ASSET_PREFIX, str(asset_path))


def resolve_theme(
        requested_theme_id: str, scale: float, app_dir: Path | None = None,
        command_console_palette: Sequence[str] | None = None) -> ThemeResolution:
    """Resolve a theme, returning Legacy after an alternate-theme failure."""
    definition = THEME_REGISTRY.get(requested_theme_id)
    fallback_used = definition is None
    if definition is None:
        logger.warning('Unknown theme ID %r; using Legacy.', requested_theme_id)
        definition = THEME_REGISTRY[DEFAULT_THEME_ID]

    try:
        if definition.theme_id == COMMAND_CONSOLE_THEME_ID:
            theme = definition.factory(scale, command_console_palette)
        else:
            theme = definition.factory(scale)
        if app_dir is not None:
            _configure_asset_path(definition, app_dir)
    except Exception:
        if definition.theme_id == DEFAULT_THEME_ID:
            raise
        logger.exception('Theme %r failed to load; using Legacy.', definition.theme_id)
        definition = THEME_REGISTRY[DEFAULT_THEME_ID]
        theme = definition.factory(scale)
        fallback_used = True

    return ThemeResolution(
        theme=theme,
        definition=definition,
        requested_theme_id=requested_theme_id,
        fallback_used=fallback_used,
    )
