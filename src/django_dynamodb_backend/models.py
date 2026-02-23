import datetime
import logging

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils import timezone
from pynamodb.attributes import UnicodeAttribute
from pynamodb.exceptions import DoesNotExist
from pynamodb.models import Model as PynamoDBModel

from .fields import DynamoDBFieldDescriptor, FieldMapper
from .managers import DynamoDBManager

logger = logging.getLogger(__name__)


class DynamoDBModelMeta(type(models.Model)):
    """Metaclass for DynamoDB models that creates PynamoDB model classes."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Create the Django model first
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip processing for abstract models and the base DynamoDBModel
        if getattr(cls._meta, "abstract", False) or name == "DynamoDBModel":
            return cls

        # Mark for later PynamoDB model creation (deferred to avoid circular dependencies)
        cls._pynamodb_model_class = None
        cls._needs_pynamodb_model = True

        return cls

    @classmethod
    def _create_pynamodb_model(mcs, django_model):
        """Create a PynamoDB model class from Django model."""
        django_model._meta.db_table

        # Get region from settings
        region = "us-east-1"
        if hasattr(settings, "DATABASES") and "default" in settings.DATABASES:
            region = settings.DATABASES["default"].get("REGION", "us-east-1")
        elif hasattr(settings, "DYNAMODB_REGION"):
            region = settings.DYNAMODB_REGION

        # Build PynamoDB attributes
        pynamodb_attrs = {
            "__module__": django_model.__module__,
        }

        # Add Meta class for PynamoDB
        meta_attrs = {
            "table_name": django_model._meta.db_table,
            "region": region,
        }

        # Use local endpoint if configured
        if hasattr(settings, "DATABASES") and settings.DATABASES.get("default", {}).get(
            "LOCAL_ENDPOINT"
        ):
            meta_attrs["host"] = settings.DATABASES["default"]["LOCAL_ENDPOINT"]

        Meta = type("Meta", (), meta_attrs)

        pynamodb_attrs["Meta"] = Meta

        # Map Django fields to PynamoDB attributes
        for field in django_model._meta.get_fields():
            if field.name.startswith("_"):
                continue

            # Skip reverse foreign keys and many-to-many
            if hasattr(field, "remote_field") and field.remote_field:
                continue

            pynamodb_attr_class = FieldMapper.get_dynamodb_attribute(field)

            # Handle primary key
            if field.primary_key:
                pynamodb_attrs[field.name] = pynamodb_attr_class(hash_key=True)
            else:
                # DynamoDB is schemaless — all non-PK attributes are optional.
                pynamodb_attrs[field.name] = pynamodb_attr_class(null=True)

        # Ensure we have a primary key
        if not any(
            getattr(attr, "is_hash_key", False)
            for attr in pynamodb_attrs.values()
            if hasattr(attr, "is_hash_key")
        ):
            # Use 'id' as default primary key if no explicit primary key
            pynamodb_attrs["id"] = UnicodeAttribute(hash_key=True)

        # Create the PynamoDB model class
        pynamodb_model_name = f"{django_model.__name__}PynamoDBModel"
        pynamodb_model = type(pynamodb_model_name, (PynamoDBModel,), pynamodb_attrs)

        return pynamodb_model

    @classmethod
    def _setup_field_descriptors(mcs, django_model):
        """Set up field descriptors for DynamoDB integration."""
        for field in django_model._meta.get_fields():
            if field.name.startswith("_"):
                continue

            if hasattr(field, "remote_field") and field.remote_field:
                continue

            # Create descriptor for field access
            descriptor = DynamoDBFieldDescriptor(field.name, field)
            setattr(django_model, field.name, descriptor)


class DynamoDBModel(models.Model, metaclass=DynamoDBModelMeta):
    """Enhanced base class for DynamoDB models with full Django integration."""

    objects = DynamoDBManager()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        # Initialize field values storage
        self._field_values = {}

        # Create Django instance for compatibility
        self._django_instance = super()

        # Initialize with provided values
        for field in self._meta.get_fields():
            if field.name in kwargs:
                value = kwargs[field.name]
                converted_value = FieldMapper.convert_value_to_dynamodb(value, field)
                self._field_values[field.name] = converted_value

        super().__init__(*args, **kwargs)
        self._pynamodb_instance = None

    @classmethod
    def _get_pynamodb_model(cls):
        """Get the PynamoDB model class for this Django model."""
        if cls._pynamodb_model_class is None and getattr(
            cls, "_needs_pynamodb_model", False
        ):
            # Create the PynamoDB model now
            cls._pynamodb_model_class = DynamoDBModelMeta._create_pynamodb_model(cls)
            cls._needs_pynamodb_model = False

        if cls._pynamodb_model_class is None:
            raise ImproperlyConfigured(f"No PynamoDB model created for {cls.__name__}")
        return cls._pynamodb_model_class

    def _get_pynamodb_instance(self):
        """Get or create a PynamoDB instance for this object."""
        if self._pynamodb_instance is None:
            pynamodb_model = self._get_pynamodb_model()

            # Create instance with current field values
            pynamodb_data = {}
            for field_name, value in self._field_values.items():
                pynamodb_data[field_name] = value

            self._pynamodb_instance = pynamodb_model(**pynamodb_data)

        return self._pynamodb_instance

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        """Save the object to DynamoDB."""
        try:
            # Get PynamoDB instance
            pynamodb_instance = self._get_pynamodb_instance()

            # Update with current field values
            for field_name, value in self._field_values.items():
                if hasattr(pynamodb_instance, field_name):
                    setattr(pynamodb_instance, field_name, value)

            # Save to DynamoDB
            pynamodb_instance.save()

            # Update our instance reference
            self._pynamodb_instance = pynamodb_instance

            logger.info(f"Saved {self.__class__.__name__} to DynamoDB")

        except Exception as e:
            logger.error(f"Error saving {self.__class__.__name__} to DynamoDB: {e}")
            raise

    def delete(self, using=None, keep_parents=False):
        """Delete the object from DynamoDB."""
        try:
            pynamodb_instance = self._get_pynamodb_instance()
            pynamodb_instance.delete()
            logger.info(f"Deleted {self.__class__.__name__} from DynamoDB")
        except DoesNotExist:
            logger.warning(f"{self.__class__.__name__} does not exist in DynamoDB")
        except Exception as e:
            logger.error(f"Error deleting {self.__class__.__name__} from DynamoDB: {e}")
            raise

    def refresh_from_db(self, using=None, fields=None):
        """Refresh the object from DynamoDB."""
        try:
            pynamodb_model = self._get_pynamodb_model()

            # Get primary key value
            pk_field = self._meta.pk
            pk_value = self._field_values.get(pk_field.name)

            if pk_value:
                # Load from DynamoDB
                pynamodb_instance = pynamodb_model.get(pk_value)

                # Update field values
                for field in self._meta.get_fields():
                    if hasattr(pynamodb_instance, field.name):
                        value = getattr(pynamodb_instance, field.name)
                        converted_value = FieldMapper.convert_value_from_dynamodb(
                            value, field
                        )
                        self._field_values[field.name] = converted_value
                        setattr(self._django_instance, field.name, converted_value)

                self._pynamodb_instance = pynamodb_instance

        except DoesNotExist:
            logger.warning(
                f"{self.__class__.__name__} with pk={pk_value} does not exist in DynamoDB"
            )
        except Exception as e:
            logger.error(
                f"Error refreshing {self.__class__.__name__} from DynamoDB: {e}"
            )
            raise

    def __str__(self):
        """String representation of the model."""
        if hasattr(self, "name"):
            return str(self.name)
        elif hasattr(self, "title"):
            return str(self.title)
        else:
            pk_value = self._field_values.get(self._meta.pk.name, "None")
            return f"{self.__class__.__name__}(pk={pk_value})"


# ---------------------------------------------------------------------------
# Example / test models – used by the test suite and demo project.
# Your own models should live in your app, not here.
# ---------------------------------------------------------------------------


class MyModel(DynamoDBModel):
    """Example DynamoDB model."""

    name = models.CharField(primary_key=True, max_length=100)
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published", auto_now_add=True)

    def __str__(self):
        return self.name


class Question(DynamoDBModel):
    """Question model using DynamoDB backend."""

    id = models.AutoField(primary_key=True)
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField("date published", auto_now_add=True)

    def __str__(self):
        return self.question_text

    @admin.display(
        boolean=True,
        ordering="pub_date",
        description="Published recently?",
    )
    def was_published_recently(self):
        now = timezone.now()
        return now - datetime.timedelta(days=1) <= self.pub_date <= now


class Choice(DynamoDBModel):
    """Choice model using DynamoDB backend."""

    id = models.AutoField(primary_key=True)
    question_id = models.CharField(max_length=50)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)

    def __str__(self):
        return self.choice_text

    @property
    def question(self):
        """Get the related Question object."""
        try:
            return Question.objects.get(id=self.question_id)
        except Question.DoesNotExist:
            return None
