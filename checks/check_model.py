"""Small dependency-free model checks; not a Home Assistant test suite."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "metronome"
# Load only the pure model, without importing the HA integration entry point.
package = types.ModuleType("metronome_model_check")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location(f"{package.__name__}.model", PACKAGE / "model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
Session = model.Session


class ModelChecks(unittest.TestCase):
    def test_count_in_and_finish(self):
        s = Session(
            {"bpm": 120, "signature": "6/8", "count_in": 2, "timer_enabled": True, "duration": 5}
        )
        self.assertEqual(s.start(100), "started")
        self.assertEqual(s.anchor_beat, -4)
        self.assertAlmostEqual(s.ends_at, 107.2)
        self.assertEqual(s.remaining_at(101), 5)
        self.assertIsNone(s.finish_due(107.19))
        self.assertEqual(s.finish_due(107.2), "finished")
        self.assertTrue(s.completed)
        self.assertIsNone(s.finish_due(108))

    def test_pause_resume_preserves_time(self):
        s = Session({"timer_enabled": True, "duration": 30})
        s.start(0)
        s.pause(10.2)
        self.assertAlmostEqual(s.remaining, 20)
        self.assertIsNone(s.ends_at)
        self.assertEqual(s.start(100), "resumed")
        self.assertAlmostEqual(s.ends_at, 120.2)

    def test_pause_during_count_in(self):
        s = Session({"timer_enabled": True, "count_in": 1, "duration": 30})
        s.start(0)
        s.pause(1.2)
        self.assertAlmostEqual(s.anchor_beat, -2)
        self.assertEqual(s.remaining, 30)
        s.start(100)
        self.assertAlmostEqual(s.ends_at, 131.2)

    def test_tempo_changes_do_not_extend_running_timer(self):
        s = Session({"timer_enabled": True, "duration": 30})
        s.start(0)
        before = s.position(10)
        s.configure({"bpm": 60}, 10)
        self.assertAlmostEqual(s.position(10), before)
        self.assertAlmostEqual(s.ends_at, 30.2)

    def test_count_in_tempo_change_moves_finish(self):
        s = Session({"timer_enabled": True, "count_in": 1, "duration": 5})
        s.start(0)
        s.configure({"bpm": 60}, 1.2)
        self.assertAlmostEqual(s.anchor_beat, -2)
        self.assertAlmostEqual(s.ends_at, 8.2)

    def test_indefinite_mode_rejects_pause(self):
        s = Session()
        s.start(1)
        self.assertIsNone(s.ends_at)
        self.assertIsNone(s.finish_due(100000))
        with self.assertRaises(ValueError):
            s.pause(2)

    def test_stop_and_restart_restores_duration(self):
        s = Session({"timer_enabled": True})
        s.start(0)
        s.pause(10)
        s.stop()
        self.assertEqual(s.remaining, 30)
        self.assertEqual(s.start(50), "started")
        self.assertAlmostEqual(s.ends_at, 80.2)

    def test_validation_is_atomic(self):
        s = Session()
        for patch in (
            {"bpm": 201},
            {"bpm": True},
            {"duration": 0},
            {"bpm": float("nan")},
            {"count_in": 1.5},
            {"signature": "7/8"},
            {"volume": 2},
            {"bpm": 80, "duration": -1},
        ):
            with self.assertRaises(ValueError):
                s.configure(patch, 0)
            self.assertEqual(s.settings["bpm"], 120)

    def test_session_locks_structural_settings(self):
        s = Session({"timer_enabled": True})
        s.start(0)
        for patch in (
            {"duration": 90},
            {"timer_enabled": False},
            {"signature": "3/4"},
            {"count_in": 1},
        ):
            with self.assertRaises(ValueError):
                s.configure(patch, 2)
        s.configure({"muted": True, "volume": 0.1, "accent": False}, 2)
        self.assertTrue(s.settings["muted"])

    def test_settings_restore_never_restores_session(self):
        s = Session({"timer_enabled": True, "duration": 359999, "bpm": 1})
        s.start(0)
        restored = Session(s.settings)
        self.assertEqual(restored.state, "idle")
        self.assertIsNone(restored.ends_at)
        self.assertEqual(restored.settings["duration"], 359999)


if __name__ == "__main__":
    unittest.main()
