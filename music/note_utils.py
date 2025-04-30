# music/note_utils.py
"""
Utilities for converting between MIDI note numbers and readable names
"""
NOTE_NAMES = ["C", "C♯", "D", "E♭", "E", "F",
              "F♯", "G", "G♯", "A", "B♭", "B"]

def midi_to_spn(n: int) -> str:
    """
    60 → 'C4', 61 → 'C♯4' … 127 → 'G9'
    Return empty string on bad input.
    """
    try:
        n = int(n)
        octave = (n // 12) - 1          # MIDI octave rule
        name   = NOTE_NAMES[n % 12]
        return f"{name}{octave}"
    except Exception:                   # noqa: BLE001
        return ""
