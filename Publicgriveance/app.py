import os
import sqlite3
import pandas as pd

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import session


import sqlite3
import pandas as pd

app = Flask(__name__)

app.secret_key = "grievance_secret"

DB_FILE = "grievance.db"


def get_db():

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def initialize_database():

    conn = sqlite3.connect(DB_FILE)

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
        complaint_attender TEXT,
        complaint_date TEXT,
        zonal_office TEXT,
        petitioner_name TEXT,
        mobile TEXT,
        petitioner_address TEXT,
        ward_no TEXT,
        category TEXT,
        description TEXT,
        ward_notification_status TEXT,
        ward_representative TEXT,
        response_details TEXT,
        informed_to_department TEXT,
        inital_action_status TEXT,
        progress_update_status TEXT,
        final_resolution_status TEXT,
        remarks_&_notes TEXT
    )
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO users
    (
        username,
        password,
        role
    )
    VALUES
    (
        'admin',
        'admin123',
        'Admin'
    )
    """)

    conn.commit()

    conn.close()


initialize_database()


# ---------------------------
# LOGIN
# ---------------------------

@app.route('/login_page')
def login_page():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    conn = get_db()

    user = conn.execute(
        '''
        SELECT *
        FROM users
        WHERE username=?
        AND password=?
        ''',
        (username, password)
    ).fetchone()

    conn.close()

    if user:
        session['user'] = username
        return redirect('/')

    return "Invalid Login"


# ---------------------------
# DASHBOARD
# ---------------------------

@app.route('/dashboard')
def dashboard():

    if 'user' not in session:
        return redirect('/login_page')

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    resolved = conn.execute(
        """
        SELECT COUNT(*)
        FROM complaints
        WHERE status='Resolved'
        """
    ).fetchone()[0]

    open_count = total - resolved

    conn.close()

    return render_template(
        'dashboard.html',
        total=total,
        resolved=resolved,
        open_count=open_count
    )


# ---------------------------
# HOME PAGE
# ---------------------------

@app.route("/")
def home():

    if 'user' not in session:
        return redirect('/login_page')

    conn = get_db()

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "complaints.html",
        complaints=complaints
    )


# ---------------------------
# SEARCH
# ---------------------------

@app.route('/search')
def search():

    keyword = request.args.get('keyword')

    conn = get_db()

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_no LIKE ?
        OR citizen_name LIKE ?
        OR mobile LIKE ?
        """,
        (
            f'%{keyword}%',
            f'%{keyword}%',
            f'%{keyword}%'
        )
    ).fetchall()

    conn.close()

    return render_template(
        'complaints.html',
        complaints=complaints
    )


# ---------------------------
# FILTER BY WARD
# ---------------------------

@app.route('/filter')
def filter_ward():

    ward = request.args.get('ward')

    conn = get_db()

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE ward_no=?
        """,
        (ward,)
    ).fetchall()

    conn.close()

    return render_template(
        'complaints.html',
        complaints=complaints
    )


# ---------------------------
# ADD COMPLAINT PAGE
# ---------------------------

@app.route("/add")
def add():

    if 'user' not in session:
        return redirect('/login_page')

    return render_template("add_complaint.html")
    return render_template("add_complaint.html")


# ---------------------------
# SAVE COMPLAINT
# ---------------------------

@app.route("/save", methods=["POST"])
def save():

    complaint_attender = request.form["complaint_attender"]
    complaint_date = request.form["complaint_date"]
    zonal_office = request.form["zonal_office"]
    petitioner_name = request.form["petitioner_name"]
    mobile = request.form["mobile"]
    petitioner_address = request.form["petitioner_address"]
    ward_no = request.form["ward_no"]
    category = request.form["category"]
    description = request.form["description"]
    ward_notification_status = request.form["ward_notification_status"]
    ward_representative = request.form["ward_representative"]
    response_details = request.form["response_details"]
    informed_to_department = request.form["informed_to_department"]
    inital_action_status = request.form["inital_action_status"]
    progress_update_status = request.form["progress_update_status"]
    final_resolution_status = request.form["final_resolution_status"]
    remarks_&_notes = request.form[" remarks_&_notes"]


    conn = get_db()

    conn.execute(
        """
        INSERT INTO complaints
        (
        complaint_attender,
        complaint_date,
        zonal_office,
        petitioner_name,
        mobile,
        petitioner_address,
        ward_no,
        category,
        description,
        ward_notification_status,
        ward_representative,
        response_details,
        informed_to_department,
        inital_action_status,
        progress_update_status,
        final_resolution_status,
        remarks_&_notes
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
        complaint_attender,
        complaint_date,
        zonal_office,
        petitioner_name,
        mobile,
        petitioner_address,
        ward_no,
        category,
        description,
        ward_notification_status,
        ward_representative,
        response_details,
        informed_to_department,
        inital_action_status,
        progress_update_status,
        final_resolution_status,
        remarks_&_notes,
        "Open"
        )
    )

    conn.commit()
    conn.close()

    return redirect("/")


# ---------------------------
# EDIT COMPLAINT
# ---------------------------

@app.route('/edit/<int:id>')
def edit(id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE id=?
        """,
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        'edit_complaint.html',
        row=row
    )


# ---------------------------
# UPDATE COMPLAINT
# ---------------------------

@app.route('/update/<int:id>', methods=['POST'])
def update(id):

    conn = get_db()

    conn.execute(
        """
        UPDATE complaints
        SET  complaint_attender=?,
        complaint_date=?,
        zonal_office=?,
        petitioner_name=?,
        mobile=?,
        petitioner_address=?,
        ward_no=?,
        category=?,
        description=?,
        ward_notification_status=?,
        ward_representative=?,
        response_details=?,
        informed_to_department=?,
        inital_action_status=?,
        progress_update_status=?,
        final_resolution_status=?,
        remarks_&_notes=?
        WHERE id=?
        """,
        (
            request.form['complaint_attender'],
            request.form['complaint_date'],
            request.form['zonal_office'],
            request.form['petitioner_name'],
            request.form['mobile'],
            request.form['petitioner_address'],
            request.form['ward_no'],
            request.form['category'],
            request.form['description'],
            request.form['ward_notification_status'],
            request.form['ward_representative'],
            request.form['response_details'],
            request.form['informed_to_department'],
            request.form['inital_action_status'],
            request.form['progress_update_status'],
            request.form['final_resolution_status'],
            request.form['remarks_&_notes'],
            id
        )
    )

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------------------
# RESOLVE COMPLAINT
# ---------------------------

@app.route('/resolve/<int:id>')
def resolve(id):

    conn = get_db()

    conn.execute(
        """
        UPDATE complaints
        SET status='Resolved'
        WHERE id=?
        """,
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------------------
# DELETE COMPLAINT
# ---------------------------

@app.route('/delete/<int:id>')
def delete(id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM complaints
        WHERE id=?
        """,
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect('/')


# ---------------------------
# EXPORT EXCEL
# ---------------------------

@app.route('/export')
def export():

    conn = get_db()

    df = pd.read_sql_query(
        "SELECT * FROM complaints",
        conn
    )

    conn.close()

    df.to_excel(
        "complaints.xlsx",
        index=False
    )

    return "Excel File Generated Successfully"


# ---------------------------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/login_page')
# MAIN
# ---------------------------

if __name__ == "__main__":

    app.run(
        host="192.168.0.6",
        port=5000,
        debug=True
    )