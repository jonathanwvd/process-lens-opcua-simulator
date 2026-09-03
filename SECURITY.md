# Security policy

## Supported versions

Only the latest tagged release receives security fixes during the alpha phase.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub’s private
security-advisory reporting for this repository. Include affected versions,
reproduction steps, impact, and any proposed mitigation.

## Deployment boundary

The default server uses anonymous OPC UA with no message security and binds to
loopback. It is intended only for local research and integration testing. Do
not expose it to an untrusted network or use it as an industrial control
endpoint. The simulator never writes to industrial systems.
