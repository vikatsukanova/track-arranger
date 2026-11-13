import pytest

from track_arranger.arrangement import (
    Section, bars_to_seconds, build_arrangement, format_time, validate_bpm,
)
from track_arranger.tips import TIPS


@pytest.mark.parametrize("bars,bpm,seconds", [(0, 174, 0), (8, 160, 12), (32, 180, 128 / 3)])
def test_bar_duration(bars, bpm, seconds):
    assert bars_to_seconds(bars, bpm) == pytest.approx(seconds)


def test_one_based_start_and_display_time():
    assert Section("Intro", 32, 1).start_seconds(174) == 0
    assert Section("Build", 16, 33).start_seconds(174) == pytest.approx(128 * 60 / 174)
    assert format_time(59.99) == "00:59"
    assert format_time(60) == "01:00"
    assert format_time(264.8) == "04:24"


@pytest.mark.parametrize("bpm", [159, 181, float("nan"), float("inf"), 0])
def test_invalid_bpm(bpm):
    with pytest.raises(ValueError, match="160 and 180"):
        validate_bpm(bpm)


@pytest.mark.parametrize("bpm", [160, 174, 174.5, 180])
def test_allowed_bpm(bpm):
    validate_bpm(bpm)


def test_negative_bar_duration():
    with pytest.raises(ValueError):
        bars_to_seconds(-1, 174)


def test_dnb_template_and_tips():
    sections = build_arrangement()
    assert [s.name for s in sections] == [
        "Intro", "Build", "Drop 1", "Breakdown", "Build 2", "Drop 2", "Outro",
    ]
    assert [s.bars for s in sections] == [32, 16, 32, 32, 16, 32, 32]
    assert [s.start_bar for s in sections] == [1, 33, 49, 81, 113, 129, 161]
    assert sum(s.bars for s in sections) == 192
    for section in sections:
        assert section.bars % 8 == 0
        assert 2 <= len(TIPS["dnb"][section.name]) <= 4
