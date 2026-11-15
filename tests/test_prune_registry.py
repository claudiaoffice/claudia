"""Pruning the demo image's old tags in the Scaleway Container Registry (``scripts/prune_registry.py``).

Every deployment of the demo pushed a new ``sha-<short sha>`` tag and none was ever deleted, so the registry grew by
one image per push to main and Scaleway billed the storage. The script runs in ``deploy-demo.yml`` before the push.
"""

import importlib.util
import io
import json
import sys
import urllib.error
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("prune_registry", ROOT / "scripts" / "prune_registry.py")
prune_registry = importlib.util.module_from_spec(SPEC)
sys.modules["prune_registry"] = prune_registry
SPEC.loader.exec_module(prune_registry)

REGION = "fr-par"
NAMESPACE = "claudia"
IMAGE = "claudia-demo"
REPOSITORY = f"rg.{REGION}.scw.cloud/{NAMESPACE}/{IMAGE}"
APP_1 = "11111111-1111-1111-1111-111111111111"
APP_2 = "22222222-2222-2222-2222-222222222222"


def tag(name: str, day: int, digest: str | None = None) -> dict[str, Any]:
    """A tag as the registry API lists it; ``day`` orders them by age (higher is newer)."""
    return {
        "id": f"id-{name}",
        "name": name,
        "digest": digest or f"sha256:{name}",
        "created_at": f"2026-11-{day:02d}T10:00:00Z",
    }


class FakeApi:
    """The parts of the Scaleway API the script asks, answered from memory; records what it deletes."""

    def __init__(self, tags: list[dict[str, Any]], running: Mapping[str, str], *, has_image: bool = True) -> None:
        self.tags = tags
        self.running = running
        self.has_image = has_image
        self.deleted: list[str] = []
        self.gone: set[str] = set()  # tag ids that answer 404 (went with a digest deleted before)

    def get(self, path: str, query: Mapping[str, str | int] | None = None) -> Any:
        query = query or {}
        if path == f"/registry/v1/regions/{REGION}/namespaces":
            names = [NAMESPACE, "other"]
            return {"namespaces": [{"id": f"ns-{n}", "name": n} for n in names if n == query.get("name")]}
        if path == f"/registry/v1/regions/{REGION}/images":
            assert query["namespace_id"] == f"ns-{NAMESPACE}"
            found = self.has_image and query.get("name") == IMAGE
            return {"images": [{"id": "img-demo", "name": IMAGE}] if found else []}
        if path == f"/registry/v1/regions/{REGION}/images/img-demo/tags":
            newest_first = sorted(self.tags, key=lambda t: t["created_at"], reverse=True)
            size, page = int(query["page_size"]), int(query["page"])
            return {"tags": newest_first[(page - 1) * size : page * size], "total_count": len(self.tags)}
        prefix = f"/containers/v1beta1/regions/{REGION}/containers/"
        if path.startswith(prefix):
            container = path.removeprefix(prefix)
            if container not in self.running:
                raise prune_registry.ApiError(404, "GET", path, '{"message": "not found"}')
            return {"id": container, "registry_image": self.running[container]}
        raise AssertionError(f"unexpected GET {path} {query}")

    def delete(self, path: str, query: Mapping[str, str | int] | None = None) -> Any:
        tag_id = path.removeprefix(f"/registry/v1/regions/{REGION}/tags/")
        assert query == {"force": "true"}
        if tag_id in self.gone:
            raise prune_registry.ApiError(404, "DELETE", path, "")
        self.deleted.append(tag_id)
        return {}


def run(api: FakeApi, **kwargs: Any) -> list[str]:
    options: dict[str, Any] = {
        "region": REGION,
        "namespace": NAMESPACE,
        "image": IMAGE,
        "keep": ["sha-new"],
        "container_ids": [APP_1, APP_2],
        "log": lambda _line: None,
    }
    options.update(kwargs)
    return prune_registry.prune(api, **options)


# --- choosing what to delete -------------------------------------------------------------------------------------


def test_every_tag_but_the_kept_ones_is_deleted():
    tags = [tag("sha-a", 1), tag("sha-b", 2), tag("sha-c", 3)]
    assert [t["name"] for t in prune_registry.tags_to_delete(tags, {"sha-b"})] == ["sha-c", "sha-a"]


