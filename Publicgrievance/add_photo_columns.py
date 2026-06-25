import sqlite3

conn = sqlite3.connect("grievance.db")
cursor = conn.cursor()

try:
    cursor.execute("""
    ALTER TABLE complaints
    ADD COLUMN before_photo TEXT
    """)
except:
    pass

try:
    cursor.execute("""
    ALTER TABLE complaints
    ADD COLUMN after_photo TEXT
    """)
except:
    pass

conn.commit()
conn.close()

print("Photo columns added successfully")