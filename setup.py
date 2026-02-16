"""
Django DynamoDB Backend - Setup Configuration

A comprehensive Django database backend for Amazon DynamoDB.
"""

import os

from setuptools import find_packages, setup


# Read the README file
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding="utf-8") as f:
        return f.read()


setup(
    name="django-dynamodb-backend",
    version="1.0.0",
    description="A comprehensive Django database backend for Amazon DynamoDB.",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    author="Django DynamoDB Backend Contributors",
    author_email="contributors@django-dynamodb-backend.org",
    url="https://github.com/jpwhite3/django-dynamodb-backend",
    project_urls={
        "Documentation": "https://django-dynamodb-backend.readthedocs.io",
        "Source": "https://github.com/jpwhite3/django-dynamodb-backend",
        "Tracker": "https://github.com/jpwhite3/django-dynamodb-backend/issues",
        "Discussions": "https://github.com/jpwhite3/django-dynamodb-backend/discussions",
    },
    license="MIT",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.11",
    install_requires=[
        "django>=4.2",
        "pynamodb>=6.0.0",
        "boto3>=1.28.0",
        "botocore>=1.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-django>=4.5.0",
            "pytest-cov>=4.0.0",
            "moto>=5.0.0",
            "black>=24.0.0",
            "flake8>=7.0.0",
            "isort>=5.13.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "redis": ["redis>=5.0.0", "django-redis>=5.4.0"],
        "docs": ["sphinx>=7.0.0", "sphinx-rtd-theme>=2.0.0"],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
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
            "django-dynamodb-backend=dynamodb_adapter.management.commands.dynamodb_performance:main",
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
