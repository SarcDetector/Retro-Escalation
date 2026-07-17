# RE-OSCR distribution

Supported tester packages are the portable Windows build documented in
[`windows/README.md`](windows/README.md) and the Linux x86-64 build documented in
[`linux/README.md`](linux/README.md).

The inherited upstream GPLv3 frontend's Inno, Debian, Arch, and generic PyInstaller recipes were
retired when the frontend product and Python namespace became RE-OSCR. They remain available in
Git history for reference, but they must not be used to publish RE-OSCR without being redesigned
and tested under the new application identity.

`re-oscr.desktop` remains reserved for a future system-installed Linux package. The current Linux
tester package is portable and runs directly from its extracted directory.
