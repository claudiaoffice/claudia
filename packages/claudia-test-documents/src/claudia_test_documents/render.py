"""Tier 3: a visual backstop for a property that is only meaningful as rendered appearance (D218).

Not run by default (``--visual``), and not a replacement for Tiers 1-2: a table or an image that is missing
entirely is caught exactly and far more cheaply by :mod:`claudia_test_documents.runner`'s own preserve checks
(``claudia_opc_io``'s byte-for-byte guarantee is strictly stronger than any pixel comparison could be). This
exists for the opposite case -- a property with no structural oracle at all, where "does it look right" is the
only available check (layout, a pivot table's rendered shape, a transition's visible effect). No current
catalogue entry needs it yet (see the implementation note); the mechanism is built and tested so it is ready
when claudia has one.

LibreOffice does the rendering, not claudia's own -- there is no PDF/print export to use even if there were one
to trust for this. By the time either file leaves claudia it is an ordinary office file, which ``soffice`` can
open and rasterize on its own, independent of anything claudia's own export pipeline did.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def render_first_page(file_bytes: bytes, suffix: str, out_dir: Path) -> Path:
    """``file_bytes`` (a file of the kind ``suffix`` names, e.g. ``".docx"``) rasterized to a PNG of its first
    page by headless LibreOffice, written under ``out_dir`` (created if needed). Raises
    ``subprocess.CalledProcessError`` if ``soffice`` fails, and ``RuntimeError`` if it exits cleanly but produces
    no file -- both real failures to surface, not to swallow into a false "no visual difference"."""
    out_dir.mkdir(parents=True, exist_ok=True)
    source = out_dir / f"input{suffix}"
    source.write_bytes(file_bytes)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "png", "--outdir", str(out_dir), str(source)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    png = source.with_suffix(".png")
    if not png.exists():
        raise RuntimeError(f"soffice exited cleanly but did not produce {png.name}")
    return png


def perceptual_difference(image_a: Path, image_b: Path) -> float:
    """``0.0`` (identical) to ``1.0`` (maximally different): the mean absolute difference per pixel per channel
    between the two images, normalized, after resizing ``image_b`` to ``image_a``'s size. Deliberately crude --
    no SSIM, no dependency beyond Pillow (already in the workspace, via python-pptx) -- good enough to catch a
    layout break, not meant as a precise similarity metric; font-hinting/anti-aliasing noise is why a caller
    should compare against a tolerance, not against zero."""
    a = Image.open(image_a).convert("RGB")
    b = Image.open(image_b).convert("RGB").resize(a.size)
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / (255 * len(stat.mean))


def visual_diff(
    file_a: bytes, file_b: bytes, suffix: str, artifacts_dir: Path, *, tolerance: float = 0.02
) -> tuple[bool, float, Path]:
    """Renders both files' first page under ``artifacts_dir`` (``a.png``, ``b.png``, kept, not a vanishing temp
    directory -- a human looking at a failure needs them to still be there) and compares them. Returns whether
    the difference is within ``tolerance``, the score itself, and ``image_b``'s own diff image (``diff.png``,
    amplified so a small but real difference is still visible by eye) for a caller to point at on failure."""
    png_a = render_first_page(file_a, suffix, artifacts_dir / "a")
    png_b = render_first_page(file_b, suffix, artifacts_dir / "b")
    score = perceptual_difference(png_a, png_b)
    a_img = Image.open(png_a).convert("RGB")
    b_img = Image.open(png_b).convert("RGB").resize(a_img.size)
    diff_path = artifacts_dir / "diff.png"
    ImageChops.difference(a_img, b_img).point(lambda v: min(255, v * 4)).save(diff_path)
    return score <= tolerance, score, diff_path
