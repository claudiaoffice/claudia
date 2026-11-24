"""``Person`` (``conftest.py``), what the steps of the scenarios drive: it must not depend on how fast the page is."""

from __future__ import annotations

from conftest import World

#: The server's list of documents and kinds reaches the front page only half a second after the password is typed, as
#: it can on a busy machine (PROC-53). The page itself is not changed: only the answer to its question comes late.
LIST_LATE = """
const fetchNow = window.fetch.bind(window)
window.fetch = (input, init) => {
  const answer = fetchNow(input, init)
  if (!String(input).endsWith('/api/docs')) return answer
  return new Promise((resolve) => document.addEventListener('input', (typed) => {
    if (typed.target.name === 'password') setTimeout(() => resolve(answer), 500)
  }))
}
"""


def test_a_person_makes_a_document_of_her_kind_when_the_list_of_kinds_comes_late(suite_world: World):
    """On a server of several apps the front page offers the kinds of document once the server's list has come (D430).
    ``create`` looked for that choice as soon as the form was filled, found nothing yet, pressed Create without a kind
    and waited 30 s for a recovery key that never came: the page said "Choose Table, Text or Slides first."."""
    ann = suite_world.join("Ann", "creates")
    ann.context.add_init_script(LIST_LATE)
    ann.create()  # waits until the presentation is open
