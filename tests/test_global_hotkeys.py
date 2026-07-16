import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from re_oscr.globalhotkeys import (
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    GlobalHotkeyController,
    key_sequence_to_windows,
)


class FakeHotkeyBackend:
    supported = True

    def __init__(self):
        self.callback = None
        self.registered = {}
        self.rejected = set()
        self.shutdown_count = 0

    def register(self, hotkey_id, hotkey):
        if hotkey.text in self.rejected:
            return False, f"{hotkey.text} is already in use."
        self.registered[hotkey_id] = hotkey
        return True, ""

    def unregister(self, hotkey_id):
        self.registered.pop(hotkey_id, None)

    def shutdown(self):
        self.shutdown_count += 1
        self.registered.clear()


class GlobalHotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_controller(self):
        backend = FakeHotkeyBackend()

        def factory(_app, callback):
            backend.callback = callback
            return backend

        controller = GlobalHotkeyController(self.app, backend_factory=factory)
        self.addCleanup(controller.shutdown)
        return controller, backend

    def test_supported_chord_is_canonical_and_maps_windows_modifiers(self):
        hotkey = key_sequence_to_windows("Ctrl+Shift+L")

        self.assertEqual(hotkey.text, "Ctrl+Shift+L")
        self.assertEqual(hotkey.virtual_key, ord("L"))
        self.assertTrue(hotkey.modifiers & MOD_CONTROL)
        self.assertTrue(hotkey.modifiers & MOD_SHIFT)
        self.assertTrue(hotkey.modifiers & MOD_NOREPEAT)

    def test_unsafe_or_reserved_bindings_are_rejected(self):
        for binding in ("A", "Space", "F12", "Ctrl+K, Ctrl+C"):
            with self.subTest(binding=binding):
                with self.assertRaises(ValueError):
                    key_sequence_to_windows(binding)

        self.assertEqual(key_sequence_to_windows("F8").text, "F8")

    def test_failed_rebind_keeps_previous_registration(self):
        controller, backend = self.make_controller()
        self.assertTrue(controller.start("Ctrl+Shift+L"))
        previous_id = controller._active_id
        backend.rejected.add("Ctrl+Alt+X")

        self.assertFalse(controller.bind("Ctrl+Alt+X"))
        self.assertEqual(controller.binding, "Ctrl+Shift+L")
        self.assertEqual(controller._active_id, previous_id)
        self.assertIn(previous_id, backend.registered)
        self.assertEqual(controller.state, "conflict")

    def test_capture_restores_previous_binding_when_candidate_conflicts(self):
        controller, backend = self.make_controller()
        self.assertTrue(controller.start("Ctrl+Shift+L"))
        backend.rejected.add("Ctrl+Alt+X")

        controller.begin_capture()
        self.assertEqual(controller.state, "capturing")
        self.assertEqual(backend.registered, {})
        self.assertFalse(controller.commit_capture("Ctrl+Alt+X"))

        self.assertEqual(controller.binding, "Ctrl+Shift+L")
        self.assertEqual(controller.state, "conflict")
        self.assertEqual(len(backend.registered), 1)

    def test_capture_reports_unbound_if_previous_registration_cannot_be_restored(self):
        controller, backend = self.make_controller()
        self.assertTrue(controller.start("Ctrl+Shift+L"))
        controller.begin_capture()
        backend.rejected.update(("Ctrl+Shift+L", "Ctrl+Alt+X"))

        self.assertFalse(controller.commit_capture("Ctrl+Alt+X"))

        self.assertEqual(controller.binding, "")
        self.assertEqual(controller.state, "conflict")
        self.assertIn("no global hotkey is active", controller.detail.lower())
        self.assertEqual(backend.registered, {})

    def test_native_activation_is_deferred_and_shutdown_is_idempotent(self):
        controller, backend = self.make_controller()
        activations = []
        controller.activated.connect(lambda: activations.append(True))
        self.assertTrue(controller.start("Ctrl+Shift+L"))

        backend.callback(controller._active_id)
        self.assertEqual(activations, [])
        self.app.processEvents()
        self.assertEqual(activations, [True])

        controller.shutdown()
        controller.shutdown()
        self.assertEqual(backend.shutdown_count, 1)
        self.assertEqual(backend.registered, {})


if __name__ == "__main__":
    unittest.main()
