# Timeline Sensitivity

Timeline Sensitivity replays the exact embedded log bytes under several explicit
symmetric clock-bound assumptions, then compares each bound's uncertainty-interval
coverage profile over the same query window. This makes assumption-driven changes
visible without presenting a bound as a measured clock error.

One command from the repository root shows it working offline:

```sh
python3 -B line-3/tools/timeline-sensitivity/sensitivity.py demo
```

Tried locally: the synthetic three-line example produced four complete five-second
profiles at 0, 250, 500 and 1000 ms, with the undated diagnostic counted separately.
The example is synthetic; no incident or clock behavior was measured.

For a Timeline Replay pack inside the current workspace:

```sh
python3 -B line-3/tools/timeline-sensitivity/sensitivity.py analyze path/to/pack.json --start 2026-10-18T10:00:00Z --end 2026-10-18T10:05:00Z --bounds-ms 0,100,500,1000 --expect-sha256 TRUSTED_DIGEST
```

The tool verifies the original pack, then rebuilds the same embedded evidence with
each requested bound (1–12 unique integers from 0 to 86,400,000 ms). It never opens
paths named by the pack, executes a service, or contacts a network. Reports contain
coverage durations and counts, not source labels, bytes or messages. The shipped
Replay parser and Time Flint snapshot are ordinary files; Python 3.10+ standard
library only, offline. The folder can be copied and used by itself.

Intervals and query windows are half-open. For every profile, the depth histogram
partitions the entire window exactly. It describes how many timestamp-uncertainty
intervals could cover an instant, not confirmed simultaneity, causality, service
load, downtime or inactivity. Clock bounds are analyst assumptions; replay proves
internal consistency, not authenticity or completeness.

Focused checks:

```sh
python3 -B -m unittest discover -s line-3/tools/timeline-sensitivity -v
```
