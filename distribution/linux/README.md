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

Wayland and X11 are both supported by Qt. If a Wayland-specific problem occurs, the X11 fallback
can be tested with `QT_QPA_PLATFORM=xcb ./RE-OSCR`.

## Building locally

Python 3.13 or newer and the project packaging dependencies are required:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pyinst]"
./distribution/linux/build_retro_escalation.sh --output-root dist --package
```

PyInstaller Linux packages are not universal binaries. A package built on a newer distribution
may not run on an older `glibc`, and an x86-64 package does not run natively on ARM64.
