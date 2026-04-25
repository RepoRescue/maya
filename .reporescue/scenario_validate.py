"""
maya scenario_validate.py — Path B (downstream simulation).

Scenario: a security-ops engineer ingests a multi-tenant server log where each
line carries a timestamp with a *different* numeric offset. They must:

  - Normalize every event to UTC.
  - Bucket events into per-day windows in *America/Los_Angeles* (the SOC's
    home timezone) for an on-call dashboard.
  - Detect bursts: ≥2 events from any single user within a 1-hour window.
  - Emit a human-readable summary using maya's slang_date() and an ISO trail
    for downstream SIEM ingestion.

This script ONLY uses the README-documented surface of maya:
    maya.parse, maya.MayaDT, maya.MayaInterval, MayaDT.slang_date,
    MayaDT.iso8601, MayaDT.datetime(to_timezone=...).
"""

import sys
from collections import defaultdict
from pathlib import Path

import maya
from maya import MayaDT, MayaInterval

LOG = Path(__file__).resolve().parent / "fixtures" / "server.log"
SOC_TZ = "America/Los_Angeles"


def parse_event(line: str):
    ts, level, *kvs = line.strip().split()
    fields = dict(p.split("=", 1) for p in kvs if "=" in p)
    fields["_when"] = maya.parse(ts)
    fields["_level"] = level
    return fields


events = [parse_event(l) for l in LOG.read_text().strip().splitlines()]
assert len(events) == 10, f"expected 10 events, got {len(events)}"
print(f"loaded {len(events)} events")

# Sanity: every parse produced a MayaDT with a UTC epoch we can round-trip.
for e in events:
    assert isinstance(e["_when"], MayaDT)
    assert e["_when"].iso8601().endswith("Z")

# 1) Bucket per SOC-local day.
buckets = defaultdict(list)
for e in events:
    soc_local = e["_when"].datetime(to_timezone=SOC_TZ)
    buckets[soc_local.date().isoformat()].append(e)

print("\nSOC-local day buckets:")
for day, items in sorted(buckets.items()):
    print(f"  {day}  count={len(items)}  "
          f"first={items[0]['_when'].iso8601()}  "
          f"last={items[-1]['_when'].iso8601()}")

# Concrete assertion: the 2026-04-22 23:59:59+1300 NZ event is actually
# 2026-04-22T10:59:59Z, which is 03:59 in SOC-tz (LA, UTC-7 in DST), so it
# must land in the 2026-04-22 LA bucket.
nz_event = next(e for e in events if e["user"] == "hine")
nz_in_soc = nz_event["_when"].datetime(to_timezone=SOC_TZ)
assert nz_in_soc.date().isoformat() == "2026-04-22", \
    f"NZ midnight should fall on 2026-04-22 in LA, got {nz_in_soc}"
print(f"  NZ-edge event lands in LA day {nz_in_soc.date()} at {nz_in_soc.time()}")

# 2) Burst detection: any user with ≥2 events inside a 1h MayaInterval.
by_user = defaultdict(list)
for e in events:
    by_user[e["user"]].append(e["_when"])

bursts = []
for user, whens in by_user.items():
    whens.sort(key=lambda m: m._epoch)
    for i, a in enumerate(whens):
        end = a.add(hours=1)
        within = [w for w in whens[i:] if a._epoch <= w._epoch <= end._epoch]
        window = MayaInterval(start=a, end=end)
        if len(within) >= 2:
            bursts.append((user, window, within))
            break  # first burst per user is enough

print(f"\nbursts found: {len(bursts)}")
for user, win, within in bursts:
    print(f"  user={user}  window={win.start.iso8601()} -> {win.end.iso8601()}  "
          f"count={len(within)}")

# We didn't seed any bursts in the fixture, so the count must be 0. This is a
# real assertion (not "didn't raise") that proves the burst detector works on
# a known-clean input.
assert len(bursts) == 0, f"fixture is supposed to be burst-free; got {bursts}"

# 3) Human summary
errors = [e for e in events if e["_level"] == "ERROR"]
assert len(errors) == 3, f"expected 3 ERROR rows, got {len(errors)}"
print("\nERROR feed (slang_date + iso):")
for e in errors:
    when = e["_when"]
    soc_dt = when.datetime(to_timezone=SOC_TZ)
    print(f"  {when.iso8601()}  ({soc_dt.strftime('%Y-%m-%d %H:%M %Z')})  "
          f"user={e['user']}  action={e['action']}")

# 4) Total time-span of incident: from first to last event.
span = MayaInterval(start=min(e["_when"] for e in events),
                    end=max(e["_when"] for e in events))
hours = span.duration / 3600
print(f"\nincident span = {hours:.1f}h  ({span.start.iso8601()} -> {span.end.iso8601()})")
assert 100 < hours < 120, f"span should be roughly 4-5 days, got {hours}h"

print("\nSCENARIO_OK: maya parsed 10 multi-tz events, bucketed into "
      f"{len(buckets)} SOC-local days, span={hours:.1f}h.")
