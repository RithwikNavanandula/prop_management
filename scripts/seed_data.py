"""Seed sample data aligned with current models.

Usage:
    python scripts/seed_data.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, engine, SessionLocal
from app.auth.dependencies import hash_password
from app.auth.models import Role, UserAccount
from app.modules.properties.models import (
    TenantOrg,
    Region,
    Property,
    Building,
    Floor,
    Unit,
    Owner,
    Tenant,
    Vendor,
)


def get_or_create(db, model, defaults=None, **filters):
    defaults = defaults or {}
    instance = db.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    params = {**filters, **defaults}
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def seed_roles(db):
    roles = [
        (1, "admin", "Full system access", {"all": True}),
        (2, "manager", "Property manager", {"properties": True, "leases": True}),
        (3, "owner", "Owner portal", {"portfolio": True}),
        (4, "tenant", "Tenant portal", {"lease": True, "payments": True}),
        (5, "vendor", "Vendor portal", {"work_orders": True}),
        (6, "accountant", "Finance portal", {"billing": True, "accounting": True}),
    ]
    for role_id, role_name, desc, perms in roles:
        role = db.query(Role).filter(Role.id == role_id).first()
        if role:
            continue
        db.add(Role(id=role_id, role_name=role_name, description=desc, permissions=perms, is_system=True))
    db.flush()


def seed_users(db, org_id):
    users = [
        {
            "username": "sample_admin",
            "email": "sample.admin@propman.local",
            "password": "sample123",
            "full_name": "Sample Admin",
            "role_id": 1,
        },
        {
            "username": "sample_manager",
            "email": "sample.manager@propman.local",
            "password": "sample123",
            "full_name": "Sample Manager",
            "role_id": 2,
        },
    ]

    for user_data in users:
        defaults = {
            "email": user_data["email"],
            "password_hash": hash_password(user_data["password"]),
            "full_name": user_data["full_name"],
            "role_id": user_data["role_id"],
            "tenant_org_id": org_id,
            "is_active": True,
        }
        user, created = get_or_create(
            db,
            UserAccount,
            defaults=defaults,
            username=user_data["username"],
        )
        if not created:
            user.full_name = user_data["full_name"]
            user.role_id = user_data["role_id"]
            user.tenant_org_id = org_id
            if not user.email:
                user.email = user_data["email"]
            if not user.password_hash:
                user.password_hash = hash_password(user_data["password"])

    db.flush()


def seed_properties(db, org):
    region_specs = [
        ("SMP-NORTH", "North Region"),
        ("SMP-CENTRAL", "Central Region"),
    ]
    regions = {}
    for code, name in region_specs:
        region, _ = get_or_create(
            db,
            Region,
            region_code=code,
            defaults={
                "region_name": name,
                "tenant_org_id": org.id,
                "country": "US",
                "currency": "USD",
                "timezone": "America/Chicago",
                "status": "Active",
            },
        )
        if region.tenant_org_id is None:
            region.tenant_org_id = org.id
        regions[code] = region

    property_specs = [
        {
            "code": "SMP-001",
            "name": "Maple Residency",
            "ptype": "Residential",
            "region": "SMP-NORTH",
            "city": "Austin",
            "state": "TX",
            "address": "121 Maple Ave",
            "rent": 1450,
        },
        {
            "code": "SMP-002",
            "name": "Riverfront Offices",
            "ptype": "Commercial",
            "region": "SMP-CENTRAL",
            "city": "Dallas",
            "state": "TX",
            "address": "88 River St",
            "rent": 2100,
        },
    ]

    for spec in property_specs:
        prop, _ = get_or_create(
            db,
            Property,
            property_code=spec["code"],
            defaults={
                "property_name": spec["name"],
                "property_type": spec["ptype"],
                "tenant_org_id": org.id,
                "region_id": regions[spec["region"]].id,
                "address_line1": spec["address"],
                "city": spec["city"],
                "state": spec["state"],
                "country": "US",
                "postal_code": "75001",
                "status": "Active",
                "total_units": 0,
                "year_built": 2018,
            },
        )

        # Keep tenant and region aligned even on pre-existing rows.
        prop.tenant_org_id = org.id
        prop.region_id = regions[spec["region"]].id

        bldg, _ = get_or_create(
            db,
            Building,
            property_id=prop.id,
            building_code=f"{spec['code']}-A",
            defaults={
                "tenant_org_id": org.id,
                "building_name": f"{spec['name']} - Block A",
                "floors_count": 2,
                "status": "Active",
            },
        )

        for floor_no in (1, 2):
            floor, _ = get_or_create(
                db,
                Floor,
                building_id=bldg.id,
                floor_number=floor_no,
                defaults={
                    "tenant_org_id": org.id,
                    "floor_name": f"Floor {floor_no}",
                    "total_units": 2,
                    "status": "Active",
                },
            )

            for suffix in ("01", "02"):
                unit_num = f"{spec['code']}-{floor_no}{suffix}"
                get_or_create(
                    db,
                    Unit,
                    property_id=prop.id,
                    unit_number=unit_num,
                    defaults={
                        "tenant_org_id": org.id,
                        "building_id": bldg.id,
                        "floor_id": floor.id,
                        "unit_type": "Office" if spec["ptype"] == "Commercial" else "2BHK",
                        "current_status": "Vacant",
                        "market_rent": spec["rent"] + floor_no * 50,
                        "area_sqft": 850 if spec["ptype"] == "Residential" else 1200,
                        "bedrooms": 2 if spec["ptype"] == "Residential" else 0,
                        "bathrooms": 2 if spec["ptype"] == "Residential" else 1,
                        "status": "Active",
                    },
                )

        prop.total_units = db.query(Unit).filter(Unit.property_id == prop.id, Unit.is_deleted == False).count()

    db.flush()


def seed_parties(db, org_id):
    owners = [
        ("SMP-OWN-001", "Jordan", "Miles", "jordan.miles@example.com"),
        ("SMP-OWN-002", "Taylor", "Stone", "taylor.stone@example.com"),
    ]
    for code, first_name, last_name, email in owners:
        get_or_create(
            db,
            Owner,
            owner_code=code,
            defaults={
                "tenant_org_id": org_id,
                "owner_type": "Individual",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": "555-1000",
                "status": "Active",
            },
        )

    tenants = [
        ("SMP-TNT-001", "Alex", "Reed", "alex.reed@example.com"),
        ("SMP-TNT-002", "Morgan", "Hall", "morgan.hall@example.com"),
    ]
    for code, first_name, last_name, email in tenants:
        get_or_create(
            db,
            Tenant,
            tenant_code=code,
            defaults={
                "tenant_org_id": org_id,
                "tenant_type": "Individual",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": "555-2000",
                "status": "Active",
            },
        )

    vendors = [
        ("SMP-VEN-001", "Prime Plumbing", "Plumbing"),
        ("SMP-VEN-002", "North Star Electric", "Electrical"),
    ]
    for code, company_name, category in vendors:
        get_or_create(
            db,
            Vendor,
            vendor_code=code,
            defaults={
                "tenant_org_id": org_id,
                "company_name": company_name,
                "service_category": category,
                "email": f"{company_name.lower().replace(' ', '')}@example.com",
                "phone": "555-3000",
                "status": "Active",
            },
        )

    db.flush()


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        seed_roles(db)

        org, _ = get_or_create(
            db,
            TenantOrg,
            org_code="SMP",
            defaults={
                "org_name": "Sample Property Org",
                "subdomain": "sample-org",
                "plan": "standard",
                "status": "Active",
            },
        )

        seed_users(db, org.id)
        seed_properties(db, org)
        seed_parties(db, org.id)

        db.commit()

        print("Sample data seeded successfully.")
        print(f"Tenant Orgs: {db.query(TenantOrg).count()}")
        print(f"Regions: {db.query(Region).count()}")
        print(f"Properties: {db.query(Property).count()}")
        print(f"Buildings: {db.query(Building).count()}")
        print(f"Units: {db.query(Unit).count()}")
        print(f"Tenants: {db.query(Tenant).count()}")
        print(f"Owners: {db.query(Owner).count()}")
        print(f"Vendors: {db.query(Vendor).count()}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
