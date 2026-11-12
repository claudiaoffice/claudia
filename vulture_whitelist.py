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
used.font_file  # FastAPI route /api/fonts/{name} in font_router (fonts.py)
# admin_api.py: the /api/admin/* routes, registered the same way
used.setup  # POST /api/admin/setup
used.logout  # POST /api/admin/logout
used.add_admin  # POST /api/admin/admins
used.remove_admin  # DELETE /api/admin/admins/{name}
used.set_max_documents  # PUT /api/admin/settings/max-documents
used.reveal_access_secret  # GET /api/admin/settings/access-secret
used.put_access_secret  # PUT /api/admin/settings/access-secret
used.rotate_access_secret  # POST /api/admin/settings/access-secret/rotate
used.set_ai  # PUT /api/admin/settings/ai
used.set_typeset  # PUT /api/admin/settings/typeset
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
used._roster  # core_methods.method("roster")
used._leave  # core_methods.method("leave")
used._propose_owner  # core_methods.method("propose_owner")
used._accept_owner  # core_methods.method("accept_owner")
used._delete_document  # core_methods.method("delete_document")
used._export_content  # core_methods.method("export_content")
used._export_office  # composes/computes/creates methods.method("export_office") (D212)
used._help_search  # core_methods.method("help_search") (E13.1, E13.3)
used._help_topic  # core_methods.method("help_topic") (E13.1, E13.3)
used._sheets  # computes_methods.method("sheets")
used._cells  # computes_methods.method("cells")
used._set_cells  # computes_methods.method("set_cells")
used._add_sheet  # computes_methods.method("add_sheet")
used._structure  # computes_methods.method("structure")
used._sizes  # computes_methods.method("sizes")
used._resize_lines  # computes_methods.method("resize_lines")
used._function_help  # computes_methods.method("function_help") (E13.5, E13.6)
used._diagrams  # computes_methods.method("diagrams") (E6.6)
used._charts  # computes_methods.method("charts") (E6.6)
used._chart_figure  # computes_methods.method("chart_figure") (E6.6)
used._define_diagram  # computes_methods.method("define_diagram") (E6.6)
used._update_diagram  # computes_methods.method("update_diagram") (E6.6)
used._forget_diagram  # computes_methods.method("forget_diagram") (E6.6)
used._add_diagram_object  # computes_methods.method("add_diagram_object") (E6.6)
used._add_chart  # computes_methods.method("add_chart") (E6.6)
used._remove_chart  # computes_methods.method("remove_chart") (E6.6)
used._define_name  # computes_methods.method("define_name") (E6.5)
used._rename_name  # computes_methods.method("rename_name") (E6.5)
used._remove_name  # computes_methods.method("remove_name") (E6.5)
used._sql_preview  # computes_methods.method("sql_preview") (E6.5)
used._define_sql  # computes_methods.method("define_sql") (E6.5)
used._blocks  # composes_methods.method("blocks")
used._suggestions  # composes_methods.method("suggestions")
used._replace_text  # composes_methods.method("replace_text")
used._set_style  # composes_methods.method("set_style")
used._set_page  # composes_methods.method("set_page")
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
used._echo  # registered with a MethodTable by a decorator (tests/test_server_protocol.py, E5.7/D31 locale test)
used.should_exit  # uvicorn.Server reads it to stop (tests/test_client_trust.py)
used.redirect_request  # urllib calls it on a redirect (tests/test_server_redirect.py)
used._test_client_calls_the_server_by_a_name_it_answers_to  # autouse fixture of packages/claudia-server/tests
used._restore_active_translation  # autouse fixture of clients/linux/tests/test_i18n.py (D160)
used._slides  # creates_methods_with(...).method("slides")
used._peek_line  # core_methods.method("peek_line")
used._restore_policy  # core_methods.method("restore_policy")
used._set_restore_policy  # core_methods.method("set_restore_policy")
used._propose_restore  # core_methods.method("propose_restore")
used._propose_switch  # core_methods.method("propose_switch")
used._answer_restore  # core_methods.method("answer_restore")
used._withdraw_restore  # core_methods.method("withdraw_restore")
used._discard_side_history  # core_methods.method("discard_side_history")
used._slide  # creates_methods_with(...).method("slide")
used._styles  # add_style_methods(...).method("styles")
# styles.py: the style and palette methods every app shares, registered the same way (E1.10, D200)
used._palette_method  # add_style_methods(...).method("palette")
used._set_role  # add_style_methods(...).method("set_role")
used._replace_palette  # add_style_methods(...).method("replace_palette")
used._set_object_style  # add_style_methods(...).method("set_object_style")
used._deviate_object_style  # add_style_methods(...).method("deviate_object_style")
used._set_paragraph_style  # add_style_methods(...).method("set_paragraph_style")
used._style_model  # add_target_methods(...).method("style_model")
used._apply_style  # add_target_methods(...).method("apply_style")
used._deviate  # add_target_methods(...).method("deviate")
used._style_uses  # add_target_methods(...).method("style_uses")
used._cell_styles  # computes_methods.method("cell_styles")
used._cell_style_at  # computes_methods.method("cell_style_at")
used._clear_cell_style  # computes_methods.method("clear_cell_style")
used._add_slide  # creates_methods_with(...).method("add_slide")
used._add_object  # creates_methods_with(...).method("add_object")
used._move_object  # creates_methods_with(...).method("move_object")
used._resize_object  # creates_methods_with(...).method("resize_object")
used._set_text  # creates_methods_with(...).method("set_text")
used._set_snap  # creates_methods_with(...).method("set_snap")
used._remove_object  # creates_methods_with(...).method("remove_object")
used._images  # creates_methods_with(...).method("images")
used._object_gets_image_fields  # registered as an upcaster by a decorator (claudia_creates AddObject schema 1 -> 2)
used._objects  # computes_methods.method("objects")
used._object_gets_snap_field  # registered as an upcaster by a decorator (claudia_creates AddObject schema 2 -> 3)

# claudia-creates-io: set-only properties of python-pptx's own objects (never read back by our code, only by
# python-pptx itself when the file is saved)
used.rgb  # RGBColor set on a run's/shape's .color or .fore_color (claudia_creates_io.pptx._style_text/_style_shape)
used.slide_width  # Presentation.slide_width, set once per deck (claudia_creates_io.pptx.slides_to_pptx)
used.slide_height  # Presentation.slide_height, set once per deck (claudia_creates_io.pptx.slides_to_pptx)

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
used.protocol_version  # http.server reads it to answer HTTP/1.1 (stub server, clients/linux/tests/test_connection.py)
used.menu_file  # Gtk.Template children of window.ui: GTK fills them by id; window.py's _attach_menus reads them by name
used.menu_edit  # (same)
used.menu_format  # (same)
used.menu_view  # (same)
used.menu_tools  # (same)
used.menu_config  # (same)
used.menu_help  # (same)

# claudia-odf-io
used.StartElementHandler  # expat calls the handlers assigned to these attributes (splice.py's `_spans`)
used.EndElementHandler  # (same)
