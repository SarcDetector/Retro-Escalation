"""Small, isolated global-hotkey service for Command Console presentation controls."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, QTimer, Signal
from PySide6.QtGui import QKeySequence


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
PRIMARY_HOTKEY_ID = 0x5245
SECONDARY_HOTKEY_ID = 0x5246


@dataclass(frozen=True)
class NativeHotkey:
    """Canonical portable text plus the Windows registration values."""

    text: str
    modifiers: int
    virtual_key: int


def _enum_value(value) -> int:
    return int(value.value if hasattr(value, 'value') else value)


def key_sequence_to_windows(text: str) -> NativeHotkey:
    """Translate one portable Qt chord into a conservative Windows hotkey."""
    from PySide6.QtCore import Qt

    sequence = QKeySequence.fromString(
        str(text).strip(), QKeySequence.SequenceFormat.PortableText)
    if sequence.isEmpty() or sequence.count() != 1:
        raise ValueError('Choose one key combination.')
    combination = sequence[0]
    key = _enum_value(combination.key())
    modifiers = combination.keyboardModifiers()
    allowed_modifiers = (
        Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.MetaModifier)
    if _enum_value(modifiers) & ~_enum_value(allowed_modifiers):
        raise ValueError(
            'Keypad and layout-specific modifiers are not supported for global bindings.')
    native_modifiers = MOD_NOREPEAT
    if modifiers & Qt.KeyboardModifier.AltModifier:
        native_modifiers |= MOD_ALT
    if modifiers & Qt.KeyboardModifier.ControlModifier:
        native_modifiers |= MOD_CONTROL
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        native_modifiers |= MOD_SHIFT
    if modifiers & Qt.KeyboardModifier.MetaModifier:
        native_modifiers |= MOD_WIN

    key_a = _enum_value(Qt.Key.Key_A)
    key_z = _enum_value(Qt.Key.Key_Z)
    key_0 = _enum_value(Qt.Key.Key_0)
    key_9 = _enum_value(Qt.Key.Key_9)
    key_f1 = _enum_value(Qt.Key.Key_F1)
    key_f24 = _enum_value(Qt.Key.Key_F24)
    function_key = False
    if key_a <= key <= key_z or key_0 <= key <= key_9:
        virtual_key = key
    elif key_f1 <= key <= key_f24:
        function_key = True
        if key == _enum_value(Qt.Key.Key_F12):
            raise ValueError('F12 is reserved by Windows and cannot be registered.')
        virtual_key = 0x70 + key - key_f1
    else:
        virtual_keys = {
            _enum_value(Qt.Key.Key_Backspace): 0x08,
            _enum_value(Qt.Key.Key_Tab): 0x09,
            _enum_value(Qt.Key.Key_Return): 0x0D,
            _enum_value(Qt.Key.Key_Enter): 0x0D,
            _enum_value(Qt.Key.Key_Pause): 0x13,
            _enum_value(Qt.Key.Key_CapsLock): 0x14,
            _enum_value(Qt.Key.Key_Escape): 0x1B,
            _enum_value(Qt.Key.Key_Space): 0x20,
            _enum_value(Qt.Key.Key_PageUp): 0x21,
            _enum_value(Qt.Key.Key_PageDown): 0x22,
            _enum_value(Qt.Key.Key_End): 0x23,
            _enum_value(Qt.Key.Key_Home): 0x24,
            _enum_value(Qt.Key.Key_Left): 0x25,
            _enum_value(Qt.Key.Key_Up): 0x26,
            _enum_value(Qt.Key.Key_Right): 0x27,
            _enum_value(Qt.Key.Key_Down): 0x28,
            _enum_value(Qt.Key.Key_Insert): 0x2D,
            _enum_value(Qt.Key.Key_Delete): 0x2E,
        }
        try:
            virtual_key = virtual_keys[key]
        except KeyError as error:
            raise ValueError(
                'That key is not supported for a global binding. Use a letter, number, '
                'function key, or navigation key.') from error

    if not function_key and native_modifiers == MOD_NOREPEAT:
        raise ValueError(
            'Add Ctrl, Alt, Shift, or Win so the global binding does not capture normal typing.')

    canonical = QKeySequence(combination).toString(
        QKeySequence.SequenceFormat.PortableText)
    if not canonical:
        raise ValueError('Choose one key combination.')
    return NativeHotkey(canonical, native_modifiers, virtual_key)


class UnsupportedHotkeyBackend:
    """No-op backend used outside Windows."""

    supported = False

    def register(self, _hotkey_id: int, _hotkey: NativeHotkey) -> tuple[bool, str]:
        return False, 'Global hotkeys are currently available on Windows only.'

    def unregister(self, _hotkey_id: int) -> None:
        pass

    def shutdown(self) -> None:
        pass


class WindowsHotkeyBackend(QAbstractNativeEventFilter):
    """Register thread-queue hotkeys and receive WM_HOTKEY through Qt."""

    supported = True

    def __init__(self, app, callback: Callable[[int], None]):
        super().__init__()
        from ctypes import wintypes

        self._app = app
        self._callback = callback
        self._registered: set[int] = set()
        self._installed = False
        self._wintypes = wintypes
        self._user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._user32.RegisterHotKey.argtypes = (
            wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.UnregisterHotKey.restype = wintypes.BOOL

    def register(self, hotkey_id: int, hotkey: NativeHotkey) -> tuple[bool, str]:
        if not self._installed:
            self._app.installNativeEventFilter(self)
            self._installed = True
        ctypes.set_last_error(0)
        accepted = bool(self._user32.RegisterHotKey(
            None, hotkey_id, hotkey.modifiers, hotkey.virtual_key))
        if not accepted:
            error_code = ctypes.get_last_error()
            if not self._registered and self._installed:
                self._app.removeNativeEventFilter(self)
                self._installed = False
            return False, (
                f'Windows rejected {hotkey.text}; it may already be in use '
                f'(error {error_code}).')
        self._registered.add(hotkey_id)
        return True, ''

    def unregister(self, hotkey_id: int) -> None:
        if hotkey_id in self._registered:
            self._user32.UnregisterHotKey(None, hotkey_id)
            self._registered.discard(hotkey_id)
        if not self._registered and self._installed:
            self._app.removeNativeEventFilter(self)
            self._installed = False

    def nativeEventFilter(self, event_type, message):
        event_name = bytes(event_type).decode(errors='ignore')
        if event_name not in ('windows_dispatcher_MSG', 'windows_generic_MSG'):
            return False, 0
        try:
            native_message = self._wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0
        hotkey_id = int(native_message.wParam)
        if native_message.message == WM_HOTKEY and hotkey_id in self._registered:
            self._callback(hotkey_id)
            return True, 0
        return False, 0

    def shutdown(self) -> None:
        for hotkey_id in tuple(self._registered):
            self.unregister(hotkey_id)
        if self._installed:
            self._app.removeNativeEventFilter(self)
            self._installed = False


def create_hotkey_backend(app, callback):
    """Create the platform backend without importing Windows APIs elsewhere."""
    if sys.platform == 'win32':
        return WindowsHotkeyBackend(app, callback)
    return UnsupportedHotkeyBackend()


class GlobalHotkeyController(QObject):
    """Transactional binding state around the small native backend."""

    status_changed = Signal(str, str)
    activated = Signal()

    def __init__(self, app, parent=None, backend_factory=create_hotkey_backend):
        super().__init__(parent)
        self._backend = backend_factory(app, self._native_activated)
        self._binding = ''
        self._active_id: int | None = None
        self._captured_binding = ''
        self._capturing = False
        self._shutting_down = False
        self._state = 'unsupported' if not self._backend.supported else 'unbound'
        self._detail = (
            'Global hotkeys are currently available on Windows only.'
            if not self._backend.supported else 'No global hotkey is assigned.')

    @property
    def supported(self) -> bool:
        return bool(self._backend.supported)

    @property
    def binding(self) -> str:
        return self._binding

    @property
    def state(self) -> str:
        return self._state

    @property
    def detail(self) -> str:
        return self._detail

    def start(self, binding: str) -> bool:
        if self._shutting_down:
            return False
        if not self.supported:
            self._emit_status('unsupported', self._detail)
            return not str(binding).strip()
        return self.bind(binding)

    def bind(self, binding: str) -> bool:
        if self._shutting_down:
            return False
        candidate_text = str(binding).strip()
        if not self.supported:
            self._emit_status(
                'unsupported', 'Global hotkeys are currently available on Windows only.')
            return False
        if not candidate_text:
            self.clear()
            return True
        try:
            candidate = key_sequence_to_windows(candidate_text)
        except ValueError as error:
            self._emit_status('invalid', str(error))
            return False
        if candidate.text == self._binding and self._active_id is not None:
            self._emit_status('registered', f'{candidate.text} is registered globally.')
            return True

        candidate_id = (
            PRIMARY_HOTKEY_ID if self._active_id != PRIMARY_HOTKEY_ID
            else SECONDARY_HOTKEY_ID)
        accepted, detail = self._backend.register(candidate_id, candidate)
        if not accepted:
            self._emit_status('conflict', detail)
            return False
        previous_id = self._active_id
        if previous_id is not None:
            self._backend.unregister(previous_id)
        self._active_id = candidate_id
        self._binding = candidate.text
        self._emit_status('registered', f'{candidate.text} is registered globally.')
        return True

    def clear(self) -> None:
        if self._shutting_down:
            return
        if self._active_id is not None:
            self._backend.unregister(self._active_id)
        self._active_id = None
        self._binding = ''
        self._emit_status(
            'unsupported' if not self.supported else 'unbound',
            'Global hotkeys are currently available on Windows only.'
            if not self.supported else 'No global hotkey is assigned.')

    def begin_capture(self) -> None:
        if self._shutting_down or self._capturing or not self.supported:
            return
        self._capturing = True
        self._captured_binding = self._binding
        if self._active_id is not None:
            self._backend.unregister(self._active_id)
            self._active_id = None
        self._emit_status('capturing', 'Press one key combination.')

    def commit_capture(self, binding: str) -> bool:
        if self._shutting_down:
            return False
        previous = self._captured_binding
        self._capturing = False
        self._binding = ''
        accepted = self.bind(binding)
        if accepted:
            self._captured_binding = ''
            return True
        failed_state = self._state
        failed_detail = self._detail
        if previous:
            restored = self.bind(previous)
            if restored:
                self._emit_status(
                    failed_state,
                    f'{failed_detail} {previous} remains active.')
            else:
                self._binding = ''
                self._active_id = None
                self._emit_status(
                    'conflict', f'{failed_detail} The previous binding could not be '
                    'restored, so no global hotkey is active.')
        self._captured_binding = ''
        return False

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._active_id is not None:
            self._backend.unregister(self._active_id)
        self._active_id = None
        self._backend.shutdown()

    def _native_activated(self, hotkey_id: int) -> None:
        if self._shutting_down or hotkey_id != self._active_id:
            return
        QTimer.singleShot(0, self._deferred_activation)

    def _deferred_activation(self) -> None:
        if not self._shutting_down:
            self.activated.emit()

    def _emit_status(self, state: str, detail: str) -> None:
        self._state = state
        self._detail = detail
        self.status_changed.emit(state, detail)
