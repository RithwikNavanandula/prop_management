import sqlite3
import os

db_path = 'property_mgmt.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for table in ['leases', 'lease_unit_links']:
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}';")
        res = cursor.fetchone()
        if res:
            print(f"Schema for {table}:")
            print(res[0])
        else:
            print(f"Table {table} not found.")
    conn.close()
