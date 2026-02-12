"""
Django DynamoDB Admin - Setup Configuration

A comprehensive Django application that provides complete Django Admin integration
with Amazon DynamoDB, including enhanced admin features and DynamoDB-specific optimizations.
"""

import os

from setuptools import find_packages, setup


# Read the README file
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding="utf-8") as f:
        return f.read()


# Read requirements
def read_requirements(filename):
    with open(filename, "r") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#") and not line.startswith("-")
        ]


setup(
    name="django-dynamodb-admin",
    version="1.0.0",
    description="Complete Django Admin integration with Amazon DynamoDB",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    author="Django DynamoDB Admin Contributors",
    author_email="contributors@django-dynamodb-admin.org",
    url="https://github.com/your-org/django-dynamo-admin",
    project_urls={
        "Documentation": "https://django-dynamo-admin.readthedocs.io",
        "Source": "https://github.com/your-org/django-dynamo-admin",
        "Tracker": "https://github.com/your-org/django-dynamo-admin/issues",
        "Discussions": "https://github.com/your-org/django-dynamo-admin/discussions",
    },
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.8",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements-dev.txt"),
        "redis": ["redis>=5.0.0"],
        "monitoring": ["django-debug-toolbar>=4.2.0"],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 4.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Database",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
    ],
    keywords=[
        "django",
        "dynamodb",
        "amazon",
        "aws",
        "admin",
        "orm",
        "database",
        "nosql",
        "web",
        "framework",
    ],
    entry_points={
        "console_scripts": [
            "django-dynamodb-admin=dynamodb_adapter.management.commands.dynamodb_performance:main",
        ],
    },
    package_data={
        "dynamodb_adapter": [
            "templates/admin/*.html",
            "templates/admin/dynamodb_adapter/*.html",
            "static/admin/dynamodb_adapter/css/*.css",
            "static/admin/dynamodb_adapter/js/*.js",
            "management/commands/*.py",
        ],
    },
)
