"""Isolated LayerShellQt support for the native Wayland live presentation.

LayerShellQt selects its Wayland shell integration through process-global
environment variables.  RE-OSCR therefore keeps the parser, main UI, and
browser overlay in the parent process and starts a presentation-only child.
The child receives normalized rows over a private stdin pipe; it never receives
the combat-log path or the settings directory.

The probing functions in this module are intentionally read-only.  Only
``prepare_environment`` mutates ``os.environ``, and it is meant to be called by
the hidden presenter before that process constructs its QApplication.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import json
import math
import os
from pathlib import Path
import re
import sys
import sysconfig
from typing import Any, Callable, Mapping

from PySide6.QtCore import (
    QLibraryInfo,
    QMargins,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
    Slot,
    qVersion,
)
from PySide6.QtGui import QGuiApplication, QWindow
from shiboken6 import Shiboken


# Values from LayerShellQt/window.h.
LAYER_BACKGROUND, LAYER_BOTTOM, LAYER_TOP, LAYER_OVERLAY = 0, 1, 2, 3
ANCHOR_NONE, ANCHOR_TOP, ANCHOR_BOTTOM, ANCHOR_LEFT, ANCHOR_RIGHT = 0, 1, 2, 4, 8
KEYBOARD_NONE, KEYBOARD_EXCLUSIVE, KEYBOARD_ON_DEMAND = 0, 1, 2

PROTOCOL = "re-oscr.wayland-live.v1"
PROTOCOL_ID = PROTOCOL
PROTOCOL_VERSION = 1
MAX_CHILD_LINE = 1_048_576
MAX_WRITE_BACKLOG = 512 * 1024
STARTUP_TIMEOUT_MS = 8_000

_PLUGIN_NAMES = ("liblayer-shell.so", "liblayershellqt.so")
_INTERFACE_NAMES = (
    "libLayerShellQtInterface.so.6",
    "libLayerShellQtInterface.so",
)

# Mangled symbols exported by LayerShellQt 6 (Itanium C++ ABI).
_SYM_GET = "_ZN12LayerShellQt6Window3getEP7QWindow"
_SYM_SET_LAYER = "_ZN12LayerShellQt6Window8setLayerENS0_5LayerE"
_SYM_SET_ANCHORS = "_ZN12LayerShellQt6Window10setAnchorsE6QFlagsINS0_6AnchorEE"
_SYM_SET_MARGINS = "_ZN12LayerShellQt6Window10setMarginsERK8QMargins"
_SYM_SET_KEYBOARD = (
    "_ZN12LayerShellQt6Window24setKeyboardInteractivity"
    "ENS0_21KeyboardInteractivityE"
)
_SYM_SET_EXCLUSIVE_ZONE = "_ZN12LayerShellQt6Window16setExclusiveZoneEi"
_REQUIRED_SYMBOLS = (
    _SYM_GET,
    _SYM_SET_LAYER,
    _SYM_SET_ANCHORS,
    _SYM_SET_MARGINS,
    _SYM_SET_KEYBOARD,
    _SYM_SET_EXCLUSIVE_ZONE,
)

# Display-only configuration accepted from the parent.  An allowlist is used
# instead of accepting arbitrary settings, so a future caller cannot
# accidentally put a config path, log path, feed token, or unrelated setting
# on the child pipe.
_CONFIGURATION_KEYS = frozenset(
    {
        "theme_id",
        "ui_scale",
        "palette",
        "style",
        "live",
        "labels",
        "header",
    }
)
_LIVE_CONFIGURATION_KEYS = frozenset(
    {
        "columns",
        "graph_active",
        "graph_field",
        "player_display",
        "window_scale",
        "opacity",
        "overlay_left",
        "overlay_top",
        "overlay_width",
        "overlay_height",
        "copy_kills",
    }
)
_LABEL_KEYS = frozenset({"activate", "deactivate", "copy", "close", "duration"})
_STYLE_KEYS = frozenset(
    {
        "background",
        "raised",
        "overlay",
        "deep",
        "border",
        "text",
        "secondary",
        "muted",
    }
)


class LayerShellError(RuntimeError):
    """A contained LayerShellQt discovery or ABI error."""


class LayerShellUnavailable(LayerShellError):
    """The host cannot safely start the native Wayland presenter."""


@dataclass(frozen=True, slots=True)
class LayerShellSupport:
    """Read-only result of probing for an ABI-compatible LayerShellQt install."""

    supported: bool
    reason: str
    plugin_root: str | None = None
    plugin_path: str | None = None
    interface_library: str | None = None
    runtime_qt_version: str = ""
    layer_shell_qt_version: str | None = None
    source: str = ""

    def __bool__(self) -> bool:
        return self.supported

    @property
    def qt_abi(self) -> str:
        """Qt major.minor ABI selected for the presenter."""
        parts = self.runtime_qt_version.split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else self.runtime_qt_version


@dataclass(frozen=True, slots=True)
class _PathCandidate:
    path: Path
    source: str
    trusted_runtime: bool = False


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _unique_candidates(candidates: list[_PathCandidate]) -> list[_PathCandidate]:
    seen: set[str] = set()
    result: list[_PathCandidate] = []
    for candidate in candidates:
        try:
            key = os.path.normcase(str(candidate.path.expanduser().resolve(strict=False)))
        except OSError:
            key = os.path.normcase(str(candidate.path.expanduser()))
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def _frozen_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))


def _multiarch_names() -> list[str]:
    names: list[str] = []
    configured = sysconfig.get_config_var("MULTIARCH")
    if configured:
        names.append(str(configured))
    machine = os.uname().machine.casefold() if hasattr(os, "uname") else ""
    common = {
        "x86_64": "x86_64-linux-gnu",
        "amd64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
        "armv7l": "arm-linux-gnueabihf",
        "ppc64le": "powerpc64le-linux-gnu",
        "riscv64": "riscv64-linux-gnu",
    }.get(machine)
    if common and common not in names:
        names.append(common)
    return names


def _plugin_root_candidates(
    environ: Mapping[str, str], frozen_root: Path | None
) -> list[_PathCandidate]:
    candidates: list[_PathCandidate] = []

    explicit = environ.get("RE_OSCR_LAYER_SHELL_PLUGIN_ROOT")
    if explicit:
        candidates.append(_PathCandidate(Path(explicit), "explicit environment"))

    if frozen_root is not None:
        for suffix in (
            ("layershellqt",),
            ("PySide6", "Qt", "plugins"),
            ("qt6", "plugins"),
            ("plugins",),
            (),
        ):
            candidates.append(
                _PathCandidate(
                    frozen_root.joinpath(*suffix),
                    "application bundle",
                    trusted_runtime=True,
                )
            )

    for item in environ.get("QT_PLUGIN_PATH", "").split(os.pathsep):
        if item:
            candidates.append(_PathCandidate(Path(item), "QT_PLUGIN_PATH"))

    # The PySide plugins directory is ABI-identical to the running Qt.  Wheels
    # do not normally include LayerShellQt, but downstream bundles sometimes
    # install it there.
    try:
        plugins_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    except (AttributeError, TypeError):
        plugins_path = ""
    if plugins_path:
        candidates.append(
            _PathCandidate(Path(plugins_path), "PySide6 plugin directory", True)
        )

    for multiarch in _multiarch_names():
        for prefix in (Path("/usr/lib"), Path("/lib"), Path("/usr/local/lib")):
            candidates.append(
                _PathCandidate(prefix / multiarch / "qt6" / "plugins", "system")
            )
    for root in (
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt6/plugins",
        "/usr/local/lib/qt6/plugins",
        "/usr/local/lib64/qt6/plugins",
    ):
        candidates.append(_PathCandidate(Path(root), "system"))
    return _unique_candidates(candidates)


def _interface_candidates(
    environ: Mapping[str, str],
    frozen_root: Path | None,
    plugin_roots: list[_PathCandidate],
) -> list[_PathCandidate]:
    candidates: list[_PathCandidate] = []
    explicit = environ.get("RE_OSCR_LAYER_SHELL_INTERFACE")
    if explicit:
        candidates.append(_PathCandidate(Path(explicit), "explicit environment"))

    if frozen_root is not None:
        for name in _INTERFACE_NAMES:
            candidates.extend(
                (
                    _PathCandidate(
                        frozen_root / name, "application bundle", trusted_runtime=True
                    ),
                    _PathCandidate(
                        frozen_root / "lib" / name,
                        "application bundle",
                        trusted_runtime=True,
                    ),
                    _PathCandidate(
                        frozen_root / "layershellqt" / name,
                        "application bundle",
                        trusted_runtime=True,
                    ),
                )
            )

    for item in environ.get("LD_LIBRARY_PATH", "").split(os.pathsep):
        if not item:
            continue
        for name in _INTERFACE_NAMES:
            candidates.append(_PathCandidate(Path(item) / name, "LD_LIBRARY_PATH"))

    # Derive likely library prefixes from each Qt plugin root.  This covers
    # /usr/lib/<multiarch>/qt6/plugins as well as /usr/lib/qt6/plugins.
    for plugin in plugin_roots:
        root = plugin.path
        possible = [root, root.parent, root.parent.parent]
        if root.name == "plugins" and root.parent.name.casefold() == "qt6":
            possible.append(root.parent.parent)
        for directory in possible:
            for name in _INTERFACE_NAMES:
                candidates.append(
                    _PathCandidate(directory / name, plugin.source, plugin.trusted_runtime)
                )

    library_roots = [
        Path("/usr/lib"),
        Path("/lib"),
        Path("/usr/lib64"),
        Path("/lib64"),
        Path("/usr/local/lib"),
        Path("/usr/local/lib64"),
    ]
    for multiarch in _multiarch_names():
        library_roots.extend(
            (
                Path("/usr/lib") / multiarch,
                Path("/lib") / multiarch,
                Path("/usr/local/lib") / multiarch,
            )
        )
    for root in library_roots:
        for name in _INTERFACE_NAMES:
            candidates.append(_PathCandidate(root / name, "system"))
    return _unique_candidates(candidates)


def _find_plugin(candidate: _PathCandidate) -> Path | None:
    root = candidate.path.expanduser()
    for name in _PLUGIN_NAMES:
        direct = root / "wayland-shell-integration" / name
        if direct.is_file():
            return direct.resolve()
        # Accept an explicit plugin file in addition to a Qt plugin root.
        if root.name == name and root.is_file():
            return root.resolve()
    return None


_QT_CORE_VERSION_RE = re.compile(r"libQt6Core\.so\.(\d+)\.(\d+)\.(\d+)")
_PLAIN_VERSION_RE = re.compile(r"^\s*Version\s*:\s*(\d+\.\d+(?:\.\d+)?)\s*$", re.M)


def _qt_version_near(paths: list[Path]) -> str:
    """Read a Qt version from nearby SONAME targets or Qt6Core.pc."""
    directories: list[Path] = []
    for path in paths:
        current = path if path.is_dir() else path.parent
        for directory in (current, current.parent, current.parent.parent):
            if directory not in directories:
                directories.append(directory)

    for directory in directories:
        core = directory / "libQt6Core.so.6"
        if core.exists():
            try:
                name = core.resolve().name
            except OSError:
                name = core.name
            match = _QT_CORE_VERSION_RE.search(name)
            if match:
                return ".".join(match.groups())
        try:
            versioned = sorted(directory.glob("libQt6Core.so.6.*"), reverse=True)
        except OSError:
            versioned = []
        for candidate in versioned:
            match = _QT_CORE_VERSION_RE.search(candidate.name)
            if match:
                return ".".join(match.groups())

        for relative in (
            Path("pkgconfig") / "Qt6Core.pc",
            Path("qt6") / "lib" / "pkgconfig" / "Qt6Core.pc",
        ):
            pc_file = directory / relative
            try:
                text = pc_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = _PLAIN_VERSION_RE.search(text)
            if match:
                return match.group(1)
    return ""


def _same_qt_abi(left: str, right: str) -> bool:
    left_parts = left.split(".")
    right_parts = right.split(".")
    return (
        len(left_parts) >= 2
        and len(right_parts) >= 2
        and left_parts[:2] == right_parts[:2]
    )


def _has_required_symbols(library: Path) -> tuple[bool, str]:
    """Validate dynsym names without loading a foreign Qt library in the parent."""
    try:
        size = library.stat().st_size
        if size <= 0 or size > 64 * 1024 * 1024:
            return False, "interface library has an invalid size"
        binary = library.read_bytes()
    except OSError as error:
        return False, f"interface library is unreadable: {error}"
    missing = [name for name in _REQUIRED_SYMBOLS if name.encode("ascii") not in binary]
    if missing:
        return False, "interface library is missing required LayerShellQt symbols"
    return True, ""


def _unsupported(reason: str, runtime_qt: str) -> LayerShellSupport:
    return LayerShellSupport(
        supported=False,
        reason=reason,
        runtime_qt_version=runtime_qt,
    )


def detect_layer_shell_support(
    environ: Mapping[str, str] | None = None,
    frozen_root: str | os.PathLike[str] | None = None,
) -> LayerShellSupport:
    """Probe for a safe native Wayland LayerShellQt child configuration.

    The function only reads paths and environment values.  It does not load the
    foreign interface library and never changes the parent environment.
    """
    environment = dict(os.environ if environ is None else environ)
    runtime_qt = qVersion()
    force = _truthy(environment.get("RE_OSCR_WAYLAND_TEST_OVERRIDE"))

    if not sys.platform.startswith("linux") and not force:
        return _unsupported("native layer-shell presentation is Linux-only", runtime_qt)

    wayland = (
        bool(environment.get("WAYLAND_DISPLAY"))
        or environment.get("XDG_SESSION_TYPE", "").casefold() == "wayland"
        or environment.get("QT_QPA_PLATFORM", "").casefold().startswith("wayland")
    )
    if not wayland and not force:
        return _unsupported("the current session is not native Wayland", runtime_qt)

    desktop = " ".join(
        environment.get(name, "")
        for name in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION")
    ).casefold()
    allow_untested = force or _truthy(
        environment.get("RE_OSCR_ALLOW_UNTESTED_COMPOSITOR")
    )
    if ("gnome" in desktop or "mutter" in desktop) and not allow_untested:
        return _unsupported(
            "GNOME/Mutter is not a tested native layer-shell target", runtime_qt
        )

    bundle_root = Path(frozen_root) if frozen_root is not None else _frozen_root()
    plugin_candidates = _plugin_root_candidates(environment, bundle_root)
    plugins: list[tuple[_PathCandidate, Path]] = []
    for candidate in plugin_candidates:
        plugin_path = _find_plugin(candidate)
        if plugin_path is not None:
            plugins.append((candidate, plugin_path))
    if not plugins:
        return _unsupported(
            "an installed LayerShellQt Wayland shell plugin was not found", runtime_qt
        )

    interfaces = [
        candidate
        for candidate in _interface_candidates(environment, bundle_root, plugin_candidates)
        if candidate.path.expanduser().is_file()
    ]
    if not interfaces:
        return _unsupported(
            "libLayerShellQtInterface.so.6 was not found", runtime_qt
        )

    explicit_version = environment.get("RE_OSCR_LAYER_SHELL_QT_VERSION", "")
    abi_failures: list[str] = []
    symbol_failures: list[str] = []
    for plugin_candidate, plugin_path in plugins:
        for interface_candidate in interfaces:
            interface_path = interface_candidate.path.expanduser().resolve()
            trusted = (
                plugin_candidate.trusted_runtime
                and interface_candidate.trusted_runtime
            )
            layer_qt = explicit_version or _qt_version_near(
                [plugin_path, plugin_candidate.path, interface_path]
            )
            if not trusted and not _same_qt_abi(runtime_qt, layer_qt):
                abi_failures.append(
                    f"{plugin_path} / {interface_path}: "
                    f"Qt {layer_qt or 'unknown'} vs runtime Qt {runtime_qt}"
                )
                continue
            symbols_ok, symbol_reason = _has_required_symbols(interface_path)
            if not symbols_ok:
                symbol_failures.append(f"{interface_path}: {symbol_reason}")
                continue
            return LayerShellSupport(
                supported=True,
                reason="LayerShellQt plugin and interface match the PySide6 Qt ABI",
                plugin_root=str(plugin_path.parent.parent),
                plugin_path=str(plugin_path),
                interface_library=str(interface_path),
                runtime_qt_version=runtime_qt,
                layer_shell_qt_version=layer_qt or runtime_qt,
                source=(
                    plugin_candidate.source
                    if plugin_candidate.source == interface_candidate.source
                    else f"{plugin_candidate.source} + {interface_candidate.source}"
                ),
            )

    if symbol_failures:
        return _unsupported(symbol_failures[0], runtime_qt)
    if abi_failures:
        return _unsupported(
            "LayerShellQt was found, but its Qt major.minor ABI could not be "
            f"safely matched ({abi_failures[0]})",
            runtime_qt,
        )
    return _unsupported("no usable LayerShellQt plugin/interface pair was found", runtime_qt)


# Alternate spelling kept as a discoverable convenience.
detect_layershell_support = detect_layer_shell_support


def layershell_supported() -> bool:
    """Raman-compatible boolean probe."""
    return detect_layer_shell_support().supported


def _environment_overrides(support: LayerShellSupport) -> dict[str, str]:
    if not support.supported or not support.plugin_root or not support.interface_library:
        raise LayerShellUnavailable(support.reason or "LayerShellQt is unavailable")
    overrides = {
        "QT_WAYLAND_SHELL_INTEGRATION": "layer-shell",
        "RE_OSCR_LAYER_SHELL_PLUGIN_ROOT": support.plugin_root,
        "RE_OSCR_LAYER_SHELL_INTERFACE": support.interface_library,
        "RE_OSCR_LAYER_SHELL_QT_VERSION": support.runtime_qt_version,
        "RE_OSCR_WAYLAND_PRESENTER": "1",
    }
    try:
        runtime_plugins = Path(
            QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    except (AttributeError, TypeError):
        runtime_plugins = Path()
    runtime_platforms = runtime_plugins / "platforms"
    if runtime_platforms.is_dir():
        # QT_PLUGIN_PATH also exposes the system LayerShellQt directory. Pin
        # the QPA plugin to PySide's own runtime so a system libqwayland
        # cannot replace the wheel/bundle platform plugin before startup.
        overrides["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(runtime_platforms)
    return overrides


def _ordered_plugin_paths(
        current: str, runtime_root: str, layer_shell_root: str,
) -> list[str]:
    """Keep PySide's plugins ahead of the additional LayerShellQt root."""
    candidates = [
        runtime_root,
        *(item for item in current.split(os.pathsep) if item),
        layer_shell_root,
    ]
    result: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in result:
            result.append(candidate)
    return result


