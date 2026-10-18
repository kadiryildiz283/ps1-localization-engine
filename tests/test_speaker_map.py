"""Unit tests for speaker identity resolution (Ginny fix)."""

from tools.speaker_map import (
    DEFAULT_VOICE_PROFILES,
    LINE_SPEAKER_OVERRIDES,
    looks_like_ginny_line,
    resolve_speaker,
)


def test_ginny_diorama_line_39_override():
    r = resolve_speaker(stem="T1L1M007", line_index=39, speaker_id="hermione")
    assert r.speaker_id == "ginny"
    assert r.voice_profile == "hermione"  # shared timbre until dedicated profile
    assert r.source == "override"


def test_ginny_diorama_line_122_override():
    r = resolve_speaker(stem="T1L1M007", line_index=122, speaker_id="hermione")
    assert r.speaker_id == "ginny"


def test_explicit_harry_stays_harry():
    r = resolve_speaker(speaker_id="harry", en_text="Hadi Ginny, gidelim buradan.")
    assert r.speaker_id == "harry"
    assert r.voice_profile == "harry"
    assert r.source == "explicit"


def test_hermione_line_not_stolen():
    r = resolve_speaker(
        speaker_id="hermione",
        en_text="I think we should follow the spiders.",
    )
    assert r.speaker_id == "hermione"


def test_ginny_first_person_detection():
    # Self-identification forms
    assert looks_like_ginny_line("Ginny: I didn't want all that!")
    assert looks_like_ginny_line("I'm Ginny. Nice to meet you.")
    # Third-person narration about Ginny is NOT Ginny speaking
    assert not looks_like_ginny_line("Ginny, who was very fond of Harry, defended him.")
    # Confession without her name needs an explicit override (line 122)
    assert not looks_like_ginny_line("It was me, Harry — but I swear I didn't mean to.")


def test_ginny_detection_promotes_hermione_pool():
    r = resolve_speaker(
        speaker_id="hermione",
        en_text="Ginny: I didn't want all that!",
    )
    assert r.speaker_id == "ginny"


def test_nameless_confession_requires_override():
    r = resolve_speaker(
        speaker_id="hermione",
        en_text="It was me, Harry. I s-swear I didn't do it on purpose.",
    )
    # Without name or override this stays hermione (pool limitation)
    assert r.speaker_id == "hermione"
    # But the diorama override catches the known line
    r2 = resolve_speaker(
        stem="T1L1M007",
        line_index=122,
        speaker_id="hermione",
        en_text="It was me, Harry. I s-swear I didn't do it on purpose.",
    )
    assert r2.speaker_id == "ginny"


def test_voice_profile_swap_for_dedicated_ginny():
    profiles = dict(DEFAULT_VOICE_PROFILES)
    profiles["ginny"] = "ginny"  # future dedicated recording
    r = resolve_speaker(
        stem="T1L1M007",
        line_index=39,
        speaker_id="hermione",
        voice_profiles=profiles,
    )
    assert r.speaker_id == "ginny"
    assert r.voice_profile == "ginny"


def test_legacy_pool_mapping():
    r = resolve_speaker(speaker_id="moaning_myrtle")
    assert r.speaker_id == "hermione"
    assert r.source == "legacy-pool"


def test_unknown_defaults_to_narrator():
    r = resolve_speaker()
    assert r.speaker_id == "narrator"


def test_unknown_label_defaults_to_narrator():
    r = resolve_speaker(speaker_id="some_random_npc")
    assert r.speaker_id == "narrator"


def test_line_overrides_cover_ginny_storybook():
    assert LINE_SPEAKER_OVERRIDES[("T1L1M007", 39)] == "ginny"
    assert LINE_SPEAKER_OVERRIDES[("T1L1M007", 122)] == "ginny"
