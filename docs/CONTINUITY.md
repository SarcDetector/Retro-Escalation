# Continuity

This document exists so that RE-OSCR can outlive its maintainer. Maintainer availability is a
risk like any other, and this project treats it the way it treats every other risk: documented,
automated, and planned for in advance. If you are reading this because the maintainer is gone,
everything you need is either in this repository or reachable from it.

**Principle: this document is a map, not a keyring. It contains no secrets, and none are needed
to keep the project alive.**

## What this project is

RE-OSCR (Retro Escalation) is an independently maintained GPL-3.0 frontend for the OSCR
combat-log parser. The parser (`STO-OSCR`) is a separate, unmodified, pinned dependency and the
single source of parser truth. RE-OSCR never patches it.

## Where everything lives

| Thing | Location | Notes |
|---|---|---|
| Source | github.com/SarcDetector/Retro-Escalation, branch `retro-escalation` | Full history, public |
| Releases | GitHub Releases on this repo | Windows + Linux packages with SHA-256 checksums, built by CI |
| PyPI package | `re-oscr` | Published by CI via trusted publishing |
| Parser dependency | `STO-OSCR` on PyPI (upstream project) | Pinned in `pyproject.toml`; never modified here |
| CI | `.github/workflows/` | Tests, Windows portable, Linux portable, GitHub release, PyPI release |
| Documentation | `docs/` | Scope, features, testing, support doctrine, CLA parity ledger, this file |

Some design working documents are maintained outside the repository. For successors: the code,
the test suite, and `re_oscr/console/tokens.py` are authoritative for the Command Console design
language; nothing outside the repo is required to build, release, or maintain.

## The authority model (no secrets exist in the release path)

- PyPI publishing uses **trusted publishing (OIDC)**: the workflow in this repository is the
  publishing credential. There is no PyPI token to find, lose, or steal.
- GitHub Releases are published by `github-actions` with repository-scoped permissions.
- Therefore: **administrative control of this GitHub repository is the entire authority
  surface.** Whoever legitimately controls the repo controls releases and PyPI publishing.
- Succession of the GitHub account itself uses GitHub's built-in successor designation
  (Settings → Account → Successor), which grants a named person management of public
  repositories upon the owner's death. No credentials change hands while the owner lives.

## How to release (the whole runbook)

1. Ensure the offline regression suite passes: `python -m unittest discover -s tests -v`.
2. Commit to `retro-escalation` with a clean tree.
3. Push a version tag (`vX.Y.Z.devN`). CI does everything else: runs tests, builds Windows and
   Linux packages with checksums, creates the GitHub prerelease, and publishes to PyPI.

There is no manual packaging step and no maintainer-machine dependency. See
[DEVELOPMENT.md](DEVELOPMENT.md) and [TESTING.md](TESTING.md) for local setup and the
feature-parity checklists.

## Invariants — the promises a successor inherits

These are commitments made to the community and to the upstream OSCR project. Keeping them is
what makes this project welcome in its ecosystem.

1. **The parser is never modified.** `STO-OSCR` stays an external, pinned dependency.
2. **Parser truth stays upstream.** League uploads use the inherited, parser-truth upload path,
   byte-identical in behavior. Derived or modified views are display-only, always labelled, and
   never uploaded.
3. **Brand separation is permanent.** OSCR is identified only as the parser; no upstream project,
   community group, or service branding or affiliation claims are used. This is enforced by the
   debranding residue check before each release; the only permitted upstream references are the
   parser credit and the functional League service URLs.
4. **Legacy stays.** The `Legacy` theme (internal ID `default`) remains the guaranteed working
   fallback, functionally unchanged.
5. **One door for support.** All RE-OSCR problems are reported to this repository — never to the
   OSCR project or its maintainers. Suspected parser bugs are reproduced against vanilla OSCR
   here first; only clean, verified reports go upstream. See [SUPPORT.md](SUPPORT.md).
6. **GPL-3.0 with corresponding source**, always, including modified redistributions.

## What "keeping it alive" actually costs

Steady-state maintenance is small: triage issues, occasionally bump `STO-OSCR`, PySide6, and
Python pins, and re-tag a release. The parser, combat-log format, and League service are
maintained upstream. Historically this is hours per month, not a job.

## Worst case: the names are lost

If the repository or PyPI name ever becomes unreachable, nothing of substance is lost. The full
history, all releases, all wheels, and all documentation are public and mirrored on every clone.
A successor forks from the last public state, chooses new names, keeps the license and the
credits, and continues. Control of the names was never control of the project.

## Successor's first day

1. Clone the repo, run the test suite, build a portable package via CI on your fork.
2. Read [PROJECT_SCOPE.md](PROJECT_SCOPE.md), [SUPPORT.md](SUPPORT.md), and
   [FEATURES.md](FEATURES.md).
3. Announce the takeover in the community's Discord so support routing follows you.
4. Keep the invariants. Everything else is yours to decide — that is the point of this project.

---

*This project was built to outlive its maintainer. That is not morbid; that is the design.*
