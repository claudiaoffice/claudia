"""Which method table a model gets."""

from claudia_computes import WorkbookModel
from claudia_core.testing import ListModel
from claudia_server.apps import methods_for
from claudia_server.computes import computes_methods
from claudia_server.protocol import core_methods


def test_each_app_gets_its_own_methods_and_unknown_apps_get_the_core():
    assert methods_for(WorkbookModel) is computes_methods
    assert methods_for(ListModel) is core_methods
