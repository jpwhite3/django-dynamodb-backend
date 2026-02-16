from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "examples.demo_project.apps.blog"
    verbose_name = "Demo Blog"
