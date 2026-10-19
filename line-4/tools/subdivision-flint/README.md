# Subdivision Flint

Tighten an exact dimensional interval when repeated uncertain inputs make a
single interval evaluation too wide. This offline Python 3.10+ tool uses only
the standard library. Copy this entire folder anywhere to use it independently.

From the repository root:

```sh
python3 -B line-4/tools/subdivision-flint/subdivision_flint.py demo
```

Observed locally: for `x * (10 m - x)` with `x` anywhere in `[0, 10] m`, the
original enclosure is `[0, 100] m²`. Four equal subintervals give a union hull of
`[0, 37.5] m²`, which is fully inside the supplied `[0, 38] m²` limit (exit 0).
The exact maximum is 25 m²; the reported upper endpoint remains conservative.
All four input ranges and their output enclosures appear in the JSON report.

To check your own supplied calculation, send a JSON object on standard input:

```sh
python3 -B line-4/tools/subdivision-flint/subdivision_flint.py run <<'JSON'
{"variables":{"x":["0 m","10 m"]},"expression":"x * (10 m - x)","to":"m^2","within":["0 * m^2","38 * m^2"],"split":{"variable":"x","parts":"4"}}
JSON
```

All five top-level keys are required. `to` and `within` may be null. Variables
are inclusive `[lower, upper]` pairs of quantity expressions. `split.variable`
must name an input; `split.parts` is a decimal **string** from `"1"` through
`"64"`. JSON numbers, duplicate keys and extra keys are rejected. Use explicit
multiplication for a coefficient of a powered unit: `38 * m^2` means 38 square
metres, whereas the inherited parser treats `38 m^2` as `(38 m)^2`.

The selected input is covered completely by equal rational subintervals sharing
endpoints. Other inputs keep their full ranges. Each subdomain uses the inherited
exact interval arithmetic; the final lower/upper endpoints are the minimum and
maximum across all subdomains. No floating point or sampled values establish the
bound. Reports include the original enclosure, exact base-unit width reduction,
converted endpoints, dimensions, and optional containment/overlap checks.

Exit 0 means successful evaluation with no failed containment check; 1 means
the final enclosure is not fully within the supplied limits; 2 means invalid
input. Exit 1 does **not** prove a real value violates the limits: enclosures can
overestimate. Overlap also proves no particular real value is attainable.

The original whole domain must evaluate successfully first. A denominator
interval containing zero is rejected even if a different algebraic formulation
could remove the singularity. No subdomain is silently omitted. This is a
bounded enclosure refiner, not symbolic solving, optimization, probability,
automatic measurement validation, or proof that inputs describe reality.
Splitting an irrelevant input may give no improvement; repeated dependencies
can remain wide. No coin, price or payment is needed.

Limits inherited from Interval Flint: 65,536 request bytes, 32 variables,
4,096 expression characters, 256 tokens, 32 nesting levels, bounded exact
arithmetic and exponents. New work is capped at 64 subdomain evaluations plus
baseline/final checks. Extremely large valid endpoint expressions can still
exceed inherited parser limits when represented as exact subdivisions; those
requests fail explicitly rather than dropping precision.

Run the regression suite:

```sh
python3 -B -m unittest discover -s line-4/tools/subdivision-flint -v
```

All 11 tests passed locally. They cover the demo, identity subdivision,
remaining dependency width, 100 seeded comparisons against independent exact
quadratic extrema and rational domain coverage, conversion, untouched inputs,
negative reciprocals, point domains, singularities, strict JSON/schema checks
and actual CLI statuses/streams. These checks are local evidence only.

`engine.py` and `interval_flint.py` are byte-identical ordinary-file snapshots
from `line-4/tools/interval-flint/`. No installed dependency or network is needed.
