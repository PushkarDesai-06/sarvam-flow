import io
import threading
import wave

import sounddevice as sd
from pynput import keyboard

from transcribe import load_env, transcribe

HOTKEY = keyboard.Key.ctrl_r
MODE = "codemix"
SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2
MAX_CHUNK_SECONDS = 29
MIN_SECONDS = 0.3


def to_wav(pcm: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    buffer.seek(0)
    return buffer


def transcribe_pcm(pcm: bytes) -> str:
    chunk_size = MAX_CHUNK_SECONDS * BYTES_PER_SECOND
    chunks = (pcm[i : i + chunk_size] for i in range(0, len(pcm), chunk_size))
    texts = (transcribe(("speech.wav", to_wav(chunk), "audio/wav"), MODE)[0] for chunk in chunks)
    return " ".join(text.strip() for text in texts if text).strip()


class Recorder:
    def __init__(self):
        self.frames: list[bytes] = []
        self.stream: sd.RawInputStream | None = None

    @property
    def active(self) -> bool:
        return self.stream is not None

    def start(self) -> None:
        self.frames = []
        self.stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            callback=lambda data, *_: self.frames.append(bytes(data)),
        )
        self.stream.start()

    def stop(self) -> bytes:
        self.stream.stop()
        self.stream.close()
        self.stream = None
        return b"".join(self.frames)


def main() -> None:
    load_env()
    recorder = Recorder()
    typist = keyboard.Controller()
    delivery_lock = threading.Lock()

    def deliver(pcm: bytes) -> None:
        if len(pcm) < MIN_SECONDS * BYTES_PER_SECOND:
            return
        with delivery_lock:
            try:
                text = transcribe_pcm(pcm)
            except Exception as error:
                print(f"Transcription failed: {error}", flush=True)
                return
            if text:
                typist.type(text + " ")
                print(f"> {text}", flush=True)

    def on_press(key) -> None:
        if key == HOTKEY and not recorder.active:
            recorder.start()
            print("Listening...", flush=True)

    def on_release(key) -> None:
        if key == HOTKEY and recorder.active:
            threading.Thread(target=deliver, args=(recorder.stop(),), daemon=True).start()

    print("Hold Right Ctrl and speak. Release to type. Ctrl+C here to quit.", flush=True)
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
