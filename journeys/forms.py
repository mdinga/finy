from django import forms


class DeleteProfileForm(forms.Form):
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "class": "form-control"}
        ),
    )
    confirmation = forms.CharField(
        label='Type "DELETE" to confirm',
        widget=forms.TextInput(attrs={"autocomplete": "off", "class": "form-control"}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Your password is incorrect.")
        return password

    def clean_confirmation(self):
        confirmation = self.cleaned_data["confirmation"].strip()
        if confirmation != "DELETE":
            raise forms.ValidationError('Type "DELETE" exactly to confirm deletion.')
        return confirmation
