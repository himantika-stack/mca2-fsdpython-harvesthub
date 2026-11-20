from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from farm.models import (
    AgriculturalExpense, CropPlan, Equipment, EquipmentMaintenance, FarmerProfile, Field,
    FieldOperation, HarvestRecord, InventoryItem,
)


class Command(BaseCommand):
    help = "Creates idempotent, clearly synthetic demo farm records for one named demo account."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=options["username"],
            defaults={"email": options["email"]},
        )
        if not created and user.email != options["email"]:
            raise CommandError("That username already belongs to a different account. Choose a distinct demo username.")
        if created:
            user.set_password(options["password"])
            user.save(update_fields=["password"])
        FarmerProfile.objects.get_or_create(
            user=user,
            defaults={"full_name": "Demo Farmer (Synthetic Data)", "farm_location": "Nashik, Maharashtra"},
        )

        north, _ = Field.objects.get_or_create(
            owner=user, name="North Plot (Demo)",
            defaults={"location": "Nashik, Maharashtra", "area": Decimal("4.50"), "area_unit": "acres", "soil_type": "Loamy", "irrigation_type": "Drip"},
        )
        east, _ = Field.objects.get_or_create(
            owner=user, name="East Orchard (Demo)",
            defaults={"location": "Nashik, Maharashtra", "area": Decimal("2.00"), "area_unit": "acres", "soil_type": "Sandy loam", "irrigation_type": "Sprinkler"},
        )
        tomato, _ = CropPlan.objects.get_or_create(
            owner=user, field=north, crop_name="Tomato (Demo)", planting_date=date.today() - timedelta(days=35),
            defaults={"crop_category": "Vegetable", "expected_harvest_date": date.today() + timedelta(days=55), "season": "Rabi", "expected_yield": Decimal("3500"), "yield_unit": "kg", "status": CropPlan.Status.GROWING},
        )
        historical_tomato, _ = CropPlan.objects.get_or_create(
            owner=user, field=east, crop_name="Tomato (Demo Harvest 2025)", planting_date=date.today() - timedelta(days=300),
            defaults={"crop_category": "Vegetable", "expected_harvest_date": date.today() - timedelta(days=200), "actual_harvest_date": date.today() - timedelta(days=200), "season": "Rabi", "expected_yield": Decimal("3000"), "actual_yield": Decimal("2700"), "yield_unit": "kg", "status": CropPlan.Status.HARVESTED},
        )
        Equipment.objects.get_or_create(
            owner=user, name="Compact Tractor (Demo)",
            defaults={"equipment_type": Equipment.Type.TRACTOR, "manufacturer": "Demo Equipment Co.", "status": Equipment.Status.AVAILABLE, "usage_hours": Decimal("128.5")},
        )
        tractor = Equipment.objects.get(owner=user, name="Compact Tractor (Demo)")
        FieldOperation.objects.get_or_create(
            owner=user, name="Tomato drip irrigation (Demo)", scheduled_date=date.today() + timedelta(days=2),
            defaults={"operation_type": FieldOperation.OperationType.IRRIGATION, "field": north, "crop": tomato, "equipment": tractor, "estimated_cost": Decimal("1200"), "status": FieldOperation.Status.PENDING},
        )
        AgriculturalExpense.objects.get_or_create(
            owner=user, category=AgriculturalExpense.Category.FERTILIZERS, field=north, crop=tomato,
            date=date.today() - timedelta(days=10), defaults={"amount": Decimal("2850"), "description": "Synthetic NPK input for demo"},
        )
        HarvestRecord.objects.get_or_create(
            owner=user, field=east, crop=historical_tomato, harvest_date=date.today() - timedelta(days=200),
            defaults={"harvested_quantity": Decimal("2700"), "expected_yield": Decimal("3000"), "yield_unit": "kg", "selling_price_per_unit": Decimal("22")},
        )
        EquipmentMaintenance.objects.get_or_create(
            owner=user, equipment=tractor, maintenance_type="Oil and filter service (Demo)", scheduled_date=date.today() + timedelta(days=14),
            defaults={"maintenance_cost": Decimal("1800"), "status": EquipmentMaintenance.Status.SCHEDULED},
        )
        InventoryItem.objects.get_or_create(
            owner=user, item_name="NPK Fertilizer (Demo)",
            defaults={"category": InventoryItem.Category.FERTILIZERS, "quantity_available": Decimal("35"), "measurement_unit": "kg", "minimum_stock_level": Decimal("40"), "unit_cost": Decimal("34")},
        )
        self.stdout.write(self.style.SUCCESS(f"Synthetic demo data ready for {user.username}. Existing real farmer accounts were not modified."))
