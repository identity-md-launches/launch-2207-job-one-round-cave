#!/usr/bin/env python3
"""Replay one evidence pack under several asserted clock bounds and compare coverage."""
import argparse
from datetime import datetime
import re
import sys

import replay
from vendor import time_flint as engine

FORMAT = 'timeline-sensitivity/1'
MAX_BOUNDS = 12


def instant(value):
    if not isinstance(value, str):
        raise replay.ReplayError('endpoint must be offset-aware ISO text')
    match = engine.ISO.fullmatch(value)
    if match is None:
        raise replay.ReplayError('endpoint needs offset-aware ISO text with at most 6 fractional digits')
    body, offset = match.groups()
    if offset != 'Z' and (int(offset[1:3]) > 23 or int(offset[4:]) > 59):
        raise replay.ReplayError('endpoint offset is outside ±23:59')
    return engine.micros(datetime.fromisoformat(body + ('+00:00' if offset == 'Z' else offset)))


def parse_bounds(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= MAX_BOUNDS:
        raise replay.ReplayError('supply 1..12 clock bounds')
    if any(type(value) is not int or not 0 <= value <= 86400000 for value in values):
        raise replay.ReplayError('each clock bound must be an integer in 0..86400000 ms')
    if len(set(values)) != len(values):
        raise replay.ReplayError('clock bounds must be unique')
    return sorted(values)


def histogram(intervals, start, end):
    if start >= end:
        raise replay.ReplayError('window start must precede end')
    changes = {start: 0, end: 0}
    for left, right in intervals:
        if left >= right:
            raise replay.ReplayError('event interval must have positive duration')
        left, right = max(start, left), min(end, right)
        if left < right:
            changes[left] = changes.get(left, 0) + 1
            changes[right] = changes.get(right, 0) - 1
    points = sorted(changes)
    depth = 0
    durations = {}
    for left, right in zip(points, points[1:]):
        depth += changes[left]
        durations[depth] = durations.get(depth, 0) + right - left
    if depth + changes[end] != 0 or sum(durations.values()) != end - start:
        raise replay.ReplayError('coverage sweep did not partition the window')
    return durations


def analyze(pack, start_text, end_text, bounds_ms):
    verified = replay.verify_pack(pack)
    bounds = parse_bounds(bounds_ms)
    start, end = instant(start_text), instant(end_text)
    if start >= end:
        raise replay.ReplayError('window start must precede end')
    inputs = []
    for item in pack['inputs']:
        import base64
        inputs.append((item['source'], base64.b64decode(item['base64'], validate=True)))
    results = []
    for bound in bounds:
        rebuilt = replay.make_pack(inputs,
            ignore_unmatched=pack['options']['ignore_unmatched'],
            clock_uncertainty_ms=bound)
        timeline = rebuilt['timeline']
        intervals = [(instant(event['start_utc']), instant(event['end_utc_exclusive']))
                     for event in timeline['events']]
        durations = histogram(intervals, start, end)
        covered = sum(duration for depth, duration in durations.items() if depth > 0)
        results.append({
            'clock_uncertainty_ms': bound,
            'timestamped_events': len(timeline['events']),
            'undated_lines': len(timeline['omitted']),
            'maximum_interval_depth': max(durations),
            'duration_by_depth_us': {str(depth): durations[depth] for depth in sorted(durations)},
            'covered_us': covered,
            'uncovered_us': end - start - covered,
        })
    baseline = results[0]['duration_by_depth_us']
    for result in results:
        keys = set(baseline) | set(result['duration_by_depth_us'])
        result['duration_delta_from_lowest_bound_us'] = {
            key: result['duration_by_depth_us'].get(key, 0) - baseline.get(key, 0)
            for key in sorted(keys, key=int)}
    return {
        'format': FORMAT,
        'replay': verified,
        'window': {'start_utc_inclusive': engine.utc_text(start),
                   'end_utc_exclusive': engine.utc_text(end),
                   'duration_us': end - start},
        'bounds_ms': bounds,
        'profiles': results,
        'interpretation': (
            'Each profile rebuilds the same embedded log bytes with a different symmetric '
            'clock bound. Depth counts intervals compatible with each instant; it does not '
            'establish simultaneity, causality or service load. Uncovered time is not proof '
            'of inactivity. Bounds are analyst assumptions, not measured clock error. '
            'Replay checks consistency, not source authenticity or completeness. Messages '
            'and source bytes are omitted from this report.')}


def demo():
    pack = replay.make_pack([('worker.log',
        b'2026-10-18T10:00:01Z accepted\n'
        b'2026-10-18T10:00:03Z recovered\n'
        b'untimestamped diagnostic\n')], ignore_unmatched=True, clock_uncertainty_ms=500)
    result = analyze(pack, '2026-10-18T10:00:00Z', '2026-10-18T10:00:05Z',
                     [0, 250, 500, 1000])
    result['example'] = 'synthetic, not a real incident'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='compare synthetic profiles at four clock bounds')
    analyze_parser = commands.add_parser('analyze', help='compare a verified evidence pack')
    analyze_parser.add_argument('pack')
    analyze_parser.add_argument('--start', required=True, help='inclusive offset-aware ISO instant')
    analyze_parser.add_argument('--end', required=True, help='exclusive offset-aware ISO instant')
    analyze_parser.add_argument('--bounds-ms', required=True,
        help='comma-separated unique integer bounds in 0..86400000, at most 12')
    analyze_parser.add_argument('--expect-sha256', help='optional trusted digest of exact pack bytes')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            result = demo()
        else:
            raw = replay.read_workspace(args.pack, replay.MAX_PACK_BYTES)
            digest = replay.digest(raw)
            if args.expect_sha256 is not None:
                if re.fullmatch(r'[0-9a-f]{64}', args.expect_sha256) is None:
                    raise replay.ReplayError('expected digest must be 64 lowercase hex digits')
                if digest != args.expect_sha256:
                    raise replay.ReplayError('pack does not match expected SHA-256')
            try:
                bounds = [int(value) for value in args.bounds_ms.split(',')]
            except ValueError as exc:
                raise replay.ReplayError('bounds must be comma-separated integers') from exc
            result = analyze(replay.load_pack(raw), args.start, args.end, bounds)
            result['pack_sha256'] = digest
        sys.stdout.buffer.write(replay.canonical(result) + b'\n')
        return 0
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        print('timeline-sensitivity: ' + engine.visible(str(exc)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
