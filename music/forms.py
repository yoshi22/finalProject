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