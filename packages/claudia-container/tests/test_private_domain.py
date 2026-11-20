"""A person's private domain (D1265): a chain of her own that only her slot's key opens, deleted with her."""

import zipfile

import pytest

from claudia_container import (
    TamperedDocument,
    add_user,
    change_password,
    create_document,
    leave_document,
    read_people,
    read_private,
    recover_access,
    remove_user,
    unlock,
    write_private,
)
from claudia_container.container import transfer_owner
from claudia_container.crypto import KdfParams
from claudia_container.slots import Role, new_private_domain, new_recovery_key

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANNA, BERT, CORA = ("Annabelle", "Correct-Horse-9"), ("Bertram", "Battery-Staple-7"), ("Cornelia", "Purple-Monkey-5")


@pytest.fixture
def path(tmp_path):
    return tmp_path / "plan.claudia"


@pytest.fixture
def recovery():
    return new_recovery_key()


@pytest.fixture
def owner(path, recovery):
    first = create_document(
        path, name="plan", app="computes", owner=ANNA[0], password=ANNA[1], kdf=CHEAP, recovery_key=recovery
    )
    add_user(path, first.keys, BERT[0], BERT[1], Role.EDITOR)
    add_user(path, first.keys, CORA[0], CORA[1], Role.VIEWER)
    return first


def names(path) -> set[str]:
    return set(zipfile.ZipFile(path).namelist())


def folder(private) -> set[str]:
    return {f"private/{private.id}/000001.blk", f"private/{private.id}/head.bin"}


def test_everybody_has_a_domain_and_an_empty_one_looks_like_any_other(path, owner):
    people = read_people(path, owner.keys)
    assert all(p.private_id for p in people) and len({p.private_id for p in people}) == 3
    sizes = {n.split("/")[1]: len(zipfile.ZipFile(path).read(n)) for n in names(path) if n.endswith("000001.blk")}
    assert len(sizes) == 3 and len(set(sizes.values())) == 1  # the same size: nobody can see who has something in it


def test_what_is_written_is_read_back_in_order(path, owner):
    write_private(path, owner.private, [b"first note", b"second note"])
    assert read_private(path, owner.private) == [b"first note", b"second note"]
    write_private(path, owner.private, [b"only this"])
    assert read_private(path, owner.private) == [b"only this"]


def test_a_domain_that_holds_nothing_reads_as_nothing(path, owner):
    assert read_private(path, owner.private) == []


def test_it_survives_a_login_and_a_password_change(path, owner):
    bert = unlock(path, *BERT)
    write_private(path, bert.private, [b"bert's note"])
    assert change_password(path, BERT[0], BERT[1], "Fresh-Walnut-8")
    again = unlock(path, BERT[0], "Fresh-Walnut-8")
    assert again.private == bert.private and again.private_key == bert.private_key
    assert read_private(path, again.private) == [b"bert's note"]


def test_nobody_elses_key_opens_it(path, owner):
    write_private(path, owner.private, [b"secret"])
    bert = unlock(path, *BERT)
    from claudia_container.slots import PrivateDomain

    with pytest.raises(TamperedDocument):
        read_private(path, PrivateDomain(owner.private.id, bert.private.key))
    with pytest.raises(TamperedDocument):
        read_private(path, PrivateDomain(bert.private.id, owner.private.key))


def test_a_domain_the_file_does_not_have_does_not_open(path, owner):
    with pytest.raises(TamperedDocument, match="not in the file"):
        read_private(path, new_private_domain())
    with pytest.raises(TamperedDocument):
        write_private(path, new_private_domain(), [b"x"])


def test_a_block_that_was_removed_or_added_is_noticed(path, owner):
    write_private(path, owner.private, [b"x" * 100])
    block = f"private/{owner.private.id}/000001.blk"
    with zipfile.ZipFile(path) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    for change in (lambda e: e.pop(block), lambda e: e.__setitem__(block[:-7] + "000002.blk", e[block])):
        broken = dict(entries)
        change(broken)
        with zipfile.ZipFile(path, "w") as z:
            for n, d in broken.items():
                z.writestr(n, d, compress_type=zipfile.ZIP_STORED)
        with pytest.raises(TamperedDocument):
            read_private(path, owner.private)
        with zipfile.ZipFile(path, "w") as z:
            for n, d in entries.items():
                z.writestr(n, d, compress_type=zipfile.ZIP_STORED)


def test_the_recovery_key_does_not_open_a_domain_and_gives_a_new_one(path, owner, recovery):
    write_private(path, owner.private, [b"annas notes"])
    old_files = folder(owner.private)
    assert old_files <= names(path)
    person = recover_access(path, recovery, ANNA[0], "Brand-New-Pass-4")
    renewed = unlock(path, ANNA[0], "Brand-New-Pass-4")
    assert renewed.private.id != owner.private.id and person.private_id == renewed.private.id
    assert not old_files & names(path)  # what was in it is gone
    assert read_private(path, renewed.private) == []
    assert renewed.private_key != owner.private_key


def test_a_person_who_leaves_takes_her_domain_with_her(path, owner):
    bert = unlock(path, *BERT)
    write_private(path, bert.private, [b"bert's note"])
    assert leave_document(path, *BERT)
    assert not any(n.startswith(f"private/{bert.private.id}/") for n in names(path))


def test_a_plain_removal_deletes_the_domain_too(path, owner):
    cora = unlock(path, *CORA)
    remove_user(path, owner.keys, CORA[0])
    assert not any(n.startswith(f"private/{cora.private.id}/") for n in names(path))
    assert any(n.startswith(f"private/{owner.private.id}/") for n in names(path))


def test_a_handover_of_ownership_keeps_both_domains(path, owner):
    bert = unlock(path, *BERT)
    write_private(path, bert.private, [b"b"])
    write_private(path, owner.private, [b"a"])
    assert transfer_owner(
        path, old_owner=ANNA[0], old_owner_password=ANNA[1], new_owner=BERT[0], new_owner_password=BERT[1]
    )
    assert read_private(path, unlock(path, *BERT).private) == [b"b"]
    assert read_private(path, unlock(path, *ANNA).private) == [b"a"]
