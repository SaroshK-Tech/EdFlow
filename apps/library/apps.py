from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.library"
    label = "library"
    verbose_name = "library".title()
