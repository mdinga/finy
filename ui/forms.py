# ui/forms.py
from django import forms
from core.models import Task, Subtask, Attachment, Space, Folder
from django.contrib.auth import get_user_model

User = get_user_model()

class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Create a password",
            "autocomplete": "new-password",
        })
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
        })
    )

    class Meta:
        model = User
        fields = ["first_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={
                "placeholder": "Your name",
                "autocomplete": "given-name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }),
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user


class TaskCreateForm(forms.ModelForm):
    """
    Aligns with core.models.Task fields exactly:
      - due_date (not due_at)
      - estimated_minutes (uses model choices)
      - repeat_rule (uses model choices)
      - spaces ManyToMany
      - folder ForeignKey

    """
    class Meta:
        model = Task
        fields = [
            "title",
            "folder",
            "spaces",
            "planned_date",
            "due_date",
            "estimated_minutes",
            "repeat_rule",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Task title"}),
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Use model choices directly — no custom lists here
        # estimated_minutes and repeat_rule automatically pick up Task's choices

        if user is not None:
            # Scope folders and spaces to the logged-in user
            self.fields["folder"].queryset = Folder.objects.filter(user=user).order_by("name")
            self.fields["spaces"].queryset = (
                Space.objects.filter(user=user)
                .select_related("category")
                .order_by("category__name", "name")
            )


class SubtaskForm(forms.ModelForm):
    """
    Replaces 'ChecklistItemForm' and the old 'next_action' field concept.
    Next actions are Subtask rows related to a Task.
    """
    class Meta:
        model = Subtask
        fields = ["title"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Add next action"})
        }


class AttachmentForm(forms.ModelForm):
    """
    Replaces TaskPictureForm. All files/images are Attachments on a Task.
    """
    class Meta:
        model = Attachment
        fields = ["image"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"})
        }

from django import forms


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "Enter your email",
            "autocomplete": "email",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Enter your password",
            "autocomplete": "current-password",
        })
    )
