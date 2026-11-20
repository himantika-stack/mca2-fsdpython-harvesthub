from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("fields", views.FieldViewSet, basename="field")
router.register("crops", views.CropPlanViewSet, basename="crop")
router.register("crop-rotations", views.CropRotationViewSet, basename="crop-rotation")
router.register("operations", views.FieldOperationViewSet, basename="operation")
router.register("expenses", views.ExpenseViewSet, basename="expense")
router.register("yields", views.HarvestRecordViewSet, basename="yield")
router.register("equipment", views.EquipmentViewSet, basename="equipment")
router.register("equipment-usage", views.EquipmentUsageViewSet, basename="equipment-usage")
router.register("maintenance", views.MaintenanceViewSet, basename="maintenance")
router.register("inventory", views.InventoryItemViewSet, basename="inventory")
router.register("inventory-transactions", views.InventoryTransactionViewSet, basename="inventory-transaction")

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/csrf", views.csrf),
    path("auth/register/", views.register),
    path("auth/register", views.register),
    path("auth/login/", views.login_view),
    path("auth/login", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/logout", views.logout_view),
    path("profile/", views.profile_view),
    path("profile", views.profile_view),
    path("dashboard/", views.dashboard),
    path("dashboard", views.dashboard),
    path("forecast/", views.forecast),
    path("forecast", views.forecast),
    path("reports/", views.reports),
    path("reports", views.reports),
    path("reports/export/", views.export_csv),
    path("reports/export", views.export_csv),
    path("", include(router.urls)),
]
