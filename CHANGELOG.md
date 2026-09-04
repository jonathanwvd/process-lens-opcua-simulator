# Changelog

## 0.3.3 — 2026-09-04

- Index every historian table by source timestamp, including compatible
  existing volumes, so steady-state retention remains bounded after a
  24-hour bootstrap.
- Preserve the 0.3.2 restart-gap and freshness semantics and all scientific
  benchmark identities.

## 0.3.2 — 2026-09-04

- Advance compatible deterministic state across wall-clock downtime before the
  OPC UA endpoint becomes ready, then commit one current frame without
  fabricating observations inside the outage gap.
- Preserve the 0.3.0 benchmark, schema, catalog, and checkpoint identities so
  existing compatible historian volumes resume in place.
- Make the container healthcheck reject stale or implausibly future source
  timestamps instead of treating server-state availability as sufficient.
- Add restart-gap, current-publication, and timestamp-freshness coverage.

## 0.3.1 — 2026-09-04

- Preserve the 0.3.0 benchmark, schema, catalog, and checkpoint identities while
  eliminating redundant per-node retention deletes during a new historian's
  bounded cold bootstrap.
- Increase the bounded cold-bootstrap write batch from 20,000 to 100,000 values;
  steady-state writes continue enforcing retention on every committed frame.
- Add direct coverage proving that retention can be deferred only for the
  already bounded, initially empty bootstrap transaction stream.

## 0.3.0 — 2026-09-04

- Add closed JSON Schema v1 contracts for benchmark manifests, runtime profiles,
  observation rows, hidden-truth frames, and dataset manifests.
- Add canonical prefixed SHA-256 manifest identities and compatibility checks.
- Add executable smoke, development, paper, and stress profiles shared by
  offline generation and the OPC UA server.
- Reject ambiguous timestamps, rounded intervals, and silently clamped runtime
  parameters before generation or server startup.
- Preserve distinct source and server timestamps in datasets and OPC UA values.
- Publish all resolved loop-model parameters and structure policies in the
  benchmark manifest.
- Enforce coupling delays, actuator travel limits, bounded anti-windup,
  bumpless manual return, reversal-aware backlash, split-range mapping, and
  protective selector behavior.
- Add deterministic invariants for model completeness, signed delayed coupling,
  control modes, balance residuals, actuator failures, and sensor recovery.
- Normalize historian timestamps and close inclusive, reverse, empty-range, and
  continuation-point behavior.
- Add bounded retention plus a transactional, versioned simulator checkpoint so
  compatible restarts continue without duplicating bootstrap history.
- Reject incompatible checkpoints and interrupted historian bootstraps before
  starting the OPC UA endpoint.
- Freeze numerical parameterizations and executable minimum signatures for all
  20 scenarios in versioned contracts.
- Scope controller-tuning scenarios to their active windows, propagate the
  downstream oscillation through the declared delayed coupling, and model
  irregular cadence with deterministic missing slots and timestamp jitter.
- Add a reproducible parallel 15/5/10-seed scenario qualification workflow and
  canonical study manifests.
- Add per-scenario 95% seed confidence intervals and development-fit,
  observation-only window baselines for cumulative PV/SP,
  controller/actuator/mode, and quality/timestamp views.
- Add explicit scenario allowlists for integrated, isolated, and deliberate
  overlap studies, with fail-fast validation and exact selection provenance.
- Add an observation-only active/inactive per-frame baseline and a graph view
  using directly connected published PVs, while reporting false alarms per
  loop-day and excluding topology-confounded scenario-name scoring.
- Add a canonical 600-run isolation matrix covering all 20 scenarios and 30
  fixed seeds, with per-run digests, failures, confidence intervals, and a
  closed JSON Schema contract.
- Excite declared upstream control loops during `process.interaction` so the
  isolated scenario propagates a measurable delayed response through the plant
  graph without implicitly enabling the global load-change scenario.
- Add a bounded-memory option for high-cadence scenario studies that omits only
  in-memory per-frame baselines while preserving scenario and window metrics.
- Exclude frames with no nominally scheduled Signals from transport-signature
  denominators, preventing high publication cadence from appearing as data loss.
- Give `control.sluggish_tuning` an explicit 0.06 normalized setpoint step and
  qualify its response over a fixed 1,800-second physical window, so changing
  the scenario-cycle duration no longer dilutes the signature threshold.
- Cache immutable scenario-onset offsets and reuse the preceding active state
  during integration, reducing qualification profiler time by about 25% while
  preserving canonical evaluation digests.
- Add observation-only temporal detection and candidate-loop localization
  baselines, using three-frame persistence and a shared identity-free anomaly
  score with average precision plus precision/recall at five.
- Compare native irregular observations with a causal 60-second last-value
  regularization that retains quality, timestamps, and explicit imputation.
- Add a cross-platform Python 3.12/3.13 CI matrix and complete-suite execution
  on Linux, macOS, and Windows release-support targets.
- Document release compatibility, 0.2-to-0.3 migration, scenario change
  control, the security threat model, and the independent scientific-review
  disposition required before publication-grade claims.
- Include citation, security, release, scientific, container, and contract
  documentation in the source distribution.
- Make the standalone container start with the bounded `smoke` profile by
  default; longer research histories remain explicit profile selections.
- Qualify scenario behavior across Linux, macOS, and Windows while defining
  byte-identical numerical replay within one recorded execution environment;
  system math libraries may differ in last-bit floating-point results.

## 0.2.0 — 2026-09-03

- Define an integrated ten-area, 50-loop, 500-signal plant catalog.
- Add 20 layered normal and failure scenarios.
- Add deterministic grey-box process, PI controller, actuator, sensor, and
  transport models.
- Add separate observation CSV and hidden-truth JSONL generation with SHA-256
  digests.
- Add a 500-node OPC UA Data Access and Historical Access server.
- Add scientific-method, research-protocol, security, citation, container, and
  continuous-integration documentation.
