"""FSM states for the review widget.

## Traceability
Feature: F001
Scenarios: SC001, SC002
"""

from aiogram.fsm.state import State, StatesGroup


class ReviewStates(StatesGroup):
    """States for the arXiv review conversation flow."""

    waiting_for_url = State()
    processing = State()
