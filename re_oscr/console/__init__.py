"""Command Console presentation primitives.

This package is intentionally independent from parser and source-model code.  It is imported only
by the Command Console construction path so the inherited OSCR-UI Legacy path keeps its existing
widget tree and styling.
"""

from .tokens import ConsoleTokens, build_console_stylesheet, refresh_style

__all__ = ("ConsoleTokens", "build_console_stylesheet", "refresh_style")
