# music/note_utils.py
"""
MIDI <-> Scientific Pitch Notation 変換ユーティリティ
  - C4 = MIDI 60 を前提
  - 0 <= midi <= 127 の範囲を想定
"""

import re
from typing import Final

_NOTE_NAMES: Final[list[str]] = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
]


def midi_to_spn(midi: int) -> str:
    """
    60 -> 'C4', 61 -> 'C#4' など
    """
    if not (0 <= midi <= 127):
        raise ValueError("midi must be 0‒127")
    note = _NOTE_NAMES[midi % 12]
    octave = midi // 12 - 1           # MIDI 0 は C-1
    return f"{note}{octave}"


_SP_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*([A-Ga-g])([#b♯♭]?)(-?\d)\s*$"
)


def spn_to_midi(spn: str) -> int:
    """
    'C4' -> 60, 'F#3' -> 54 など
    """
    m = _SP_RE.match(spn)
    if not m:
        raise ValueError("invalid SPN string")

    letter, accidental, octave_s = m.groups()
    letter = letter.upper()

    # シャープ/フラットを統一表記に
    acc_map = {"♯": "#", "#": "#", "♭": "b", "b": "b", "": ""}
    accidental = acc_map[accidental]

    name = letter + accidental
    if name not in _NOTE_NAMES:
        # フラット表記はシャープ表記へ変換
        flat_to_sharp = {
            "Db": "C#", "Eb": "D#", "Gb": "F#",
            "Ab": "G#", "Bb": "A#"
        }
        name = flat_to_sharp.get(name)
        if not name:
            raise ValueError("unsupported note name")

    midi = _NOTE_NAMES.index(name) + (int(octave_s) + 1) * 12
    if not (0 <= midi <= 127):
        raise ValueError("resulting midi out of range")
    return midi
