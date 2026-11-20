from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import CropPlan, Field, InventoryItem


class FarmerOwnershipTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user("alice", "alice@example.com", "SafePass123!")
        self.bob = User.objects.create_user("bob", "bob@example.com", "SafePass123!")
        self.alice_field = Field.objects.create(owner=self.alice, name="Alice Field", area=2, area_unit="acres")
        self.bob_field = Field.objects.create(owner=self.bob, name="Bob Field", area=3, area_unit="acres")

    def test_farmer_cannot_read_or_use_another_farmers_field(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(f"/api/fields/{self.bob_field.id}/")
        self.assertEqual(response.status_code, 404)
        response = self.client.post("/api/crops/", {
            "field": self.bob_field.id, "crop_name": "Rice", "planting_date": "2026-06-01",
            "expected_harvest_date": "2026-10-01", "status": "planned",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CropPlan.objects.filter(owner=self.alice, crop_name="Rice").exists())

    def test_inventory_stock_out_cannot_be_negative(self):
        item = InventoryItem.objects.create(owner=self.alice, item_name="Seed", category="seeds", quantity_available=Decimal("4"), measurement_unit="kg", minimum_stock_level=1, unit_cost=2)
        self.client.force_authenticate(self.alice)
        response = self.client.post("/api/inventory-transactions/", {
            "item": item.id, "transaction_type": "stock_out", "quantity": "5", "transaction_date": str(date.today()),
        }, format="json")
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.quantity_available, Decimal("4"))

    def test_crop_plan_overlap_is_rejected(self):
        CropPlan.objects.create(owner=self.alice, field=self.alice_field, crop_name="Wheat", planting_date=date.today(), expected_harvest_date=date.today() + timedelta(days=100))
        self.client.force_authenticate(self.alice)
        response = self.client.post("/api/crops/", {
            "field": self.alice_field.id, "crop_name": "Corn", "planting_date": str(date.today() + timedelta(days=20)),
            "expected_harvest_date": str(date.today() + timedelta(days=120)), "status": "planned",
        }, format="json")
        self.assertEqual(response.status_code, 400)
