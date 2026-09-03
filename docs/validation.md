# Validation record for 0.2.0

Date: 2026-09-03
Host profile: Apple Silicon macOS, Python 3.12.13
Scope: pre-publication local release candidate

## Structural validation

| Check | Result |
| --- | --- |
| Unique control loops | 50 |
| Unique temporal Signals | 500 |
| Loop-associated Signals | 250 |
| Plant-context Signals | 250 |
| Unique candidate OPC UA NodeIds | 500 |
| Named scenario families | 20 |
| Signals per control loop | 5 |
| Catalog SHA-256 | `6c737ebdffa92708361632de0bad17a61c28e9b264608a3361558dee1e2339cb` |

## Automated checks

Ten tests passed locally. They cover catalog integrity, deterministic replay,
seed sensitivity, finite and bounded states, fault-truth isolation, transport
failure semantics, sparse plant-wide coupling, dataset byte reproducibility,
and an independent OPC UA client read from a 500-node server.

Static analysis and formatting checks passed with Ruff.

## Six-hour generation benchmark

Command:

```bash
process-plant-simulator generate \
  --duration-hours 6 \
  --sample-seconds 30 \
  --seed 20260903 \
  --output var/observations-6h.csv \
  --truth-output var/truth-6h.jsonl
```

| Metric | Result |
| --- | ---: |
| Frames | 720 |
| Published observations | 315,141 |
| Wall time | 8.08 s |
| Maximum resident set size | 79,937,536 bytes |
| Observation file size | approximately 31 MiB |
| Truth file size | approximately 13 MiB |
| Observation SHA-256 | `ea794857e9d0fc210000f907fe31f9a28aa2d44b9c6208b1917c6dcd6aba06bd` |
| Truth SHA-256 | `fbf71e4edc6d3968cc729a936305eccf0db50737b4322f677677e3c447ddd449` |

The digests printed by the application matched independent `shasum -a 256`
results. Generated files remain ignored and are not distributed in Git.

## Interpretation

This evidence verifies software behavior and reproducibility on one host. It
does not validate refinery fidelity, parameter calibration, fault prevalence,
or cross-platform bitwise identity. Linux CI, longer profiles, OPC UA
Historical Access continuation, and empirical calibration remain future
release gates.
