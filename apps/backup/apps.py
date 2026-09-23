from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.backup"
    label = "backup"
    verbose_name = "backup".title()
