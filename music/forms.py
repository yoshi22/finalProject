from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class SignUpForm(UserCreationForm):
    """User registration form with username & email."""

    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {"email": forms.EmailInput(attrs={"required": True})}
