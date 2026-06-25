import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

cursor.execute("DELETE FROM complaints")

cursor.execute("""
DELETE FROM sqlite_sequence
WHERE name='complaints'
""")

conn.commit()

conn.close()

print("Complaint table reset")