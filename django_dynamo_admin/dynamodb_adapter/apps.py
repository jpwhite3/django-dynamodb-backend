from django.apps import AppConfig


class DynamodbAdapterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_dynamo_admin.dynamodb_adapter"
