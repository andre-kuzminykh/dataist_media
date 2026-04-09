"""
Global test fixtures for the arXiv editorial pipeline.

Provides reusable sample data (HTML snippets, parsed article dicts,
editorial dicts) and a tmp_path-based fixture for publisher tests.

No database or external services are required.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Sample arXiv HTML
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_arxiv_html() -> str:
    """Minimal arXiv HTML page containing article, abstract, and figures."""
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Test Paper</title></head>
<body>
<article>
  <div class="ltx_abstract">
    <h2>Abstract</h2>
    <p>This paper introduces a novel method for training transformers.</p>
  </div>
  <section>
    <h2>1. Introduction</h2>
    <p>Deep learning has revolutionised natural language processing.</p>
  </section>
  <section>
    <h2>2. Method</h2>
    <p>We propose a new attention mechanism called MegaAttention.</p>
    <figure id="fig1">
      <img src="/html/2301.12345v1/extracted/img1.png"
           alt="Architecture diagram" />
      <figcaption>
        <span class="ltx_tag ltx_tag_figure">Figure 1:</span>
        Architecture overview of MegaAttention.
      </figcaption>
    </figure>
  </section>
  <section>
    <h2>3. Results</h2>
    <p>Our model achieves state-of-the-art on all benchmarks.</p>
    <figure id="fig2">
      <img src="/html/2301.12345v1/extracted/img2.png"
           alt="Benchmark results" />
      <figcaption>
        <span class="ltx_tag ltx_tag_figure">Figure 2:</span>
        Benchmark comparison table.
      </figcaption>
    </figure>
  </section>
</article>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Parsed article dict (output of ArxivParserService.parse_article)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_parsed_article() -> dict:
    """Parsed article dict matching ParsedArticleSchema structure."""
    return {
        "abstract": "This paper introduces a novel method for training transformers.",
        "article": (
            "1. Introduction\n"
            "Deep learning has revolutionised natural language processing.\n"
            "2. Method\n"
            "We propose a new attention mechanism called MegaAttention.\n"
            "3. Results\n"
            "Our model achieves state-of-the-art on all benchmarks."
        ),
        "figures": [
            {
                "url": "https://arxiv.org/html/2301.12345v1/extracted/img1.png",
                "filename": "img1.png",
                "caption": "Figure 1: Architecture overview of MegaAttention.",
                "figure_id": "fig1",
                "figure_label": "Figure 1:",
                "source_base": "/html/2301.12345v1",
            },
            {
                "url": "https://arxiv.org/html/2301.12345v1/extracted/img2.png",
                "filename": "img2.png",
                "caption": "Figure 2: Benchmark comparison table.",
                "figure_id": "fig2",
                "figure_label": "Figure 2:",
                "source_base": "/html/2301.12345v1",
            },
        ],
        "source_url": "https://arxiv.org/html/2301.12345v1",
        "html_url": "https://arxiv.org/html/2301.12345v1",
    }


# ---------------------------------------------------------------------------
# Editorial article dict (output of ContentGeneratorService)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_editorial() -> dict:
    """Editorial article dict matching EditorialArticleSchema structure."""
    return {
        "title": "MegaAttention: новый прорыв в обработке текста",
        "subtitle": "Исследователи предлагают механизм внимания нового поколения",
        "short_intro": (
            "Группа исследователей представила MegaAttention — механизм, "
            "который превосходит все существующие подходы."
        ),
        "article_body": (
            "## Введение\n\n"
            "Глубокое обучение изменило обработку естественного языка.\n\n"
            "## Метод\n\n"
            "MegaAttention использует разреженные матрицы для ускорения.\n\n"
            "## Результаты\n\n"
            "Модель достигает state-of-the-art на всех бенчмарках."
        ),
        "links": {
            "github_url": "https://github.com/example/mega-attention",
            "huggingface_url": "",
            "project_url": "",
            "demo_url": "",
        },
    }


# ---------------------------------------------------------------------------
# Publisher tmp_path fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def publish_dir(tmp_path):
    """Provide a temporary directory simulating ASSET_STORAGE_PATH."""
    return tmp_path / "published"
