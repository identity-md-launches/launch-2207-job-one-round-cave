#!/usr/bin/env python3
"""Enclose a dimensional formula over exact, user-supplied input intervals."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
import re
import sys

import engine

MAX_BYTES = 65536
MAX_INPUTS = 32
NAME = re.compile(r"[a-z][a-z0-9]{0,31}\Z")


class IntervalError(ValueError):
    pass


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction
    dims: engine.Dimensions

    def checked(self, pos: int) -> "Interval":
        if self.lo > self.hi:
            raise IntervalError("lower endpoint exceeds upper endpoint")
        engine.Parser.bounded(engine.Quantity(self.lo, self.dims), pos)
        engine.Parser.bounded(engine.Quantity(self.hi, self.dims), pos)
        return self


def scalar(source: str) -> engine.Quantity:
    if type(source) is not str or not source.strip():
        raise IntervalError("endpoints and limits must be nonempty expressions")
    return engine.Parser(source).parse()


def interval_pair(pair: object) -> Interval:
    if type(pair) is not list or len(pair) != 2:
        raise IntervalError("an interval must be a two-element [lower, upper] list")
    lo, hi = (scalar(value) for value in pair)
    if lo.dims != hi.dims:
        raise IntervalError("interval endpoints have different dimensions")
    return Interval(lo.value, hi.value, lo.dims).checked(0)


def multiply(a: Interval, b: Interval, pos: int) -> Interval:
    products = (a.lo * b.lo, a.lo * b.hi, a.hi * b.lo, a.hi * b.hi)
    dims = tuple(x + y for x, y in zip(a.dims, b.dims))
    return Interval(min(products), max(products), dims).checked(pos)


def reciprocal(q: Interval, pos: int) -> Interval:
    if q.lo <= 0 <= q.hi:
        raise engine.UnitError("denominator interval includes zero", pos)
    dims = tuple(-d for d in q.dims)
    return Interval(1 / q.hi, 1 / q.lo, dims).checked(pos)


def power(q: Interval, n: int, pos: int) -> Interval:
    if n < 0:
        return power(reciprocal(q, pos), -n, pos)
    dims = tuple(d * n for d in q.dims)
    if n == 0:
        return Interval(Fraction(1), Fraction(1), dims).checked(pos)
    if n % 2 == 1:
        return Interval(q.lo ** n, q.hi ** n, dims).checked(pos)
    lower = 0 if q.lo <= 0 <= q.hi else min(q.lo ** n, q.hi ** n)
    return Interval(Fraction(lower), max(q.lo ** n, q.hi ** n), dims).checked(pos)


class Formula:
    def __init__(self, source: str, variables: dict[str, Interval]):
        self.source = source
        self.tokens = engine.tokenize(source)
        self.variables = variables
        self.i = 0
        self.depth = 0

    @property
    def here(self) -> engine.Token:
        return self.tokens[self.i]

    def take(self, kind: str) -> bool:
        if self.here.kind == kind:
            self.i += 1
            return True
        return False

    def parse(self) -> Interval:
        result = self.add()
        if self.here.kind != "end":
            raise engine.UnitError("unexpected token; operator required", self.here.pos)
        return result

    def add(self) -> Interval:
        left = self.multiply()
        while self.here.kind in ("+", "-"):
            op = self.here
            self.i += 1
            right = self.multiply()
            if left.dims != right.dims:
                raise engine.UnitError("addition needs matching dimensions", op.pos)
            if op.kind == "+":
                left = Interval(left.lo + right.lo, left.hi + right.hi, left.dims)
            else:
                left = Interval(left.lo - right.hi, left.hi - right.lo, left.dims)
            left = left.checked(op.pos)
        return left

    def multiply(self) -> Interval:
        left = self.unary()
        while self.here.kind in ("*", "/"):
            op = self.here
            self.i += 1
            right = self.unary()
            left = multiply(left, right if op.kind == "*" else reciprocal(right, op.pos), op.pos)
        return left

    def unary(self) -> Interval:
        if self.depth >= engine.MAX_DEPTH:
            raise engine.UnitError("formula nesting exceeds 32 levels", self.here.pos)
        self.depth += 1
        try:
            if self.here.kind in ("+", "-"):
                op = self.here
                self.i += 1
                q = self.unary()
                return (Interval(-q.hi, -q.lo, q.dims).checked(op.pos)
                        if op.kind == "-" else q)
            return self.power()
        finally:
            self.depth -= 1

    def power(self) -> Interval:
        q = self.atom()
        if self.here.kind == "^":
            op = self.here
            self.i += 1
            exponent = self.unary()
            if (exponent.dims != engine.ZERO or exponent.lo != exponent.hi
                    or exponent.lo.denominator != 1):
                raise engine.UnitError("exponent must be an exact dimensionless integer", op.pos)
            n = exponent.lo.numerator
            if abs(n) > 12:
                raise engine.UnitError("exponent exceeds -12..12", op.pos)
            return power(q, n, op.pos)
        return q

    def atom(self) -> Interval:
        token = self.here
        if self.take("("):
            q = self.add()
            if not self.take(")"):
                raise engine.UnitError("missing closing parenthesis", self.here.pos)
            return q
        if self.take("number"):
            source = token.text
            if self.here.kind == "unit" and self.here.text in engine.UNITS:
                source += " " + self.here.text
                self.i += 1
            q = scalar(source)
            return Interval(q.value, q.value, q.dims).checked(token.pos)
        if self.take("unit"):
            if token.text in self.variables:
                return self.variables[token.text]
            q = scalar(token.text)
            return Interval(q.value, q.value, q.dims).checked(token.pos)
        raise engine.UnitError("expected number, unit, variable, or parenthesized formula", token.pos)


def evaluate(request: object) -> dict:
    if type(request) is not dict or set(request) != {"variables", "expression", "to", "within"}:
        raise IntervalError("request needs exactly variables, expression, to, within")
    variables, expression, target, limits = (request[k] for k in
                                               ("variables", "expression", "to", "within"))
    if type(variables) is not dict or len(variables) > MAX_INPUTS:
        raise IntervalError("variables must be an object with at most 32 entries")
    if type(expression) is not str or not expression.strip():
        raise IntervalError("expression must be a nonempty string")
    if target is not None and (type(target) is not str or not target.strip()):
        raise IntervalError("to must be a nonempty unit expression or null")
    if limits is not None and (type(limits) is not list or len(limits) != 2):
        raise IntervalError("within must be a two-element interval or null")
    bound_vars = {}
    for name, pair in variables.items():
        if type(name) is not str or not NAME.fullmatch(name) or name in engine.UNITS:
            raise IntervalError(f"invalid or reserved variable name: {name!r}")
        bound_vars[name] = interval_pair(pair)
    result = Formula(expression, bound_vars).parse()
    scale = Fraction(1)
    label = engine.dimensions(result.dims)
    if target is not None:
        unit = engine.Parser(target, target=True).parse()
        if unit.value <= 0 or unit.dims != result.dims:
            raise IntervalError("target must be positive and match result dimensions")
        scale, label = unit.value, target
    display = Interval(result.lo / scale, result.hi / scale, result.dims).checked(0)
    output = {
        "expression": expression,
        "lower": engine.exact_decimal(display.lo),
        "upper": engine.exact_decimal(display.hi),
        "unit": label,
        "base_lower": engine.exact_decimal(result.lo),
        "base_upper": engine.exact_decimal(result.hi),
        "base_unit": engine.dimensions(result.dims),
        "dimensions": dict(zip(("length", "mass", "time", "data"), result.dims)),
        "enclosure": "inclusive",
    }
    if limits is not None:
        wanted = interval_pair(limits)
        if wanted.dims != result.dims:
            raise IntervalError("within limits have different dimensions from result")
        contained = wanted.lo <= result.lo and result.hi <= wanted.hi
        overlaps = not (result.hi < wanted.lo or result.lo > wanted.hi)
        output["within"] = {
            "lower": limits[0], "upper": limits[1],
            "fully_within": contained, "overlaps": overlaps,
        }
    return output


def decode(data: bytes) -> object:
    if len(data) > MAX_BYTES:
        raise IntervalError("request exceeds 65536 bytes")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise IntervalError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result
    def forbidden(value):
        raise IntervalError("JSON numbers and nonfinite constants are not accepted; use strings")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_int=forbidden, parse_float=forbidden, parse_constant=forbidden)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise IntervalError(f"invalid request JSON: {exc}") from exc


def demo_request() -> dict:
    return {
        "variables": {"size": ["9 MiB", "11 MiB"],
                      "rate": ["2 MiB/s", "2.5 MiB/s"]},
        "expression": "size / rate",
        "to": "s",
        "within": ["3 s", "6 s"],
    }


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("command", choices=("run", "demo"))
    args = cli.parse_args(argv)
    try:
        request = demo_request() if args.command == "demo" else decode(sys.stdin.buffer.read(MAX_BYTES + 1))
        output = evaluate(request)
        print(json.dumps(output, indent=2, ensure_ascii=True))
        return 1 if output.get("within", {}).get("fully_within") is False else 0
    except (IntervalError, engine.UnitError, ZeroDivisionError) as exc:
        print(f"interval-flint: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