def prepare_environment(
    support: LayerShellSupport | None = None,
) -> LayerShellSupport:
    """Prepare the presenter child before it constructs QApplication.

    This is the one deliberately process-mutating helper in the module.  The
    parent-side controller uses ``QProcessEnvironment`` instead.
    """
    selected = support or detect_layer_shell_support()
    overrides = _environment_overrides(selected)
    try:
        runtime_root = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    except (AttributeError, TypeError):
        runtime_root = ""
    plugin_paths = _ordered_plugin_paths(
        os.environ.get("QT_PLUGIN_PATH", ""),
        runtime_root,
        str(selected.plugin_root),
    )
    os.environ["QT_PLUGIN_PATH"] = os.pathsep.join(plugin_paths)

    os.environ.update(overrides)
    return selected


def _cpp_ptr(obj: Any) -> ctypes.c_void_p:
    try:
        pointer = Shiboken.getCppPointer(obj)[0]
    except Exception as error:
        raise LayerShellError("unable to obtain the Qt C++ object pointer") from error
    if not pointer:
        raise LayerShellError("Qt returned a null C++ object pointer")
    return ctypes.c_void_p(pointer)


_LIBRARY_CACHE: dict[str, dict[str, Any]] = {}


def _interface_path(interface_library: str | os.PathLike[str] | None = None) -> str:
    selected = str(
        interface_library
        or os.environ.get("RE_OSCR_LAYER_SHELL_INTERFACE", "")
    )
    if not selected:
        support = detect_layer_shell_support()
        if not support.supported or not support.interface_library:
            raise LayerShellUnavailable(support.reason)
        selected = support.interface_library
    return str(Path(selected).expanduser().resolve())


