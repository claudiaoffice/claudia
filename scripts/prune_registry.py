"""Delete the demo image's old tags in the Scaleway Container Registry before a new one is pushed (``deploy-demo.yml``).

Every deployment of the demo pushes the image under a new tag (``sha-<short sha>``). Scaleway keeps them all and bills
the storage, so before the push this script deletes every tag of the image except

* the tag about to be pushed (redeploying the same commit does not upload it again),
* the tags the demo containers run now (a deployment that fails leaves the running version in place),
* the newest ``--keep-newest`` others (none by default), and
* every tag pointing at the same digest as one of those: deleting a tag removes its manifest, and with it every
  other tag of that digest.

Going back to an earlier version needs none of the deleted tags: the deployment copies any tag from GHCR again.
Nothing is deleted when a container or the registry cannot be asked, because then it is not known what runs.

``uv run --no-project python scripts/prune_registry.py --region fr-par --namespace NS --image claudia-demo \\``
``    --keep sha-1a2b3c4 --container UUID [--container UUID ...] [--keep-newest N] [--dry-run]``

The API key is read from ``SCW_SECRET_KEY`` (rights: ContainersReadOnly or more, ContainerRegistryFullAccess). Only
the standard library is used, so the runner needs nothing installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Protocol

API_ROOT = "https://api.scaleway.com"
PAGE_SIZE = 100  # the most the registry API hands out per page
TIMEOUT = 30  # seconds per request

Query = Mapping[str, str | int]
Tag = Mapping[str, Any]

# Everything that ends up in a URL path is checked, so that a variable set wrongly cannot point a DELETE elsewhere.
_REGION = re.compile(r"^[a-z]{2}-[a-z]{3}$")
_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_TAG = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ApiError(Exception):
    """The Scaleway API answered with an error status."""

    def __init__(self, status: int, method: str, path: str, body: str) -> None:
        super().__init__(f"HTTP {status} from {method} {path}: {body[:500]}")
        self.status = status


class Api(Protocol):
    """The two calls the pruning needs; :class:`ScalewayApi` makes them over HTTP, the tests from memory."""

    def get(self, path: str, query: Query | None = None) -> Any: ...

    def delete(self, path: str, query: Query | None = None) -> Any: ...


class ScalewayApi:
    """A minimal client of ``api.scaleway.com``: JSON in, JSON out, :class:`ApiError` for any 4xx or 5xx."""

    def __init__(self, secret_key: str, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self._secret_key = secret_key
        self._open = opener

    def get(self, path: str, query: Query | None = None) -> Any:
        return self._call("GET", path, query)

    def delete(self, path: str, query: Query | None = None) -> Any:
        return self._call("DELETE", path, query)

    def _call(self, method: str, path: str, query: Query | None) -> Any:
        url = API_ROOT + path + (f"?{urllib.parse.urlencode(query)}" if query else "")
        request = urllib.request.Request(url, method=method, headers={"X-Auth-Token": self._secret_key})
        try:
            with self._open(request, timeout=TIMEOUT) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise ApiError(error.code, method, path, error.read().decode("utf-8", "replace")) from error
        return json.loads(body) if body else None


def tag_of(registry_image: str, repository: str) -> str | None:
    """The tag of ``registry_image`` if it is an image of ``repository`` (``rg.fr-par.scw.cloud/ns/claudia-demo``)."""
    prefix = f"{repository}:"
    if not registry_image.startswith(prefix):
        return None
    return registry_image.removeprefix(prefix) or None


def tags_to_delete(tags: Iterable[Tag], keep: set[str], keep_newest: int = 0) -> list[Tag]:
    """The tags to delete, newest first: all but those named in ``keep``, the ``keep_newest`` newest others, and any
    tag sharing a digest with a kept one."""
    newest_first = sorted(tags, key=lambda tag: tag.get("created_at") or "", reverse=True)
    others = [tag for tag in newest_first if tag["name"] not in keep]
    kept = keep | {tag["name"] for tag in others[:keep_newest]}
    kept_digests = {tag.get("digest") for tag in newest_first if tag["name"] in kept} - {None, ""}
    return [tag for tag in newest_first if tag["name"] not in kept and tag.get("digest") not in kept_digests]


def _running_tags(api: Api, region: str, container_ids: Iterable[str], repository: str) -> set[str]:
    running: set[str] = set()
    for container_id in container_ids:
        container = api.get(f"/containers/v1beta1/regions/{region}/containers/{container_id}")
        tag = tag_of(container.get("registry_image") or "", repository)
        if tag:
            running.add(tag)
    return running


def _image_id(api: Api, region: str, namespace: str, image: str) -> str | None:
    namespaces = api.get(f"/registry/v1/regions/{region}/namespaces", {"name": namespace})["namespaces"]
    matching = [entry["id"] for entry in namespaces if entry["name"] == namespace]
    if len(matching) != 1:
        raise LookupError(f"{len(matching)} registry namespaces called {namespace!r} in {region}, expected one")
    images = api.get(f"/registry/v1/regions/{region}/images", {"namespace_id": matching[0], "name": image})["images"]
    return next((entry["id"] for entry in images if entry["name"] == image), None)


def _all_tags(api: Api, region: str, image_id: str) -> list[Tag]:
    tags: list[Tag] = []
    page = 1
    while True:
        query: Query = {"page": page, "page_size": PAGE_SIZE, "order_by": "created_at_desc"}
        chunk = api.get(f"/registry/v1/regions/{region}/images/{image_id}/tags", query)["tags"]
        tags.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            return tags
        page += 1


def prune(
    api: Api,
    *,
    region: str,
    namespace: str,
    image: str,
    keep: Iterable[str],
    container_ids: Iterable[str],
    keep_newest: int = 0,
    dry_run: bool = False,
    log: Callable[[str], object] = print,
) -> list[str]:
    """Delete the old tags of ``image`` (see the module docstring) and return their names, newest first.

    Everything is asked before anything is deleted, so an error while asking leaves the registry as it was.
    """
    repository = f"rg.{region}.scw.cloud/{namespace}/{image}"
    kept = set(keep) | _running_tags(api, region, container_ids, repository)
    image_id = _image_id(api, region, namespace, image)
    if image_id is None:
        log(f"{repository} is not in the registry yet; nothing to delete")
        return []
    doomed = tags_to_delete(_all_tags(api, region, image_id), kept, keep_newest)
    log(f"keeping {', '.join(sorted(kept))} (and the tags sharing their digests); {len(doomed)} old tag(s) to delete")
    for tag in doomed:
        log(f"{'would delete' if dry_run else 'deleting'} {repository}:{tag['name']}")
        if dry_run:
            continue
        try:
            api.delete(f"/registry/v1/regions/{region}/tags/{tag['id']}", {"force": "true"})
        except ApiError as error:
            if error.status != 404:  # a 404 is a tag that went with a digest deleted just before
                raise
    return [tag["name"] for tag in doomed]


def _invalid_values(args: argparse.Namespace) -> list[str]:
    checks = [(_REGION, [args.region]), (_NAME, [args.namespace, args.image]), (_TAG, args.keep)]
    checks.append((_UUID, args.container))
    return [value for pattern, values in checks for value in values if not pattern.match(value)]


def main(
    argv: Sequence[str],
    environ: Mapping[str, str] = os.environ,
    api_factory: Callable[[str], Api] = ScalewayApi,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--region", required=True, help="fr-par, nl-ams or pl-waw")
    parser.add_argument("--namespace", required=True, help="the registry namespace, as in rg.REGION.scw.cloud/NS")
    parser.add_argument("--image", required=True, help="the image name in the namespace, e.g. claudia-demo")
    parser.add_argument("--keep", action="append", default=[], help="a tag to keep (repeatable)")
    parser.add_argument("--container", action="append", default=[], help="a container whose tag to keep (repeatable)")
    parser.add_argument("--keep-newest", type=int, default=0, help="also keep this many of the newest other tags")
    parser.add_argument("--dry-run", action="store_true", help="say what would be deleted, delete nothing")
    args = parser.parse_args(argv)

    secret_key = environ.get("SCW_SECRET_KEY", "")
    if not secret_key:
        print("SCW_SECRET_KEY is not set", file=sys.stderr)
        return 2
    invalid = _invalid_values(args)
    if invalid or args.keep_newest < 0:
        print(f"refusing values that do not belong in a URL: {invalid or [args.keep_newest]}", file=sys.stderr)
        return 2

    try:
        deleted = prune(
            api_factory(secret_key),
            region=args.region,
            namespace=args.namespace,
            image=args.image,
            keep=args.keep,
            container_ids=args.container,
            keep_newest=args.keep_newest,
            dry_run=args.dry_run,
        )
    except (ApiError, LookupError, urllib.error.URLError) as error:
        # A warning, not an error: the deployment goes on, and the next one tries again.
        print(f"::warning::old tags not deleted: {error}")
        return 1
    print(f"{'would delete' if args.dry_run else 'deleted'} {len(deleted)} old tag(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
