"""Speaker identity and voice-profile resolution.

Separates WHO speaks (speaker_id) from WHICH voice model is used
(voice_profile). This is the fix for Ginny being swallowed by the
Hermione voice pool: Ginny keeps her own identity even when the
current voice profile is still `hermione`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Logical speakers (in-game identity). Every distinct character keeps its
# own speaker_id rather than being swallowed into a coarse pool.
SPEAKER_IDS = {
    "harry",
    "ron",
    "hermione",
    "ginny",
    "moaning_myrtle",
    "narrator",
    "dumbledore",
    "arthur_weasley",
    "lockhart",
    "nearly_headless_nick",
    "flitwick",
    "fudge",
    "snape",
    "lucius",
    "filch",
    "draco",
    "hagrid",
    "riddle",
    "mrs_weasley",
    "mcgonagall",
    "sprout",
    "fat_lady",
    "oliver_wood",
    "neville",
    "fred_george",
    "dobby",
    "peeves",
    "sorting_hat",
}

# Voice profile actually loaded by XTTS (file stem under audio/profiles/).
# Every distinct character defaults to its own dedicated profile.
DEFAULT_VOICE_PROFILES: dict[str, str] = {sid: sid for sid in SPEAKER_IDS}

# Fallback timbre if a dedicated profile WAV has not been extracted yet.
LEGACY_FALLBACK_PROFILES: dict[str, str] = {
    "ginny": "hermione",
    "moaning_myrtle": "hermione",
    "arthur_weasley": "dumbledore",
    "lockhart": "dumbledore",
    "nearly_headless_nick": "dumbledore",
    "flitwick": "dumbledore",
    "fudge": "dumbledore",
    "lucius": "snape",
    "filch": "snape",
    "mcgonagall": "mrs_weasley",
    "sprout": "mrs_weasley",
    "fat_lady": "mrs_weasley",
    "oliver_wood": "ron",
    "neville": "ron",
    "fred_george": "ron",
    "peeves": "dobby",
}

# Historical coarse pools (for unknown/legacy aliases only).
_LEGACY_POOLS: dict[str, set[str]] = {
    "hermione": {"myrtle"},
    "ron": {"colin"},
    "mrs_weasley": {"madam_hooch"},
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
    # T1L2M007 Kovuk Bahçesi — Arthur Weasley (önceki dumbledore havuzundan ayrıldı)
    ("T1L2M007", 75): "arthur_weasley",
    ("T1L2M007", 76): "arthur_weasley",
    ("T1L2M007", 77): "arthur_weasley",
    ("T1L2M007", 78): "arthur_weasley",
    ("T1L2M007", 79): "arthur_weasley",
    ("T1L2M007", 91): "arthur_weasley",
}


def resolve_profile_name(voice_profile: str, profiles_dir: str = "audio/profiles") -> str:
    """Return `voice_profile` if its WAV/latent exists, else fall back safely."""
    import os

    wav_path = os.path.join(profiles_dir, f"{voice_profile}.wav")
    lat_path = os.path.join(profiles_dir, f"{voice_profile}_latents.pt")
    if os.path.exists(wav_path) or os.path.exists(lat_path):
        return voice_profile
    return LEGACY_FALLBACK_PROFILES.get(voice_profile, voice_profile)


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
