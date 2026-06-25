import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS complaints(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_no TEXT,
    citizen_name TEXT,
    mobile TEXT,
    ward_no TEXT,
    category TEXT,
    description TEXT,
    status TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
INSERT OR IGNORE INTO users
(username,password,role)
VALUES
('admin','admin123','Admin')
""")

conn.commit()
conn.close()

print("Database Created Successfully")