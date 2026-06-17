import sqlite3

conn = sqlite3.connect("grievance.db")

conn.execute("DELETE FROM complaints")

conn.commit()
conn.close()

print("All complaints deleted successfully")