def _library(
    interface_library: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    path = _interface_path(interface_library)
    cached = _LIBRARY_CACHE.get(path)
    if cached is not None:
        return cached
    try:
        mode = getattr(ctypes, "RTLD_LOCAL", 0) | getattr(os, "RTLD_NOW", 0)
        library = ctypes.CDLL(path, mode=mode)
        functions = {symbol: library[symbol] for symbol in _REQUIRED_SYMBOLS}
        functions[_SYM_GET].restype = ctypes.c_void_p
        functions[_SYM_GET].argtypes = [ctypes.c_void_p]
        for symbol in (
            _SYM_SET_LAYER,
            _SYM_SET_ANCHORS,
            _SYM_SET_KEYBOARD,
            _SYM_SET_EXCLUSIVE_ZONE,
        ):
            functions[symbol].restype = None
            functions[symbol].argtypes = [ctypes.c_void_p, ctypes.c_int]
        functions[_SYM_SET_MARGINS].restype = None
        functions[_SYM_SET_MARGINS].argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
    except (OSError, KeyError, AttributeError) as error:
        raise LayerShellError(
            f"LayerShellQt interface could not be loaded safely: {error}"
        ) from error
    # Retain the CDLL itself as long as any prepared function pointer is used.
    functions["_library"] = library
    _LIBRARY_CACHE[path] = functions
    return functions


def configure_as_overlay(
    qwindow: QWindow,
    anchors: int = ANCHOR_TOP | ANCHOR_LEFT,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
):
    """Configure a QWindow as a non-focus-stealing overlay layer surface.

    Returns the opaque ``LayerShellQt::Window*`` used by ``set_margins``.
    Failures are converted to ``LayerShellError`` rather than leaking ctypes
    implementation errors into the presenter.
    """
    if qwindow is None:
        raise LayerShellError("configure_as_overlay requires a QWindow")
    try:
        left, top, right, bottom = (int(value) for value in margins)
    except (TypeError, ValueError, OverflowError) as error:
        raise LayerShellError("overlay margins must contain four integers") from error
    functions = _library()
    try:
        layer_window = functions[_SYM_GET](_cpp_ptr(qwindow))
        if not layer_window:
            raise LayerShellError("LayerShellQt::Window::get returned null")
        functions[_SYM_SET_LAYER](layer_window, LAYER_OVERLAY)
        functions[_SYM_SET_KEYBOARD](layer_window, KEYBOARD_NONE)
        functions[_SYM_SET_ANCHORS](layer_window, int(anchors))
        functions[_SYM_SET_EXCLUSIVE_ZONE](layer_window, -1)
        set_margins(layer_window, left, top, right, bottom)
    except LayerShellError:
        raise
    except Exception as error:
        raise LayerShellError("LayerShellQt rejected the overlay configuration") from error
    return layer_window


def set_margins(
    layer_window: Any,
    left: int,
    top: int,
    right: int = 0,
    bottom: int = 0,
) -> None:
    """Move a configured layer surface by updating its anchor margins."""
    pointer = (
        layer_window
        if isinstance(layer_window, ctypes.c_void_p)
        else ctypes.c_void_p(int(layer_window or 0))
    )
    if not pointer.value:
        raise LayerShellError("cannot set margins on a null LayerShellQt window")
    margins = QMargins(int(left), int(top), int(right), int(bottom))
    try:
        _library()[_SYM_SET_MARGINS](pointer, _cpp_ptr(margins))
    except LayerShellError:
        raise
    except Exception as error:
        raise LayerShellError("LayerShellQt could not update overlay margins") from error


def create_relative_pointer(
    on_motion: Callable[[float, float], None],
) -> object | None:
    """Attach optional raw relative-pointer motion to Qt's Wayland display.

    pywayland has no universal wheel, and some compositors do not advertise the
    protocol.  Every import, native-interface, bind, and callback failure is
    therefore contained and represented by ``None`` (or an ignored callback)
    rather than taking down the presenter.
    """
    if not callable(on_motion):
        return None
    try:
        from pywayland import ffi
        from pywayland.client import Display
        from pywayland.protocol.relative_pointer_unstable_v1 import (
            ZwpRelativePointerManagerV1,
        )
        from pywayland.protocol.wayland import WlSeat

        application = QGuiApplication.instance()
        if application is None:
            return None
        native = application.nativeInterface()
        display_pointer = native.display()
        if not display_pointer:
            return None

        display = Display()
        # Borrow Qt's wl_display.  The returned holder keeps every wrapper alive;
        # callers must not call Display.disconnect() on it.
        display._ptr = ffi.cast("struct wl_display *", display_pointer)
        registry = display.get_registry()
        bound: dict[str, Any] = {}

        def on_global(registry_object, name, interface, version):
            try:
                if interface == "wl_seat" and "seat" not in bound:
                    bound["seat"] = registry_object.bind(
                        name, WlSeat, min(int(version), 5)
                    )
                elif (
                    interface == "zwp_relative_pointer_manager_v1"
                    and "manager" not in bound
                ):
                    bound["manager"] = registry_object.bind(
                        name, ZwpRelativePointerManagerV1, min(int(version), 1)
                    )
            except Exception:
                return

        registry.dispatcher["global"] = on_global
        display.roundtrip()
        if "seat" not in bound or "manager" not in bound:
            return None
        pointer = bound["seat"].get_pointer()
        relative = bound["manager"].get_relative_pointer(pointer)

        def on_relative_motion(
            relative_pointer,
            time_high,
            time_low,
            dx,
            dy,
            dx_unaccelerated,
            dy_unaccelerated,
        ):
            del (
                relative_pointer,
                time_high,
                time_low,
                dx_unaccelerated,
                dy_unaccelerated,
            )
            try:
                on_motion(float(dx), float(dy))
            except Exception:
                return

        relative.dispatcher["relative_motion"] = on_relative_motion
        display.roundtrip()
        return {
            "display": display,
            "registry": registry,
            "pointer": pointer,
            "relative": relative,
            **bound,
        }
    except Exception:
        return None


def _safe_scalar(value: Any, *, string_limit: int = 512) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return max(-(2**63), min(2**63 - 1, value))
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, str):
        return value[:string_limit]
    # Do not stringify arbitrary objects: a Path, settings object, or parser
    # object must never accidentally become presentation-protocol content.
    return None


