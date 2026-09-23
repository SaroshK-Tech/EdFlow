from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "accounts".title()

    def ready(self):
        from . import signals  # noqa: F401  (connect auth history signals)
