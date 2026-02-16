import requests

def test_login():
    base_url = "http://localhost:8000"
    creds = {"username": "admin", "password": "admin123"}
    
    print(f"Attempting login to {base_url}/api/auth/login...")
    session = requests.Session()
    try:
        resp = session.post(f"{base_url}/api/auth/login", json=creds)
        print(f"Login Status: {resp.status_code}")
        print(f"Login Response: {resp.text}")
        print(f"Cookies: {session.cookies.get_dict()}")
        
        if resp.status_code == 200:
            print("\nAttempting to access /dashboard...")
            dash_resp = session.get(f"{base_url}/dashboard")
            print(f"Dashboard Status: {dash_resp.status_code}")
            print(f"Dashboard URL (after redirect?): {dash_resp.url}")
            if dash_resp.history:
                print("Redirect history:")
                for r in dash_resp.history:
                    print(f" - {r.status_code} {r.url}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
