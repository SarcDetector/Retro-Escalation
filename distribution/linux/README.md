# Linux portable development build

The Linux tester package is an x86-64 PyInstaller folder distributed as a `tar.gz` archive. It is
built on Ubuntu 22.04 so it targets Ubuntu 22.04 and newer distributions with compatible `glibc`
and desktop libraries.

## Running the package

Extract the archive into a directory owned by your user. Settings are written to a `settings`
folder beside the executable, so a read-only system directory is not suitable.

```bash
tar -xzf RE-OSCR-*-linux-x86_64.tar.gz
cd RE-OSCR
./RE-OSCR
```

The Qt runtime normally finds the required display libraries on a desktop installation. On a
minimal Debian or Ubuntu installation, install these if Qt reports a missing `xcb`, EGL, or OpenGL
library:

```bash
sudo apt-get install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0
```

Wayland and X11 are both supported by Qt. Windows, X11, and unsupported Wayland environments use
the normal in-process Qt popout. On a supported native Wayland session, RE-OSCR can instead render
the local live meter in an isolated layer-shell presentation process. The main RE-OSCR process
still owns the only combat-log parser; the child receives normalized rows and presentation
settings only. The browser/OBS overlay remains the existing browser source and is unaffected.

The native path targets KDE Plasma/KWin and wlroots compositors. GNOME/Mutter support is not
claimed. It needs LayerShellQt components compatible with the bundled Qt runtime. Missing,
incompatible, or failed native components fall back to the normal popout without stopping the
parser.

`pywayland` is optional and is used only for pointer-driven dragging. For a PyPI/pipx install,
request that helper with:

```bash
pipx install 're-oscr[wayland]'
```

PyPI does not provide a CPython 3.13 wheel for the pinned `pywayland==0.4.18`. pipx consequently
builds it from source and needs a compiler, `pkg-config`, Python development headers matching its
Python interpreter, libffi development headers, and the Wayland headers and protocol tools. On
Debian or Ubuntu, install the usual prerequisites first:

```bash
sudo apt-get install build-essential pkg-config python3-dev libffi-dev \
  libwayland-dev libwayland-bin wayland-protocols
```

If pipx uses a separately installed Python 3.13, its matching headers must also be available; the
package may be named `python3.13-dev` where the distribution provides it.

Without the extra, layer-shell can still provide overlay placement when compatible native
components are available; dragging is disabled. The portable build conditionally includes
compatible layer-shell components found on its Linux build host. Their absence does not make the
package unusable—the package keeps the normal Qt fallback.

The extra does not install LayerShellQt. Native layer-shell placement still requires a separately
installed or bundled LayerShellQt plugin and interface built for the same Qt major/minor ABI as
RE-OSCR's PySide6 runtime.

If a Wayland-specific problem occurs, the X11 fallback can be tested with:

```bash
QT_QPA_PLATFORM=xcb ./RE-OSCR
```

## Building locally

Python 3.13 or newer, its development headers, and the native build prerequisites are required:

```bash
sudo apt-get install build-essential pkg-config python3-dev libffi-dev \
  libwayland-dev libwayland-bin wayland-protocols
```

Then install both packaging dependencies and the optional dragging helper:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pyinst,wayland]"
./distribution/linux/build_retro_escalation.sh --output-root dist --package
```

PyInstaller Linux packages are not universal binaries. A package built on a newer distribution
may not run on an older `glibc`, and an x86-64 package does not run natively on ARM64.
