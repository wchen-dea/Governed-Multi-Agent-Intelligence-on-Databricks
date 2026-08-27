import csv
import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

username = os.environ["ODS_MYSQL_USER"]
password = os.environ["ODS_MYSQL_PASSWORD"]

# Connection details
host = "ods-rds-prd-01.cluster-crel14flfits.us-west-2.rds.amazonaws.com"
port = 3306  # default MySQL port
database = "OperationalDataStore"  # update if different

# Connect to ODS Prod
conn = mysql.connector.connect(
    host=host, port=port, database=database, user=username, password=password
)

cursor = conn.cursor()

# List all tables in the database
cursor.execute(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = %s
    AND table_type = 'BASE TABLE'
""",
    (database,),
)
tables = [row[0] for row in cursor.fetchall()]

print(f"Found {len(tables)} tables: {tables}")

tables = ["", ""]
# Export each table as CSV to a local directory (upload to the UC volume separately if needed).
output_path = Path(os.environ.get("ODS_EXPORT_DIR", "./ods_export"))
output_path.mkdir(parents=True, exist_ok=True)

for table_name in tables:
    print(f"Exporting table: {table_name}")
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    file_path = output_path / f"{table_name}.csv"
    with file_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"  -> Exported {len(rows)} rows to {file_path}")

cursor.close()
conn.close()
print("\nDone! All tables exported.")
