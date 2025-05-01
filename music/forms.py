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

    def clean(self):
        cd = super().clean()
        lo, hi = cd.get("note_min"), cd.get("note_max")
        if lo is not None and hi is not None and lo > hi:
            raise forms.ValidationError("最低音は最高音以下にしてください。")
        return cd


SPN_RE = r"^[A-G](?:#|b)?[0-8]$"                   # 例: C4, F#3, Bb2

class SPNField(forms.CharField):
    """
    Web では C4, F#3 … と入力させ、モデルへは MIDI (int) を渡すカスタム Field
    """
    default_validators = [
        validators.RegexValidator(
            regex=SPN_RE,
            message="例: C4, F#3, Bb2 形式で入力してください",
            code="invalid_spn",
        )
    ]

    def to_python(self, value: str | None) -> int | None:            # ⇦ ★ ここで変換
        if value in self.empty_values:
            return None
        return spn_to_midi(value.strip())

    def prepare_value(self, value):                                  # フォーム初期値用
        if value in self.empty_values:
            return ""
        if isinstance(value, int):
            return midi_to_spn(value)
        return value