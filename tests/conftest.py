"""Shared test fixtures: tiny temporary PDFs created with PyMuPDF."""
from __future__ import annotations

import os
import sys

import pytest
import pymupdf


# Make the app package importable when running pytest from the project root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_pdf(path: str, page_labels):
    doc = pymupdf.open()
    for label in page_labels:
        page = doc.new_page(width=400, height=500)
        page.insert_text((50, 50), str(label), fontsize=20, fontname="helv")
    doc.save(path)
    doc.close()


@pytest.fixture
def small_pdf(tmp_path):
    p = tmp_path / "small.pdf"
    _make_pdf(str(p), ["A", "B", "C"])
    return str(p)


@pytest.fixture
def two_page_pdf(tmp_path):
    p = tmp_path / "two.pdf"
    _make_pdf(str(p), ["X", "Y"])
    return str(p)


@pytest.fixture
def single_page_pdf(tmp_path):
    p = tmp_path / "single.pdf"
    _make_pdf(str(p), ["only"])
    return str(p)
