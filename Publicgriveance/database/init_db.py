import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
password TEXT,
role TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_attender TEXT,
    complaint_date TEXT,
    zonal_office TEXT,
    petitioner_name TEXT,
    mobile TEXT,
    petitioner_address TEXT,
    ward_no TEXT,
    category TEXT,
    description TEXT,
    ward_notification_status TEXT,
    ward_representative TEXT,
    response_details TEXT,
    informed_to_department TEXT,
    inital_action_status TEXT,
    progress_update_status TEXT,
    final_resolution_status TEXT,
    remarks_notes TEXT,
    status TEXT
)
""")

cursor.execute("""
INSERT INTO users(username,password,role)
VALUES('admin','admin123','Admin')
""")

conn.commit()
conn.close()

print("Database Created")