from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F


class FarmerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="farmer_profile")
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30, blank=True)
    farm_location = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.full_name or self.user.username

    class Meta:
        db_table = "harvesthub_farmer_profile"


class OwnedModel(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)ss")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Field(OwnedModel):
    class AreaUnit(models.TextChoices):
        ACRES = "acres", "Acres"
        HECTARES = "hectares", "Hectares"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        FALLOW = "fallow", "Fallow"
        PREPARING = "preparing", "Preparing"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=120)
    location = models.CharField(max_length=255, blank=True)
    area = models.DecimalField(max_digits=10, decimal_places=2)
    area_unit = models.CharField(max_length=12, choices=AreaUnit.choices, default=AreaUnit.ACRES)
    soil_type = models.CharField(max_length=80, blank=True)
    irrigation_type = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "harvesthub_field"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_field_name_per_farmer")]
        indexes = [models.Index(fields=["owner", "status"])]

    def __str__(self):
        return self.name


class CropPlan(OwnedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        GROWING = "growing", "Growing"
        HARVESTED = "harvested", "Harvested"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="crop_plans")
    crop_name = models.CharField(max_length=120)
    crop_category = models.CharField(max_length=80, blank=True)
    planting_date = models.DateField()
    expected_harvest_date = models.DateField()
    actual_harvest_date = models.DateField(null=True, blank=True)
    season = models.CharField(max_length=60, blank=True)
    expected_yield = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_yield = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    yield_unit = models.CharField(max_length=30, default="kg")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_crop_plan"
        ordering = ["-planting_date"]
        indexes = [models.Index(fields=["owner", "field", "planting_date"]), models.Index(fields=["owner", "status"])]

    def clean(self):
        if self.expected_harvest_date < self.planting_date:
            raise ValidationError({"expected_harvest_date": "Expected harvest cannot precede planting."})
        if self.actual_harvest_date and self.actual_harvest_date < self.planting_date:
            raise ValidationError({"actual_harvest_date": "Actual harvest cannot precede planting."})

    def __str__(self):
        return f"{self.crop_name} — {self.field.name}"


class CropRotationHistory(OwnedModel):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="rotation_history")
    previous_crop = models.CharField(max_length=120)
    next_crop = models.CharField(max_length=120)
    rotation_date = models.DateField()
    note = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_crop_rotation_history"
        ordering = ["-rotation_date"]
        indexes = [models.Index(fields=["owner", "field", "rotation_date"])]


class Equipment(OwnedModel):
    class Type(models.TextChoices):
        TRACTOR = "tractor", "Tractor"
        HARVESTER = "harvester", "Harvester"
        WATER_PUMP = "water_pump", "Water Pump"
        SEEDER = "seeder", "Seeder"
        SPRAYER = "sprayer", "Sprayer"
        CULTIVATOR = "cultivator", "Cultivator"
        OTHER = "other", "Other Equipment"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        IN_USE = "in_use", "In Use"
        MAINTENANCE = "maintenance", "Under Maintenance"
        RETIRED = "retired", "Retired"

    name = models.CharField(max_length=120)
    equipment_type = models.CharField(max_length=20, choices=Type.choices, default=Type.OTHER)
    model = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    usage_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_maintenance_date = models.DateField(null=True, blank=True)
    next_maintenance_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "harvesthub_equipment"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_equipment_name_per_farmer")]
        indexes = [models.Index(fields=["owner", "status"])]


class FieldOperation(OwnedModel):
    class OperationType(models.TextChoices):
        LAND_PREPARATION = "land_preparation", "Land Preparation"
        SOWING = "sowing", "Sowing"
        IRRIGATION = "irrigation", "Irrigation"
        FERTILIZER = "fertilizer", "Fertilizer Application"
        PESTICIDE = "pesticide", "Pesticide Application"
        WEEDING = "weeding", "Weeding"
        HARVESTING = "harvesting", "Harvesting"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=120)
    operation_type = models.CharField(max_length=25, choices=OperationType.choices, default=OperationType.OTHER)
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="operations")
    crop = models.ForeignKey(CropPlan, on_delete=models.SET_NULL, related_name="operations", null=True, blank=True)
    scheduled_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.SET_NULL, related_name="operations", null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_field_operation"
        ordering = ["scheduled_date"]
        indexes = [models.Index(fields=["owner", "scheduled_date", "status"])]

    def clean(self):
        if self.completion_date and self.completion_date < self.scheduled_date:
            raise ValidationError({"completion_date": "Completion cannot precede scheduled date."})


