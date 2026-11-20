from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

def health_check(request):
    return JsonResponse({"status": "healthy", "service": "harvesthub-backend"})

urlpatterns = [
    path("healthz", health_check),
    path("healthz/", health_check),
    path("admin/", admin.site.urls),
    path("api/", include("farm.urls")),
]
