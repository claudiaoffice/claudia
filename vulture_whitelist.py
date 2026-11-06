"""Names vulture cannot see being used. Each line says who uses it.

Everything here is public API of the kernel or a registration done by a decorator. New entries need a reason.
"""

from vulture.whitelist_utils import Whitelist

used = Whitelist()

used.failed  # Context.failed: set by Document, read by models in settle() after a rolled-back command
used.__cause__  # ReplayError chains the original exception
used._add_1_to_2  # registered as an upcaster by a decorator (tests/test_commands.py)
used.Thing  # registered with a CommandRegistry by a decorator (tests/test_commands.py)
used.Bad  # registered with a CommandRegistry by a decorator (tests/test_commands.py)

# claudia-server: routes and protocol methods are registered by decorators and called by name
used.protocol  # FastAPI route /api/protocol in create_app
used.live  # FastAPI WebSocket route in create_app
used.landing  # FastAPI route / in create_app
used._ping  # core_methods.method("ping")
used._snapshot  # core_methods.method("snapshot")
used._changes_since  # core_methods.method("changes_since")
used._history  # core_methods.method("history")
used._apply  # core_methods.method("apply")
used._save_checkpoint  # core_methods.method("save_checkpoint")
used._presence  # core_methods.method("presence")
used._lock  # core_methods.method("lock")
used._unlock  # core_methods.method("unlock")
used._new_recovery_key  # core_methods.method("new_recovery_key")
used._chat  # core_methods.method("chat")
used._log  # core_methods.method("log")
used._chat_log  # core_methods.method("chat_log")
used._add_user  # core_methods.method("add_user")
used._sheets  # computes_methods.method("sheets")
used._cells  # computes_methods.method("cells")
used._set_cells  # computes_methods.method("set_cells")
used._add_sheet  # computes_methods.method("add_sheet")
used._structure  # computes_methods.method("structure")
used._sizes  # computes_methods.method("sizes")
used._resize_lines  # computes_methods.method("resize_lines")
used._blocks  # composes_methods.method("blocks")
used._suggestions  # composes_methods.method("suggestions")
used._replace_text  # composes_methods.method("replace_text")
used._set_style  # composes_methods.method("set_style")
used._change_style  # composes_methods.method("change_style")
used._deviate_style  # composes_methods.method("deviate_style")
used._rename_style  # composes_methods.method("rename_style")
used._check_css  # composes_methods.method("check_css")
used._look  # composes_methods.method("look")
used._hold  # composes_methods.method("hold")
used._suggest  # composes_methods.method("suggest")
used._accept  # composes_methods.method("accept_suggestion")
used._reject  # composes_methods.method("reject_suggestion")
used._paragraph_by_id  # registered as an upcaster by a decorator (composes tests/test_text_documents_are_forever.py)
used._boom  # registered with a MethodTable by a decorator (tests/test_server_hub.py)
used._nan  # registered with a MethodTable by a decorator (tests/test_server_hub.py)
used._even  # registered as a parameter kind by a decorator (tests/test_server_protocol.py)
used._double  # registered with a MethodTable by a decorator (tests/test_server_protocol.py)
used.should_exit  # uvicorn.Server reads it to stop (tests/test_client_trust.py)
used.redirect_request  # urllib calls it on a redirect (tests/test_server_redirect.py)
used._test_client_calls_the_server_by_a_name_it_answers_to  # autouse fixture of packages/claudia-server/tests
used._slides  # creates_methods_with(...).method("slides")
used._slide  # creates_methods_with(...).method("slide")
used._styles  # creates_methods_with(...).method("styles")
used._add_slide  # creates_methods_with(...).method("add_slide")
used._add_object  # creates_methods_with(...).method("add_object")
used._move_object  # creates_methods_with(...).method("move_object")
used._resize_object  # creates_methods_with(...).method("resize_object")
used._set_text  # creates_methods_with(...).method("set_text")
used._remove_object  # creates_methods_with(...).method("remove_object")

# claudia-fonts: set on a fontTools table in claudia_fonts.testing, which tests use
used.macStyle  # head.macStyle is read by fontTools when the font is saved

# claudia-typeset tests: pytest reads these by name
used.pytestmark  # module variable read by pytest (skip conditions, markers such as gtk and e2e, fixtures)
used.needs_tex  # fixture requested by name with pytest.mark.usefixtures("needs_tex") in the real-engine tests

# claudia-shell-gtk (clients/linux): frameworks call these by name
used.do_activate  # Gio.Application virtual method: GLib calls it when the application is activated
used.pytest_collection_modifyitems  # pytest hook, found by name (clients/linux/tests/conftest.py)
used.do_GET  # http.server calls it by name (the stub site of clients/linux/tests/test_webpage.py)
used.log_message  # http.server calls it by name (silences the stub site's log)
used.optionxform  # configparser reads this attribute to keep the case of keys (test_identity.py)
