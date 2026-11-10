# sarvam-flow

Push-to-talk dictation for Windows, powered by [Sarvam AI](https://docs.sarvam.ai) speech to text. Hold **Right Ctrl**, speak, release, and the text is typed into whatever window has focus. Dictation defaults to Marathi using standard transcription in the native script.

## Download the Windows app

Once a version is published, download `SarvamFlow.exe` from [GitHub Releases](https://github.com/PushkarDesai-06/sarvam-flow/releases). Open it, paste your own Sarvam API key into **Your Sarvam API key**, then click **Use key** or press Enter. Python and a `.env` file are not required for the packaged app.

The key is masked, cleared from the textbox after use, and saved locally in Windows Credential Manager for your Windows account. It loads automatically next time you open the app. To change it, enter a replacement while idle and click **Use key**. Keys are never included in the build or uploaded by CI. An optional `.env` beside the executable is also supported; a saved key takes precedence.

If Sarvam reports an invalid API key, the app removes the saved key and asks for a replacement. Network errors, empty credits, and rate limits do not erase it. If the credential store is unavailable, the app reports that saving failed and uses the entered key for the current session only.

For builds that have not been released yet, open a successful **Windows app** run in [Actions](https://github.com/PushkarDesai-06/sarvam-flow/actions), download the `SarvamFlow-windows-x64` artifact, and extract it. The download includes the executable and a SHA-256 checksum.

## Requirements for running from source

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

For the desktop app, you can enter your key in the window. For the console version, or to load a key automatically, create a file called `.env` in the `sarvam-flow` folder:

```powershell
Set-Content -Path .env -Value "SARVAM_API_KEY=your_key_here" -Encoding ascii
```

You can also create it in Notepad. Just make sure it is saved as `.env` and not `.env.txt`. Never commit this file, it is already in `.gitignore`.

## Desktop app

Open the native Python desktop window:

```powershell
.venv\Scripts\python app.py
```

The interface uses Tkinter, included with the standard Python installer for Windows. No additional GUI packages are required.

- Select the input language and output mode. Defaults are **Marathi** and **Transcribe**; selections apply for this session.
- Click **Start recording**, speak, then click **Stop recording** to preview the transcript in the window. Click **Copy** to paste it elsewhere.
- To dictate directly into another app, focus that app, hold **Right Ctrl**, and release. Keep it focused until the text arrives. If Sarvam Flow is focused when the result arrives, the text stays in the preview.
- The status shows recording, transcription progress, and errors. Start and stop tones still play.
- The app restores your saved key automatically, falling back to `.env` if no key is saved. Enter a new key in **Your Sarvam API key** and click **Use key** or press Enter to save a replacement.
- Minimize the window to keep using the hotkey. Close it to stop the microphone and hotkey listener. Closing during transcription discards the pending result.

To launch without a console window, use `.venv\Scripts\pythonw app.py` after verifying setup. Do not run the desktop and console versions at the same time, since both listen for Right Ctrl.

## Console version

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

Use the desktop window's selectors for language and mode. For the console version, edit the constants at the top of `flow.py`:

| Setting | Default | Notes |
| --- | --- | --- |
| `HOTKEY` | `keyboard.Key.ctrl_r` | Any `pynput` key, e.g. `keyboard.Key.f8` |
| `MODE` | `transcribe` | `transcribe` (native script), `translate` (to English), `translit` (romanized), `verbatim`, `codemix` |
| `LANGUAGE_CODE` | `mr-IN` | Marathi input; set to `unknown` for automatic language detection |

The standalone `transcribe.py` command still auto-detects the input language.

Recordings longer than 29 seconds are split into chunks, since Sarvam's standard API accepts up to 30 seconds per request.

## CI and releases

`.github/workflows/windows.yml` runs on pushes to `main`, pull requests targeting `main`, manual dispatches, and pushed tags starting with `v`.

1. Run unit tests and a native window smoke test on Windows with Python 3.10 and 3.12.
2. After tests pass, use Python 3.12 and PyInstaller to build a Windows x64 executable. The spec explicitly bundles the two tones, without `.env` or recordings.
3. Smoke-test the executable without microphone access, keyboard hooks, or Sarvam requests, then upload it with a checksum as a 14-day Actions artifact.
4. On a `v*` tag push, publish the same files to a GitHub Release using the built-in `GITHUB_TOKEN`. No repository API key secret is needed.

To publish a version after committing the desired changes:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

Build locally on Windows:

```powershell
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m PyInstaller --clean --noconfirm SarvamFlow.spec
```

The output is `dist\SarvamFlow.exe`. Test source changes with `.venv\Scripts\python -m unittest discover -s tests -v`; test the native window and bundled assets with `.venv\Scripts\python app.py --smoke-test`.

## Troubleshooting

- **Nothing is recorded:** Settings > Privacy & security > Microphone, and turn on **"Let desktop apps access your microphone"**. Also check that the right input device is the Windows default.
- **Text doesn't appear in some apps:** Windows blocks typing into apps running as administrator from a normal process. Run PowerShell as administrator too if you need to dictate into those.
- **`KeyError: 'SARVAM_API_KEY'`:** the `.env` file is missing, misnamed (check it isn't `.env.txt`), or not in the same folder as `flow.py`.
- **`'py' is not recognized`:** reinstall Python from python.org with the launcher enabled, or use `python` instead of `py`.
- **Antivirus warning:** the global hotkey uses a keyboard hook, which some antivirus tools flag. Allow it if you trust the code.
