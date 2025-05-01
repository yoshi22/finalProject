from django import forms
from django.core import validators
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import VocalProfile, Playlist
from .note_utils import spn_to_midi, midi_to_spn

# ──────────────────────────────────────────────────────────────
#  共通
# ──────────────────────────────────────────────────────────────
User   = get_user_model()
SPN_RE = r"^[A-G](?:#|b)?[0-8]$"           # 例: C4, F#3, Bb2


class SPNField(forms.CharField):
    """
    Scientific Pitch Notation (C4, F#3 …) で入出力し、
    モデルとは MIDI 整数でやり取りするカスタムフィールド。
    """
    default_validators = [
        validators.RegexValidator(
            regex   = SPN_RE,
            message = "例: C4, F#3, Bb2 の形式で入力してください",
            code    = "invalid_spn",
        )
    ]

    # フォーム入力 → Python 値（MIDI int）へ
    def to_python(self, value: str | None) -> int | None:
        if value in self.empty_values:
            return None
        return spn_to_midi(value.strip())

    # Python 値 → フォーム初期値（SPN 文字列）へ
    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        if isinstance(value, int):
            return midi_to_spn(value)
        return value


# ──────────────────────────────────────────────────────────────
#  認証 & Playlist 関連フォーム
# ──────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────
#  Vocal range 入力フォーム
# ──────────────────────────────────────────────────────────────
class VocalRangeForm(forms.ModelForm):
    note_min = SPNField(label="最低音")
    note_max = SPNField(label="最高音")

    class Meta:
        model  = VocalProfile
        fields = ("note_min", "note_max")

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get("note_min"), cleaned.get("note_max")
        if lo is not None and hi is not None and lo > hi:
            raise forms.ValidationError("最低音は最高音以下にしてください。")
        return cleaned
