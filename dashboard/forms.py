from django import forms
from django.contrib.auth.forms import AuthenticationForm

from network.models import AppConfig, DailyVerse, MinistryContent, PrayerRequest, Program, SpecialVerse


class StyledForm:
    """Gives every widget the dashboard's input classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "switch")
            elif isinstance(w, forms.ClearableFileInput):
                w.attrs.setdefault("class", "file")
            else:
                w.attrs.setdefault("class", "input")


class StaffLoginForm(StyledForm, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(placeholder="Username", autocomplete="username")
        self.fields["password"].widget.attrs.update(placeholder="Password", autocomplete="current-password")

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("This account doesn't have dashboard access.", code="no_staff")


class AppConfigForm(StyledForm, forms.ModelForm):
    class Meta:
        model = AppConfig
        exclude = ["updated_at"]
        widgets = {
            "stream_url": forms.URLInput(attrs={"placeholder": "https://…/index.m3u8"}),
            "stream_backup_url": forms.URLInput(attrs={"placeholder": "Optional"}),
            "offline_message": forms.Textarea(attrs={"rows": 2}),
            "announcement": forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. Special Easter service at 7 PM",
                                                  "data-counter": "300"}),
            "min_app_version": forms.TextInput(attrs={"placeholder": "1.0.0", "inputmode": "decimal"}),
            "donation_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }


class MinistryContentForm(StyledForm, forms.ModelForm):
    class Meta:
        model = MinistryContent
        exclude = ["updated_at"]
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "phone": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+91…"}),
            "whatsapp": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+91…"}),
        }


class ProgramForm(StyledForm, forms.ModelForm):
    class Meta:
        model = Program
        fields = ["title", "speaker", "day_of_week", "start_time", "end_time", "description",
                  "thumbnail", "thumbnail_url", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
            "thumbnail": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "thumbnail_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def clean_thumbnail(self):
        f = self.cleaned_data.get("thumbnail")
        if f and hasattr(f, "size") and f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Keep images under 2 MB.")
        return f


class CopyDayForm(forms.Form):
    source = forms.TypedChoiceField(choices=Program.Day.choices, coerce=int)
    targets = forms.TypedMultipleChoiceField(choices=Program.Day.choices, coerce=int)
    replace = forms.BooleanField(required=False)


class DailyVerseForm(StyledForm, forms.ModelForm):
    class Meta:
        model = DailyVerse
        fields = ["reference", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}


class SpecialVerseForm(StyledForm, forms.ModelForm):
    class Meta:
        model = SpecialVerse
        fields = ["date", "reference", "text", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "text": forms.Textarea(attrs={"rows": 4}),
        }


class PrayerUpdateForm(forms.ModelForm):
    class Meta:
        model = PrayerRequest
        fields = ["status", "note"]