def test_a_tag_sharing_its_digest_with_a_kept_one_is_kept():
    """Deleting a tag by force removes its manifest, and with it every tag pointing at the same digest."""
    tags = [tag("sha-a", 1, "sha256:same"), tag("latest", 2, "sha256:same"), tag("sha-b", 3)]
    assert [t["name"] for t in prune_registry.tags_to_delete(tags, {"sha-a"})] == ["sha-b"]


def test_keep_newest_spares_the_newest_others_and_their_digests():
    tags = [tag("sha-a", 1), tag("sha-b", 2, "sha256:b"), tag("sha-c", 3), tag("b-alias", 4, "sha256:b")]
    deleted = prune_registry.tags_to_delete(tags, {"sha-c"}, keep_newest=1)
    assert [t["name"] for t in deleted] == ["sha-a"]


def test_nothing_is_deleted_when_everything_is_kept():
    assert prune_registry.tags_to_delete([tag("sha-a", 1)], {"sha-a"}) == []


def test_the_tag_of_an_image_of_the_repository():
    assert prune_registry.tag_of(f"{REPOSITORY}:sha-a", REPOSITORY) == "sha-a"


def test_an_image_of_another_repository_has_no_tag_here():
    assert prune_registry.tag_of(f"{REPOSITORY}-old:sha-a", REPOSITORY) is None
    assert prune_registry.tag_of("docker.io/library/nginx:latest", REPOSITORY) is None
    assert prune_registry.tag_of(f"{REPOSITORY}:", REPOSITORY) is None


# --- talking to the registry --------------------------------------------------------------------------------------


def test_prune_keeps_the_new_tag_and_what_the_containers_run():
    api = FakeApi(
        [tag("sha-a", 1), tag("sha-b", 2), tag("sha-c", 3), tag("sha-new", 4)],
        {APP_1: f"{REPOSITORY}:sha-b", APP_2: f"{REPOSITORY}:sha-c"},
    )
    assert run(api) == ["sha-a"]
    assert api.deleted == ["id-sha-a"]


def test_prune_ignores_a_container_running_an_image_from_elsewhere():
    api = FakeApi([tag("sha-a", 1), tag("sha-b", 2)], {APP_1: f"{REPOSITORY}:sha-b", APP_2: "nginx:latest"})
    assert run(api) == ["sha-a"]


def test_prune_reads_every_page_of_tags():
    tags = [tag(f"sha-{n:03d}", 1 + n % 28) for n in range(250)]
    api = FakeApi(tags, {APP_1: f"{REPOSITORY}:sha-000", APP_2: f"{REPOSITORY}:sha-000"})
    assert len(run(api)) == 249
    assert "id-sha-000" not in api.deleted


def test_prune_with_no_image_in_the_registry_yet_deletes_nothing():
    api = FakeApi([], {APP_1: "", APP_2: ""}, has_image=False)
    assert run(api) == []
    assert api.deleted == []


def test_a_dry_run_deletes_nothing():
    api = FakeApi([tag("sha-a", 1), tag("sha-b", 2)], {APP_1: f"{REPOSITORY}:sha-b", APP_2: f"{REPOSITORY}:sha-b"})
    lines: list[str] = []
    assert run(api, dry_run=True, log=lines.append) == ["sha-a"]
    assert api.deleted == []
    assert f"would delete {REPOSITORY}:sha-a" in lines


def test_a_tag_that_went_with_an_earlier_digest_is_not_an_error():
    api = FakeApi(
        [tag("sha-a", 1, "sha256:x"), tag("x-alias", 2, "sha256:x"), tag("sha-b", 3)],
        {APP_1: f"{REPOSITORY}:sha-b", APP_2: f"{REPOSITORY}:sha-b"},
    )
    api.gone = {"id-sha-a"}
    assert run(api) == ["x-alias", "sha-a"]
    assert api.deleted == ["id-x-alias"]


def test_nothing_is_deleted_when_a_container_cannot_be_asked():
    """Without knowing what runs, the running image might be deleted; better to keep everything this time."""
    api = FakeApi([tag("sha-a", 1)], {APP_1: f"{REPOSITORY}:sha-a"})
    with pytest.raises(prune_registry.ApiError):
        run(api)
    assert api.deleted == []


