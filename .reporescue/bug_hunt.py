"""
maya bug_hunt.py — Step 7 anti-PyCG-blindspot probing.

We deliberately try inputs/operations that the unit tests skip, looking for
silent breakage in the rescued maya. Each probe records:
  PROBE / PASS / FAIL / SURPRISE.

Findings DO NOT block USABLE; they go in REPORT.md.
"""

import sys
import traceback
import maya
from maya import MayaDT, MayaInterval

results = []

def probe(name, fn):
    try:
        ok, detail = fn()
        results.append((name, "PASS" if ok else "FAIL", detail))
        print(f"  [{('PASS' if ok else 'FAIL'):4s}] {name}: {detail}")
    except Exception as e:
        results.append((name, "SURPRISE", f"{type(e).__name__}: {e}"))
        print(f"  [SURP] {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)


# 1. DST forward jump — local time that does not exist in Europe/Paris.
# 2026-03-29 02:30 Europe/Paris does not exist (clocks jumped 02:00 -> 03:00).
def p1():
    d = maya.when("2026-03-29 02:30", timezone="Europe/Paris")
    iso = d.iso8601()
    # Expected: maya should fold it forward to 03:30 CEST = 01:30 UTC.
    # Acceptable: 00:30 UTC (interpreted as CET) OR 01:30 UTC (CEST). Either
    # is a defensible normalization; the bug would be silent corruption (e.g.
    # off by >2h or producing a wrong day).
    return ("2026-03-29T0" in iso and iso.endswith("Z")), iso

# 2. DST fall-back ambiguity — Europe/Paris 2026-10-25 02:30 happens twice.
def p2():
    d = maya.when("2026-10-25 02:30", timezone="Europe/Paris")
    return d.iso8601().startswith("2026-10-25T"), d.iso8601()

# 3. Leap-second-ish: 23:59:60 (POSIX rejects). Some parsers raise, some
# silently coerce to 24:00:00. Either is fine; SURPRISE = wrong day.
def p3():
    try:
        d = maya.parse("2016-12-31T23:59:60Z")
        return False, f"unexpectedly accepted: {d.iso8601()}"
    except Exception as e:
        return True, f"correctly rejected: {type(e).__name__}"

# 4. Unicode timezone alias (IANA does not include non-ASCII names).
def p4():
    try:
        d = maya.when("2026-04-25 09:00", timezone="Europe/Köln")  # not IANA
        return False, f"silently accepted bogus tz: {d.iso8601()}"
    except Exception as e:
        return True, f"rejected non-IANA tz: {type(e).__name__}"

# 5. Repeated parse — state leak / caching.
def p5():
    a = maya.parse("2026-04-25T13:30:00Z").iso8601()
    b = maya.parse("2026-04-25T13:30:00Z").iso8601()
    c = maya.parse("2026-04-25T13:30:00Z").iso8601()
    return a == b == c, f"{a} | {b} | {c}"

# 6. Pre-1970 epoch (rescued path: line 265 fallback).
def p6():
    d = maya.parse("1899-06-15T12:00:00Z")
    iso = d.iso8601()
    return iso.startswith("1899-06-15T12:00:00"), iso

# 7. Year 9999 boundary.
def p7():
    d = maya.parse("9999-12-31T23:59:59Z")
    return d.iso8601().startswith("9999-12-31T"), d.iso8601()

# 8. MayaInterval crossing DST forward jump — duration math sanity.
# Paris 2026-03-29 01:00 CET -> 04:00 CEST. UTC duration = 2h, NOT 3h.
def p8():
    s = maya.when("2026-03-29 01:00", timezone="Europe/Paris")
    e = maya.when("2026-03-29 04:00", timezone="Europe/Paris")
    iv = MayaInterval(start=s, end=e)
    # In *wall* clock it's 3h, in real (UTC) seconds it's 2h.
    return iv.duration == 7200, f"duration={iv.duration}s (expected 7200s = 2h real)"

# 9. Cross-year intersection.
def p9():
    a = MayaInterval(start=maya.parse("2025-12-31T22:00:00Z"),
                     end  =maya.parse("2026-01-01T02:00:00Z"))
    b = MayaInterval(start=maya.parse("2026-01-01T00:00:00Z"),
                     end  =maya.parse("2026-01-01T05:00:00Z"))
    inter = a & b
    return inter is not None and inter.duration == 7200, \
        f"{inter.start.iso8601() if inter else None} -> {inter.end.iso8601() if inter else None}"

# 10. Empty / whitespace input — must raise, not return a silent wrong value.
def p10():
    try:
        d = maya.when("   ")
        return False, f"silently accepted whitespace: {d.iso8601()}"
    except Exception as e:
        return True, f"rejected: {type(e).__name__}"

print("=== bug-hunt probes ===")
probe("DST forward jump (Paris 02:30 nonexistent)", p1)
probe("DST fold ambiguity (Paris Oct 25 02:30)", p2)
probe("Leap second (23:59:60)", p3)
probe("Non-IANA Unicode tz (Europe/Köln)", p4)
probe("Repeated parse stability", p5)
probe("Pre-1970 epoch", p6)
probe("Year 9999 boundary", p7)
probe("Interval over DST forward jump (real-second duration)", p8)
probe("Cross-year interval intersection", p9)
probe("Whitespace-only input rejected", p10)

failures = [r for r in results if r[1] != "PASS"]
print(f"\nProbes total={len(results)} pass={len(results)-len(failures)} non-pass={len(failures)}")
for name, status, detail in failures:
    print(f"  {status}: {name}  -- {detail}")
