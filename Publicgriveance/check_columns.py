import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

cursor.execute("PRAGMA table_info(complaints)")

columns = cursor.fetchall()

for col in columns:
    print(col)

conn.close()