"""Speaker identity and voice-profile resolution.

Separates WHO speaks (speaker_id) from WHICH voice model is used
(voice_profile). This is the fix for Ginny being swallowed by the
Hermione voice pool: Ginny keeps her own identity even when the
current voice profile is still `hermione`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Logical speakers (in-game identity).
SPEAKER_IDS = {
    "harry",
    "ron",
    "hermione",
    "ginny",
    "narrator",
    "dumbledore",
    "snape",
    "draco",
    "hagrid",
    "riddle",
    "mrs_weasley",
    "dobby",
    "sorting_hat",
}

# Voice profile actually loaded by XTTS (file stem under audio/profiles/).
# Profiles can be shared; identities must not be.
DEFAULT_VOICE_PROFILES: dict[str, str] = {
    "harry": "harry",
    "ron": "ron",
    "hermione": "hermione",
    # Ginny has no dedicated recording yet — shares Cansel's timbre but
    # is tracked as her own speaker so we can swap the profile later
    # without reclassifying every line.
    "ginny": "hermione",
    "narrator": "narrator",
    "dumbledore": "dumbledore",
    "snape": "snape",
    "draco": "draco",
    "hagrid": "hagrid",
    "riddle": "riddle",
    "mrs_weasley": "mrs_weasley",
    "dobby": "dobby",
    "sorting_hat": "sorting_hat",
}

# Historical coarse pools. Kept only as fallback when no explicit
# speaker_id is present. Never use these for Ginny.
_LEGACY_POOLS = {
    "hermione": {"hermione", "moaning_myrtle", "myrtle"},
    "ron": {"ron", "fred", "george", "oliver_wood", "neville", "colin"},
    "dumbledore": {
        "dumbledore",
        "arthur_weasley",
        "lockhart",
        "flitwick",
        "fudge",
        "nearly_headless_nick",
    },
    "mrs_weasley": {
        "mrs_weasley",
        "mcgonagall",
        "sprout",
        "madam_hooch",
        "fat_lady",
    },
}


@dataclass(frozen=True)
class ResolvedSpeaker:
    speaker_id: str
    voice_profile: str
    source: str  # "explicit" | "override" | "legacy-pool" | "default"

    def __post_init__(self) -> None:
        if self.speaker_id not in SPEAKER_IDS:
            raise ValueError(f"unknown speaker_id: {self.speaker_id}")
        if not self.voice_profile:
            raise ValueError("voice_profile must be non-empty")


# Explicit identity overrides for known mis-pooled lines.
# Key: (stem, dialogue_id or line_index) -> speaker_id
LINE_SPEAKER_OVERRIDES: dict[tuple, str] = {
    # Storybook diorama (T1L1M007) — Ginny lines previously forced to hermione
    ("T1L1M007", 39): "ginny",
    ("T1L1M007", 122): "ginny",
}

# Stem-level dialogue-id overrides (in-game WADs).
DIALOGUE_SPEAKER_OVERRIDES: dict[tuple, str] = {
    # T1L2M001 Kovuk Bahçesi — Molly'nin Howler tiradı
    ("T1L2M001", 77): "mrs_weasley",
}


_GINNY_RE = re.compile(
    r"\b(ginny|ginny weasley|weasley'?s sister)\b",
    re.IGNORECASE,
)
_SPEECH_VERB_RE = re.compile(
    r"\b(said|says|shouted|whispered|replied|asked|cried|muttered)\b",
    re.IGNORECASE,
)


def looks_like_ginny_line(en: str) -> bool:
    """True when the English line is spoken *by* Ginny, not merely about her.

    Name-based heuristic only. Lines where Ginny confesses without naming
    herself ("It was me, Harry...") require an explicit override — see
    LINE_SPEAKER_OVERRIDES.
    """
    text = en or ""
    if not _GINNY_RE.search(text):
        return False
    lowered = text.lower()
    # Third-person narration about Ginny stays narrator:
    # "Ginny, who was very fond of Harry, defended him."
    if re.search(
        r"\b(said|says|shouted|whispered|replied|asked|cried|muttered|defended|told|explained)\b",
        lowered,
    ) and not re.search(r"\bginny\s*:", lowered):
        return False
    first_person = bool(re.search(r"\b(i\b|i'm|i've|i'll|me\b|my\b)\b", lowered))
    # "Ginny: I didn't want all that!" style
    if re.search(r"\bginny\s*:", lowered):
        return True
    # "M-merhaba Harry! ... Ben Ginny." — self-introduction
    if re.search(r"\b(i am ginny|i'm ginny|ben ginny|my name is ginny)\b", lowered):
        return True
    return first_person


def resolve_speaker(
    *,
    speaker_id: str | None = None,
    stem: str | None = None,
    dialogue_id: int | None = None,
    line_index: int | None = None,
    en_text: str | None = None,
    voice_profiles: dict[str, str] | None = None,
) -> ResolvedSpeaker:
    """Resolve final (speaker_id, voice_profile) for one line.

    Priority:
      1. Explicit line/dialogue override (fixes known Ginny bugs)
      2. Explicit speaker_id passed in
      3. Ginny detection from text
      4. Legacy pool mapping of a coarse label
      5. narrator default
    """
    profiles = voice_profiles or DEFAULT_VOICE_PROFILES

    if stem is not None and line_index is not None:
        key = (stem, line_index)
        if key in LINE_SPEAKER_OVERRIDES:
            sid = LINE_SPEAKER_OVERRIDES[key]
            return ResolvedSpeaker(sid, profiles[sid], "override")

    if stem is not None and dialogue_id is not None:
        key = (stem, dialogue_id)
        if key in DIALOGUE_SPEAKER_OVERRIDES:
            sid = DIALOGUE_SPEAKER_OVERRIDES[key]
            return ResolvedSpeaker(sid, profiles[sid], "override")

    if speaker_id:
        # Historical bug: lines classified as hermione that are actually Ginny.
        if speaker_id == "hermione" and looks_like_ginny_line(en_text or ""):
            return ResolvedSpeaker("ginny", profiles["ginny"], "override")
        if speaker_id in SPEAKER_IDS:
            return ResolvedSpeaker(speaker_id, profiles[speaker_id], "explicit")
        # legacy coarse label
        for pool_owner, members in _LEGACY_POOLS.items():
            if speaker_id in members:
                return ResolvedSpeaker(pool_owner, profiles[pool_owner], "legacy-pool")
        return ResolvedSpeaker("narrator", profiles["narrator"], "default")

    if looks_like_ginny_line(en_text or ""):
        return ResolvedSpeaker("ginny", profiles["ginny"], "override")

    return ResolvedSpeaker("narrator", profiles["narrator"], "default")
