# Build and Packaging instructions for Windows

## Retro Escalation portable development build

Create the repository virtual environment and install the packaging dependency:

```powershell
python -m pip install -e ".[pyinst]"
```

Then build and optionally package the one-folder application:

```powershell
.\distribution\windows\build_retro_escalation.ps1 `
    -OutputRoot "E:\re-oscar\re-oscr theme switching" `
    -Package
```

The generated `Retro-Escalation.exe` uses the `settings` folder beside the executable by default.
It does not use the normal OSCR settings folder. The build includes its source commit in
`BUILD_INFO.txt`, a GPLv3 licence copy, the tester checklist, a ZIP, and a SHA-256 checksum.

## Upstream OSCR build

## Building
To build the app, first activate your virtual environment and install all dependencies.

While in the base directory of the project, run ```pyinstaller --noconfirm --clean --onedir --name OSCR-UI main.py --add-data assets:assets --add-data locales:locales --windowed --icon assets/oscr_icon_small.ico``` to build the app.

While in the base directory of the project, run ```iscc distribution\OSCR-UI.iss``` to package the app with [Inno Setup Installer](https://jrsoftware.org/isinfo.php). If the command `iscc` is not available, add the install location of the `iscc` executable to PATH or provide the full path to the executable.

The resulting installer will be placed into the `dist\OSCR-UI\` folder.
