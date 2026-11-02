# Changelog of claudia-client

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-02

First version (E3.1).

### Added
- `TlsPolicy`, `UntrustedCertificate`, `fingerprint_of`: trusting a server's certificate like an SSH host (the person
  is shown the fingerprint once; a different certificate later is refused loudly).
