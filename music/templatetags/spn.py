# music/templatetags/spn.py
from django import template
from music.note_utils import midi_to_spn

register = template.Library()

@register.filter(name="spn")
def spn(value):
    """Usage: {{ 60|spn }} -> C4  """
    return midi_to_spn(value)
