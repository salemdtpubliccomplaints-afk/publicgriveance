import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

try:
    cursor.execute("""
    ALTER TABLE complaints
    ADD COLUMN petitioner_name TEXT
    """)
    print("petitioner_name column added")
except Exception as e:
    print(e)

conn.commit()
conn.close()