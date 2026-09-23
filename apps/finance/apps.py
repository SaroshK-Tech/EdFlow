from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.finance"
    label = "finance"
    verbose_name = "finance".title()
