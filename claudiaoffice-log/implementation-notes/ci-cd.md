# CI/CD (GitHub Actions)

GitLab is abandoned; its leftover `.gitlab-ci.yml` was deleted on 2026-11-10.

- `docker.yml`: one image, linux/amd64 only (Scaleway takes nothing else). Smoke test = each app with `CLAUDIA_DEMO=1` answers `/api/health`.
- `deploy-demo.yml`: GHCR -> `rg.<region>.scw.cloud/<namespace>/claudia-demo:sha-<short>` -> `PATCH registry_image` + `POST .../deploy` on the Scaleway Containers API (`v1beta1`), then waits for `status=ready` and asks the demo URL. GitHub environment `demo` (optional approval). Variables/secrets are listed at the top of the file.
- `deb.yml` + `packaging/debian/build-deb.sh`: layout `/opt/claudia/{python,venv,web,shell}`, launcher `/usr/bin/claudia-composes` sets `CLAUDIA_SERVER_PYTHON`, `CLAUDIA_WEB_DIR` and `PYTHONPATH`. The venv is made at its final path (not relocatable), so the build needs an empty writable `/opt/claudia`.
- Open: deploy/publish are not gated by `ci.yml` (only by the image smoke test); arm64 image; deb for creates/computes shells (only composes has a client yet); signing of the deb / an apt repository.
- Unverified Scaleway details (documentation silent): that `PATCH registry_image` is accepted on an existing container, the `status` values (`ready`/`error`), WebSocket support on the platform.
