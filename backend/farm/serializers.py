from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from .models import (
    AgriculturalExpense, CropPlan, CropRotationHistory, Equipment, EquipmentMaintenance,
    EquipmentUsage, FarmerProfile, Field, FieldOperation, HarvestRecord, InventoryItem,
    InventoryTransaction,
)

User = get_user_model()


class RegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    farm_location = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        profile_values = {key: validated_data.pop(key, "") for key in ("full_name", "phone_number", "farm_location")}
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        FarmerProfile.objects.create(user=user, **profile_values)
        return user


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = FarmerProfile
        fields = ["full_name", "phone_number", "farm_location", "username", "email"]


class OwnedModelSerializer(serializers.ModelSerializer):
    """Ensures every foreign-key record supplied to a farmer belongs to that farmer."""
    owner_related_fields = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["request"].user
        for field_name in self.owner_related_fields:
            value = attrs.get(field_name, getattr(self.instance, field_name, None))
            if value is not None and value.owner_id != user.id:
                raise serializers.ValidationError({field_name: "Select one of your own records."})
        return attrs

    def create(self, validated_data):
        return super().create({**validated_data, "owner": self.context["request"].user})


class FieldSerializer(OwnedModelSerializer):
    active_crop = serializers.SerializerMethodField()

    class Meta:
        model = Field
        fields = ["id", "name", "location", "area", "area_unit", "soil_type", "irrigation_type", "status", "latitude", "longitude", "boundary_geojson", "active_crop", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def get_active_crop(self, obj):
        crop = obj.crop_plans.filter(status__in=[CropPlan.Status.PLANNED, CropPlan.Status.GROWING]).order_by("planting_date").first()
        return CropPlanCompactSerializer(crop).data if crop else None

    def validate_area(self, value):
        if value <= 0:
            raise serializers.ValidationError("Area must be greater than zero.")
        return value


class CropPlanCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropPlan
        fields = ["id", "crop_name", "status", "planting_date", "expected_harvest_date"]


class CropPlanSerializer(OwnedModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    owner_related_fields = ("field",)

    class Meta:
        model = CropPlan
        fields = ["id", "field", "field_name", "crop_name", "crop_category", "planting_date", "expected_harvest_date", "actual_harvest_date", "season", "expected_yield", "actual_yield", "yield_unit", "status", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        field = attrs.get("field", getattr(self.instance, "field", None))
        planting = attrs.get("planting_date", getattr(self.instance, "planting_date", None))
        harvest = attrs.get("expected_harvest_date", getattr(self.instance, "expected_harvest_date", None))
        if field and planting and harvest:
            actual = attrs.get("actual_harvest_date", getattr(self.instance, "actual_harvest_date", None))
            if harvest < planting:
                raise serializers.ValidationError({"expected_harvest_date": "Expected harvest cannot precede planting."})
            if actual and actual < planting:
                raise serializers.ValidationError({"actual_harvest_date": "Actual harvest cannot precede planting."})
            overlap = CropPlan.objects.filter(
                owner=self.context["request"].user, field=field,
                planting_date__lte=harvest, expected_harvest_date__gte=planting,
            ).exclude(status__in=[CropPlan.Status.CANCELLED, CropPlan.Status.FAILED])
            if self.instance:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                raise serializers.ValidationError({"field": "This crop schedule overlaps an existing active plan in the field."})
        return attrs


class CropRotationSerializer(OwnedModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    owner_related_fields = ("field",)

    class Meta:
        model = CropRotationHistory
        fields = ["id", "field", "field_name", "previous_crop", "next_crop", "rotation_date", "note", "created_at"]
        read_only_fields = ["created_at"]


class EquipmentSerializer(OwnedModelSerializer):
    class Meta:
        model = Equipment
        fields = ["id", "name", "equipment_type", "model", "manufacturer", "purchase_date", "purchase_cost", "status", "usage_hours", "last_maintenance_date", "next_maintenance_date", "created_at", "updated_at"]
        read_only_fields = ["usage_hours", "created_at", "updated_at"]


class FieldOperationSerializer(OwnedModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    crop_name = serializers.CharField(source="crop.crop_name", read_only=True)
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)
    owner_related_fields = ("field", "crop", "equipment")

    class Meta:
        model = FieldOperation
        fields = ["id", "name", "operation_type", "field", "field_name", "crop", "crop_name", "scheduled_date", "completion_date", "equipment", "equipment_name", "estimated_cost", "actual_cost", "status", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        crop = attrs.get("crop", getattr(self.instance, "crop", None))
        field = attrs.get("field", getattr(self.instance, "field", None))
        if crop and field and crop.field_id != field.id:
            raise serializers.ValidationError({"crop": "Selected crop belongs to a different field."})
        scheduled = attrs.get("scheduled_date", getattr(self.instance, "scheduled_date", None))
        completed = attrs.get("completion_date", getattr(self.instance, "completion_date", None))
        if scheduled and completed and completed < scheduled:
            raise serializers.ValidationError({"completion_date": "Completion cannot precede the scheduled date."})
        return attrs

    def validate_estimated_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Cost cannot be negative.")
        return value

    def validate_actual_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Cost cannot be negative.")
        return value


class ExpenseSerializer(OwnedModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)
    crop_name = serializers.CharField(source="crop.crop_name", read_only=True)
    owner_related_fields = ("field", "crop")

    class Meta:
        model = AgriculturalExpense
        fields = ["id", "category", "field", "field_name", "crop", "crop_name", "amount", "date", "description", "quantity", "unit", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        crop = attrs.get("crop", getattr(self.instance, "crop", None))
        field = attrs.get("field", getattr(self.instance, "field", None))
        if crop and field and crop.field_id != field.id:
            raise serializers.ValidationError({"crop": "Selected crop belongs to a different field."})
        return attrs

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class HarvestRecordSerializer(OwnedModelSerializer):
    crop_name = serializers.CharField(source="crop.crop_name", read_only=True)
    field_name = serializers.CharField(source="field.name", read_only=True)
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    yield_per_area = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    owner_related_fields = ("crop", "field")

    class Meta:
        model = HarvestRecord
        fields = ["id", "crop", "crop_name", "field", "field_name", "harvest_date", "harvested_quantity", "yield_unit", "expected_yield", "selling_price_per_unit", "revenue", "yield_per_area", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        crop = attrs.get("crop", getattr(self.instance, "crop", None))
        field = attrs.get("field", getattr(self.instance, "field", None))
        if crop and field and crop.field_id != field.id:
            raise serializers.ValidationError({"field": "Harvest field must match the crop's field."})
        return attrs

    def validate_harvested_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Harvest quantity must be greater than zero.")
        return value

    def validate_selling_price_per_unit(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Selling price cannot be negative.")
        return value


class EquipmentUsageSerializer(OwnedModelSerializer):
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)
    owner_related_fields = ("equipment", "operation")

    class Meta:
        model = EquipmentUsage
        fields = ["id", "equipment", "equipment_name", "operation", "usage_date", "hours", "note", "created_at"]
        read_only_fields = ["created_at"]

    @transaction.atomic
    def create(self, validated_data):
        entry = super().create(validated_data)
        Equipment.objects.filter(pk=entry.equipment_id).update(usage_hours=F("usage_hours") + entry.hours)
        entry.equipment.refresh_from_db(fields=["usage_hours"])
        return entry

    def validate_hours(self, value):
        if value <= 0:
            raise serializers.ValidationError("Usage hours must be greater than zero.")
        return value


class MaintenanceSerializer(OwnedModelSerializer):
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)
    owner_related_fields = ("equipment",)

    class Meta:
        model = EquipmentMaintenance
        fields = ["id", "equipment", "equipment_name", "maintenance_type", "scheduled_date", "completed_date", "maintenance_cost", "description", "status", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def update(self, instance, validated_data):
        record = super().update(instance, validated_data)
        if record.status == EquipmentMaintenance.Status.COMPLETED and record.completed_date:
            Equipment.objects.filter(pk=record.equipment_id).update(
                last_maintenance_date=record.completed_date,
                status=Equipment.Status.AVAILABLE,
            )
        return record

    def validate_maintenance_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Maintenance cost cannot be negative.")
        return value


class InventoryItemSerializer(OwnedModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = ["id", "item_name", "category", "quantity_available", "measurement_unit", "minimum_stock_level", "unit_cost", "supplier", "purchase_date", "expiry_date", "is_low_stock", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_quantity_available(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity cannot be negative.")
        return value

    def validate_minimum_stock_level(self, value):
        if value < 0:
            raise serializers.ValidationError("Minimum stock level cannot be negative.")
        return value

    def validate_unit_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit cost cannot be negative.")
        return value


class InventoryTransactionSerializer(OwnedModelSerializer):
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    owner_related_fields = ("item",)

    class Meta:
        model = InventoryTransaction
        fields = ["id", "item", "item_name", "transaction_type", "quantity", "transaction_date", "note", "created_at"]
        read_only_fields = ["created_at"]

    @transaction.atomic
    def create(self, validated_data):
        owner = self.context["request"].user
        item = InventoryItem.objects.select_for_update().get(pk=validated_data["item"].pk, owner=owner)
        quantity = validated_data["quantity"]
        if validated_data["transaction_type"] == InventoryTransaction.TransactionType.STOCK_OUT:
            if item.quantity_available < quantity:
                raise serializers.ValidationError({"quantity": "Stock out would make inventory negative."})
            item.quantity_available = F("quantity_available") - quantity
        else:
            item.quantity_available = F("quantity_available") + quantity
        item.save(update_fields=["quantity_available", "updated_at"])
        validated_data["item"] = item
        return super().create(validated_data)
