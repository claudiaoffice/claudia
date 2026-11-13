"""The language of a text (D915): :func:`~claudia_core.normalize_language` and :class:`~claudia_core.SetLanguage`,
which moved to the kernel so that presentations have one too (D917). Re-exported here."""

from claudia_core.language import MAX_LENGTH, LanguageChanged, LanguageError, SetLanguage, normalize_language

__all__ = ["MAX_LENGTH", "LanguageChanged", "LanguageError", "SetLanguage", "normalize_language"]
