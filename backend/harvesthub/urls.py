from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connections
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    # The original health check only proved that Gunicorn had started. Verify the
    # dependency required by every authenticated endpoint as well, so a broken
    # database cannot make Render report the service as healthy.
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
        # Authentication depends on this table. Checking it also catches a
        # database that is reachable but has not received Django migrations.
        get_user_model().objects.exists()
    except DatabaseError:
        return JsonResponse(
            {"status": "unhealthy", "service": "harvesthub-backend", "database": "unavailable"},
            status=503,
        )
    return JsonResponse({"status": "healthy", "service": "harvesthub-backend"})

urlpatterns = [
    path("healthz", health_check),
    path("healthz/", health_check),
    path("admin/", admin.site.urls),
    path("api/", include("farm.urls")),
]
