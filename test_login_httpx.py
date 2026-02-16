import httpx
import asyncio

async def test_login():
    base_url = "http://localhost:8000"
    creds = {"username": "admin", "password": "admin123"}
    
    print(f"Attempting login to {base_url}/api/auth/login...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{base_url}/api/auth/login", json=creds)
            print(f"Login Status: {resp.status_code}")
            print(f"Login Response: {resp.text}")
            print(f"Cookies: {dict(client.cookies)}")
            
            if resp.status_code == 200:
                print("\nAttempting to access /dashboard...")
                # httpx client persists cookies across requests in the same session/client? 
                # Actually AsyncClient does if used as context context manager? 
                # No, need to verify.
                # Let's manually set cookies if needed, but client should handle it.
                
                dash_resp = await client.get(f"{base_url}/dashboard")
                print(f"Dashboard Status: {dash_resp.status_code}")
                # check for redirect
                if dash_resp.status_code in (301, 302, 307):
                    print(f"Dashboard Redirect to: {dash_resp.headers.get('location')}")
                else:
                    print(f"Dashboard content len: {len(dash_resp.text)}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_login())
