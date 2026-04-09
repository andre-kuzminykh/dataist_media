"""Review FSM states.
## Traceability
Feature: F001, F002
Scenarios: SC001-SC012
"""
from aiogram.fsm.state import State, StatesGroup

class ReviewStates(StatesGroup):
    waiting_for_url = State()
    parsing = State()
    choosing_title = State()
    typing_custom_title = State()
    viewing_cover_description = State()
    typing_cover_edit = State()
    generating_image = State()
    building = State()
