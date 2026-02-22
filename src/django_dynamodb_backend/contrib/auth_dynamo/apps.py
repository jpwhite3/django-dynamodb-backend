from django.apps import AppConfig


class AuthDynamoConfig(AppConfig):
    name = "django_dynamodb_backend.contrib.auth_dynamo"
    label = "auth_dynamo"
    verbose_name = "DynamoDB Authentication"
