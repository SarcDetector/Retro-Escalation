# Build and Packaging instructions for Windows

## RE-OSCR portable development build

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

The generated `RE-OSCR.exe` uses the `settings` folder beside the executable by default. It does
not use the official frontend's settings folder. The build includes its source commit in
`BUILD_INFO.txt`, a GPLv3 licence copy, the tester checklist, a ZIP, and a SHA-256 checksum.

## Automated tester package

The `Windows portable build` GitHub Actions workflow runs regression tests, builds this package,
checks that its executable starts, and uploads the ZIP and SHA-256 file as a workflow artifact.
It runs automatically for relevant changes on `retro-escalation` and can also be started manually
from the repository's Actions page.

Historical upstream packaging files remain in Git history for licence provenance and are not used
by the RE-OSCR portable build.
