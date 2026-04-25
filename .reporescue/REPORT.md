# maya — Usability Validation

**Selected rescue**: sonnet (srconly: PASS)
**Scenario type**: B (end-user library API) — supplemented with Path-B downstream-style scenario
**Real-world use**: maya is Kenneth Reitz's "Datetimes for Humans" library — natural-language date parsing (`maya.when("two weeks ago")`), multi-timezone normalization, and ISO-8601 / RFC-2822 emission.

## Step 0: Import sanity
`repos/rescue_sonnet/maya/venv-t2/bin/python -c "import maya"` -> OK
`maya.__version__` = 0.6.0a1, `maya.now()` returns a live MayaDT.

## Step 1: Model selection
All five rescues PASS in T2 (full + srconly). Picked **sonnet** by priority. Sonnet srconly also PASS, so the source patch is independently effective.

## Step 4: Install + core feature (clean venv)
- `python3.13 -m venv /tmp/maya-clean && /tmp/maya-clean/bin/pip install -e repos/rescue_sonnet/maya` -> OK (resolves humanize, pytz>=2026.1, dateparser>=1.3.0, tzlocal>=5.3.1, pendulum>=3.2.0, snaptime>=0.2.4).
- Core feature: parse 3 user timestamps with 3 IANA TZs at the same UTC instant, build MayaInterval working-hour windows, intersect (NY ∩ Paris == 13:00–15:00 UTC, NY ∩ Paris ∩ Shanghai == none), then iterate maya.intervals(stride=30min) over the overlap.
- Result: PASS (`usability_validate.py`).
- CWD during run = `/tmp` (verified inside the script).

## Hard constraint 6: Py3.13 surface stressed
| Surface | Evidence |
|---|---|
| `Datetime.utcfromtimestamp` removed/deprecated in 3.12+ | `src/maya/core.py:262, 265` rescued to `Datetime.fromtimestamp(_, timezone.utc)`. Exercised every time we call `MayaDT.datetime(to_timezone=...)`. |
| pendulum 3.x parser API change | `core.py:811` try/except wraps `pendulum.parse(...)` with `datetime.fromisoformat` fallback. Exercised by every `maya.parse("…Z")` and `maya.when("2026-04-25 09:00", timezone=…)` call. |
| pytz 2026.1 (latest) tz lookup | live tz lookups for Europe/Paris, Asia/Shanghai, America/Los_Angeles, etc. |
| `dateparser>=1.3` + `tzlocal>=5.3.1` + `humanize>=4.15` | all use `importlib.metadata` lazily on Python 3.13; pulled in via `pip install -e`. |

## Beyond unit tests (constraint 3)
`grep -r "intersect\|&" tests/` shows tests cover `intervals()` count assertions and pair-wise `&` for canned datetimes, but no test chains `when() -> multi-timezone working-hour intervals -> n-ary intersection -> intervals(stride=30min) -> per-user strftime`. `scenario_validate.py`'s 10-event multi-offset log ingestion + per-day SOC bucketing + per-user burst-window detection is also outside `tests/`.

## Hard constraint 5: three distinct paths
- `maya.core.when` / `maya.core.parse` (NL + ISO entry points)
- `maya.MayaInterval` (`__init__`, `&`/intersection, `.duration`, `.contains`)
- `maya.intervals` generator (stride iteration)
- `MayaDT.datetime(to_timezone=...)` / `iso8601` / `rfc2822` / `slang_date` (formatting + tz translation)
=> 4 distinct sub-surfaces, all real-call.

## Step 6: Downstream / Scenario
- **Path A**: WebSearch + GitHub topic browse turned up no active project (≥100 stars, commit in last 2 yr) that imports `maya`. The library is itself abandoned and has no active reverse-deps. SKIPPED.
- **Path B**: `scenario_validate.py` (104 lines, ≥30) ingests `fixtures/server.log` (10 real log lines, 7 different numeric offsets including +0000, -0700, +1300, +0530), normalizes to UTC via `maya.parse`, buckets into SOC-local LA days, runs a sliding 1-h burst detector per user, and emits ISO + RFC + LA-local summaries. Includes a deliberate cross-DST NZ-edge event whose LA bucket is asserted. PASS.

## Step 7: Bug-hunt
`bug_hunt.py` ran 10 probes; all 10 PASS:
1. DST forward jump (Paris 02:30 nonexistent) -> normalized to 01:30 UTC.
2. DST fall-back ambiguity (Paris Oct 25 02:30) -> resolved to 01:30 UTC.
3. Leap second `23:59:60` -> correctly rejected with `ValueError`.
4. Non-IANA Unicode tz `Europe/Köln` -> rejected (`UnknownTimeZoneError`).
5. Repeated parse stability -> stable.
6. Pre-1970 epoch (1899-06-15) -> exercises rescued `core.py:265` fallback path correctly.
7. Year-9999 boundary -> OK.
8. MayaInterval crossing DST forward jump -> `duration` == 2h real seconds (correct).
9. Cross-year interval intersection -> 2h overlap returned correctly.
10. Whitespace-only input -> rejected with `ValueError`.

No bugs found.

## Verdict
STATUS: USABLE

Reason: maya installs cleanly out of tree; the rescued `Datetime.fromtimestamp(_, timezone.utc)` and pendulum-3.x parser fallback are both exercised by a 3-user multi-timezone scheduling scenario and a 10-event multi-offset SOC log scenario; four distinct surfaces all return correct values; 10 anti-blindspot probes (DST forward+fall-back, leap second, Unicode tz, pre-1970, year-9999, cross-year intersection, whitespace) all pass.
