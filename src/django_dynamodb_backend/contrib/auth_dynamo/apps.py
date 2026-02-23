from django.apps import AppConfig


class AuthDynamoConfig(AppConfig):
    name = "django_dynamodb_backend.contrib.auth_dynamo"
    label = "auth_dynamo"
    verbose_name = "DynamoDB Authentication"

    def ready(self):
        from .managers import DynamoUserManager
        from .models import DynamoUser

        manager = DynamoUserManager()
        manager.model = DynamoUser
        DynamoUser.objects = manager
        DynamoUser._default_manager = manager
