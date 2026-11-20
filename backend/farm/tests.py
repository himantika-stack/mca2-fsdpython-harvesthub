from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import (
    AgriculturalExpense, CropPlan, CropRotationHistory, Equipment,
    EquipmentMaintenance, Field, FieldOperation, HarvestRecord,
    InventoryItem, InventoryTransaction
)

User = get_user_model()


class FarmerOwnershipTests(APITestCase):
    def setUp(self):
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
        item = InventoryItem.objects.create(
            owner=self.alice, item_name="Seed", category="seeds",
            quantity_available=Decimal("4"), measurement_unit="kg",
            minimum_stock_level=1, unit_cost=2
        )
        self.client.force_authenticate(self.alice)
        response = self.client.post("/api/inventory-transactions/", {
            "item": item.id, "transaction_type": "stock_out", "quantity": "5",
            "transaction_date": str(date.today()),
        }, format="json")
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.quantity_available, Decimal("4"))

    def test_crop_plan_overlap_is_rejected(self):
        CropPlan.objects.create(
            owner=self.alice, field=self.alice_field, crop_name="Wheat",
            planting_date=date.today(),
            expected_harvest_date=date.today() + timedelta(days=100)
        )
        self.client.force_authenticate(self.alice)
        response = self.client.post("/api/crops/", {
            "field": self.alice_field.id, "crop_name": "Corn",
            "planting_date": str(date.today() + timedelta(days=20)),
            "expected_harvest_date": str(date.today() + timedelta(days=120)),
            "status": "planned",
        }, format="json")
        self.assertEqual(response.status_code, 400)


class FullPlatformFeatureTests(APITestCase):
    def test_healthz_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "healthy")

    def test_csrf_cookie_endpoint(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("csrfToken", data)
        self.assertIn("csrftoken", response.cookies)

    def test_farmer_registration_flow(self):
        # Registration succeeds with JSON response and sets session
        reg_data = {
            "full_name": "Green Acres Farmer",
            "username": "greenfarmer",
            "email": "farmer@greenacres.farm",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
            "phone_number": "+919876543210",
            "farm_location": "Punjab, India",
        }
        response = self.client.post("/api/auth/register/", reg_data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers.get("content-type"), "application/json")
        self.assertEqual(response.json()["user"]["username"], "greenfarmer")
        self.assertEqual(response.json()["user"]["full_name"], "Green Acres Farmer")

        # Duplicate username is rejected with clean 400 JSON
        response = self.client.post("/api/auth/register/", reg_data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers.get("content-type"), "application/json")
        self.assertIn("username", response.json())

    def test_login_logout_and_profile_flow(self):
        User.objects.create_user("loginfarmer", "login@farm.org", "FarmerSecret123!")

        # Login with valid credentials
        login_res = self.client.post("/api/auth/login/", {
            "username": "loginfarmer",
            "password": "FarmerSecret123!",
        }, format="json")
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("user", login_res.json())

        # Read Profile
        prof_res = self.client.get("/api/profile/")
        self.assertEqual(prof_res.status_code, 200)
        self.assertEqual(prof_res.json()["username"], "loginfarmer")

        # Update Profile
        patch_res = self.client.patch("/api/profile/", {
            "farm_location": "Haryana, India",
            "phone_number": "+918888888888"
        }, format="json")
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["farm_location"], "Haryana, India")

        # Logout
        logout_res = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_res.status_code, 204)

    def test_field_and_crop_management(self):
        farmer = User.objects.create_user("fieldfarmer", "field@farm.org", "Pass12345!")
        self.client.force_authenticate(farmer)

        # Create field
        field_res = self.client.post("/api/fields/", {
            "name": "North Field",
            "area": "10.5",
            "area_unit": "acres",
            "soil_type": "Loam",
            "status": "active"
        }, format="json")
        self.assertEqual(field_res.status_code, 201)
        field_id = field_res.json()["id"]

        # Plan crop
        today_date = date.today()
        crop_res = self.client.post("/api/crops/", {
            "crop_name": "Wheat HD-2967",
            "field": field_id,
            "planting_date": str(today_date),
            "expected_harvest_date": str(today_date + timedelta(days=120)),
            "expected_yield": "5000.00",
            "yield_unit": "kg",
            "status": "planned"
        }, format="json")
        self.assertEqual(crop_res.status_code, 201)
        crop_id = crop_res.json()["id"]

        # Record operation
        op_res = self.client.post("/api/operations/", {
            "name": "Primary Tillage",
            "field": field_id,
            "crop": crop_id,
            "operation_type": "land_preparation",
            "scheduled_date": str(today_date),
            "status": "completed"
        }, format="json")
        self.assertEqual(op_res.status_code, 201)

        # Record expense
        exp_res = self.client.post("/api/expenses/", {
            "category": "seeds",
            "field": field_id,
            "crop": crop_id,
            "amount": "12500.00",
            "date": str(today_date),
            "description": "High yield certified seeds"
        }, format="json")
        self.assertEqual(exp_res.status_code, 201)

        # Record yield
        yield_res = self.client.post("/api/yields/", {
            "field": field_id,
            "crop": crop_id,
            "harvest_date": str(today_date),
            "harvested_quantity": "5200.00",
            "yield_unit": "kg",
            "selling_price_per_unit": "25.00"
        }, format="json")
        self.assertEqual(yield_res.status_code, 201)

        # Equipment and maintenance
        eq_res = self.client.post("/api/equipment/", {
            "name": "Mahindra 575 DI",
            "equipment_type": "tractor",
            "manufacturer": "Mahindra",
            "status": "available"
        }, format="json")
        self.assertEqual(eq_res.status_code, 201)
        eq_id = eq_res.json()["id"]

        maint_res = self.client.post("/api/maintenance/", {
            "equipment": eq_id,
            "maintenance_type": "Engine Oil Replacement",
            "scheduled_date": str(today_date + timedelta(days=15)),
            "maintenance_cost": "3500.00",
            "status": "scheduled"
        }, format="json")
        self.assertEqual(maint_res.status_code, 201)

        # Inventory management
        inv_res = self.client.post("/api/inventory/", {
            "item_name": "Urea Fertilizer",
            "category": "fertilizers",
            "quantity_available": "50.00",
            "measurement_unit": "bags",
            "minimum_stock_level": "10.00",
            "unit_cost": "300.00"
        }, format="json")
        self.assertEqual(inv_res.status_code, 201)
        inv_id = inv_res.json()["id"]

        # Stock transaction
        tx_res = self.client.post("/api/inventory-transactions/", {
            "item": inv_id,
            "transaction_type": "stock_out",
            "quantity": "5.00",
            "transaction_date": str(today_date),
            "note": "Field application"
        }, format="json")
        self.assertEqual(tx_res.status_code, 201)

        # Dashboard analytics returns populated calculations
        dash_res = self.client.get("/api/dashboard/")
        self.assertEqual(dash_res.status_code, 200)
        summary = dash_res.json()["summary"]
        self.assertEqual(summary["total_fields"], 1)
        self.assertEqual(summary["available_equipment"], 1)

        # Reports and Analytics
        rep_res = self.client.get("/api/reports/")
        self.assertEqual(rep_res.status_code, 200)
        self.assertIn("profitability", rep_res.json())

        # CSV Export
        csv_res = self.client.get("/api/reports/export/?type=expenses")
        self.assertEqual(csv_res.status_code, 200)
        self.assertEqual(csv_res.headers.get("content-type"), "text/csv")
        self.assertIn(b"High yield certified seeds", csv_res.content)
