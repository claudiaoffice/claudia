"""Deleting and hiding a style: the steps of ``claudiaoffice-log/specs/composes/deleting-a-style.feature`` (E1.10).

Steps work on what a person sees and does: the right-click style menu, the style button in the bar (it names the style
of the paragraph the caret is in), Format ▸ All Styles…, its rows and the Delete dialog. Whether a paragraph is bold or
italic is read from how the browser draws it. Nothing here calls the server or reads the app's state.
"""

from __future__ import annotations

import re

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/composes/deleting-a-style.feature")

PARAGRAPHS = "[data-testid=text] [data-paragraph]"
LIST = "[data-testid=styles-list]"
DIALOG = "[data-testid=style-delete]"


# -- what the steps share ----------------------------------------------------------------------------------------------


def paragraph(page, words: str):
    found = page.locator(PARAGRAPHS).filter(has_text=words)
    assert found.count() == 1, f"one paragraph should read “{words}”, there are {found.count()}"
    assert found.is_visible(), f"“{words}” is not visible"
    return found


def row(page, name: str):
    """The row of All styles that shows the style called ``name`` (exactly)."""
    exact = re.compile(rf"^{re.escape(name)}$")
    return page.locator(f"{LIST} li[data-style]").filter(has=page.locator(".sample", has_text=exact))


def close_dialogs(page) -> None:
    """Close what is open over the text (All styles, a menu), as a person would: with Escape."""
    for _ in range(3):
        if not page.locator(".modal").count() and not page.locator("[data-testid=style-menu]").count():
            return
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)


def write(page, words: str) -> None:
    """Write ``words`` as a paragraph of its own at the end of the text."""
    close_dialogs(page)
    text = page.locator("[data-testid=text]")
    if page.locator(PARAGRAPHS).filter(has_text=re.compile(r"\S")).count():
        page.locator(PARAGRAPHS).last.click()
        page.keyboard.press("Control+End")
        page.keyboard.press("Enter")
    else:
        text.click()
    page.keyboard.type(words)
    page.wait_for_function(
        "([sel, words]) => [...document.querySelectorAll(sel)].some(e => e.textContent.trim() === words)",
        arg=[PARAGRAPHS, words],
    )


def give_own_style(page, words: str, name: str, button: str) -> None:
    """Change the look of the paragraph ``words`` in its style menu (``bold`` or ``italic``), which makes a style of the
    document's own for it, and give that style the name it asks for."""
    target = paragraph(page, words)
    target.click()
    target.click(button="right")
    page.wait_for_selector("[data-testid=style-menu]")
    page.click(f"[data-testid={button}]")
    page.wait_for_selector("[data-testid=name-invitation]")
    page.fill("[data-testid=name-invitation] input", name)
    page.click("[data-testid=name-invitation] button[type=submit]")
    page.wait_for_selector("[data-testid=name-invitation]", state="detached")
    close_dialogs(page)


def choose_style(page, words: str, name: str) -> None:
    """Give the paragraph ``words`` the style ``name`` from the style button in the bar."""
    paragraph(page, words).click()
    page.click("[data-testid=style-button]")
    exact = re.compile(rf"^{re.escape(name)}$")
    page.locator(".style-list .style-opt").filter(has=page.locator(".name", has_text=exact)).click()
    page.wait_for_function(
        "name => document.querySelector('[data-testid=style-button]').textContent.includes(name)", arg=name
    )


def look(page, words: str) -> dict:
    return paragraph(page, words).evaluate(
        """e => {
          const c = getComputedStyle(e)
          return { weight: Number(c.fontWeight), italic: c.fontStyle === 'italic' }
        }"""
    )


def all_styles(page) -> None:
    close_dialogs(page)
    page.click('.menus .title:text-is("Format")')
    page.click('.menus .drop [role=menuitem]:has-text("All Styles")')
    page.wait_for_selector(LIST)


def ask_to_delete(page, name: str) -> None:
    all_styles(page)
    row(page, name).locator("[data-delete]").click()
    page.wait_for_selector(DIALOG)


def choose_rebase(page, target: str) -> None:
    page.check("[data-testid=way-rebase]")
    page.select_option("[data-testid=rebase-target]", label=target)


def delete(page) -> None:
    page.click("[data-testid=delete-style]")
    page.wait_for_selector(DIALOG, state="detached")
    page.wait_for_selector("[data-testid=deleted]")


# -- Given -------------------------------------------------------------------------------------------------------------


@given(parsers.parse('a new composes document "{name}" in which I am Ann, an owner'))
def _new_document(world, name):  # noqa: ARG001 - the name is for the reader; every scenario gets a document of its own
    world.join("Ann").create()


@given(parsers.parse('the paragraph "{words}" has a style of my own, "{name}", that makes it bold'))
def _own_bold_style(world, words, name):
    write(world.ann.page, words)
    give_own_style(world.ann.page, words, name, "bold")


