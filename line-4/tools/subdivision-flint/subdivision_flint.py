#!/usr/bin/env python3
"""Tighten an exact dimensional interval by covering one input with subintervals."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import re
import sys

import interval_flint as interval

MAX_PARTS = 64


def quantity(value, dims):
    """Exact base-unit expression, independent of decimal display precision."""
    return f"({value.numerator}/{value.denominator}) * ({interval.engine.dimensions(dims)})"


def evaluate(request):
    required = {"variables", "expression", "to", "within", "split"}
    if type(request) is not dict or set(request) != required:
        raise interval.IntervalError("request needs exactly variables, expression, to, within, split")
    split = request["split"]
    if type(split) is not dict or set(split) != {"variable", "parts"}:
        raise interval.IntervalError("split needs exactly variable and parts")
    name, parts = split["variable"], split["parts"]
    if type(name) is not str:
        raise interval.IntervalError("split variable must be a string")
    if type(parts) is not str or not re.fullmatch(r"[1-9][0-9]?", parts):
        raise interval.IntervalError("parts must be a decimal string from 1 to 64")
    count = int(parts)
    if count > MAX_PARTS:
        raise interval.IntervalError("parts exceeds 64")
    original = {key: request[key] for key in required - {"split"}}
    # Validate the WHOLE original domain first. Splitting never hides singularities.
    baseline = interval.evaluate(original)
    if name not in original["variables"]:
        raise interval.IntervalError("split variable is not in variables")
    domain = interval.interval_pair(original["variables"][name])
    segments = []
    lower, upper = None, None
    for index in range(count):
        lo = domain.lo + (domain.hi - domain.lo) * Fraction(index, count)
        hi = domain.lo + (domain.hi - domain.lo) * Fraction(index + 1, count)
        pair = [quantity(lo, domain.dims), quantity(hi, domain.dims)]
        subrequest = dict(original)
        subrequest["variables"] = dict(original["variables"], **{name: pair})
        result = interval.evaluate(subrequest)
        a, b = Fraction(result["base_lower"]), Fraction(result["base_upper"])
        lower = a if lower is None else min(lower, a)
        upper = b if upper is None else max(upper, b)
        segments.append({"input_base_lower": interval.engine.exact_decimal(lo),
                         "input_base_upper": interval.engine.exact_decimal(hi),
                         "result": result})
    # The union hull covers the complete domain; there is no sampled-value claim.
    tightened = interval.evaluate({
        "variables": {"result": [quantity(lower, tuple(baseline["dimensions"].values())),
                                  quantity(upper, tuple(baseline["dimensions"].values()))]},
        "expression": "result", "to": original["to"], "within": original["within"]})
    del tightened["expression"]
    width_before = Fraction(baseline["base_upper"]) - Fraction(baseline["base_lower"])
    return {"expression": original["expression"], "split": split,
            "input_base_unit": interval.engine.dimensions(domain.dims),
            "baseline": baseline, "tightened": tightened,
            "base_width_reduction": interval.engine.exact_decimal(width_before - (upper - lower)),
            "segments": segments,
            "method": "inclusive equal rational subintervals; union hull of exact enclosures"}


def demo_request():
    return {"variables": {"x": ["0 m", "10 m"]},
            "expression": "x * (10 m - x)", "to": "m^2",
            "within": ["0 m^2", "38 * m^2"],
            "split": {"variable": "x", "parts": "4"}}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("command", choices=("demo", "run"))
    args = cli.parse_args(argv)
    try:
        request = (demo_request() if args.command == "demo" else
                   interval.decode(sys.stdin.buffer.read(interval.MAX_BYTES + 1)))
        result = evaluate(request)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 1 if result["tightened"].get("within", {}).get("fully_within") is False else 0
    except (interval.IntervalError, interval.engine.UnitError, ZeroDivisionError) as exc:
        print(f"subdivision-flint: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
