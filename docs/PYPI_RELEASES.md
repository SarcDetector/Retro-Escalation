# PyPI releases

RE-OSCR publishes a platform-independent Python wheel and source distribution.  This gives Linux
and macOS users a supported install path through `pipx`; portable Windows and Linux builds remain
separate release artifacts.

## One-time owner setup

1. Create a GitHub environment named `pypi` for this repository.  Restrict it to trusted
   maintainers and require approval before deployment.
2. Sign in to PyPI and add a **pending GitHub Actions Trusted Publisher** with:
   - project name: `re-oscr`
   - owner: `SarcDetector`
   - repository: `Retro-Escalation`
   - workflow: `pypi-release.yml`
   - environment: `pypi`

PyPI creates the project when the first approved release is published.  A pending publisher does
not reserve the name, so confirm `re-oscr` is still available immediately before the first tag.

## Publishing a release

1. Set the version in both `retro_escalation.py` and `main.py` to a public PEP 440 version, such
   as `11.1.0`.  Do not use a `+local` suffix for a public PyPI release.
2. Commit that version bump and push it to `retro-escalation`.
3. Create and push the matching tag, for example `v11.1.0`.
4. Approve the `pypi` environment deployment in GitHub Actions if the environment requires it.

The workflow reruns the regression suite, builds the source distribution and universal wheel,
checks the package metadata, verifies that the tag and application version match, then publishes
through PyPI Trusted Publishing.  No long-lived PyPI token is stored in GitHub.

The same tag also runs fresh Windows and Linux portable builds, verifies their checksums, and
creates or updates one GitHub prerelease with both packages attached. Release notes can be stored
at `docs/releases/<tag>.md`; otherwise GitHub generates them from the commit history.

For a development release such as `11.1.0.dev12`, tag `v11.1.0.dev12`. If it is the only PyPI
release, users can install it normally with `pipx install re-oscr`; once a stable release exists,
they opt in to later development builds with `pipx install re-oscr --pip-args="--pre"`.
