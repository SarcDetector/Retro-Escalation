# Development baseline

RE-OSCR currently targets Python 3.13 or newer and uses the official `STO-OSCR==11.0.0` parser.
Its frontend was inherited from an upstream GPLv3 baseline. Keep frontend work separate from parser
behavior: changes inside the upstream parser dependency are outside this project's scope.

The immutable pre-coprocessor checkpoint is
[RE-OSCR v11.1.0.dev12](baselines/v11.1.0.dev12.md). The audited CLA calculation inventory is
maintained separately in [CLA_PARITY.md](CLA_PARITY.md); it is a compatibility plan, not a claim
about shipped dev12 behavior.

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
window or overwrite a tester's installed OSCR application or RE-OSCR preferences.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
```

GitHub runs the same command on Windows for every branch push and pull request.

## What the baseline protects

- Command Console fresh-setting defaults and settings type persistence.
- The complete Legacy palette, including the ten chart colours.
- Theme stylesheet generation and scaling.
- Built-in theme registry construction, failure logging, and guaranteed Legacy fallback.
- Theme selection persistence without changing the active theme before restart.
- Construction of the real RE-OSCR window in both built-in themes: four Legacy tabs and five
  Command Console pages.
- Display-only Workbench derivation without mutating parser models or League upload coordinates.
- Frozen Analysis identity columns sharing the original tree model, selection, sorting, and
  vertical navigation.
- Identical parser totals in Legacy, Command Console parser-truth, and unmodified derived
  views.
