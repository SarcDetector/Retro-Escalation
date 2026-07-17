# Getting help with RE-OSCR

RE-OSCR (Retro Escalation) is an **independently maintained frontend** that uses OSCR as its
parser. It is not affiliated with the OSCR project or its maintainers.

**One door: every problem with RE-OSCR gets reported here, and only here.**

- Bug reports and feature requests:
  [github.com/SarcDetector/Retro-Escalation/issues](https://github.com/SarcDetector/Retro-Escalation/issues)
- Downloads: [Releases](https://github.com/SarcDetector/Retro-Escalation/releases)

Please do **not** report RE-OSCR problems to the OSCR project or its maintainers. Even if a
problem looks like a parser problem — report it here first. Triage is our job, not
yours, and not theirs.

## What happens to your report

| What broke | Who owns it | What we do |
|---|---|---|
| Crash, UI glitch, theme, tables, graphs | RE-OSCR | Fixed here. |
| Live Parser: popout, hotkey, browser/OBS feed, LAN | RE-OSCR | Fixed here. This is RE-OSCR infrastructure, not OSCR. |
| Install / packaging (Windows ZIP, Linux, PyPI) | RE-OSCR | Fixed here. |
| A number looks wrong | RE-OSCR until proven otherwise | Every derived or modified view is labelled in the UI. If a **labelled** view is wrong, that is our math. If a parser-truth value is wrong, see below. |
| Suspected parser bug | OSCR — but you still report it **here** | We reproduce it against vanilla OSCR first. If it reproduces, the RE-OSCR maintainer files one clean upstream report. RE-OSCR users never need to contact OSCR. |
| League service down / upload rejected | The upstream League service — still report **here** | We confirm whether it is our client or their service, and tell you. Do not chase the service operators. |

## Writing a useful report

Include:

1. RE-OSCR version (Settings → About) and theme (Command Console or Legacy).
2. What you did, what you expected, what happened.
3. The combat log file, if the problem involves parsing or numbers.
4. A screenshot, if the problem is visual.

## Boundaries (the fine print that keeps everyone sane)

- The OSCR parser ships as a separate, unmodified dependency. RE-OSCR never patches it.
- League uploads use the inherited, parser-truth upload path, unchanged. Labelled/modified
  views are display-only and are never uploaded.
- "Parser truth stays upstream" is not a slogan; it is the support contract. If RE-OSCR shows
  it unlabelled, it is the parser's number. If it is labelled, it is ours — blame us first.

---

## Implementation notes (maintainers)

Crash / unhandled-exception dialog copy:

> **RE-OSCR encountered a problem**
>
> This is RE-OSCR (Retro Escalation), an independently maintained frontend for the OSCR
> parser. Please report this at
> `github.com/SarcDetector/Retro-Escalation/issues` — **not** to the OSCR project or its
> maintainers.
>
> [Copy details] [Open issue tracker] [Close]

Rules for Sol:

- Every error surface (crash dialog, parser-failure banner, League-connection failure state)
  links to the RE-OSCR tracker. No error surface may link upstream.
- Parser exceptions are caught and presented as "parser reported a problem with this log —
  report it to RE-OSCR with the log attached", never as raw tracebacks implying OSCR fault.
- League failure states must distinguish "our client couldn't connect" from "service
  unavailable" where detectable, and say which one it is.
