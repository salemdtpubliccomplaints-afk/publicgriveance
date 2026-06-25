import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

columns = [
    "ALTER TABLE complaints ADD COLUMN village TEXT",
    "ALTER TABLE complaints ADD COLUMN area TEXT",
    "ALTER TABLE complaints ADD COLUMN assigned_to TEXT",
    "ALTER TABLE complaints ADD COLUMN priority TEXT",
    "ALTER TABLE complaints ADD COLUMN remarks TEXT",
    "ALTER TABLE complaints ADD COLUMN followup_date TEXT"
]

for sql in columns:
    try:
        cursor.execute(sql)
        print("Added:", sql)
    except Exception as e:
        print("Skipped:", e)

conn.commit()
conn.close()

print("Database Updated Successfully")