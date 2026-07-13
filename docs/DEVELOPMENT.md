# Development baseline

Retro Escalation currently targets Python 3.13 or newer and starts from OSCR-UI 11.1.0. Keep
feature work separate from parser behavior: changes under the upstream `STO-OSCR` dependency are
outside this project's theme scope.

## Windows setup

From PowerShell in the repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Run the checks

The suite uses Python's built-in `unittest` runner. The startup check builds the real Qt interface
with a temporary settings folder and the off-screen Qt platform, so it does not open a visible
window or overwrite a tester's OSCR preferences.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

GitHub runs the same command on Windows for every branch push and pull request.

## What the baseline protects

- OSCR-UI 11.1.0 fresh-setting defaults and settings type persistence.
- The complete existing Default palette, including the ten chart colours.
- Theme stylesheet generation and scaling.
- Built-in theme registry construction, failure logging, and guaranteed Default fallback.
- Theme selection persistence without changing the active theme before restart.
- Construction of the real four-page OSCR window in both built-in themes.

Later milestones should extend these checks with an explicit comparison showing identical parser
results in Default and Command Console.
