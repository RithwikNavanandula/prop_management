
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
# Import all models to ensure metadata is complete
from app.modules.properties import models as pm
from app.modules.leasing import models as lm
from app.modules.billing import models as bm
from app.modules.accounting import models as am
from app.modules.maintenance import models as mm
from app.modules.crm import models as cm
from app.modules.marketing import models as mkm
from app.modules.compliance import models as cpm
from app.modules.workflow import models as wm

from datetime import date, timedelta

def test_lease_creation():
    db = SessionLocal()
    try:
        # Ensure all tables are created
        Base.metadata.create_all(bind=engine)
        
        # 1. Get a property and unit
        unit = db.query(pm.Unit).filter(pm.Unit.is_deleted == False).first()
        if not unit:
            print("No unit found to test with.")
            # Create a dummy property and unit if needed, but for now let's hope one exists
            return

        print(f"Testing with Unit ID: {unit.id}, Property ID: {unit.property_id}")

        # 2. Prepare lease data
        import random
        lease_num = f"TEST-L-{random.randint(10000, 99999)}"
        
        lease_data = {
            "lease_number": lease_num,
            "property_id": unit.property_id,
            "unit_id": unit.id,
            "tenant_id": 1,  
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=365),
            "base_rent_amount": 1500.00,
            "base_rent_currency": "USD"
        }

        # 3. Create Lease
        print(f"Creating lease {lease_num}...")
        lease = lm.Lease(**lease_data)
        lease.created_by = 1 
        
        db.add(lease)
        db.commit()
        db.refresh(lease)
        print(f"Lease created with ID: {lease.id}")

        # 4. Link Unit and Update Status
        if lease.unit_id:
            u = db.query(pm.Unit).filter(pm.Unit.id == lease.unit_id).first()
            if u:
                u.current_status = "Occupied"
                link = lm.LeaseUnitLink(
                    lease_id=lease.id,
                    unit_id=lease.unit_id,
                    allocated_rent=lease.base_rent_amount
                )
                db.add(link)
                db.commit()
                print("Unit status updated and link created.")

        print("SUCCESS: Lease creation flow completed.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILURE: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_lease_creation()
