"""
PDF text extraction helpers.

This stays free/local by using:
  1) `pypdf` if installed (recommended)
  2) `pdfplumber` if installed
  3) `pdftotext` binary if available (Poppler)

If none are available, extraction returns an empty list.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Optional


def _extract_with_pypdf(pdf_path: Path) -> Optional[list[str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    try:
        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return pages
    except Exception:
        return None


def _extract_with_pdfplumber(pdf_path: Path) -> Optional[list[str]]:
    try:
        import pdfplumber  # type: ignore
    except Exception:
        return None

    try:
        pages: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for p in pdf.pages:
                text = p.extract_text() or ""
                pages.append(text)
        return pages
    except Exception:
        return None


def _extract_with_pdftotext(pdf_path: Path) -> Optional[list[str]]:
    exe = shutil.which("pdftotext")
    if not exe:
        return None

    # `pdftotext input.pdf -` writes text to stdout.
    try:
        proc = subprocess.run(
            [exe, "-enc", "UTF-8", "-nopgbrk", str(pdf_path), "-"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None

        # No page boundaries available in this mode; return as a single “page”.
        return [proc.stdout or ""]
    except Exception:
        return None


def _extract_with_ocr_tesseract(pdf_path: Path, *, dpi: int = 200, languages: str = "eng") -> Optional[list[str]]:
    tesseract_exe = shutil.which("tesseract")
    pdftoppm_exe = shutil.which("pdftoppm")
    if not tesseract_exe or not pdftoppm_exe:
        return None

    try:
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            prefix = tmpdir / "page"

            proc = subprocess.run(
                [pdftoppm_exe, "-r", str(int(dpi)), "-png", str(pdf_path), str(prefix)],
                check=False,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                return None

            def page_num(p: Path) -> int:
                m = re.search(r"-(\\d+)\\.png$", p.name)
                return int(m.group(1)) if m else 0

            images = sorted(tmpdir.glob("page-*.png"), key=page_num)
            if not images:
                return None

            pages: list[str] = []
            for img in images:
                proc2 = subprocess.run(
                    [tesseract_exe, str(img), "stdout", "-l", languages],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if proc2.returncode != 0:
                    pages.append("")
                else:
                    pages.append(proc2.stdout or "")

            return pages
    except Exception:
        return None


def extract_pdf_pages_text(
    pdf_path: Path,
    *,
    ocr_enabled: bool = False,
    ocr_languages: str = "eng",
    ocr_dpi: int = 200,
) -> list[str]:
    """Return a list of per-page text strings (may be empty)."""
    pages: Optional[list[str]] = None
    for fn in (_extract_with_pypdf, _extract_with_pdfplumber, _extract_with_pdftotext):
        pages = fn(pdf_path)
        if pages is not None:
            break

    pages = pages or []
    if any(p.strip() for p in pages):
        return pages

    if ocr_enabled:
        ocr_pages = _extract_with_ocr_tesseract(pdf_path, dpi=ocr_dpi, languages=ocr_languages)
        if ocr_pages is not None:
            return ocr_pages
    return []


def extraction_backend() -> str:
    """Return which backend is currently available (best-effort)."""
    try:
        import pypdf  # type: ignore  # noqa: F401

        return "pypdf"
    except Exception:
        pass

    try:
        import pdfplumber  # type: ignore  # noqa: F401

        return "pdfplumber"
    except Exception:
        pass

    if shutil.which("pdftotext"):
        return "pdftotext"

    if shutil.which("tesseract") and shutil.which("pdftoppm"):
        return "tesseract"

    return "none"
