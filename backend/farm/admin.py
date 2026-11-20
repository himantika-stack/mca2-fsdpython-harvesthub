from django.contrib import admin

from .models import (
    AgriculturalExpense, CropPlan, CropRotationHistory, Equipment, EquipmentMaintenance,
    EquipmentUsage, FarmerProfile, Field, FieldOperation, HarvestRecord, InventoryItem,
    InventoryTransaction,
)


@admin.register(FarmerProfile)
class FarmerProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone_number", "farm_location")
    search_fields = ("full_name", "user__username", "user__email")


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "area", "area_unit", "status")
    list_filter = ("status", "area_unit")
    search_fields = ("name", "location", "owner__username")


@admin.register(CropPlan)
class CropPlanAdmin(admin.ModelAdmin):
    list_display = ("crop_name", "field", "owner", "planting_date", "expected_harvest_date", "status")
    list_filter = ("status", "season")


for model in (CropRotationHistory, FieldOperation, AgriculturalExpense, HarvestRecord, Equipment,
              EquipmentUsage, EquipmentMaintenance, InventoryItem, InventoryTransaction):
    admin.site.register(model)
