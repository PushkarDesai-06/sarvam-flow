# sarvam-flow

Push-to-talk dictation for Windows, powered by [Sarvam AI](https://docs.sarvam.ai) speech to text. Hold **Right Ctrl**, speak, release, and the text is typed into whatever window has focus. Works with Indian languages and mixed Hindi/English (English words stay in English).

## Requirements

- Windows 10 or 11 with a microphone
- [Python 3.10 or newer](https://www.python.org/downloads/windows/) (tick **"Add python.exe to PATH"** in the installer)
- [Git for Windows](https://git-scm.com/download/win)
- A Sarvam API key from the [Sarvam dashboard](https://dashboard.sarvam.ai)

## Install

Open **PowerShell** and run:

```powershell
git clone https://github.com/PushkarDesai-06/sarvam-flow.git
cd sarvam-flow
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Then create a file called `.env` in the `sarvam-flow` folder with your key:

```powershell
Set-Content -Path .env -Value "SARVAM_API_KEY=your_key_here" -Encoding ascii
```

You can also create it in Notepad. Just make sure it is saved as `.env` and not `.env.txt`. Never commit this file, it is already in `.gitignore`.

## Run

```powershell
.venv\Scripts\python flow.py
```

Keep that window open. Click into any app (Notepad, browser, Slack, etc.), hold **Right Ctrl**, speak, and let go. The transcript appears in the console and gets typed where your cursor is. Press `Ctrl+C` in the console to quit.

A tone plays when recording starts and another when it stops, using the sounds from `claude-dictate` bundled in `assets/sounds`. Use headphones if your microphone picks up the start tone from your speakers. Sound playback failures are reported in the console and do not stop dictation.

To check that your key and setup work without the microphone, transcribe any WAV file:

```powershell
.venv\Scripts\python transcribe.py path\to\audio.wav
```

## Settings

Edit the constants at the top of `flow.py`:

| Setting | Default | Notes |
| --- | --- | --- |
| `HOTKEY` | `keyboard.Key.ctrl_r` | Any `pynput` key, e.g. `keyboard.Key.f8` |
| `MODE` | `codemix` | `transcribe` (native script), `translate` (to English), `translit` (romanized), `verbatim`, `codemix` |

Recordings longer than 29 seconds are split into chunks, since Sarvam's standard API accepts up to 30 seconds per request.

## Troubleshooting

- **Nothing is recorded:** Settings > Privacy & security > Microphone, and turn on **"Let desktop apps access your microphone"**. Also check that the right input device is the Windows default.
- **Text doesn't appear in some apps:** Windows blocks typing into apps running as administrator from a normal process. Run PowerShell as administrator too if you need to dictate into those.
- **`KeyError: 'SARVAM_API_KEY'`:** the `.env` file is missing, misnamed (check it isn't `.env.txt`), or not in the same folder as `flow.py`.
- **`'py' is not recognized`:** reinstall Python from python.org with the launcher enabled, or use `python` instead of `py`.
- **Antivirus warning:** the global hotkey uses a keyboard hook, which some antivirus tools flag. Allow it if you trust the code.
