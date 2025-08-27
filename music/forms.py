from typing import Optional, Union
from django import forms
from django.core import validators
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import VocalProfile, Playlist
from .note_utils import spn_to_midi, midi_to_spn

# ------------------------------
#  Common
# ------------------------------
User   = get_user_model()
SPN_RE = r"^[A-G](?:#|b)?[0-8]$"           # Example: C4, F#3, Bb2


class SPNField(forms.CharField):
    """
    Input and output in Scientific Pitch Notation (C4, F#3, etc.),
    while interacting with the model as MIDI integers.
    """
    default_validators = [
        validators.RegexValidator(
            regex   = SPN_RE,
            message = "Please input in the format: C4, F#3, Bb2",
            code    = "invalid_spn",
        )
    ]

    # Form input -> Python value (MIDI int)
    def to_python(self, value: Optional[str]) -> Optional[int]:
        if value in self.empty_values:
            return None
        return spn_to_midi(value.strip())

    # Python value -> Form initial value (SPN string)
    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        if isinstance(value, int):
            return midi_to_spn(value)
        return value


# ------------------------------
#  Authentication & Playlist Forms
# ------------------------------
class SignUpForm(UserCreationForm):
    class Meta:
        model   = User
        fields  = ("username", "email")
        widgets = {"email": forms.EmailInput(attrs={"required": True})}


class PlaylistRenameForm(forms.ModelForm):
    class Meta:
        model  = Playlist
        fields = ("name",)


class AddTrackForm(forms.Form):
    """Dropdown of existing playlists + “＋ New playlist…” option."""
    playlist = forms.ChoiceField(label="Add to playlist")
    new_name = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "New playlist name"}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(pl.id, pl.name) for pl in user.playlists.all()]
        choices.append(("__new__", "＋ New playlist…"))
        self.fields["playlist"].choices = choices
        self.fields["playlist"].widget.attrs.update({"style": "font-size:0.9rem"})


# ------------------------------
#  Vocal range Input Form
# ------------------------------
class VocalRangeForm(forms.ModelForm):
    note_min = SPNField(label="Lowest Note")
    note_max = SPNField(label="Highest Note")

    class Meta:
        model  = VocalProfile
        fields = ("note_min", "note_max")

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get("note_min"), cleaned.get("note_max")
        if lo is not None and hi is not None and lo > hi:
            raise forms.ValidationError("The lowest note must be below the highest note.")
        return cleaned