def _sanitize_list(value: Any, *, max_items: int = 512) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[Any] = []
    for item in value[:max_items]:
        if isinstance(item, (list, tuple)):
            result.append([_safe_scalar(part) for part in item[:128]])
        elif isinstance(item, dict):
            result.append(
                {
                    str(key)[:128]: _safe_scalar(part)
                    for key, part in list(item.items())[:128]
                }
            )
        else:
            result.append(_safe_scalar(item))
    return result


def _sanitize_configuration(configuration: Any) -> dict[str, Any]:
    if not isinstance(configuration, dict):
        return {}
    result: dict[str, Any] = {}
    for key in _CONFIGURATION_KEYS:
        if key not in configuration:
            continue
        value = configuration[key]
        if key == "live" and isinstance(value, dict):
            result[key] = {
                item_key: (
                    _sanitize_list(item_value, max_items=64)
                    if item_key == "columns"
                    else _safe_scalar(item_value)
                )
                for item_key, item_value in value.items()
                if item_key in _LIVE_CONFIGURATION_KEYS
            }
        elif key == "labels" and isinstance(value, dict):
            result[key] = {
                item_key: _safe_scalar(item_value)
                for item_key, item_value in value.items()
                if item_key in _LABEL_KEYS
            }
        elif key == "style" and isinstance(value, dict):
            result[key] = {
                item_key: _safe_scalar(item_value)
                for item_key, item_value in value.items()
                if item_key in _STYLE_KEYS
            }
        elif key in {"palette", "header"}:
            result[key] = _sanitize_list(value, max_items=128)
        else:
            result[key] = _safe_scalar(value)
    return result