def test_an_unknown_namespace_is_an_error():
    api = FakeApi([tag("sha-a", 1)], {APP_1: "", APP_2: ""})
    with pytest.raises(LookupError, match="nowhere"):
        run(api, namespace="nowhere")
    assert api.deleted == []


# --- the HTTP layer -----------------------------------------------------------------------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def test_the_api_sends_the_key_and_the_query_and_reads_json():
    seen: list[Any] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        seen.append((request, timeout))
        return FakeResponse(json.dumps({"tags": []}).encode())

    api = prune_registry.ScalewayApi("secret", opener=opener)
    assert api.get("/registry/v1/regions/fr-par/images/x/tags", {"page": 2, "order_by": "created_at_desc"}) == {
        "tags": []
    }
    request, timeout = seen[0]
    assert request.full_url == (
        "https://api.scaleway.com/registry/v1/regions/fr-par/images/x/tags?page=2&order_by=created_at_desc"
    )
    assert request.get_method() == "GET"
    assert request.get_header("X-auth-token") == "secret"
    assert timeout > 0


def test_the_api_answers_none_for_an_empty_body():
    api = prune_registry.ScalewayApi("secret", opener=lambda request, timeout: FakeResponse(b""))
    assert api.delete("/registry/v1/regions/fr-par/tags/t", {"force": "true"}) is None


def test_the_api_turns_an_http_error_into_an_api_error():
    def opener(request: Any, timeout: float) -> FakeResponse:
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"message": "denied"}'))  # type: ignore[arg-type]

    api = prune_registry.ScalewayApi("secret", opener=opener)
    with pytest.raises(prune_registry.ApiError, match="HTTP 403 from DELETE .*denied") as caught:
        api.delete("/registry/v1/regions/fr-par/tags/t")
    assert caught.value.status == 403


# --- the command line ---------------------------------------------------------------------------------------------

ARGS = ["--region", REGION, "--namespace", NAMESPACE, "--image", IMAGE, "--keep", "sha-new", "--container", APP_1]


def test_main_prunes_with_the_key_from_the_environment(capsys):
    api = FakeApi([tag("sha-a", 1), tag("sha-b", 2)], {APP_1: f"{REPOSITORY}:sha-b"})
    keys: list[str] = []

    def factory(key: str) -> FakeApi:
        keys.append(key)
        return api

    assert prune_registry.main(ARGS, {"SCW_SECRET_KEY": "secret"}, factory) == 0
    assert keys == ["secret"]
    assert api.deleted == ["id-sha-a"]
    assert "deleted 1 old tag(s)" in capsys.readouterr().out


def test_main_without_a_key_fails(capsys):
    assert prune_registry.main(ARGS, {}, lambda key: pytest.fail("no API without a key")) == 2
    assert "SCW_SECRET_KEY" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("option", "value"),
    [("--container", "not-a-uuid"), ("--region", "../x"), ("--namespace", "a/b"), ("--keep", "a b")],
)
def test_main_refuses_values_that_would_bend_a_url(option, value, capsys):
    args = [*ARGS, option, value]
    assert prune_registry.main(args, {"SCW_SECRET_KEY": "secret"}, lambda key: pytest.fail("not called")) == 2
    assert value in capsys.readouterr().err


def test_main_reports_an_api_failure_as_a_warning(capsys):
    api = FakeApi([tag("sha-a", 1)], {})
    assert prune_registry.main(ARGS, {"SCW_SECRET_KEY": "secret"}, lambda key: api) == 1
    assert capsys.readouterr().out.startswith("::warning::old tags not deleted: HTTP 404")


# --- the workflow -------------------------------------------------------------------------------------------------


def test_the_demo_deployment_prunes_before_it_pushes():
    workflow = (ROOT / ".github" / "workflows" / "deploy-demo.yml").read_text(encoding="utf-8")
    prune = workflow.index("python scripts/prune_registry.py")
    assert prune < workflow.index("docker push"), "the old tags must go before the new image is pushed"
    assert "continue-on-error: true" in workflow[workflow.rindex("- name:", 0, prune) : prune]
