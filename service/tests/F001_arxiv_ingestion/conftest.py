"""
Feature-specific fixtures for F001 — arXiv Article Ingestion & Parsing.

Provides canonical arXiv URLs and HTML fragments used by SC001–SC004.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# URL fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid_arxiv_abs_url() -> str:
    """A valid arXiv /abs/ URL without version suffix."""
    return "https://arxiv.org/abs/2301.12345"


@pytest.fixture()
def valid_arxiv_html_url() -> str:
    """A valid arXiv /html/ URL with version suffix."""
    return "https://arxiv.org/html/2301.12345v1"


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_html_with_figures() -> str:
    """Full arXiv-style HTML containing <article>, abstract, and figures."""
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Test Paper</title></head>
<body>
<article>
  <div class="ltx_abstract">
    <h2>Abstract</h2>
    <p>We present a novel approach to large-scale optimisation.</p>
  </div>
  <section>
    <h2>1. Introduction</h2>
    <p>Optimisation is a cornerstone of machine learning.</p>
  </section>
  <figure id="fig1">
    <img src="/html/2301.12345v1/extracted/figure1.png"
         alt="Loss landscape" />
    <figcaption>
      <span class="ltx_tag ltx_tag_figure">Figure 1:</span>
      Loss landscape visualisation.
    </figcaption>
  </figure>
  <figure id="fig2">
    <img src="https://arxiv.org/html/2301.12345v1/extracted/figure2.png"
         alt="Convergence plot" />
    <figcaption>
      <span class="ltx_tag ltx_tag_figure">Figure 2:</span>
      Convergence comparison.
    </figcaption>
  </figure>
</article>
</body>
</html>"""


@pytest.fixture()
def sample_html_without_figures() -> str:
    """arXiv-style HTML with <article> and abstract but no <figure> tags."""
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Theory Paper</title></head>
<body>
<article>
  <div class="ltx_abstract">
    <h2>Abstract</h2>
    <p>We prove a new bound on convergence rates.</p>
  </div>
  <section>
    <h2>1. Proof</h2>
    <p>Consider the following theorem.</p>
  </section>
</article>
</body>
</html>"""


@pytest.fixture()
def sample_html_without_article_tag() -> str:
    """HTML that lacks an <article> tag entirely (fallback to <body>)."""
    return """<!DOCTYPE html>
<html lang="en">
<head><title>Minimal Page</title></head>
<body>
  <p>This page has no article tag but has body content.</p>
  <p>Second paragraph of the body.</p>
</body>
</html>"""


@pytest.fixture()
def sample_html_without_abstract() -> str:
    """HTML with <article> but no abstract div/blockquote."""
    return """<!DOCTYPE html>
<html lang="en">
<head><title>No Abstract Paper</title></head>
<body>
<article>
  <section>
    <h2>1. Introduction</h2>
    <p>We skip the abstract and jump right in.</p>
  </section>
</article>
</body>
</html>"""
