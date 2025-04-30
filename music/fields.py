# music/fields.py
from django import forms
from django.core.exceptions import ValidationError
from .note_utils import spn_to_midi, midi_to_spn


class SPNField(forms.CharField):
    """
    Scientific Pitch Notation (例: C4, F#3, Bb2) を扱う CharField。
    - 送信時は str を受け取り、clean() 内で MIDI(int) に変換して返す
    - 初期値には MIDI(int) を渡しても OK ── to_python() で文字列へ
    """

    default_error_messages = {
        "invalid": "音名+オクターブ (例: C4, F#3, Bb2) で入力してください。",
    }

    def to_python(self, value):
        """
        フィールドをテンプレートに渡すときの表示用変換。
        (モデル側に int が入っていてもフォームでは 'C4' などで見える)
        """
        if value in self.empty_values:
            return ""
        if isinstance(value, int):
            # モデルインスタンス -> フォーム初期値
            return midi_to_spn(value)
        return value.strip()

    def clean(self, value):
        """
        フォーム送信時の検証＆MIDI への変換
        """
        value = super().clean(value)
        if not value:
            return None

        try:
            return spn_to_midi(value)
        except ValueError:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
