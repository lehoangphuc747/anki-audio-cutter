# -*- coding: utf-8 -*-
"""
Anki interop module managing note addition/deletion, database operations, and configurations.
"""
import os
from typing import Optional

from aqt import mw

# Addon root path
ADDON_ROOT = os.path.dirname(__file__)


def _config() -> dict:
    addon_name = os.path.basename(ADDON_ROOT)
    return mw.addonManager.getConfig(addon_name) or {}


def _save_config(cfg: dict) -> None:
    addon_name = os.path.basename(ADDON_ROOT)
    mw.addonManager.writeConfig(addon_name, cfg)


def _add_note(
    deck_name: Optional[str],
    notetype_name: Optional[str],
    fields: dict,
    audio_filename: str,
    audio_field_name: str,
    tags: str,
) -> Optional[int]:
    col = mw.col
    if col is None:
        return None
    model = (
        col.models.by_name(notetype_name) if notetype_name else col.models.current()
    )
    if model is None:
        return None
    did = col.decks.id(deck_name) if deck_name else col.decks.get_current_id()

    note = col.new_note(model)
    sound_tag = f"[sound:{audio_filename}]"
    field_names = [f["name"] for f in model["flds"]]

    for fname, value in (fields or {}).items():
        if fname in field_names:
            note[fname] = value or ""

    # Place audio in the user-selected field if not already present
    target = audio_field_name if audio_field_name in field_names else field_names[-1]
    existing = note[target]
    if sound_tag not in existing:
        note[target] = (existing + " " + sound_tag).strip() if existing else sound_tag

    if tags:
        note.tags = col.tags.split(tags)
    col.add_note(note, did)
    return note.id


def _undo_last_note(audio_filename: str) -> None:
    # Use native Anki checkpoint undo
    if mw.col:
        mw.col.undo()

    # Delete audio file if it exists in media folder
    media_dir = mw.col.media.dir()
    if media_dir and audio_filename:
        audio_path = os.path.join(media_dir, audio_filename)
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
