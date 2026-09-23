from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.students"
    label = "students"
    verbose_name = "students".title()
