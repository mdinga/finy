from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend:
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        email = email or username
        if not email or not password:
            return None

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and user.is_active:
            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
