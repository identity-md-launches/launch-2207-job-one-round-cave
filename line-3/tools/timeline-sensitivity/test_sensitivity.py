"""Offline synthetic checks for sensitivity rebuild and interval coverage."""
import copy
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import replay
import sensitivity as tool

HERE = Path(__file__).resolve().parent
START = '2026-10-18T10:00:00Z'
END = '2026-10-18T10:00:05Z'


class SensitivityTests(unittest.TestCase):
    def test_demo_changes_coverage_across_bounds(self):
        result = tool.demo()
        self.assertEqual(result['bounds_ms'], [0, 250, 500, 1000])
        profiles = result['profiles']
        self.assertEqual([p['covered_us'] for p in profiles],
                         [2_000_000, 3_000_000, 4_000_000, 5_000_000])
        self.assertTrue(all(p['undated_lines'] == 1 for p in profiles))
        self.assertTrue(all(sum(map(int, p['duration_by_depth_us'].values())) == 5_000_000
                            for p in profiles))

    def test_histogram_against_independent_integer_oracle(self):
        rng = random.Random(32)
        for _ in range(400):
            intervals = [(a, a + rng.randrange(1, 8))
                         for a in (rng.randrange(-5, 15) for _ in range(rng.randrange(25)))]
            got = tool.histogram(intervals, 0, 10)
            self.assertEqual(sum(got.values()), 10)
            expected = Counter(sum(a <= t < b for a, b in intervals) for t in range(10))
            self.assertEqual(got, dict(expected))

    def test_full_replay_bounds_validation_and_no_message_echo(self):
        pack = replay.make_pack([('private.log', b'2026-10-18T10:00:01Z PRIVATE_NOTE\n')])
        original = copy.deepcopy(pack)
        result = tool.analyze(pack, START, END, [0, 500])
        self.assertEqual(pack, original)
        encoded = replay.canonical(result)
        self.assertNotIn(b'PRIVATE_NOTE', encoded)
        self.assertNotIn(b'private.log', encoded)
        pack['timeline']['events'][0]['message'] = 'forged'
        with self.assertRaises(replay.ReplayError):
            tool.analyze(pack, START, END, [0])
        for bounds in ([], [True], [-1], [86400001], [1, 1], [0] * 13, [1.5]):
            with self.assertRaises(replay.ReplayError):
                tool.parse_bounds(bounds)

    def test_instant_offsets_and_bad_window(self):
        self.assertEqual(tool.instant('2026-10-18T12:00+02:00'), tool.instant(START))
        for value in ('2026-02-30T00:00Z', '2026-10-18T10:00:00',
                      '2026-10-18T10:00:00+24:00', True):
            with self.assertRaises((ValueError, OverflowError)):
                tool.instant(value)
        with self.assertRaises(replay.ReplayError):
            tool.histogram([], 10, 10)

    def test_provenance_and_copied_folder_cli_with_digest(self):
        provenance = json.loads((HERE / 'PROVENANCE.json').read_text())
        for item in provenance['dependencies']:
            self.assertEqual(hashlib.sha256((HERE / item['path']).read_bytes()).hexdigest(),
                             item['sha256'])
        scratch = Path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp).resolve()
            copied = root / 'tool'
            shutil.copytree(HERE, copied)
            raw = replay.canonical(replay.make_pack([
                ('sample.log', b'2026-10-18T10:00:01Z accepted\n')])) + b'\n'
            pack = root / 'pack.json'
            pack.write_bytes(raw)
            command = [sys.executable, '-B', str(copied / 'sensitivity.py'), 'analyze',
                       str(pack), '--start', START, '--end', END, '--bounds-ms', '0,500']
            good = subprocess.run(command + ['--expect-sha256', replay.digest(raw)],
                                  cwd=root, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)['profiles'][1]['clock_uncertainty_ms'], 500)
            bad = subprocess.run(command + ['--expect-sha256', '0' * 64],
                                 cwd=root, capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, b'')


if __name__ == '__main__':
    unittest.main()
