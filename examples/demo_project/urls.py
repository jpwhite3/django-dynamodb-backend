# Interactive Demo URLs

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", admin.site.urls),  # Redirect root to admin for demo
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site header
admin.site.site_header = "Django DynamoDB Admin Demo"
admin.site.site_title = "DynamoDB Admin"
admin.site.index_title = "Interactive Demo Dashboard"
