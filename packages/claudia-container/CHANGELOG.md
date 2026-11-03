# Changelog of claudia-container

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-02

First version (E2.2, first slice). Design: D70-D82 in `claude/e2-container-design.md` of the project.

### Added
- `KdfParams`, `LoginMaterial`, `derive_login_material`, `derive_recovery_material`: Argon2id and HKDF behind one small
  interface; a login yields a *locator* and a *key-encryption key* (names stay hidden, D72).
- `seal`, `open_sealed`, `random_key`, `DecryptionError`: AES-256-GCM with a random nonce and authenticated data.
- `password_problems`, `require_strong_password`, `WeakPassword`: the password rules of D79.
- `Role`, `Domain`, `KeySlot`, `Unlocked`, `new_domain_keys`, `make_slot`, `open_slot`: one key slot per user, holding the
  domain keys of the user's role (D71).
- `new_recovery_key`, `format_recovery_key`, `parse_recovery_key`, `InvalidRecoveryKey`: the recovery key (D75).
