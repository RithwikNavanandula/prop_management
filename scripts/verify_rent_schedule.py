import httpx
import asyncio
from datetime import date, timedelta
import time

async def verify_rent_schedule():
    async with httpx.AsyncClient(base_url="http://localhost:8000", follow_redirects=True) as client:
        # Login
        login_data = {"username": "admin", "password": "admin123"}
        print(f"Logging in as {login_data['username']}...")
        r = await client.post("/api/auth/login", json=login_data)
        if r.status_code != 200:
            print(f"Login failed: {r.status_code} {r.text}")
            return
            
        print("Login successful.")
        
        # Create a test lease
        lease_number = f"VERIFY-RS-{int(time.time())}"
        lease_data = {
            "lease_number": lease_number,
            "property_id": 1,
            "tenant_id": 1,
            "tenant_org_id": 1,
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=365)).isoformat(),
            "base_rent_amount": 1200,
            "rent_frequency": "Monthly"
        }
        
        print(f"Creating lease {lease_number}...")
        r = await client.post("/api/leases", json=lease_data)
        if r.status_code != 201:
            print(f"Failed to create lease: {r.status_code} {r.text}")
            return
            
        lease = r.json()
        lease_id = lease["id"]
        print(f"Created lease ID: {lease_id}")
        
        # Check rent schedule
        print(f"Fetching rent schedule for lease {lease_id}...")
        r = await client.get(f"/api/leases/{lease_id}/rent-schedule")
        if r.status_code != 200:
            print(f"Failed to fetch rent schedule: {r.status_code} {r.text}")
            return
            
        schedule = r.json()
        items = schedule.get("items", [])
        print(f"Generated {len(items)} rent schedule items.")
        
        if len(items) >= 12:
            print("Verification SUCCESS: Rent schedule generated correctly.")
        else:
            print(f"Verification FAILURE: Expected at least 12 items, got {len(items)}")

if __name__ == "__main__":
    asyncio.run(verify_rent_schedule())
