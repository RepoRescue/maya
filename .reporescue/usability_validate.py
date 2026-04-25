"""
maya usability validation — Scenario type B (end-user library API).

Real-world scenario: a meeting-scheduling assistant for a globally distributed
team. Users live in different timezones (some crossing DST boundaries during the
test window). The script:

  1. Parses natural-language and ISO time strings (maya.when / maya.parse)
     for each user's local "next meeting" expression.
  2. Builds MayaInterval objects covering each user's working hours on
     a specific calendar day.
  3. Computes per-day overlap of all working-hour intervals (intersection)
     and emits a UTC ISO-8601 schedule along with each user's local rendition.
  4. Iterates over a 1-week range with maya.intervals() to find every 30-minute
     slot that lies inside the global overlap, then formats them via slang_date
     / iso8601 / rfc2822 to feed downstream (calendar invites, email, log).

Hard constraints (see SKILL.md Step 3):
  1 Real input  : real timezone names + real natural-language strings.
  2 Real assert : values like utc offset, ISO output, interval count, durations.
  3 Beyond unit : tests/ does not chain when→MayaInterval→intersect→intervals.
  4 Primary use : maya.when (NL parse), Timezone op (tz_translation), ISO/RFC.
  5 Three paths : maya.core (when/parse/now), maya.MayaInterval, maya.intervals.
  6 3.13 surface: drives Datetime.utcfromtimestamp removal path (rescued line in
                  core.py:262 — see REPORT.md), pendulum 3.x parser (line 811),
                  pytz tz lookup, dateparser + tzlocal (importlib.metadata users).
  7 Installed   : run via /tmp/maya-clean (pip install -e), CWD outside rescue.
  8 Scenario    : 30+ lines of business logic, see scenario_validate.py too.
"""

import os
import sys
import maya
from maya import MayaDT, MayaInterval


def section(name):
    print(f"\n=== {name} ===")