ITALIC_ON = 'the paragraph "{words}" has a style of my own, "{name}", based on "{base}", that makes it italic'


@given(parsers.parse(ITALIC_ON))
def _own_italic_style_on(world, words, name, base):
    page = world.ann.page
    write(page, words)
    choose_style(page, words, base)
    give_own_style(page, words, name, "italic")


@given(parsers.parse('I have deleted "{name}" by assigning "{target}"'))
def _deleted_by_assigning(world, name, target):
    page = world.ann.page
    ask_to_delete(page, name)
    page.select_option("[data-testid=assign-target]", label=target)
    delete(page)


# -- When --------------------------------------------------------------------------------------------------------------


@when(parsers.parse('I ask to delete "{name}" in All styles'))
def _ask_to_delete(world, name):
    ask_to_delete(world.ann.page, name)


@when(parsers.parse('I choose to re-base it on "{target}"'))
def _choose_rebase(world, target):
    choose_rebase(world.ann.page, target)


@when("I delete the style")
def _delete(world):
    delete(world.ann.page)


@when(parsers.parse('I delete "{name}" by re-basing it on "{target}"'))
def _delete_by_rebasing(world, name, target):
    page = world.ann.page
    ask_to_delete(page, name)
    choose_rebase(page, target)
    delete(page)


@when("I choose Undo in the message that says it was deleted")
def _undo(world):
    world.ann.page.click("[data-testid=undo-delete]")


@when("I open All styles")
def _open_all_styles(world):
    all_styles(world.ann.page)


@when(parsers.parse('I hide "{name}"'))
def _hide(world, name):
    row(world.ann.page, name).locator("[data-hide]").click()


@when("I choose to show hidden styles")
def _show_hidden(world):
    world.ann.page.check("[data-testid=show-hidden]")


@when(parsers.parse('I show "{name}"'))
def _show(world, name):
    row(world.ann.page, name).locator("[data-hide]").click()


# -- Then --------------------------------------------------------------------------------------------------------------


@then(parsers.parse('the way chosen is "Assign another style", with "{target}" to take its place'))
def _assign_chosen(world, target):
    page = world.ann.page
    assert page.is_checked("[data-testid=way-assign]")
    chosen = page.eval_on_selector("[data-testid=assign-target]", "s => s.selectedOptions[0].textContent.trim()")
    assert chosen == target


@then(parsers.parse("I am told that {count:d} paragraph will look different"))
def _told_what_changes(world, count):
    said = world.ann.page.locator("[data-testid=looks-change]")
    assert said.is_visible()
    assert re.search(rf"Will look different: {count} paragraph\b", said.inner_text()), said.inner_text()


@then("I am not told that anything will look different")
def _told_nothing_changes(world):
    assert world.ann.page.locator("[data-testid=looks-change]").count() == 0


@then(parsers.re(r'"(?P<words>[^"]+)" has the style "(?P<name>[^"]+)" and is (?P<how>not bold|bold and italic|bold)$'))
def _has_style(world, words, name, how):
    page = world.ann.page
    close_dialogs(page)
    paragraph(page, words).click()
    page.wait_for_function(
        "name => document.querySelector('[data-testid=style-button]').textContent.trim().startsWith(name)", arg=name
    )
    assert page.inner_text("[data-testid=style-button]").replace("▾", "").strip() == name
    seen = look(page, words)
    assert (seen["weight"] >= 600) == (how != "not bold"), seen
    assert seen["italic"] == (how == "bold and italic"), seen


@then(parsers.parse('"{name}" is no longer among the styles'))
def _not_among(world, name):
    row(world.ann.page, name).wait_for(state="detached")


@then(parsers.parse('"{name}" is among the styles again'))
def _among_again(world, name):
    page = world.ann.page
    if not page.locator(LIST).count():
        all_styles(page)
    row(page, name).wait_for(state="visible")


@then(parsers.parse('"{name}" waits for a name'))
def _waits_for_a_name(world, name):
    page = world.ann.page
    all_styles(page)
    assert row(page, name).locator(".flag", has_text="to name").is_visible()


@then(parsers.parse('"{own}" offers Delete and "{builtin}" offers only Hide'))
def _what_rows_offer(world, own, builtin):
    page = world.ann.page
    assert row(page, own).locator("[data-delete]").is_visible()
    assert row(page, builtin).locator("[data-delete]").count() == 0
    assert row(page, builtin).locator("[data-hide]").is_visible()


@then(parsers.parse('"{name}" is among the styles again, marked hidden'))
def _among_hidden(world, name):
    found = row(world.ann.page, name)
    found.wait_for(state="visible")
    assert found.locator(".hiddenflag").is_visible()
