from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import Playlist
from .models import VocalProfile

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
    """
    ・note_min, note_max は MIDI ノート番号（整数）を想定
      └ 例) C4=60, A4=69 …など
    ・最低音 ≤ 最高音 であることをバリデーション
    """

    class Meta:
        model = VocalProfile
        fields = ("note_min", "note_max")
        widgets = {
            "note_min": forms.NumberInput(
                attrs={"class": "form-control", "min": 21, "max": 108}
            ),
            "note_max": forms.NumberInput(
                attrs={"class": "form-control", "min": 21, "max": 108}
            ),
        }
        labels = {
            "note_min": "最低音 (MIDI 番号)",
            "note_max": "最高音 (MIDI 番号)",
        }

    def clean(self):
        cleaned = super().clean()
        lo = cleaned.get("note_min")
        hi = cleaned.get("note_max")
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError("最高音は最低音以上にしてください。")
        return cleaned