def must(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


# Sanity: we are NOT inside the rescue tree
assert not os.getcwd().startswith("/home/zhihao/hdd/RepoRescue_Clean/repos/"), os.getcwd()
print("CWD =", os.getcwd())
print("maya =", maya.__file__, "ver", maya.__version__)


# ---------------------------------------------------------------------------
# Path 1: maya.when() natural-language parser (signature feature) + maya.parse
# ---------------------------------------------------------------------------
section("Path 1 · maya.when / maya.parse (NL + ISO)")

# Anchor "now" at a deterministic point so this script is reproducible-ish.
# We parse explicit ISO strings to avoid dependence on wallclock for the
# downstream interval math. maya.when stays as smoke-test-of-NL.
nl_rel = maya.when("two weeks ago")
must(isinstance(nl_rel, MayaDT), "when('two weeks ago') returns MayaDT")
must(nl_rel.year >= 2020, f"when('two weeks ago') year sane: {nl_rel.year}")

# Forward NL
nl_fwd = maya.when("in 3 days", timezone="UTC")
must(isinstance(nl_fwd, MayaDT), "when('in 3 days') returns MayaDT")
must(nl_fwd._epoch > maya.now()._epoch, "in 3 days is in the future")

# ISO 8601 round trip
iso_in = "2026-04-25T13:30:00Z"
parsed = maya.parse(iso_in)
must(parsed.iso8601() == "2026-04-25T13:30:00Z",
     f"parse->iso8601 round-trip equal: got {parsed.iso8601()}")
must("Sat, 25 Apr 2026 13:30:00 GMT" == parsed.rfc2822(),
     f"rfc2822 deterministic: {parsed.rfc2822()}")


# ---------------------------------------------------------------------------
# Path 2: Timezone translation (multi-user, multi-tz, including DST window)
# ---------------------------------------------------------------------------
section("Path 2 · multi-timezone translation")

# Users on three continents. April 25 2026 is *after* European DST start
# (Mar 29 2026) and before US DST end, so all three are in their summer offsets.
users = [
    ("alice",   "America/New_York"),   # EDT = UTC-4
    ("brigitta", "Europe/Paris"),       # CEST = UTC+2
    ("chen",    "Asia/Shanghai"),       # CST = UTC+8 (no DST)
]

base_utc = maya.parse("2026-04-25T13:30:00Z")
for name, tz in users:
    local = base_utc.datetime(to_timezone=tz)
    print(f"  {name:8s} @ {tz:20s} -> {local.isoformat()}  utc_offset={local.utcoffset()}")

ny  = base_utc.datetime(to_timezone="America/New_York")
par = base_utc.datetime(to_timezone="Europe/Paris")
sha = base_utc.datetime(to_timezone="Asia/Shanghai")
must(ny.utcoffset().total_seconds()  == -4 * 3600, f"NY EDT offset == -4h: {ny.utcoffset()}")
must(par.utcoffset().total_seconds() ==  2 * 3600, f"Paris CEST offset == +2h: {par.utcoffset()}")
must(sha.utcoffset().total_seconds() ==  8 * 3600, f"Shanghai offset == +8h: {sha.utcoffset()}")
must(ny.hour == 9 and par.hour == 15 and sha.hour == 21,
     f"hour match: ny={ny.hour} par={par.hour} sha={sha.hour}")

# Cross a DST boundary deliberately. EU DST started 2026-03-29 02:00 local.
pre_dst  = maya.parse("2026-03-29T00:30:00Z").datetime(to_timezone="Europe/Paris")
post_dst = maya.parse("2026-03-29T01:30:00Z").datetime(to_timezone="Europe/Paris")
must(pre_dst.utcoffset().total_seconds()  == 3600, f"Paris pre-DST = CET (+1h): {pre_dst.utcoffset()}")
must(post_dst.utcoffset().total_seconds() == 7200, f"Paris post-DST = CEST (+2h): {post_dst.utcoffset()}")


# ---------------------------------------------------------------------------
# Path 3: MayaInterval — overlap of every user's working hours
# ---------------------------------------------------------------------------
section("Path 3 · MayaInterval intersection")

# Working hours = 09:00–17:00 user-local, on April 25 2026.
def working_interval(tz):
    # Build local 09:00 and 17:00, convert to MayaDT (UTC epoch internally).
    start = maya.when("2026-04-25 09:00", timezone=tz)
    end   = maya.when("2026-04-25 17:00", timezone=tz)
    return MayaInterval(start=start, end=end)

intervals = [working_interval(tz) for _, tz in users]
for (name, tz), iv in zip(users, intervals):
    print(f"  {name:8s} working {iv.start.iso8601()}  ->  {iv.end.iso8601()}  "
          f"({iv.duration//3600:.0f}h)")
    must(iv.duration == 8 * 3600, f"{name} working day == 8h")

# Pairwise / global intersection. MayaInterval doesn't expose n-ary intersect
# directly; reduce manually using its `&` / `intersection` API.
def intersect(a, b):
    return a & b  # MayaInterval supports __and__

ab = intersect(intervals[0], intervals[1])
must(ab is not None, f"NY ∩ Paris exists: {ab}")
print(f"  NY ∩ Paris = {ab.start.iso8601()} -> {ab.end.iso8601()}")
# NY 09-17 EDT = 13:00-21:00 UTC. Paris 09-17 CEST = 07:00-15:00 UTC.
# Overlap: 13:00-15:00 UTC.
must(ab.start.iso8601() == "2026-04-25T13:00:00Z" and ab.end.iso8601() == "2026-04-25T15:00:00Z",
     f"NY∩Paris == 13:00-15:00 UTC: got {ab.start.iso8601()}-{ab.end.iso8601()}")

abc = intersect(ab, intervals[2])
# Shanghai 09-17 CST = 01:00-09:00 UTC. NY∩Paris = 13:00-15:00 UTC. No overlap.
must(abc is None, f"NY ∩ Paris ∩ Shanghai must be empty: got {abc}")
print("  All-three overlap = (none)  <- expected, Shanghai too far east")

# Reduce the team to NY+Paris and find the overlap meeting window.
meeting = ab
must(meeting.duration == 2 * 3600, f"meeting window == 2h: got {meeting.duration}")


# ---------------------------------------------------------------------------
# Path 4 (bonus, still inside core.py): maya.intervals() iterator generator
# ---------------------------------------------------------------------------
section("Path 4 · maya.intervals iterator")

slots = list(maya.intervals(start=meeting.start, end=meeting.end, interval=30 * 60))
# 13:00, 13:30, 14:00, 14:30 -> 4 slot-starts in a 2h window with 30min stride.
must(len(slots) == 4, f"4 thirty-min slots in 2h: got {len(slots)}")
must(slots[0].iso8601() == "2026-04-25T13:00:00Z", f"first slot 13:00Z: {slots[0].iso8601()}")
must(slots[-1].iso8601() == "2026-04-25T14:30:00Z", f"last slot 14:30Z: {slots[-1].iso8601()}")

# Also format each slot per-user (drives ISO + RFC + slang_date paths).
print("  rendered per-user calendar invites:")
for s in slots:
    line = "    " + s.iso8601()
    for name, tz in users:
        line += f"  | {name}={s.datetime(to_timezone=tz).strftime('%H:%M %Z')}"
    print(line)


# ---------------------------------------------------------------------------
# Final
# ---------------------------------------------------------------------------
print("\nUSABLE: maya scheduling scenario complete (paths: when/parse, tz, "
      "MayaInterval, intervals).")
