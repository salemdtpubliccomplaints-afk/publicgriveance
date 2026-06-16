import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

try:
    cursor.execute("""
    ALTER TABLE complaints
    ADD COLUMN division_no TEXT
    """)

    print("Division Number column added.")

except Exception as e:
    print(e)

conn.commit()
conn.close()