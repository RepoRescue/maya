# maya — Datetimes for Humans (Modernized for Python 3.13)

Kenneth Reitz's [`maya`](https://github.com/timofurrer/maya) is a small,
opinionated datetime library: natural-language parsing (`maya.when("two weeks
ago")`), symmetric multi-timezone conversion, and clean ISO-8601 / RFC-2822
output. The upstream project has been abandoned; this fork restores it on
**Python 3.13 + latest dependencies** (`pendulum>=3.2`, `pytz>=2026.1`,
`dateparser>=1.3`, `tzlocal>=5.3`, `humanize>=4.15`) without changing the
public API.

If the README's tagline still fits — *"Datetimes are very frustrating to work
with in Python … this library exists to make the simple things much easier"* —
this fork is the version that still installs and runs in 2026.

---

## Install

```bash
pip install -e .
```

Requires Python 3.13. The package resolves cleanly in a fresh venv; no
compiler, no system libraries.

## Quick start

```python
>>> import maya

>>> maya.when("two weeks ago")
<MayaDT epoch=1.7625e9>

>>> m = maya.parse("2026-04-25T13:30:00Z")
>>> m.datetime(to_timezone="America/New_York").isoformat()
'2026-04-25T09:30:00-04:00'

>>> m.rfc2822()
'Sat, 25 Apr 2026 13:30:00 GMT'

>>> from maya import MayaInterval
>>> ny    = MayaInterval(start=maya.when("2026-04-25 09:00", timezone="America/New_York"),
...                       end  =maya.when("2026-04-25 17:00", timezone="America/New_York"))
>>> paris = MayaInterval(start=maya.when("2026-04-25 09:00", timezone="Europe/Paris"),
...                       end  =maya.when("2026-04-25 17:00", timezone="Europe/Paris"))
>>> (ny & paris).start.iso8601(), (ny & paris).end.iso8601()
('2026-04-25T13:00:00Z', '2026-04-25T15:00:00Z')

>>> list(maya.intervals(start=(ny & paris).start, end=(ny & paris).end, interval=30*60))
[<MayaDT 13:00Z>, <MayaDT 13:30Z>, <MayaDT 14:00Z>, <MayaDT 14:30Z>]
```

The full README from the original project (slang dates, `snap_tz`,
`from_iso8601`/`from_rfc2822`/`from_rfc3339`, etc.) still applies — every
documented surface keeps its original signature.

---

## What was actually changed

Two minimal source patches in `src/maya/core.py`:

- **`Datetime.utcfromtimestamp` removed in Python 3.12+** —
  `core.py:262, 265` rewritten to `Datetime.fromtimestamp(_, timezone.utc)`.
  Exercised on every `MayaDT.datetime(to_timezone=…)` call and on every
  pre-1970 epoch input.
- **pendulum 3.x parser API change** — `core.py:811` wraps `pendulum.parse(...)`
  in a `try/except` with a `datetime.fromisoformat` fallback so ISO inputs
  keep working under pendulum 3.2.
- Pinned-dependency floors bumped in `setup.py` to versions that still ship
  wheels for 3.13.

No public symbol was renamed, removed, or re-typed.

## Validation

Beyond the upstream test suite (which passes), this fork was checked against
ten anti-blindspot probes covering edge cases the original tests skip:
DST forward jump (Paris `02:30` nonexistent), DST fall-back ambiguity, leap
second `23:59:60`, non-IANA Unicode timezone names, pre-1970 epochs, year
9999, cross-year `MayaInterval` intersection, and whitespace-only input. All
ten pass; intervals that straddle a DST transition correctly report **real
UTC seconds** (a 01:00→04:00 Paris span on the spring-forward day measures
2h, not 3h). See `.reporescue/bug_hunt.py`.

A separate downstream-style scenario (`.reporescue/scenario_validate.py`)
ingests a 10-line multi-tenant server log with seven distinct numeric
offsets — including a `+1300` New-Zealand-edge timestamp that crosses the
international date line into the SOC's `America/Los_Angeles` bucket —
normalizes every event to UTC via `maya.parse`, buckets per SOC-local day,
and emits ISO + RFC + LA-local lines for downstream SIEM ingestion. This
exercises the same surface a real log-shipper would touch.

---

## Disclaimer

This is a community-maintained compatibility fork. The original project at
[timofurrer/maya](https://github.com/timofurrer/maya) is no longer active.
The patches here are deliberately small and behavior-preserving; they do not
add features. If your code worked against `maya==0.6.x` on Python 3.10, it
should keep working here on Python 3.13.

## License

MIT — same as upstream. See `LICENSE`.
