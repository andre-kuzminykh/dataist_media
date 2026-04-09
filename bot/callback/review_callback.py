"""Callback data for review flow.
## Traceability
Feature: F001, F002
"""
from aiogram.filters.callback_data import CallbackData


class TitleCallback(CallbackData, prefix="ttl"):
    action: str  # "pick" or "custom"
    index: int = 0  # 1-10 for pick


class CoverCallback(CallbackData, prefix="cvr"):
    action: str  # "generate", "custom", "approve", "edit_after_gen"


class LangCallback(CallbackData, prefix="lng"):
    show: str  # "ru" or "en" — which version to show next
