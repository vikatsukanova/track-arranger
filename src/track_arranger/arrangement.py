from dataclasses import dataclass

BEATS_PER_BAR = 4

TEMPLATES = {
    "dnb": (
        ("Intro", 32),
        ("Build", 16),
        ("Drop 1", 32),
        ("Breakdown", 32),
        ("Build 2", 16),
        ("Drop 2", 32),
        ("Outro", 32),
    ),
}


@dataclass(frozen=True)
class Section:

    name: str
    bars: int
    start_bar: int

    def start_seconds(self, bpm: float) -> float:
        return bars_to_seconds(self.start_bar - 1, bpm)


def validate_bpm(bpm: float) -> None:
    if not 160 <= bpm <= 180:
        raise ValueError("BPM must be between 160 and 180 (inclusive).")


def bars_to_seconds(bars: int, bpm: float) -> float:
    validate_bpm(bpm)
    if bars < 0:
        raise ValueError("Bar duration cannot be negative.")
    return bars * BEATS_PER_BAR * 60 / bpm


def format_time(seconds: float) -> str:
    minutes, seconds_part = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds_part:02d}"


def build_arrangement(genre: str = "dnb") -> list[Section]:
    sections = []
    start_bar = 1
    for name, bars in TEMPLATES[genre]:
        if bars <= 0 or bars % 8:
            raise ValueError("Section lengths must be positive multiples of 8.")
        sections.append(Section(name, bars, start_bar))
        start_bar += bars
    return sections
