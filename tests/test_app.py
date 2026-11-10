import os
import queue
import sys
import threading
import unittest
from sarvamai.core.api_error import ApiError
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

with patch.dict(sys.modules, {"pynput": SimpleNamespace(keyboard=SimpleNamespace(Key=SimpleNamespace(ctrl_r="ctrl_r")))}):
    import app
    import flow


class AppTests(unittest.TestCase):
    def setUp(self):
        for name in ("read_key", "save_key", "remove_key"):
            patcher = patch.object(app, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
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
        self.save_key.assert_called_once_with("user-test-key")

    def test_saved_key_restored_on_restart_over_env_file(self):
        self.read_key.return_value = "saved-test-key"
        with patch.dict(os.environ, {"SARVAM_API_KEY": "env-test-key"}):
            self.ui.restore_key()
            self.assertEqual(os.environ["SARVAM_API_KEY"], "saved-test-key")

    def test_no_saved_key_preserves_environment(self):
        self.read_key.return_value = None
        with patch.dict(os.environ, {"SARVAM_API_KEY": "env-test-key"}):
            self.ui.restore_key()
            self.assertEqual(os.environ["SARVAM_API_KEY"], "env-test-key")

    def test_storage_failure_does_not_claim_key_was_saved(self):
        self.ui.api_key.get.return_value = "user-test-key"
        self.save_key.side_effect = RuntimeError("locked")
        with patch.dict(os.environ, {}, clear=True):
            self.ui.use_key()
            self.assertEqual(os.environ["SARVAM_API_KEY"], "user-test-key")
        self.assertIn("could not be saved", self.ui.status.set.call_args.args[0])

    def test_rejected_key_is_removed_and_requires_replacement(self):
        error = ApiError(status_code=403, body={"error": {"code": "invalid_api_key_error"}})
        with patch.object(app, "transcribe_pcm", side_effect=error), patch.dict(os.environ, {"SARVAM_API_KEY": "bad-test-key"}):
            self.ui.recognize(b"audio", "transcribe", "mr-IN")
            self.ui.process_events()
            self.assertNotIn("SARVAM_API_KEY", os.environ)
        self.remove_key.assert_called_once()

    def test_non_auth_errors_keep_saved_key(self):
        for status, code in ((402, "insufficient_quota_error"), (429, "rate_limit_exceeded_error"), (503, "internal_server_error"), (403, "TIER_LIMIT_REACHED")):
            with self.subTest(status=status):
                error = ApiError(status_code=status, body={"error": {"code": code}})
                with patch.object(app, "transcribe_pcm", side_effect=error), patch.dict(os.environ, {"SARVAM_API_KEY": "saved-test-key"}):
                    self.ui.recognize(b"audio", "transcribe", "mr-IN")
                    self.ui.process_events()
                    self.assertEqual(os.environ["SARVAM_API_KEY"], "saved-test-key")
        self.remove_key.assert_not_called()

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