class AgriculturalExpense(OwnedModel):
    class Category(models.TextChoices):
        SEEDS = "seeds", "Seeds"
        FERTILIZERS = "fertilizers", "Fertilizers"
        PESTICIDES = "pesticides", "Pesticides"
        IRRIGATION = "irrigation", "Irrigation"
        LABOUR = "labour", "Labour"
        FUEL = "fuel", "Fuel"
        MAINTENANCE = "maintenance", "Equipment Maintenance"
        OTHER = "other", "Other Agricultural Expense"

    category = models.CharField(max_length=20, choices=Category.choices)
    field = models.ForeignKey(Field, on_delete=models.SET_NULL, related_name="expenses", null=True, blank=True)
    crop = models.ForeignKey(CropPlan, on_delete=models.SET_NULL, related_name="expenses", null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "harvesthub_agricultural_expense"
        ordering = ["-date"]
        indexes = [models.Index(fields=["owner", "date", "category"])]


class HarvestRecord(OwnedModel):
    crop = models.ForeignKey(CropPlan, on_delete=models.PROTECT, related_name="harvest_records")
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="harvest_records")
    harvest_date = models.DateField()
    harvested_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    yield_unit = models.CharField(max_length=30, default="kg")
    expected_yield = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    selling_price_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_harvest_record"
        ordering = ["-harvest_date"]
        indexes = [models.Index(fields=["owner", "harvest_date"]), models.Index(fields=["owner", "crop"])]

    @property
    def revenue(self):
        return self.harvested_quantity * self.selling_price_per_unit if self.selling_price_per_unit is not None else None

    @property
    def yield_per_area(self):
        return self.harvested_quantity / self.field.area if self.field.area else None


class EquipmentUsage(OwnedModel):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="usage_entries")
    operation = models.ForeignKey(FieldOperation, on_delete=models.SET_NULL, related_name="usage_entries", null=True, blank=True)
    usage_date = models.DateField()
    hours = models.DecimalField(max_digits=8, decimal_places=2)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_equipment_usage"
        ordering = ["-usage_date"]
        indexes = [models.Index(fields=["owner", "equipment", "usage_date"])]


class EquipmentMaintenance(OwnedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name="maintenance_records")
    maintenance_type = models.CharField(max_length=120)
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    maintenance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        db_table = "harvesthub_equipment_maintenance"
        ordering = ["scheduled_date"]
        indexes = [models.Index(fields=["owner", "scheduled_date", "status"])]


class InventoryItem(OwnedModel):
    class Category(models.TextChoices):
        SEEDS = "seeds", "Seeds"
        FERTILIZERS = "fertilizers", "Fertilizers"
        PESTICIDES = "pesticides", "Pesticides"
        FUEL = "fuel", "Fuel"
        SPARE_PARTS = "spare_parts", "Equipment Spare Parts"
        OTHER = "other", "Other Supplies"

    item_name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=Category.choices)
    quantity_available = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    measurement_unit = models.CharField(max_length=30)
    minimum_stock_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.CharField(max_length=120, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "harvesthub_inventory_item"
        ordering = ["item_name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "item_name"], name="unique_inventory_name_per_farmer"),
            models.CheckConstraint(condition=models.Q(quantity_available__gte=0), name="inventory_quantity_nonnegative"),
        ]
        indexes = [models.Index(fields=["owner", "category"])]

    @property
    def is_low_stock(self):
        return self.quantity_available <= self.minimum_stock_level


class InventoryTransaction(OwnedModel):
    class TransactionType(models.TextChoices):
        STOCK_IN = "stock_in", "Stock In"
        STOCK_OUT = "stock_out", "Stock Out"

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateField()
    note = models.TextField(blank=True)

    class Meta:
        db_table = "harvesthub_inventory_transaction"
        ordering = ["-transaction_date", "-id"]
        indexes = [models.Index(fields=["owner", "item", "transaction_date"])]

    def clean(self):
        if self.quantity <= Decimal("0"):
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
