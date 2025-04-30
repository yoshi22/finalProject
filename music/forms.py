from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .note_utils import midi_to_spn, spn_to_midi

from .models import Playlist
from .models import VocalProfile
from .fields import SPNField
from django.core import validators

User = get_user_model()


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {"email": forms.EmailInput(attrs={"required": True})}


class PlaylistRenameForm(forms.ModelForm):
    class Meta:
        model = Playlist
        fields = ("name",)


class AddTrackForm(forms.Form):
    """Dropdown of existing playlists + 'New…' option."""
    playlist = forms.ChoiceField(label="Add to playlist")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(pl.id, pl.name) for pl in user.playlists.all()]
        choices.append(("__new__", "＋ New playlist…"))
        self.fields["playlist"].choices = choices
        self.fields["playlist"].widget.attrs.update({"style": "font-size:0.9rem"})
        self.fields["playlist"].required = True

    new_name = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "New playlist name"}),
    )

class VocalProfileForm(forms.ModelForm):
    class Meta:
        model = VocalProfile
        fields = ("note_min", "note_max")
        widgets = {
            "note_min": forms.NumberInput(attrs={"min": 40, "max": 80}),
            "note_max": forms.NumberInput(attrs={"min": 0, "max": 90}),
        }

class VocalRangeForm(forms.ModelForm):
    note_min = SPNField(label="最低音")
    note_max = SPNField(label="最高音")

    class Meta:
        model  = VocalProfile
        fields = ("note_min", "note_max")

    # SPN を初期値として表示
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:                     # 既存レコードあり
            self.initial["note_min"] = midi_to_spn(self.instance.note_min)
            self.initial["note_max"] = midi_to_spn(self.instance.note_max)


class SPNField(forms.CharField):
    default_validators = [
        validators.RegexValidator(
            regex=r"^\s*[A-Ga-g][#b]?(-?\d)\s*$",
            message="例）C4, F#3, Bb2 のように入力してください",
        )
    ]

    def to_python(self, value):
        if not value:
            return None
        try:
            return spn_to_midi(value)
        except ValueError:
            raise forms.ValidationError("音名＋オクターブ（例：C4）を入力してください")