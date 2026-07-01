import os
import io
import sqlite3
import pandas as pd

from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "grievance_secret"

DB_FILE = "grievance.db"
UPLOAD_FOLDER = os.path.join("static", "uploads")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(cursor, table_name, column_name, column_type):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if column_name not in existing_columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


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
        remarks_and_notes TEXT,
        before_photo TEXT,
        after_photo TEXT,
        status TEXT DEFAULT 'Open'
    )
    """)

    required_columns = {
        "complaint_attender": "TEXT",
        "complaint_date": "TEXT",
        "zonal_office": "TEXT",
        "petitioner_name": "TEXT",
        "mobile": "TEXT",
        "petitioner_address": "TEXT",
        "ward_no": "TEXT",
        "category": "TEXT",
        "description": "TEXT",
        "ward_notification_status": "TEXT",
        "ward_representative": "TEXT",
        "response_details": "TEXT",
        "informed_to_department": "TEXT",
        "inital_action_status": "TEXT",
        "progress_update_status": "TEXT",
        "final_resolution_status": "TEXT",
        "remarks_and_notes": "TEXT",
        "before_photo": "TEXT",
        "after_photo": "TEXT",
        "status": "TEXT DEFAULT 'Open'"
    }

    for column_name, column_type in required_columns.items():
        ensure_column(cursor, "complaints", column_name, column_type)

    cursor.execute("""
    INSERT OR IGNORE INTO users(username, password, role)
    VALUES('admin', 'admin123', 'Admin')
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO users(username, password, role)
    VALUES('warriors', 'warriors@2026', 'User')
    """)

    cursor.execute("""
    UPDATE users
    SET role='Admin'
    WHERE username='admin'
    """)

    cursor.execute("""
    UPDATE users
    SET role='User'
    WHERE username='warriors'
    """)

    conn.commit()
    conn.close()


def save_uploaded_file(file_object, prefix):
    if not file_object or not file_object.filename:
        return ""

    filename = secure_filename(file_object.filename)
    filename = f"{prefix}_{filename}"

    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file_object.save(save_path)

    return "uploads/" + filename


def is_admin():
    return session.get("role") == "Admin"


initialize_database()


@app.route("/login_page")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE username=?
        AND password=?
        """,
        (username, password)
    ).fetchone()

    conn.close()

    if user:
        session.clear()
        session["user"] = user["username"]
        session["role"] = user["role"]
        return redirect("/")

    return "Invalid Login"


@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login_page")

    conn = get_db()

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template("complaints.html", complaints=complaints)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login_page")

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    open_count = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE final_resolution_status IS NULL
           OR final_resolution_status=''
           OR final_resolution_status='Open'
    """).fetchone()[0]

    in_progress = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE final_resolution_status='In Progress'
    """).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE final_resolution_status='Resolved'
           OR final_resolution_status='Closed'
           OR status='Resolved'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total=total,
        open_count=open_count,
        in_progress=in_progress,
        resolved=resolved
    )


@app.route("/search")
def search():
    if "user" not in session:
        return redirect("/login_page")

    keyword = request.args.get("keyword", "")

    conn = get_db()

    complaints = conn.execute(
        """
        SELECT *
        FROM complaints
        WHERE petitioner_name LIKE ?
        OR mobile LIKE ?
        OR ward_no LIKE ?
        OR category LIKE ?
        OR zonal_office LIKE ?
        """,
        (
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        )
    ).fetchall()

    conn.close()

    return render_template("complaints.html", complaints=complaints)


@app.route("/add")
def add():
    if "user" not in session:
        return redirect("/login_page")

    return render_template("add_complaint.html")


@app.route("/save", methods=["POST"])
def save():
    if "user" not in session:
        return redirect("/login_page")

    before_photo_path = save_uploaded_file(
        request.files.get("before_photo"),
        "before"
    )

    after_photo_path = ""
    informed_to_department = ""
    inital_action_status = ""
    progress_update_status = ""
    final_resolution_status = "Open"
    remarks_and_notes = ""

    if is_admin():
        after_photo_path = save_uploaded_file(
            request.files.get("after_photo"),
            "after"
        )
        informed_to_department = request.form.get("informed_to_department", "")
        inital_action_status = request.form.get("inital_action_status", "")
        progress_update_status = request.form.get("progress_update_status", "")
        final_resolution_status = request.form.get("final_resolution_status", "")
        remarks_and_notes = request.form.get("remarks_and_notes", "")

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
            remarks_and_notes,
            before_photo,
            after_photo,
            status
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            request.form.get("complaint_attender", ""),
            request.form.get("complaint_date", ""),
            request.form.get("zonal_office", ""),
            request.form.get("petitioner_name", ""),
            request.form.get("mobile", ""),
            request.form.get("petitioner_address", ""),
            request.form.get("ward_no", ""),
            request.form.get("category", ""),
            request.form.get("description", ""),
            request.form.get("ward_notification_status", ""),
            request.form.get("ward_representative", ""),
            request.form.get("response_details", ""),
            informed_to_department,
            inital_action_status,
            progress_update_status,
            final_resolution_status,
            remarks_and_notes,
            before_photo_path,
            after_photo_path,
            "Open"
        )
    )

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/edit/<int:id>")
def edit(id):
    if "user" not in session:
        return redirect("/login_page")

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

    return render_template("edit_complaint.html", row=row)


