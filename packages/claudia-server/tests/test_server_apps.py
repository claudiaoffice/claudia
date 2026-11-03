"""Which method table and which stand-in assistant a model gets."""

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_core.testing import ListModel
from claudia_server.apps import methods_for, stand_in_assistant_for
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.protocol import core_methods
from claudia_server.standin import ScriptedEngine
from claudia_server.standin_text import TextEngine


def test_each_app_gets_its_own_methods_and_unknown_apps_get_the_core():
    assert methods_for(WorkbookModel) is computes_methods
    assert methods_for(TextModel) is composes_methods
    assert methods_for(ListModel) is core_methods


def test_workbooks_and_texts_get_their_own_stand_in_and_others_none():
    assert stand_in_assistant_for(ListModel) is None
    engines = {type(stand_in_assistant_for(m)().engine) for m in (WorkbookModel, TextModel)}
    assert engines == {ScriptedEngine, TextEngine}
