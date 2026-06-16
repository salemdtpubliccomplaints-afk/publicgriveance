import sqlite3

conn = sqlite3.connect("grievance.db")

cursor = conn.cursor()

try:
    cursor.execute("""
    ALTER TABLE complaints
    ADD COLUMN division_no TEXT
    """)

    print("Division No column added.")
print("Zonal Office column added.")
print("Assigned Officer column added.")
print("Date of Complaint column added.")
print("Ward Notification Status column added.")
print("Ward Representative column added.")
print("Response Details column added.")
print("Informed To Dept column added.")
print("Initial Action Status column added.")
print("Progress Update Status column added.")
print("Final Resolution Status column added.")
print("Remarks & Notes column added.")  



    

except Exception as e:
    print(e)

conn.commit()
conn.close()