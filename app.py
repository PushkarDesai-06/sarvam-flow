import os
import queue
import sys
import threading
import tkinter as tk
import wave
from tkinter import ttk

from pynput import keyboard

from flow import BYTES_PER_SECOND, HOTKEY, MIN_SECONDS, SOUNDS_DIR, Recorder, play_tone, transcribe_pcm
from transcribe import load_env

LANGUAGES = {
    "Marathi": "mr-IN",
    "Auto-detect": "unknown",
    "Hindi": "hi-IN",
    "English": "en-IN",
    "Bengali": "bn-IN",
    "Gujarati": "gu-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
    "Odia": "od-IN",
    "Punjabi": "pa-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
}
MODES = {
    "Transcribe": "transcribe",
    "Mixed languages": "codemix",
    "Translate to English": "translate",
    "Roman script": "translit",
    "Verbatim": "verbatim",
}


class DictationApp:
    def __init__(self, root: tk.Tk, enable_hotkey: bool = True):
        self.root = root
        self.events = queue.Queue()
        self.recorder = Recorder()
        self.closed = threading.Event()
        self.busy = False
        self.source = None
        self.hotkey_down = False
        self.listener = None
        self.typist = keyboard.Controller()
        self.language = tk.StringVar(value="Marathi")
        self.mode = tk.StringVar(value="Transcribe")
        self.status = tk.StringVar(value="Ready")
        self.api_key = tk.StringVar()
        self.key_status = tk.StringVar()
        self.build_window()
        self.update_key_status()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if enable_hotkey:
            try:
                self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                self.listener.start()
            except Exception:
                self.status.set("Hotkey unavailable. Use the Record button.")
        self.root.after(50, self.process_events)

    def build_window(self):
        self.root.title("Sarvam Flow")
        self.root.geometry("580x640")
        self.root.minsize(500, 580)
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 12, "bold"))
        body = ttk.Frame(self.root, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Sarvam Flow", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Your voice, in your language.").pack(anchor="w", pady=(4, 20))

        settings = ttk.Frame(body)
        settings.pack(fill="x")
        settings.columnconfigure((0, 1), weight=1)
        ttk.Label(settings, text="Language").grid(row=0, column=0, sticky="w")
        ttk.Label(settings, text="Output").grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.language_box = ttk.Combobox(settings, textvariable=self.language, values=list(LANGUAGES), state="readonly")
        self.language_box.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.mode_box = ttk.Combobox(settings, textvariable=self.mode, values=list(MODES), state="readonly")
        self.mode_box.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(6, 0))

        ttk.Label(body, textvariable=self.status, style="Status.TLabel", wraplength=480).pack(anchor="w", pady=(22, 8))
        self.record_button = ttk.Button(body, text="Start recording", command=self.toggle_recording)
        self.record_button.pack(fill="x", ipady=6)
        ttk.Label(body, text="Record here to preview text. In another app, hold Right Ctrl\nand release to type there. Keep that app focused until text arrives.").pack(anchor="w", pady=(10, 18))

        transcript_header = ttk.Frame(body)
        transcript_header.pack(fill="x")
        ttk.Label(transcript_header, text="Latest transcript").pack(side="left")
        self.copy_button = ttk.Button(transcript_header, text="Copy", command=self.copy_text, state="disabled")
        self.copy_button.pack(side="right")
        self.transcript = tk.Text(body, height=6, wrap="word", font=("Segoe UI", 11), state="disabled")
        self.transcript.pack(fill="both", expand=True, pady=(6, 16))

        ttk.Separator(body).pack(fill="x", pady=(0, 12))
        ttk.Label(body, text="Your Sarvam API key").pack(anchor="w")
        ttk.Label(body, textvariable=self.key_status).pack(anchor="w")
        key_row = ttk.Frame(body)
        key_row.pack(fill="x", pady=(6, 0))
        self.key_entry = ttk.Entry(key_row, textvariable=self.api_key, show="*")
        self.key_entry.pack(side="left", fill="x", expand=True)
        self.key_entry.bind("<Return>", lambda event: self.use_key())
        self.key_button = ttk.Button(key_row, text="Use key", command=self.use_key)
        self.key_button.pack(side="right", padx=(8, 0))
        ttk.Label(body, text="Key entered here is used for this session only.").pack(anchor="w", pady=(5, 0))

    def update_key_status(self):
        configured = bool(os.environ.get("SARVAM_API_KEY", "").strip())
        self.key_status.set("Key configured. You can replace it below." if configured else "Paste your own key below, then click Use key.")

    def use_key(self):
        if self.busy or self.recorder.active:
            return
        key = self.api_key.get().strip()
        if not key:
            self.status.set("Enter an API key before clicking Use key.")
            self.key_entry.focus_set()
            return
        os.environ["SARVAM_API_KEY"] = key
        self.api_key.set("")
        self.update_key_status()
        self.status.set("Key set for this session. Ready to record.")

    def on_press(self, key):
        if key == HOTKEY and not self.hotkey_down:
            self.hotkey_down = True
            self.events.put(("press", None))

    def on_release(self, key):
        if key == HOTKEY:
            self.hotkey_down = False
            self.events.put(("release", None))

    def set_controls(self):
        locked = self.busy or self.recorder.active
        for widget in (self.language_box, self.mode_box):
            widget.configure(state="disabled" if locked else "readonly")
        for widget in (self.key_entry, self.key_button):
            widget.configure(state="disabled" if locked else "normal")
        self.record_button.configure(
            text="Transcribing..." if self.busy else "Stop recording" if self.recorder.active else "Start recording",
            state="disabled" if self.busy else "normal",
        )

    def toggle_recording(self):
        if self.recorder.active:
            self.stop_recording()
        else:
            self.start_recording("button")

    def start_recording(self, source):
        if self.busy or self.recorder.active:
            return
        if not os.environ.get("SARVAM_API_KEY", "").strip():
            self.status.set("Add an API key first.")
            self.key_entry.focus_set()
            return
        try:
            self.recorder.start()
        except Exception:
            self.status.set("Microphone unavailable. Check your device and permissions.")
            return
        self.source = source
        self.status.set("Recording...")
        self.set_controls()
        play_tone("recording-started.wav")

    def stop_recording(self):
        if not self.recorder.active:
            return
        try:
            pcm = self.recorder.stop()
        except Exception:
            self.status.set("Recording failed. Check your microphone and try again.")
            self.set_controls()
            return
        play_tone("recording-stopped.wav")
        if len(pcm) < MIN_SECONDS * BYTES_PER_SECOND:
            self.status.set("Recording too short. Hold a little longer.")
            self.set_controls()
            return
        self.busy = True
        self.status.set("Transcribing...")
        self.set_controls()
        threading.Thread(
            target=self.recognize,
            args=(pcm, MODES[self.mode.get()], LANGUAGES[self.language.get()]),
            daemon=True,
        ).start()

    def recognize(self, pcm, mode, language):
        try:
            text = transcribe_pcm(pcm, mode=mode, language_code=language)
            self.events.put(("result", text))
        except Exception:
            self.events.put(("error", "Transcription failed. Check your connection, API key and credits."))

    def type_text(self, text):
        try:
            for character in text + " ":
                if self.closed.is_set():
                    return
                self.typist.type(character)
            self.events.put(("done", "Text inserted"))
        except Exception:
            self.events.put(("error", "Could not insert text. Use Copy to paste the transcript."))

    def show_result(self, text):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.insert("1.0", text)
        self.transcript.configure(state="disabled")
        self.copy_button.configure(state="normal" if text else "disabled")
        if text and self.source == "hotkey" and self.root.focus_displayof() is None:
            self.status.set("Inserting text...")
            threading.Thread(target=self.type_text, args=(text,), daemon=True).start()
        else:
            self.finish("Transcript ready" if text else "No speech detected. Try again.")

    def finish(self, status):
        self.busy = False
        self.status.set(status)
        self.set_controls()

    def process_events(self):
        if self.closed.is_set():
            return
        for _ in range(100):
            try:
                event, value = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "press":
                self.start_recording("hotkey")
            elif event == "release" and self.source == "hotkey":
                self.stop_recording()
            elif event == "result":
                self.show_result(value)
            elif event in ("error", "done"):
                self.finish(value)
        self.root.after(50, self.process_events)

    def copy_text(self):
        text = self.transcript.get("1.0", "end-1c")
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status.set("Copied to clipboard")

    def close(self):
        self.closed.set()
        if self.listener is not None:
            self.listener.stop()
        try:
            if self.recorder.active:
                self.recorder.stop()
        finally:
            self.root.destroy()


def smoke_test():
    root = tk.Tk()
    root.withdraw()
    ui = DictationApp(root, enable_hotkey=False)
    try:
        root.update_idletasks()
        assert ui.language.get() == "Marathi"
        assert ui.mode.get() == "Transcribe"
        assert ui.key_entry.cget("show") == "*"
        ui.show_result("नमस्कार")
        assert ui.transcript.get("1.0", "end-1c") == "नमस्कार"
        for name in ("recording-started.wav", "recording-stopped.wav"):
            with wave.open(str(SOUNDS_DIR / name), "rb") as audio:
                assert audio.getsampwidth() == 2 and audio.getnframes() > 0
    finally:
        ui.close()


def main():
    if "--smoke-test" in sys.argv:
        smoke_test()
        return
    load_env()
    root = tk.Tk()
    DictationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