def _sanitize_rows(rows: Any) -> list[list[Any]]:
    if not isinstance(rows, (list, tuple)):
        return []
    result: list[list[Any]] = []
    for row in rows[:100]:
        if not isinstance(row, (list, tuple)):
            continue
        sanitized: list[Any] = []
        for column, value in enumerate(row[:16]):
            # OSCR's normalized player cell is (character_name, account_handle).
            # Preserve that two-part display identity without allowing arbitrary
            # nested data into the presenter protocol.
            if column == 0 and isinstance(value, (list, tuple)):
                sanitized.append([_safe_scalar(part) for part in value[:2]])
            else:
                sanitized.append(_safe_scalar(value))
        result.append(sanitized)
    return result


def _packet(packet_type: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "type": packet_type,
        "payload": dict(payload or {}),
    }


class WaylandPresentationProcess(QObject):
    """Parent-side lifecycle and private IPC for the Wayland presenter child."""

    ready = Signal()
    close_requested = Signal()
    parser_requested = Signal(bool)
    geometry_changed = Signal(object)
    unavailable = Signal(str)

    def __init__(
        self,
        app_dir: str,
        support: LayerShellSupport | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._app_dir = str(Path(app_dir).expanduser().resolve())
        self._support = support or detect_layer_shell_support()
        self._process: QProcess | None = None
        self._stdout_buffer = bytearray()
        self._stderr_tail = bytearray()
        self._outbox: list[dict[str, Any]] = []
        self._snapshot_sequence = 0
        self._ready_received = False
        self._expected_shutdown = False
        self._failed = not self._support.supported
        self._failure_reported = False
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.setInterval(STARTUP_TIMEOUT_MS)
        self._startup_timer.timeout.connect(self._on_startup_timeout)

    @classmethod
    def create_if_supported(
        cls, app_dir: str, parent: QObject | None = None
    ) -> WaylandPresentationProcess | None:
        """Return a lazy controller only when a safe native path is available."""
        support = detect_layer_shell_support()
        if not support.supported:
            return None
        return cls(app_dir=app_dir, support=support, parent=parent)

    @property
    def support(self) -> LayerShellSupport:
        return self._support

    @property
    def running(self) -> bool:
        process = self._process
        return bool(
            process is not None
            and process.state() != QProcess.ProcessState.NotRunning
        )

    @property
    def ready_received(self) -> bool:
        """Whether the child confirmed a configured, shown layer surface."""
        return self._ready_received

    def show_presentation(
        self,
        configuration: dict,
        rows: list,
        duration: float,
        parser_active: bool,
    ) -> bool:
        """Start lazily, then configure and show the presentation-only child."""
        if self._failed or not self._support.supported:
            return False
        self.send_configuration(configuration)
        self.send_snapshot(rows, duration)
        self.send_parser_state(parser_active)
        self._queue(_packet("show"), coalesce_group="visibility")
        if not self.running:
            return self._start()
        self._flush_outbox()
        return True

    @Slot()
    def hide_presentation(self) -> None:
        """Hide the child surface while leaving the sole parent parser running."""
        if self._failed:
            return
        self._queue(_packet("hide"), coalesce_group="visibility")

    @Slot(dict)
    def send_configuration(self, configuration: dict) -> None:
        """Send only allowlisted presentation settings."""
        if self._failed:
            return
        self._queue(
            _packet("configure", _sanitize_configuration(configuration)),
            coalesce_group="configure",
        )

    @Slot(object, float)
    def send_snapshot(self, rows: Any, duration: float) -> None:
        """Publish normalized rows, replacing any queued stale snapshot."""
        if self._failed:
            return
        try:
            safe_duration = float(duration)
        except (TypeError, ValueError, OverflowError):
            safe_duration = 0.0
        if not math.isfinite(safe_duration):
            safe_duration = 0.0
        self._snapshot_sequence += 1
        self._queue(
            _packet(
                "snapshot",
                {
                    "sequence": self._snapshot_sequence,
                    "rows": _sanitize_rows(rows),
                    "duration": max(0.0, safe_duration),
                },
            ),
            coalesce_group="snapshot",
        )

    @Slot(bool)
    def send_parser_state(self, active: bool) -> None:
        """Mirror parser state for controls; the child never owns a parser."""
        if self._failed:
            return
        self._queue(
            _packet("parser-state", {"active": bool(active)}),
            coalesce_group="parser-state",
        )

    @Slot()
    def shutdown(self) -> None:
        """Ask the child to exit and bound teardown if it is unresponsive."""
        self._expected_shutdown = True
        self._startup_timer.stop()
        self._outbox.clear()
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        try:
            process.write(self._encode(_packet("shutdown")))
            process.waitForBytesWritten(50)
            process.closeWriteChannel()
        except RuntimeError:
            pass
        # QApplication teardown may begin immediately after this method, so Qt
        # timers are not a reliable orphan-prevention mechanism here.  Bound the
        # complete graceful/terminate/kill sequence to roughly 1.5 seconds.
        if process.waitForFinished(750):
            return
        process.terminate()
        if process.waitForFinished(500):
            return
        process.kill()
        process.waitForFinished(250)

    def _start(self) -> bool:
        if self._failed or self.running:
            return not self._failed
        entry = Path(__file__).resolve().parents[1] / "retro_escalation.py"
        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = [
                "--wayland-live-presenter",
                "--app-dir",
                self._app_dir,
            ]
        else:
            if not entry.is_file():
                self._fail("the hidden presenter entry point was not found")
                return False
            program = sys.executable
            arguments = [
                str(entry),
                "--wayland-live-presenter",
                "--app-dir",
                self._app_dir,
            ]

        process = QProcess(self)
        self._process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        try:
            overrides = _environment_overrides(self._support)
        except LayerShellError as error:
            self._fail(str(error))
            return False
        for name, value in overrides.items():
            environment.insert(name, value)

        try:
            runtime_root = QLibraryInfo.path(
                QLibraryInfo.LibraryPath.PluginsPath)
        except (AttributeError, TypeError):
            runtime_root = ""
        plugin_paths = _ordered_plugin_paths(
            environment.value("QT_PLUGIN_PATH"),
            runtime_root,
            str(self._support.plugin_root),
        )
        environment.insert("QT_PLUGIN_PATH", os.pathsep.join(plugin_paths))

        environment.insert("QT_QPA_PLATFORM", "wayland")
        process.setProcessEnvironment(environment)
        if Path(self._app_dir).is_dir():
            process.setWorkingDirectory(self._app_dir)

        process.started.connect(self._on_started)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.bytesWritten.connect(self._on_bytes_written)
        process.errorOccurred.connect(self._on_process_error)
        process.finished.connect(self._on_finished)
        self._ready_received = False
        self._expected_shutdown = False
        self._failure_reported = False
        self._startup_timer.start()
        process.start(program, arguments)
        return True

    def _queue(
        self, packet: dict[str, Any], *, coalesce_group: str | None = None
    ) -> None:
        if coalesce_group is not None:
            if coalesce_group == "visibility":
                # Before the first ready event, a buffered show is also the
                # layer-surface handshake.  A quick user close must leave that
                # show ahead of the hide so the child can configure once and
                # remain reusable instead of timing out permanently.
                preserve_initial_show = (
                    packet.get("type") == "hide"
                    and not self._ready_received
                    and any(
                        pending.get("_group") == "visibility"
                        and pending.get("type") == "show"
                        for pending in self._outbox
                    )
                )
                if preserve_initial_show:
                    self._outbox = [
                        pending
                        for pending in self._outbox
                        if not (
                            pending.get("_group") == "visibility"
                            and pending.get("type") == "hide"
                        )
                    ]
                    packet["_group"] = coalesce_group
                    self._outbox.append(packet)
                    self._flush_outbox()
                    return
                matching = {"visibility"}
            else:
                matching = {coalesce_group}
            self._outbox = [
                pending
                for pending in self._outbox
                if pending.get("_group") not in matching
            ]
            packet["_group"] = coalesce_group
        self._outbox.append(packet)
        self._flush_outbox()

    @staticmethod
    def _encode(packet: dict[str, Any]) -> bytes:
        wire_packet = {key: value for key, value in packet.items() if key != "_group"}
        encoded = (
            json.dumps(
                wire_packet,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        if len(encoded) - 1 > MAX_CHILD_LINE:
            raise ValueError("presenter protocol message exceeds the child line limit")
        return encoded

    def _flush_outbox(self) -> None:
        process = self._process
        if (
            process is None
            or process.state() != QProcess.ProcessState.Running
            or self._failed
        ):
            return
        while self._outbox and process.bytesToWrite() <= MAX_WRITE_BACKLOG:
            packet = self._outbox.pop(0)
            try:
                written = process.write(self._encode(packet))
            except (RuntimeError, TypeError, ValueError) as error:
                self._fail(f"the presenter pipe rejected a message: {error}")
                return
            if written < 0:
                self._fail("the presenter pipe closed while sending a message")
                return

    @Slot()
    def _on_started(self) -> None:
        self._flush_outbox()

    @Slot(int)
    def _on_bytes_written(self, count: int) -> None:
        del count
        self._flush_outbox()

    @Slot()
    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        self._stdout_buffer.extend(bytes(process.readAllStandardOutput()))
        if len(self._stdout_buffer) > MAX_CHILD_LINE * 2:
            self._fail("the presenter sent an oversized protocol message")
            return
        while b"\n" in self._stdout_buffer:
            line, _, remainder = self._stdout_buffer.partition(b"\n")
            self._stdout_buffer = bytearray(remainder)
            if not line:
                continue
            if len(line) > MAX_CHILD_LINE:
                self._fail("the presenter sent an oversized protocol message")
                return
            self._handle_child_line(bytes(line))

    @Slot()
    def _read_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        self._stderr_tail.extend(bytes(process.readAllStandardError()))
        if len(self._stderr_tail) > 16_384:
            del self._stderr_tail[:-16_384]

    def _handle_child_line(self, line: bytes) -> None:
        try:
            packet = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(packet, dict) or packet.get("protocol") != PROTOCOL:
            return
        event_type = packet.get("type")
        if event_type not in {"ready", "close", "parser", "geometry", "error"}:
            return
        payload = packet.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "ready":
            if not self._ready_received:
                self._ready_received = True
                self._startup_timer.stop()
                self.ready.emit()
            return
        if event_type == "close":
            self.close_requested.emit()
            return
        if event_type == "parser":
            active = payload.get("active")
            if isinstance(active, bool):
                self.parser_requested.emit(active)
            return
        if event_type == "geometry":
            geometry: dict[str, int] = {}
            limits = {
                "left": (0, 100_000),
                "top": (0, 100_000),
                "width": (0, 16_384),
                "height": (0, 16_384),
            }
            for key, (minimum, maximum) in limits.items():
                value = payload.get(key)
                if isinstance(value, bool) or not isinstance(value, int):
                    return
                geometry[key] = max(minimum, min(maximum, value))
            self.geometry_changed.emit(geometry)
            return
        message = payload.get("message")
        self._fail(
            str(message)[:1_024] if isinstance(message, str) else "presenter error"
        )

    @Slot()
    def _on_startup_timeout(self) -> None:
        if not self._ready_received and not self._expected_shutdown:
            self._fail("the native Wayland presenter did not become ready")

    @Slot(object)
    def _on_process_error(self, error: object) -> None:
        if self._expected_shutdown:
            return
        process = self._process
        detail = process.errorString() if process is not None else str(error)
        self._fail(f"the native Wayland presenter failed: {detail}")

    @Slot(int, object)
    def _on_finished(self, exit_code: int, exit_status: object) -> None:
        self._startup_timer.stop()
        if self._expected_shutdown:
            return
        self._fail(
            f"the native Wayland presenter exited unexpectedly (code {exit_code})"
        )

    def _fail(self, reason: str) -> None:
        if self._expected_shutdown:
            return
        self._failed = True
        self._startup_timer.stop()
        self._outbox.clear()
        process = self._process
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
        if not self._failure_reported:
            self._failure_reported = True
            self.unavailable.emit(str(reason)[:2_048])

__all__ = [
    "ANCHOR_BOTTOM",
    "ANCHOR_LEFT",
    "ANCHOR_NONE",
    "ANCHOR_RIGHT",
    "ANCHOR_TOP",
    "KEYBOARD_EXCLUSIVE",
    "KEYBOARD_NONE",
    "KEYBOARD_ON_DEMAND",
    "LAYER_BACKGROUND",
    "LAYER_BOTTOM",
    "LAYER_OVERLAY",
    "LAYER_TOP",
    "LayerShellError",
    "LayerShellSupport",
    "LayerShellUnavailable",
    "PROTOCOL",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "WaylandPresentationProcess",
    "configure_as_overlay",
    "create_relative_pointer",
    "detect_layer_shell_support",
    "detect_layershell_support",
    "layershell_supported",
    "prepare_environment",
    "set_margins",
]
