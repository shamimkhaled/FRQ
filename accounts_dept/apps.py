from django.apps import AppConfig


class AccountsDeptConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts_dept'

    def ready(self):
        from . import signals  # noqa: F401
