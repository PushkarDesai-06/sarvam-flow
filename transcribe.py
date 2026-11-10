import os
import sys
from pathlib import Path

from sarvamai import SarvamAI


def load_env(path: Path = Path(__file__).with_name(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())


def transcribe(audio, mode: str = "transcribe") -> tuple[str, str | None]:
    client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
    response = client.speech_to_text.transcribe(file=audio, model="saaras:v4", mode=mode)
    return response.transcript, response.language_code


if __name__ == "__main__":
    load_env()
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "sample.wav"
    mode = sys.argv[2] if len(sys.argv) > 2 else "transcribe"
    with open(audio_path, "rb") as audio:
        text, language = transcribe(audio, mode)
    print(f"[{language}] {text}")
