from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "interactive_demo.apps.blog"
    verbose_name = "Demo Blog"
