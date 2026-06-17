import sqlite3

conn = sqlite3.connect("grievance.db")

conn.execute("""
INSERT OR IGNORE INTO users(username, password, role)
VALUES('warriors', 'warriors@2026', 'User')
""")

conn.commit()
conn.close()

print("User created successfully")