@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if "user" not in session:
        return redirect("/login_page")

    conn = get_db()

    existing_row = conn.execute(
        """
        SELECT before_photo, after_photo
        FROM complaints
        WHERE id=?
        """,
        (id,)
    ).fetchone()

    before_photo_path = existing_row["before_photo"] if existing_row else ""
    after_photo_path = existing_row["after_photo"] if existing_row else ""

    new_before_photo = save_uploaded_file(
        request.files.get("before_photo"),
        "before"
    )

    if new_before_photo:
        before_photo_path = new_before_photo

    if is_admin():
        new_after_photo = save_uploaded_file(
            request.files.get("after_photo"),
            "after"
        )

        if new_after_photo:
            after_photo_path = new_after_photo

        conn.execute(
            """
            UPDATE complaints
            SET
                complaint_attender=?,
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
                remarks_and_notes=?,
                before_photo=?,
                after_photo=?
            WHERE id=?
            """,
            (
                request.form.get("complaint_attender", ""),
                request.form.get("complaint_date", ""),
                request.form.get("zonal_office", ""),
                request.form.get("petitioner_name", ""),
                request.form.get("mobile", ""),
                request.form.get("petitioner_address", ""),
                request.form.get("ward_no", ""),
                request.form.get("category", ""),
                request.form.get("description", ""),
                request.form.get("ward_notification_status", ""),
                request.form.get("ward_representative", ""),
                request.form.get("response_details", ""),
                request.form.get("informed_to_department", ""),
                request.form.get("inital_action_status", ""),
                request.form.get("progress_update_status", ""),
                request.form.get("final_resolution_status", ""),
                request.form.get("remarks_and_notes", ""),
                before_photo_path,
                after_photo_path,
                id
            )
        )

    else:
        conn.execute(
            """
            UPDATE complaints
            SET
                complaint_attender=?,
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
                before_photo=?
            WHERE id=?
            """,
            (
                request.form.get("complaint_attender", ""),
                request.form.get("complaint_date", ""),
                request.form.get("zonal_office", ""),
                request.form.get("petitioner_name", ""),
                request.form.get("mobile", ""),
                request.form.get("petitioner_address", ""),
                request.form.get("ward_no", ""),
                request.form.get("category", ""),
                request.form.get("description", ""),
                request.form.get("ward_notification_status", ""),
                request.form.get("ward_representative", ""),
                request.form.get("response_details", ""),
                before_photo_path,
                id
            )
        )

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/resolve/<int:id>")
def resolve(id):
    if "user" not in session:
        return redirect("/login_page")

    if not is_admin():
        return redirect("/")

    conn = get_db()

    conn.execute(
        """
        UPDATE complaints
        SET status='Resolved',
            final_resolution_status='Resolved'
        WHERE id=?
        """,
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/login_page")

    if not is_admin():
        return redirect("/")

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

    return redirect("/")


@app.route("/export")
def export():
    if "user" not in session:
        return redirect("/login_page")

    conn = get_db()

    if is_admin():
        query = """
        SELECT
            id AS 'ID',
            complaint_attender AS 'Complaint Attender',
            complaint_date AS 'Complaint Date',
            zonal_office AS 'Zonal Office',
            petitioner_name AS 'Petitioner Name',
            mobile AS 'Mobile',
            petitioner_address AS 'Petitioner Address',
            ward_no AS 'Ward No',
            category AS 'Category',
            description AS 'Description',
            ward_notification_status AS 'Ward Notification Status',
            ward_representative AS 'Ward Representative',
            response_details AS 'Response Details',
            before_photo AS 'Before Action Photo',
            informed_to_department AS 'Informed To Department',
            inital_action_status AS 'Initial Action Status',
            progress_update_status AS 'Progress Update Status',
            final_resolution_status AS 'Final Resolution Status',
            after_photo AS 'After Resolution Photo',
            remarks_and_notes AS 'Remarks And Notes',
            status AS 'Status'
        FROM complaints
        ORDER BY id DESC
        """
    else:
        query = """
        SELECT
            id AS 'ID',
            complaint_attender AS 'Complaint Attender',
            complaint_date AS 'Complaint Date',
            zonal_office AS 'Zonal Office',
            petitioner_name AS 'Petitioner Name',
            mobile AS 'Mobile',
            petitioner_address AS 'Petitioner Address',
            ward_no AS 'Ward No',
            category AS 'Category',
            description AS 'Description',
            ward_notification_status AS 'Ward Notification Status',
            ward_representative AS 'Ward Representative',
            response_details AS 'Response Details',
            before_photo AS 'Before Action Photo',
            status AS 'Status'
        FROM complaints
        ORDER BY id DESC
        """

    df = pd.read_sql_query(query, conn)
    conn.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Complaints")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="complaints.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login_page")


if __name__ == "__main__":
    app.run(debug=True)
