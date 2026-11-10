from pathlib import Path

root = Path(SPECPATH)
analysis = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "assets/sounds/recording-started.wav"), "assets/sounds"),
        (str(root / "assets/sounds/recording-stopped.wav"), "assets/sounds"),
    ],
    hiddenimports=["pynput.keyboard._win32", "pynput.mouse._win32", "keyring.backends.Windows"],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="SarvamFlow",
    console=False,
    upx=False,
)
