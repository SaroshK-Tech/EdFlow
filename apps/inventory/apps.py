from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.inventory"
    label = "inventory"
    verbose_name = "inventory".title()
