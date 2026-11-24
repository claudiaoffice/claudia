"""The server image is built from images with a stated version (CODE-20).

An image named without a tag, or as ``:latest``, changes under the build without a commit: the image's build tool,
or its base, is whatever was newest on the day it was built. Dependabot (``.github/dependabot.yml``) proposes the
updates instead, one reviewed commit at a time.
"""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"
FROM = re.compile(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE | re.MULTILINE)
COPY_FROM = re.compile(r"^COPY\s+--from=(\S+)", re.IGNORECASE | re.MULTILINE)


def _images() -> list[str]:
    """Every image the Dockerfile pulls: the ``FROM`` and ``COPY --from`` references that are not its own stages."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    stages = {match.group(2) for match in FROM.finditer(text) if match.group(2)}
    references = [match.group(1) for match in FROM.finditer(text)] + COPY_FROM.findall(text)
    return [reference for reference in references if reference not in stages]


def test_the_dockerfile_pulls_images():
    assert _images()


def test_every_image_has_a_version_that_is_not_latest():
    unpinned = [image for image in _images() if ":" not in image.split("/")[-1] or image.endswith(":latest")]
    assert not unpinned, f"name a version (dependabot proposes updates): {unpinned}"
