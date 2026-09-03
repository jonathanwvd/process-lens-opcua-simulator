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

## Security boundary

Version 0.2.0 implements only an anonymous `NoSecurity` development profile and
binds the container port to loopback. This profile is not suitable for an
untrusted network. Certificate-based SignAndEncrypt profiles and user identity
configuration are planned before any non-local deployment guidance.

## Compatibility test

The automated suite starts the server on an ephemeral loopback port, resolves
the namespace by URI with an independent `asyncua` client, reads a control-loop
PV, and verifies the engineering-unit property and total 500-node server map.
