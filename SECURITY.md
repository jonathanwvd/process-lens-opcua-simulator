# Security policy and threat model

## Supported versions

Only the latest published release receives security fixes. Version 0.3.0 is an
alpha research release and is not a production industrial source. See
[Release and compatibility](docs/release.md) for the exact version table.

## Reporting a vulnerability

Do not include credentials, private endpoints, exploit payloads, or historian
contents in a public issue. Use GitHub's private vulnerability reporting for
this repository when it is enabled. If it is unavailable, contact the
repository owner privately and provide the affected version, reproduction
conditions, expected impact, and the smallest safe proof of concept.

## Intended trust boundary

The bundled server is a synthetic research and integration-test source. Its
default OPC UA endpoint uses anonymous access and `NoSecurity`. The Compose
profile binds the endpoint to host loopback, drops Linux capabilities, uses a
read-only root filesystem, and persists only the SQLite historian volume.

The supported deployment boundary is therefore:

- a developer workstation or isolated laboratory network;
- trusted local OPC UA clients;
- no routable exposure of port 4840 to an untrusted network;
- no production control, safety, or industrial write path;
- no confidential or proprietary input data.

The simulator does not provide certificate enrollment, user authentication,
authorization roles, audit-event retention, denial-of-service protection, or
high-availability guarantees. Those controls must be supplied by an external
deployment boundary, and such deployments are not covered by the public
support statement.

## Assets and threats

| Asset | Relevant threat | Current control | Residual limitation |
| --- | --- | --- | --- |
| Benchmark identity | Catalog or parameter substitution | Closed schemas and SHA-256 manifest identity | Digests establish identity, not author authenticity |
| Observation history | Silent truncation, duplication, or incompatible restart | Transactional checkpoint, retention bounds, mismatch rejection | SQLite is development persistence, not replicated archival storage |
| Hidden truth | Label leakage into evaluated methods | Separate truth artifact; absent from OPC UA | Researchers must maintain separation after export |
| OPC UA endpoint | Unauthorized reads or resource exhaustion | Loopback-only container default and bounded history responses | Anonymous `NoSecurity` is unsafe on untrusted networks |
| Release artifacts | Dependency or artifact tampering | Pinned runtime dependency, CI builds, planned checksums and provenance | Signed release provenance remains a publication gate |

## Secrets and data handling

The repository and generated benchmark artifacts require no credentials.
Never commit tunnel tokens, certificates, private keys, source credentials, or
private endpoint names. Generated histories and datasets are disposable unless
explicitly selected as research evidence. Hidden-truth artifacts must not be
mounted into an inference service or exposed through OPC UA.
