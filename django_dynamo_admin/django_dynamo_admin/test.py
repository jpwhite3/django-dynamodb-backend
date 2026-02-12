from django.test import TestCase
from myapp.models import MyModel


class DynamoDBAdapterTestCase(TestCase):
    def setUp(self):
        self.model = MyModel(name="test")

    def test_create_model(self):
        self.model.save()
        self.assertTrue(self.model.exists())

    def test_destroy_model(self):
        self.model.save()
        self.model.delete()
        self.assertFalse(self.model.exists())
