import sqlite3

conn = sqlite3.connect("grievance.db")

conn.execute("""
INSERT OR IGNORE INTO users(username, password, role)
VALUES('staff1', 'staff123', 'User')
""")

conn.execute("""
UPDATE users
SET role='Admin'
WHERE username='admin'
""")

conn.commit()
conn.close()

print("Users updated successfully")