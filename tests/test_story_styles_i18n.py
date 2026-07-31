from __future__ import annotations

import gettext
from pathlib import Path

import polib
import pytest

from src.i18n.locale_registry import get_locale_codes, get_project_root
from src.i18n.story_styles import STORY_STYLE_KEYS


def _story_styles_po_path(locale: str) -> Path:
    return get_project_root() / "static" / "locales" / locale / "modules" / "story_styles.po"


@pytest.mark.parametrize("locale", get_locale_codes())
def test_story_style_source_translations_are_complete(locale: str):
    po = polib.pofile(str(_story_styles_po_path(locale)))
    translations = {entry.msgid: entry.msgstr for entry in po if not entry.obsolete}

    assert set(translations) == set(STORY_STYLE_KEYS)
    assert all(translations[key].strip() for key in STORY_STYLE_KEYS)


@pytest.mark.parametrize("locale", get_locale_codes())
def test_compiled_story_styles_resolve_without_key_fallback(locale: str):
    mo_path = get_project_root() / "static" / "locales" / locale / "LC_MESSAGES" / "messages.mo"
    with mo_path.open("rb") as file:
        translations = gettext.GNUTranslations(file)

    for key in STORY_STYLE_KEYS:
        assert translations.gettext(key) != key
