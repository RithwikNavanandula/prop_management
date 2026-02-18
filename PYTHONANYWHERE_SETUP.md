# PythonAnywhere Deployment Guide — PropManager Pro

> **Username:** `rymaai`  
> **Project folder:** `/home/rymaai/prop_management`  
> **Framework:** FastAPI (served via WSGI adapter)

---

## Step 1 — Upload Your Code

### Option A: Git Clone (Recommended)
Open a **Bash console** from the PythonAnywhere dashboard:
```bash
cd ~
git clone <your-repo-url> prop_management
```

### Option B: Manual Upload
1. Go to **Files** tab on PythonAnywhere
2. Create folder `/home/rymaai/prop_management`
3. Upload the entire project contents (zip → upload → unzip)

---

## Step 2 — Create a Virtual Environment

In the Bash console:
```bash
cd ~/prop_management
mkvirtualenv --python=/usr/bin/python3.10 propmanager_env
pip install -r requirements.txt
```

> [!NOTE]
> PythonAnywhere free tier supports Python 3.10. Adjust the version if needed.

---

## Step 3 — Create Required Directories

```bash
cd ~/prop_management
mkdir -p uploads static/qrcodes
```

---

## Step 4 — Initialize the Database

```bash
cd ~/prop_management
python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

This creates `property_mgmt.db` with all tables.

---

## Step 5 — Create the Web App

1. Go to **Web** tab on PythonAnywhere
2. Click **Add a new web app**
3. Select **Manual configuration** (NOT Flask/Django)
4. Choose **Python 3.10**

---

## Step 6 — Configure WSGI

1. On the **Web** tab, click the link to the **WSGI configuration file**  
   (e.g., `/var/www/rymaai_pythonanywhere_com_wsgi.py`)
2. **Delete all existing content** and replace with:

```python
import sys
import os

# Add project to path
project_home = '/home/rymaai/prop_management'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variables
os.environ['DATABASE_URL'] = 'sqlite:////home/rymaai/prop_management/property_mgmt.db'

from app.main import app
from a2wsgi import ASGIMiddleware

# PythonAnywhere serves WSGI — wrap the ASGI FastAPI app as WSGI
application = ASGIMiddleware(app)
```

> [!IMPORTANT]
> This is the same content as your `wsgi.py` file — copy it verbatim into PythonAnywhere's WSGI config file.

---

## Step 7 — Set Virtualenv Path

On the **Web** tab, in the **Virtualenv** section:
```
/home/rymaai/.virtualenvs/propmanager_env
```

---

## Step 8 — Configure Static Files

On the **Web** tab, add these static file mappings:

| URL | Directory |
|-----|-----------|
| `/static` | `/home/rymaai/prop_management/app/static` |
| `/uploads` | `/home/rymaai/prop_management/uploads` |

---

## Step 9 — Set Environment Variables (Optional)

If you prefer environment variables over `.env`, go to the **Web** tab and add these in the **Environment variables** section:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | *(your generated key from .env)* |
| `DATABASE_URL` | `sqlite:////home/rymaai/prop_management/property_mgmt.db` |
| `DEBUG` | `False` |

> [!TIP]
> The app reads from `.env` automatically via `python-dotenv`, so this step is optional if your `.env` file is properly configured.

---

## Step 10 — Create Default Admin User

In a Bash console:
```bash
cd ~/prop_management
workon propmanager_env
python -c "
from app.database import SessionLocal
from app.auth.models import UserAccount, Role
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
db = SessionLocal()

# Create admin role if not exists
role = db.query(Role).filter(Role.role_name == 'Admin').first()
if not role:
    role = Role(role_name='Admin', description='System Administrator', 
                permissions={'admin': True, 'properties': True, 'leases': True, 
                'billing': True, 'maintenance': True, 'accounting': True,
                'crm': True, 'marketing': True, 'compliance': True,
                'workflow': True, 'system': True, 'dashboard': True,
                'reports': True, 'portfolio': True, 'tenants': True,
                'owners': True, 'vendors': True, 'finance': True,
                'payments': True, 'work_orders': True, 'sales': True},
                is_system=True, is_active=True)
    db.add(role)
    db.commit()
    db.refresh(role)

# Create admin user
admin = db.query(UserAccount).filter(UserAccount.username == 'admin').first()
if not admin:
    admin = UserAccount(
        username='admin',
        email='admin@propmanager.com',
        password_hash=pwd_context.hash('admin123'),
        full_name='System Admin',
        role_id=role.id,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print('Admin user created: admin / admin123')
else:
    print('Admin user already exists')
db.close()
"
```

> [!CAUTION]
> Change the default password (`admin123`) immediately after first login!

---

## Step 11 — Reload & Test

1. Go to the **Web** tab
2. Click the green **Reload** button
3. Visit `https://rymaai.pythonanywhere.com`
4. Login with `admin` / `admin123`

---

## Troubleshooting

### Error Log Location
Check the **Web** tab → **Log files** section:
- **Error log:** `/var/log/rymaai.pythonanywhere.com.error.log`
- **Server log:** `/var/log/rymaai.pythonanywhere.com.server.log`

### Common Issues

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Ensure virtualenv path is set correctly on Web tab |
| `sqlite3.OperationalError: unable to open database` | Check file permissions: `chmod 664 property_mgmt.db` and `chmod 775 ~/prop_management` |
| Static files not loading | Verify static file mappings on Web tab |
| `ImportError: app.main` | Ensure `sys.path` includes project root in WSGI file |

### Updating the App
```bash
cd ~/prop_management
git pull origin main                    # if using git
workon propmanager_env
pip install -r requirements.txt         # if deps changed
```
Then click **Reload** on the Web tab.
