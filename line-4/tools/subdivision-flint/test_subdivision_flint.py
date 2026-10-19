import copy
from fractions import Fraction
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

import subdivision_flint as f


class SubdivisionTests(unittest.TestCase):
    def test_demo_changes_inconclusive_bound_to_proved_containment(self):
        r = f.evaluate(f.demo_request())
        self.assertEqual((r['baseline']['lower'], r['baseline']['upper']), ('0', '100'))
        self.assertFalse(r['baseline']['within']['fully_within'])
        self.assertEqual((r['tightened']['lower'], r['tightened']['upper']), ('0', '37.5'))
        self.assertTrue(r['tightened']['within']['fully_within'])
        self.assertEqual(r['base_width_reduction'], '62.5')

    def test_one_part_identical_to_baseline(self):
        q = f.demo_request()
        q['split']['parts'] = '1'
        r = f.evaluate(q)
        for key in ('lower', 'upper', 'base_lower', 'base_upper', 'within'):
            self.assertEqual(r['baseline'][key], r['tightened'][key])

    def test_dependency_is_not_magically_removed(self):
        q = f.demo_request()
        q.update(expression='x-x', within=None, to='m')
        r = f.evaluate(q)
        self.assertEqual((r['tightened']['lower'], r['tightened']['upper']), ('-2.5', '2.5'))

    def test_exact_cover_and_independent_quadratic_oracle(self):
        rng = random.Random(31)
        for _ in range(100):
            a = rng.randint(-20, 0)
            b = rng.randint(1, 20)
            count = rng.randint(1, 64)
            q = f.demo_request()
            q.update(variables={'x': [f'{a} m', f'{b} m']}, within=None)
            q['split']['parts'] = str(count)
            r = f.evaluate(q)
            lo, hi = (Fraction(r['tightened'][k]) for k in ('lower', 'upper'))
            # Independent analytic extremum at x=5, endpoints otherwise.
            values = [Fraction(a*(10-a)), Fraction(b*(10-b))]
            if a <= 5 <= b:
                values.append(Fraction(25))
            self.assertLessEqual(lo, min(values))
            self.assertGreaterEqual(hi, max(values))
            self.assertGreaterEqual(lo, Fraction(r['baseline']['lower']))
            self.assertLessEqual(hi, Fraction(r['baseline']['upper']))
            segments = r['segments']
            self.assertEqual(Fraction(segments[0]['input_base_lower']), a)
            self.assertEqual(Fraction(segments[-1]['input_base_upper']), b)
            for left, right in zip(segments, segments[1:]):
                self.assertEqual(left['input_base_upper'], right['input_base_lower'])

    def test_conversion_and_unselected_variable(self):
        q = f.demo_request()
        q.update(variables={'x': ['0 cm', '1000 cm'], 'y': ['1 m', '2 m']},
                 expression='x*y', to='cm^2', within=None)
        r = f.evaluate(q)
        self.assertEqual((r['tightened']['lower'], r['tightened']['upper']), ('0', '200000'))
        self.assertEqual(r['tightened']['dimensions']['length'], 2)

    def test_negative_reciprocal_and_zero_width_domain(self):
        q = f.demo_request()
        q.update(variables={'x': ['-2 s', '-2 s']}, expression='1/x', to='s^-1', within=None)
        r = f.evaluate(q)
        self.assertEqual((r['tightened']['lower'], r['tightened']['upper']), ('-0.5', '-0.5'))

    def test_singularity_is_never_hidden(self):
        for expression in ('1/x', '1/(x-x)', 'x^-1'):
            q = f.demo_request()
            q.update(expression=expression, to=None, within=None)
            with self.assertRaises(f.interval.engine.UnitError):
                f.evaluate(q)

    def test_input_is_not_mutated(self):
        q = f.demo_request()
        before = copy.deepcopy(q)
        f.evaluate(q)
        self.assertEqual(q, before)

    def test_strict_schema_and_parts(self):
        for parts in (True, 4, '0', '-1', '65', '999', '04', '1.0', None):
            q = f.demo_request()
            q['split']['parts'] = parts
            with self.assertRaises(f.interval.IntervalError):
                f.evaluate(q)
        q = f.demo_request()
        q['split']['variable'] = 'missing'
        with self.assertRaises(f.interval.IntervalError):
            f.evaluate(q)
        for q in ({}, [], dict(f.demo_request(), extra=True)):
            with self.assertRaises(f.interval.IntervalError):
                f.evaluate(q)

    def test_invalid_dimensions_and_json(self):
        q = f.demo_request()
        q['to'] = 's'
        with self.assertRaises(f.interval.IntervalError):
            f.evaluate(q)
        for data in (b'{"a":1}', b'{"a":"1","a":"2"}', b'[' * 2000,
                     b' ' * 65537, b'\xff'):
            with self.assertRaises(f.interval.IntervalError):
                f.interval.decode(data)

    def test_cli_statuses_and_streams(self):
        script = str(Path(__file__).with_name('subdivision_flint.py'))
        cases = [(None, 0)]
        q = f.demo_request()
        q['within'] = ['0 m^2', '25 * m^2']
        cases.append((q, 1))
        cases.append(({}, 2))
        for q, status in cases:
            r = subprocess.run([sys.executable, '-B', script, 'demo' if q is None else 'run'],
                               input=None if q is None else json.dumps(q),
                               text=True, capture_output=True)
            self.assertEqual(r.returncode, status, r.stderr)
            if status == 2:
                self.assertFalse(r.stdout)
                self.assertTrue(r.stderr)
            else:
                self.assertFalse(r.stderr)
                json.loads(r.stdout)


if __name__ == '__main__':
    unittest.main()
