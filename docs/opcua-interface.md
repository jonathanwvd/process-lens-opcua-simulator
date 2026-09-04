# OPC UA interface

## Namespace and hierarchy

Namespace URI:

```text
https://github.com/jonathanwvd/process-lens-opcua-simulator
```

Logical hierarchy:

```text
Objects
└── Plant
    ├── ControlLoops
    │   └── <LOOP>
    │       ├── PV
    │       ├── SP
    │       ├── OP
    │       ├── MODE
    │       └── MVFB
    └── Areas
        └── <AREA>
            └── <EQUIPMENT>
                └── <SIGNAL>
```

Each Variable exposes `SignalId`, `EngineeringUnit`, and `DescriptionPtBr`
properties. Stable string identifiers are listed in the signal catalog. A
client must resolve the runtime namespace index from the namespace URI rather
than assuming `ns=2`.

## Time and quality

Each published `DataValue` carries source and server timestamps. Normal values
use `Good`; deliberate bad-quality cases use `Bad`; irregular-cadence cases use
`Uncertain` and retain their shifted source timestamp. Gap and communication
loss scenarios omit observations rather than fabricating zeroes.

Historical reads return the values, statuses, and timestamps that were
observed. This follows the OPC UA Part 11 principle that raw historical data
represent what a subscriber would have seen at that time.

Source timestamps are normalized to UTC before SQLite encoding and query
bounds use the same representation. Both interval endpoints are inclusive.
Ascending and reverse reads are supported; empty ranges return no values.
Responses are capped by the selected runtime profile and use OPC UA
continuation points without repeating or skipping the boundary sample.

Different catalog cadences remain different in history. `Good`, `Uncertain`,
`Bad`, and `BadNoCommunication` have explicit status-code mappings. Gap and
communication-loss scenarios do not create synthetic zeroes or historical
rows; recovery resumes with a fresh `Good` value and timestamp. Irregular
cadence retains different source and server timestamps.

## Retention and restart

When history is enabled, each node is pruned against the configured retention
window as new values arrive. Observation rows and the simulator checkpoint are
committed in one SQLite transaction. The checkpoint pins benchmark version,
catalog digest, namespace, seed, UTC origin, elapsed time, integration step,
publication cadence, and scenario cycle.

On restart, the deterministic model replays to the checkpoint without writing
the bootstrap period again. If wall-clock time advanced while the server was
offline, the model then advances deterministically across that interval and
writes one current frame; the outage remains an explicit gap rather than a
fabricated historical stream. Existing historical rows otherwise remain
unchanged and live publication continues from the next frame. A configuration
mismatch fails before the endpoint starts. A database containing observations
without a complete checkpoint is treated as an interrupted bootstrap and
requires an explicit `--reset`; it is never silently repaired or duplicated.

## Security boundary

The server implements only an anonymous `NoSecurity` development profile and
the container binds its port to loopback. This profile is not suitable for an
untrusted network. Certificate-based SignAndEncrypt profiles and user identity
configuration are required before any non-local deployment guidance.

## Compatibility test

The server publishes a non-historized `Plant.SimulatorHeartbeat` technical node
outside the 500-Signal scientific catalog. Its source timestamp advances with
each simulation frame even when a declared scenario intentionally suppresses
Signal observations. The container healthcheck reads this node and rejects
stale or implausibly future source timestamps in addition to checking server
state; it therefore measures process liveness without erasing simulated data
unavailability.

The automated suite starts the server on ephemeral loopback ports and resolves
the namespace by URI with an independent `asyncua` client. It verifies the
500-node map, current values and engineering metadata, multi-page Historical
Access, inclusive and reverse bounds, empty ranges, mixed cadences, status and
timestamp preservation, gaps, recovery, retention, restart continuity, and
checkpoint mismatch rejection.
