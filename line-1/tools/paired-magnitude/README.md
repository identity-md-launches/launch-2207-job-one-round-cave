# Paired Magnitude

Estimate the candidate-minus-baseline mean for a continuous metric, with a
reproducible case-level paired bootstrap percentile interval. This extends the
line's paired benchmark evidence to latency, size, cost, or another numeric
measurement. It resamples each case's already-paired difference, so each
replicate preserves the same-case comparison.

Python 3.9+, standard library only. From the repository root, see the synthetic
example work:

```sh
python3 -B line-1/tools/paired-magnitude/paired_magnitude.py --demo
```

With the default seed and 2000 replicates, the 12-case synthetic latency
illustration reports a mean difference of -5 ms and a 95% percentile interval
of approximately [-8.42, -1.5] ms. Negative values mean the candidate metric
was lower. The illustration is invented and makes no claim about a real system.

For your own observations, save a UTF-8 CSV in the workspace with exactly this
header and one row per paired case:

```csv
case,baseline,candidate
case-a,28.4,24.1
case-b,31.0,32.2
case-c,22.7,19.6
```

Run it with `python3 -B line-1/tools/paired-magnitude/paired_magnitude.py
--input path/to/your.csv`. Use the optional `--confidence`, `--replicates`, and
`--seed` flags to set a confidence level from 0.80–0.99, 200–20000 bootstrap
replicates, and a repeatable random seed. The JSON result includes the raw CSV
SHA-256, sample mean and median paired differences, interpolated interval
endpoints, and the fixed SplitMix64-v1 generator identifier. Identical input and
options produce identical output across supported Python versions.

The CSV uses finite numeric values and unique case IDs; it accepts UTF-8 (with
optional BOM), quoted fields and CRLF. Input is limited to 2 MiB and 10000
cases, and the input file must resolve inside the current workspace. No file is
written. Exit 2 reports malformed input on stderr without a partial JSON result.

The interval is a percentile bootstrap over cases. It assumes the selected
cases can be treated as independent draws from the target case population.
Repeated runs, correlated cases, selected benchmarks, drift, and case-level
clustering can make it too narrow or otherwise misleading. It is not a
simultaneous interval for many metrics, does not adjust repeated looks, and
does not establish practical value. It is not the exact binary test in Paired
Verdict or the cluster-aware inference in Cluster Verdict. Freeze the metric,
case set, direction, and analysis before viewing results. A descriptive interval
over a fixed benchmark says nothing by itself about untested tasks.
