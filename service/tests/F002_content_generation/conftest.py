"""
Feature-specific fixtures for F002 — Editorial Content & HTML Generation.

Provides sample editorial article dicts and parsed article dicts used
by SC005, SC006, SC008.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def sample_editorial_article() -> dict:
    """Sample editorial article dict as returned by ContentGeneratorService."""
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


@pytest.fixture()
def sample_parsed_article_with_figures() -> dict:
    """Parsed article dict with abstract, article text, and figures."""
    return {
        "abstract": "This paper introduces a novel method for training transformers.",
        "article": (
            "Deep learning has revolutionised NLP. "
            "We propose MegaAttention, a new attention mechanism. "
            "Our model achieves state-of-the-art on all benchmarks."
        ),
        "figures": [
            {
                "url": "https://arxiv.org/html/2301.12345v1/extracted/img1.png",
                "filename": "img1.png",
                "caption": "Figure 1: Architecture overview.",
                "figure_id": "fig1",
                "figure_label": "Figure 1:",
                "source_base": "/html/2301.12345v1",
            },
        ],
        "source_url": "https://arxiv.org/html/2301.12345v1",
        "html_url": "https://arxiv.org/html/2301.12345v1",
    }
