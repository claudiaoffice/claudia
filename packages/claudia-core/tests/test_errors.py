"""Every kernel error carries a stable, machine-readable ``code`` (E5.7 groundwork, D31): see errors.py."""

from claudia_core import (
    KernelError,
    MissingUpcaster,
    RedactionError,
    RegionHeld,
    ReplayError,
    RevisionMismatch,
    SchemaTooNew,
    StaleEdit,
    UndoConflict,
    UndoRefused,
    UnknownCommand,
)

SUBCLASSES = (
    UnknownCommand,
    SchemaTooNew,
    MissingUpcaster,
    RevisionMismatch,
    RegionHeld,
    StaleEdit,
    UndoRefused,
    UndoConflict,
    RedactionError,
    ReplayError,
)


def test_every_subclass_has_its_own_non_empty_code():
    for cls in SUBCLASSES:
        assert isinstance(cls.code, str) and cls.code, f"{cls.__name__} has no code"


def test_codes_are_unique_across_the_hierarchy():
    codes = [cls.code for cls in SUBCLASSES]
    assert len(codes) == len(set(codes)), f"duplicate codes: {codes}"


def test_a_subclass_that_sets_no_code_would_inherit_the_base_ones():
    # documents the fallback a future, as yet unwritten, KernelError subclass would get
    assert KernelError.code == "kernel_error"


def test_undo_refused_has_its_own_code_though_it_is_a_region_held():
    # UndoRefused is mechanically a RegionHeld (same lock), but a different thing to say to a person
    assert UndoRefused.code != RegionHeld.code


def test_code_is_a_class_attribute_not_part_of_init():
    # adding or reading `code` must never change a class's public __init__ signature (docs/versioning.md)
    sentinel = object()
    held = RegionHeld([("ann", sentinel)])
    assert held.code == "region_held"
    assert held.holders == [("ann", sentinel)]  # the structured data a renderer would use alongside the code


def test_missing_upcaster_now_carries_its_structured_data_too():
    error = MissingUpcaster("SET_VALUE", 3)
    assert error.code == "missing_upcaster"
    assert (error.kind, error.schema) == ("SET_VALUE", 3)


def test_str_of_an_error_is_unchanged_english_prose():
    # the baked message stays as the development/debug default; only `code` is new
    error = UnknownCommand("FROB")
    assert "FROB" in str(error)
    assert error.kind == "FROB"
