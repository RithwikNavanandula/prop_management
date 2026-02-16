import httpx
import json

BASE_URL = "http://localhost:8000"

def test_hierarchy():
    # Login as admin
    login_data = {"username": "admin", "password": "admin123"}
    with httpx.Client() as client:
        # Create a session
        try:
            resp = client.post(f"{BASE_URL}/api/auth/login", json=login_data)
            if resp.status_code != 200:
                print(f"Login failed with status {resp.status_code}: {resp.text}")
                return
        except Exception as e:
            print(f"Connection to server failed: {e}")
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create Property
        prop_data = {"property_code": "VERIFY01", "property_name": "Verification Property", "property_type": "Residential"}
        resp = client.post(f"{BASE_URL}/api/properties", json=prop_data, headers=headers)
        if resp.status_code != 201:
            print(f"Failed to create property: {resp.text}")
            return
        prop_id = resp.json()["id"]
        print(f"Property created: {prop_id}")

        # 2. Create Building
        bldg_data = {"building_code": "BLDG-A", "building_name": "Building A"}
        resp = client.post(f"{BASE_URL}/api/properties/{prop_id}/buildings", json=bldg_data, headers=headers)
        bldg_id = resp.json()["id"]
        print(f"Building created: {bldg_id}")

        # 3. Create Floor
        floor_data = {"floor_number": 1, "floor_name": "Ground Floor"}
        resp = client.post(f"{BASE_URL}/api/properties/{prop_id}/buildings/{bldg_id}/floors", json=floor_data, headers=headers)
        floor_id = resp.json()["id"]
        print(f"Floor created: {floor_id}")

        # 4. Create Unit
        unit_data = {
            "unit_number": "101",
            "building_id": bldg_id,
            "floor_id": floor_id,
            "unit_type": "1BHK"
        }
        resp = client.post(f"{BASE_URL}/api/properties/{prop_id}/units", json=unit_data, headers=headers)
        unit_id = resp.json()["id"]
        print(f"Unit created: {unit_id}")

        # 5. Create Asset
        asset_data = {"asset_name": "Verification AC", "asset_category": "Appliance", "asset_type": "AC"}
        resp = client.post(f"{BASE_URL}/api/properties/{prop_id}/units/{unit_id}/assets", json=asset_data, headers=headers)
        asset_id = resp.json()["id"]
        print(f"Asset created: {asset_id}")

        # 6. Verify Listings
        resp = client.get(f"{BASE_URL}/api/properties/{prop_id}/units", headers=headers)
        units = resp.json()["items"]
        found_unit = next((u for u in units if u["id"] == unit_id), None)
        assert found_unit["building_id"] == bldg_id
        assert found_unit["floor_id"] == floor_id
        print("Unit hierarchy verified")

        resp = client.get(f"{BASE_URL}/api/properties/{prop_id}/units/{unit_id}/assets", headers=headers)
        assets = resp.json()["items"]
        assert any(a["id"] == asset_id for a in assets)
        print("Unit asset verified")

        print("All verification steps passed!")

if __name__ == "__main__":
    try:
        test_hierarchy()
    except Exception as e:
        print(f"Test failed: {e}")
