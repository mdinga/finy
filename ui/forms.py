# ui/forms.py
from django import forms
from core.models import Task, Subtask, Attachment, Space, Folder


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
