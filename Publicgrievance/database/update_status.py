import sqlite3

conn = sqlite3.connect("grievance.db")
cursor = conn.cursor()

try:
    cursor.execute(
        "ALTER TABLE complaints ADD COLUMN status TEXT"
    )

    print("Status column added")

except Exception as e:
    print(e)

conn.commit()
conn.close()