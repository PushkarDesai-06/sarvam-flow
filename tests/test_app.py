import os
import queue
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

with patch.dict(sys.modules, {"pynput": SimpleNamespace(keyboard=SimpleNamespace(Key=SimpleNamespace(ctrl_r="ctrl_r")))}):
    import app
    import flow


class AppTests(unittest.TestCase):
    def setUp(self):
        self.ui = app.DictationApp.__new__(app.DictationApp)
        self.ui.root = MagicMock()
        self.ui.events = queue.Queue()
        self.ui.closed = threading.Event()
        self.ui.busy = False
        self.ui.source = None
        self.ui.hotkey_down = False
        self.ui.listener = MagicMock()
        self.ui.recorder = MagicMock(active=False)
        for name in ("status", "api_key", "key_status", "key_entry", "key_button", "language_box", "mode_box", "record_button", "transcript", "copy_button", "typist"):
            setattr(self.ui, name, MagicMock())
        self.ui.language = MagicMock()
        self.ui.language.get.return_value = "Marathi"
        self.ui.mode = MagicMock()
        self.ui.mode.get.return_value = "Transcribe"

    def test_missing_key_does_not_start_microphone(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": ""}):
            self.ui.start_recording("button")
        self.ui.recorder.start.assert_not_called()

    def test_user_key_replaces_existing_key_and_clears_textbox(self):
        self.ui.api_key.get.return_value = "  user-test-key  "
        with patch.dict(os.environ, {"SARVAM_API_KEY": "old-test-key"}):
            self.ui.use_key()
            self.assertEqual(os.environ["SARVAM_API_KEY"], "user-test-key")
        self.ui.api_key.set.assert_called_once_with("")
        self.assertNotIn("user-test-key", self.ui.status.set.call_args.args[0])

    def test_blank_key_preserves_current_key(self):
        self.ui.api_key.get.return_value = "  "
        with patch.dict(os.environ, {"SARVAM_API_KEY": "old-test-key"}):
            self.ui.use_key()
            self.assertEqual(os.environ["SARVAM_API_KEY"], "old-test-key")

    def test_key_cannot_change_during_recording_or_transcription(self):
        self.ui.api_key.get.return_value = "new-test-key"
        with patch.dict(os.environ, {"SARVAM_API_KEY": "old-test-key"}):
            for busy, recording in ((True, False), (False, True)):
                self.ui.busy = busy
                self.ui.recorder.active = recording
                self.ui.use_key()
                self.assertEqual(os.environ["SARVAM_API_KEY"], "old-test-key")

    def test_hotkey_repeat_produces_one_press(self):
        self.ui.on_press(flow.HOTKEY)
        self.ui.on_press(flow.HOTKEY)
        self.ui.on_release(flow.HOTKEY)
        self.assertEqual(list(self.ui.events.queue), [("press", None), ("release", None)])

    def test_hotkey_release_does_not_stop_button_recording(self):
        self.ui.source = "button"
        self.ui.events.put(("release", None))
        self.ui.process_events()
        self.ui.recorder.stop.assert_not_called()

    def test_busy_rejects_new_recording(self):
        self.ui.busy = True
        self.ui.start_recording("hotkey")
        self.ui.recorder.start.assert_not_called()

    def test_stop_snapshots_selected_settings(self):
        self.ui.recorder.active = True
        pcm = b"\0" * flow.BYTES_PER_SECOND
        def stop():
            self.ui.recorder.active = False
            return pcm
        self.ui.recorder.stop.side_effect = stop
        with patch.object(app, "play_tone"), patch.object(app.threading, "Thread") as worker:
            self.ui.stop_recording()
        self.assertTrue(self.ui.busy)
        self.assertEqual(worker.call_args.kwargs["args"], (pcm, "transcribe", "mr-IN"))

    def test_button_result_never_types_into_another_app(self):
        self.ui.source = "button"
        self.ui.root.focus_displayof.return_value = None
        with patch.object(app.threading, "Thread") as worker:
            self.ui.show_result("नमस्कार")
        worker.assert_not_called()
        self.ui.transcript.insert.assert_called_once_with("1.0", "नमस्कार")

    def test_hotkey_result_does_not_type_into_settings(self):
        self.ui.source = "hotkey"
        self.ui.root.focus_displayof.return_value = self.ui.key_entry
        with patch.object(app.threading, "Thread") as worker:
            self.ui.show_result("नमस्कार")
        worker.assert_not_called()

    def test_hotkey_result_types_when_another_app_is_focused(self):
        self.ui.source = "hotkey"
        self.ui.root.focus_displayof.return_value = None
        with patch.object(app.threading, "Thread") as worker:
            self.ui.show_result("नमस्कार")
        self.assertEqual(worker.call_args.kwargs["args"], ("नमस्कार",))

    def test_api_failure_returns_safe_error_to_ui(self):
        with patch.object(app, "transcribe_pcm", side_effect=RuntimeError("sensitive detail")):
            self.ui.recognize(b"audio", "transcribe", "mr-IN")
        event, message = self.ui.events.get_nowait()
        self.assertEqual(event, "error")
        self.assertNotIn("sensitive detail", message)

    def test_close_stops_capture_and_discards_pending_results(self):
        self.ui.recorder.active = True
        self.ui.close()
        self.ui.listener.stop.assert_called_once()
        self.ui.recorder.stop.assert_called_once()
        self.ui.events.put(("result", "नमस्कार"))
        self.ui.process_events()
        self.ui.type_text("नमस्कार")
        self.ui.transcript.insert.assert_not_called()
        self.ui.typist.type.assert_not_called()


class AudioTests(unittest.TestCase):
    def test_selected_settings_reach_every_chunk(self):
        with patch.object(flow, "transcribe", return_value=("नमस्कार", "mr-IN")) as recognize:
            result = flow.transcribe_pcm(b"\0" * flow.BYTES_PER_SECOND * 30, "verbatim", "mr-IN")
        self.assertEqual(result, "नमस्कार नमस्कार")
        self.assertEqual(recognize.call_count, 2)
        for call in recognize.call_args_list:
            self.assertEqual(call.args[1], "verbatim")
            self.assertEqual(call.kwargs["language_code"], "mr-IN")

    def test_microphone_start_failure_releases_device(self):
        recorder = flow.Recorder()
        with patch.object(flow.sd, "RawInputStream") as stream:
            stream.return_value.start.side_effect = RuntimeError("unavailable")
            with self.assertRaises(RuntimeError):
                recorder.start()
            stream.return_value.close.assert_called_once()
        self.assertFalse(recorder.active)

    def test_microphone_stop_failure_releases_device(self):
        recorder = flow.Recorder()
        stream = MagicMock()
        stream.stop.side_effect = RuntimeError("disconnected")
        recorder.stream = stream
        with self.assertRaises(RuntimeError):
            recorder.stop()
        stream.close.assert_called_once()
        self.assertFalse(recorder.active)


if __name__ == "__main__":
    unittest.main()
