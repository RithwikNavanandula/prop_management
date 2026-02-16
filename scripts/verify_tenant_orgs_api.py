import httpx
import asyncio

async def verify_api():
    base_url = "http://localhost:8000"
    creds = {"username": "admin", "password": "admin123"}
    
    async with httpx.AsyncClient() as client:
        # 1. Login
        print(f"Logging in to {base_url}...")
        resp = await client.post(f"{base_url}/api/auth/login", json=creds)
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code}")
            return
            
        # 2. Check tenant-orgs API
        print("Checking /api/properties/tenant-orgs...")
        resp = await client.get(f"{base_url}/api/properties/tenant-orgs")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response:", resp.json())
        else:
            print("Error Response:", resp.text)

if __name__ == "__main__":
    asyncio.run(verify_api())
