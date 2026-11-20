import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import (
    AgriculturalExpense, CropPlan, CropRotationHistory, Equipment, EquipmentMaintenance,
    EquipmentUsage, FarmerProfile, Field, FieldOperation, HarvestRecord, InventoryItem,
    InventoryTransaction,
)
from .serializers import (
    CropPlanSerializer, CropRotationSerializer, EquipmentSerializer, EquipmentUsageSerializer,
    ExpenseSerializer, FieldOperationSerializer, FieldSerializer, HarvestRecordSerializer,
    InventoryItemSerializer, InventoryTransactionSerializer, MaintenanceSerializer,
    ProfileSerializer, RegistrationSerializer,
)
from .rotation_rules import recommendation_for


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf(request):
    return Response({"detail": "CSRF cookie set.", "csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response({"user": ProfileSerializer(user.farmer_profile).data}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request):
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    profile, _ = FarmerProfile.objects.get_or_create(user=user, defaults={"full_name": user.get_full_name() or user.username})
    return Response({"user": ProfileSerializer(profile).data})


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PATCH"])
def profile_view(request):
    profile, _ = FarmerProfile.objects.get_or_create(
        user=request.user, defaults={"full_name": request.user.get_full_name() or request.user.username}
    )
    if request.method == "PATCH":
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(ProfileSerializer(profile).data)


class FarmerOwnedViewSet(viewsets.ModelViewSet):
    """Defence in depth: rows are constrained by owner before all object lookups."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save()


class FieldViewSet(FarmerOwnedViewSet):
    queryset = Field.objects.all()
    serializer_class = FieldSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get("search")
        status_value = self.request.query_params.get("status")
        if query:
            queryset = queryset.filter(name__icontains=query) | queryset.filter(location__icontains=query)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset.distinct()


class CropPlanViewSet(FarmerOwnedViewSet):
    queryset = CropPlan.objects.select_related("field")
    serializer_class = CropPlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ("field", "status", "season"):
            if value := self.request.query_params.get(key):
                queryset = queryset.filter(**{key: value})
        return queryset


class CropRotationViewSet(FarmerOwnedViewSet):
    queryset = CropRotationHistory.objects.select_related("field")
    serializer_class = CropRotationSerializer

    @action(detail=False, methods=["get"], url_path="recommendations")
    def recommendations(self, request):
        field_id = request.query_params.get("field")
        if not field_id:
            return Response({"detail": "field query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        field = Field.objects.filter(owner=request.user, pk=field_id).first()
        if field is None:
            return Response({"detail": "Field not found."}, status=status.HTTP_404_NOT_FOUND)
        latest_rotation = CropRotationHistory.objects.filter(owner=request.user, field=field).order_by("-rotation_date").first()
        previous_crop = latest_rotation.next_crop if latest_rotation else None
        if previous_crop is None:
            historic_plan = CropPlan.objects.filter(owner=request.user, field=field, status=CropPlan.Status.HARVESTED).order_by("-actual_harvest_date", "-expected_harvest_date").first()
            previous_crop = historic_plan.crop_name if historic_plan else None
        if previous_crop is None:
            return Response({"field": field.name, "available": False, "message": "No crop rotation history exists for this field yet. Record a previous crop first."})
        return Response({"field": field.name, "available": True, "previous_crop": previous_crop, **recommendation_for(previous_crop)})


class FieldOperationViewSet(FarmerOwnedViewSet):
    queryset = FieldOperation.objects.select_related("field", "crop", "equipment")
    serializer_class = FieldOperationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ("field", "crop", "status", "operation_type"):
            if value := self.request.query_params.get(key):
                queryset = queryset.filter(**{key: value})
        start, end = self.request.query_params.get("start"), self.request.query_params.get("end")
        if start:
            queryset = queryset.filter(scheduled_date__gte=start)
        if end:
            queryset = queryset.filter(scheduled_date__lte=end)
        return queryset


class ExpenseViewSet(FarmerOwnedViewSet):
    queryset = AgriculturalExpense.objects.select_related("field", "crop")
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ("field", "crop", "category"):
            if value := self.request.query_params.get(key):
                queryset = queryset.filter(**{key: value})
        start, end = self.request.query_params.get("start"), self.request.query_params.get("end")
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        return queryset


class HarvestRecordViewSet(FarmerOwnedViewSet):
    queryset = HarvestRecord.objects.select_related("field", "crop")
    serializer_class = HarvestRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ("field", "crop"):
            if value := self.request.query_params.get(key):
                queryset = queryset.filter(**{key: value})
        return queryset


class EquipmentViewSet(FarmerOwnedViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if status_value := self.request.query_params.get("status"):
            queryset = queryset.filter(status=status_value)
        return queryset


class EquipmentUsageViewSet(FarmerOwnedViewSet):
    queryset = EquipmentUsage.objects.select_related("equipment", "operation")
    serializer_class = EquipmentUsageSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    @transaction.atomic
    def perform_destroy(self, instance):
        equipment = Equipment.objects.select_for_update().get(pk=instance.equipment_id, owner=self.request.user)
        equipment.usage_hours = max(Decimal("0"), equipment.usage_hours - instance.hours)
        equipment.save(update_fields=["usage_hours", "updated_at"])
        instance.delete()


class MaintenanceViewSet(FarmerOwnedViewSet):
    queryset = EquipmentMaintenance.objects.select_related("equipment")
    serializer_class = MaintenanceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if status_value := self.request.query_params.get("status"):
            queryset = queryset.filter(status=status_value)
        return queryset


class InventoryItemViewSet(FarmerOwnedViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if category := self.request.query_params.get("category"):
            queryset = queryset.filter(category=category)
        if self.request.query_params.get("low_stock") == "true":
            queryset = queryset.filter(quantity_available__lte=F("minimum_stock_level"))
        return queryset


class InventoryTransactionViewSet(FarmerOwnedViewSet):
    queryset = InventoryTransaction.objects.select_related("item")
    serializer_class = InventoryTransactionSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    @transaction.atomic
    def perform_destroy(self, instance):
        item = InventoryItem.objects.select_for_update().get(pk=instance.item_id, owner=self.request.user)
        if instance.transaction_type == InventoryTransaction.TransactionType.STOCK_IN:
            if item.quantity_available < instance.quantity:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"detail": "Cannot remove this stock-in transaction after its stock has been used."})
            item.quantity_available = F("quantity_available") - instance.quantity
        else:
            item.quantity_available = F("quantity_available") + instance.quantity
        item.save(update_fields=["quantity_available", "updated_at"])
        instance.delete()


@api_view(["GET"])
def dashboard(request):
    user = request.user
    today = date.today()
    fields = Field.objects.filter(owner=user)
    crops = CropPlan.objects.filter(owner=user)
    expenses = AgriculturalExpense.objects.filter(owner=user)
    harvests = HarvestRecord.objects.filter(owner=user)
    equipment = Equipment.objects.filter(owner=user)
    operations = FieldOperation.objects.filter(owner=user)
    inventory = InventoryItem.objects.filter(owner=user)
    maintenance = EquipmentMaintenance.objects.filter(owner=user)

    area_acres = Decimal("0")
    area_breakdown = {"acres": Decimal("0"), "hectares": Decimal("0")}
    for item in fields.values("area", "area_unit"):
        area = item["area"] or Decimal("0")
        area_breakdown[item["area_unit"]] += area
        area_acres += area if item["area_unit"] == Field.AreaUnit.ACRES else area * Decimal("2.47105")

    upcoming_operations = operations.filter(scheduled_date__gte=today).exclude(status__in=[FieldOperation.Status.COMPLETED, FieldOperation.Status.CANCELLED]).order_by("scheduled_date")[:8]
    upcoming_maintenance = maintenance.filter(scheduled_date__gte=today).exclude(status__in=[EquipmentMaintenance.Status.COMPLETED, EquipmentMaintenance.Status.CANCELLED]).order_by("scheduled_date")[:8]
    crop_distribution = list(crops.filter(status__in=[CropPlan.Status.PLANNED, CropPlan.Status.GROWING]).values("crop_name").annotate(value=Count("id")).order_by("crop_name"))
    expense_months = list(expenses.extra(select={"month": "DATE_FORMAT(date, '%%Y-%%m')"}).values("month").annotate(value=Sum("amount")).order_by("month"))
    yield_comparison = [{
        "label": f"{record.crop.crop_name} ({record.harvest_date:%d %b})",
        "expected": record.expected_yield,
        "actual": record.harvested_quantity,
        "unit": record.yield_unit,
    } for record in harvests.select_related("crop").order_by("-harvest_date")[:8]]
    equipment_utilization = [{
        "name": item.name,
        "usage_hours": item.usage_hours,
        "status": item.status,
        "maintenance_cost": item.maintenance_records.aggregate(total=Sum("maintenance_cost"))["total"] or Decimal("0"),
    } for item in equipment]

    def activity(kind, item, activity_date, title):
        return {"type": kind, "id": item.id, "date": activity_date, "title": title, "status": item.status}

    activities = [activity("operation", item, item.scheduled_date, item.name) for item in upcoming_operations]
    activities += [activity("maintenance", item, item.scheduled_date, f"{item.equipment.name}: {item.maintenance_type}") for item in upcoming_maintenance]
    activities.sort(key=lambda row: row["date"])

    yield_by_unit = list(harvests.values("yield_unit").annotate(value=Sum("harvested_quantity")).order_by("yield_unit"))
    return Response({
        "summary": {
            "total_fields": fields.count(),
            "total_farm_area_acres": round(area_acres, 2),
            "area_breakdown": area_breakdown,
            "active_crops": crops.filter(status__in=[CropPlan.Status.PLANNED, CropPlan.Status.GROWING]).count(),
            "upcoming_harvests": crops.filter(expected_harvest_date__gte=today, status__in=[CropPlan.Status.PLANNED, CropPlan.Status.GROWING]).count(),
            "total_expenses": expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0"),
            "recorded_yield_by_unit": yield_by_unit,
            "available_equipment": equipment.filter(status=Equipment.Status.AVAILABLE).count(),
            "equipment_under_maintenance": equipment.filter(status=Equipment.Status.MAINTENANCE).count(),
            "inventory_stock_alerts": inventory.filter(quantity_available__lte=F("minimum_stock_level")).count(),
            "upcoming_activities": len(activities),
        },
        "charts": {
            "crop_distribution": crop_distribution,
            "monthly_expenses": expense_months,
            "yield_comparison": yield_comparison,
            "equipment_utilization": equipment_utilization,
        },
        "upcoming_activities": activities,
    })


@api_view(["GET"])
def forecast(request):
    crop_name = request.query_params.get("crop_name", "").strip()
    if not crop_name:
        return Response({"detail": "crop_name query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
    records = HarvestRecord.objects.filter(owner=request.user, crop__crop_name__iexact=crop_name).order_by("-harvest_date")
    if records.count() < 3:
        return Response({"available": False, "message": "At least three historical harvest records are required for a forecast."})
    quantities = list(records.values_list("harvested_quantity", flat=True))
    estimate = sum(quantities, Decimal("0")) / len(quantities)
    return Response({
        "available": True,
        "method": "Simple average of recorded historical harvest quantities",
        "sample_size": len(quantities),
        "crop_name": crop_name,
        "estimated_yield": round(estimate, 2),
        "yield_unit": records.first().yield_unit,
        "disclaimer": "This is a calculated estimate from recorded farmer data, not an agronomic prediction.",
    })


@api_view(["GET"])
def reports(request):
    user = request.user
    start, end = request.query_params.get("start"), request.query_params.get("end")
    field_id, crop_id, category = request.query_params.get("field"), request.query_params.get("crop"), request.query_params.get("category")
    expenses = AgriculturalExpense.objects.filter(owner=user)
    harvests = HarvestRecord.objects.filter(owner=user)
    if start:
        expenses, harvests = expenses.filter(date__gte=start), harvests.filter(harvest_date__gte=start)
    if end:
        expenses, harvests = expenses.filter(date__lte=end), harvests.filter(harvest_date__lte=end)
    if field_id:
        expenses, harvests = expenses.filter(field_id=field_id), harvests.filter(field_id=field_id)
    if crop_id:
        expenses, harvests = expenses.filter(crop_id=crop_id), harvests.filter(crop_id=crop_id)
    if category:
        expenses = expenses.filter(category=category)
    total_expenses = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    revenue = sum((record.revenue or Decimal("0")) for record in harvests)
    by_category = list(expenses.values("category").annotate(total=Sum("amount")).order_by("category"))
    yield_by_crop = list(harvests.values("crop__crop_name", "yield_unit").annotate(total=Sum("harvested_quantity")).order_by("crop__crop_name"))
    return Response({
        "filters": {"start": start, "end": end, "field": field_id, "crop": crop_id, "category": category},
        "field_summary": list(Field.objects.filter(owner=user).values("id", "name", "area", "area_unit", "status")),
        "crop_plans": list(CropPlan.objects.filter(owner=user).values("id", "crop_name", "field__name", "planting_date", "expected_harvest_date", "status")),
        "crop_rotation": list(CropRotationHistory.objects.filter(owner=user).values("field__name", "previous_crop", "next_crop", "rotation_date")),
        "expenses": {"total": total_expenses, "by_category": by_category},
        "yields": {"total_by_crop": yield_by_crop, "records": HarvestRecordSerializer(harvests, many=True).data},
        "equipment": list(Equipment.objects.filter(owner=user).values("name", "equipment_type", "status", "usage_hours")),
        "maintenance": list(EquipmentMaintenance.objects.filter(owner=user).values("equipment__name", "status", "scheduled_date", "maintenance_cost")),
        "inventory": InventoryItemSerializer(InventoryItem.objects.filter(owner=user), many=True).data,
        "profitability": {"recorded_revenue": revenue, "expenses": total_expenses, "estimated_profit": revenue - total_expenses},
    })


@api_view(["GET"])
def export_csv(request):
    report_type = request.query_params.get("type", "expenses")
    data_sets = {
        "expenses": (AgriculturalExpense.objects.filter(owner=request.user).select_related("field", "crop"), ["date", "category", "field", "crop", "amount", "description"]),
        "yields": (HarvestRecord.objects.filter(owner=request.user).select_related("field", "crop"), ["harvest_date", "crop", "field", "harvested_quantity", "yield_unit", "selling_price_per_unit", "revenue"]),
        "inventory": (InventoryItem.objects.filter(owner=request.user), ["item_name", "category", "quantity_available", "measurement_unit", "minimum_stock_level", "unit_cost"]),
        "equipment": (Equipment.objects.filter(owner=request.user), ["name", "equipment_type", "status", "usage_hours", "next_maintenance_date"]),
    }
    if report_type not in data_sets:
        return Response({"detail": "Unsupported report type."}, status=status.HTTP_400_BAD_REQUEST)
    queryset, headers = data_sets[report_type]
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="harvesthub-{report_type}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for record in queryset:
        row = []
        for heading in headers:
            if heading == "field":
                value = record.field.name if getattr(record, "field", None) else ""
            elif heading == "crop":
                value = record.crop.crop_name if getattr(record, "crop", None) else ""
            else:
                value = getattr(record, heading, "")
            row.append(value)
        writer.writerow(row)
    return response
