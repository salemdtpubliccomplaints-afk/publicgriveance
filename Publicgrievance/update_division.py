import sqlite3

conn = sqlite3.connect("grievance.db")
cursor = conn.cursor()

columns = [
    "zonal_office TEXT",
    "ward_no TEXT",
    "complaint_attender TEXT",
    "complaint_date TEXT",
    "ward_notification_status TEXT",
    "ward_representative TEXT",
    "response_details TEXT",
    "informed_to_department TEXT",
    "inital_action_status TEXT",
    "progress_update_status TEXT",
    "final_resolution_status TEXT",
    "remarks_and_notes TEXT",
    "petitioner_address TEXT"
    
]

for column in columns:

    try:

        cursor.execute(
            f"ALTER TABLE complaints ADD COLUMN {column}"
        )

        print(f"Added {column}")

    except Exception as e:

        print(f"Skipped {column}")

conn.commit()
conn.close()

print("Database Updated")