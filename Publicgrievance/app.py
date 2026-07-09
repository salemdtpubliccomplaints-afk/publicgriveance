import os
import io
import uuid
import mimetypes
import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd
import requests

from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "grievance_secret"

UPLOAD_FOLDER = os.path.join("static", "uploads")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "complaint-photos")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class PGConnection:
    """
    Small wrapper to keep the existing app code style working.
    It allows conn.execute(...) like SQLite, but sends queries to PostgreSQL.
    """
    def __init__(self):
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL environment variable is missing")

        self.raw = psycopg2.connect(
            database_url,
            cursor_factory=DictCursor
        )

    def execute(self, query, params=None):
        query = query.replace("?", "%s")
        cur = self.raw.cursor()
        cur.execute(query, params or ())
        return cur

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def get_db():
    return PGConnection()


def initialize_database():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
        id SERIAL PRIMARY KEY,
        complaint_no TEXT UNIQUE,
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
        petitioner_application TEXT,
        after_photo TEXT,
        status TEXT DEFAULT 'Open',
        complaint_type TEXT DEFAULT 'Complaint'
    )
    """)


    conn.execute("""
    ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS complaint_no TEXT UNIQUE
    """)

    conn.execute("""
    UPDATE complaints
    SET complaint_no = 'SS-' || EXTRACT(YEAR FROM CURRENT_DATE)::INT || '-' || LPAD(id::TEXT, 6, '0')
    WHERE complaint_no IS NULL OR complaint_no = ''
    """)

    conn.execute("""
    ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS petitioner_application TEXT
    """)

    conn.execute("""
    ALTER TABLE complaints
    ADD COLUMN IF NOT EXISTS complaint_type TEXT DEFAULT 'Complaint'
    """)

    conn.execute("""
    UPDATE complaints
    SET complaint_type='Complaint'
    WHERE complaint_type IS NULL OR complaint_type=''
    """)

    conn.execute("""
    INSERT INTO users(username, password, role)
    VALUES('admin', 'admin123', 'Admin')
    ON CONFLICT (username) DO NOTHING
    """)

    conn.execute("""
    INSERT INTO users(username, password, role)
    VALUES('warriors', 'warriors@2026', 'User')
    ON CONFLICT (username) DO NOTHING
    """)

    conn.execute("""
    UPDATE users
    SET role='Admin'
    WHERE username='admin'
    """)

    conn.execute("""
    UPDATE users
    SET role='User'
    WHERE username='warriors'
    """)

    conn.commit()
    conn.close()



def generate_complaint_no(conn, complaint_type="Complaint"):
    """
    Generate complaint number.
    Normal complaints: SS-YYYY-000001
    Needs complaints: NEEDS-YYYY-000001
    """
    year = request.form.get("complaint_date", "")[:4]
    if not year:
        from datetime import datetime
        year = datetime.now().strftime("%Y")

    prefix = "NEEDS" if complaint_type == "Needs" else "SS"
    prefix = f"{prefix}-{year}-"

    cur = conn.execute(
        """
        SELECT complaint_no
        FROM complaints
        WHERE complaint_no LIKE ?
        ORDER BY complaint_no DESC
        LIMIT 1
        """,
        (prefix + "%",)
    )

    row = cur.fetchone()

    if row and row["complaint_no"]:
        try:
            last_number = int(row["complaint_no"].split("-")[-1])
        except Exception:
            last_number = 0
    else:
        last_number = 0

    return f"{prefix}{last_number + 1:06d}"


def save_uploaded_file(file_object, prefix):
    """
    Upload complaint photos to Supabase Storage and return the public URL.

    Required Render Environment Variables:
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
    - SUPABASE_STORAGE_BUCKET

    Bucket should be public in Supabase Storage.
    """
    if not file_object or not file_object.filename:
        return ""

    original_filename = secure_filename(file_object.filename)
    if not original_filename:
        return ""

    file_ext = os.path.splitext(original_filename)[1].lower()
    unique_filename = f"{prefix}_{uuid.uuid4().hex}{file_ext}"
    object_path = f"complaints/{unique_filename}"

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file_object.save(save_path)
        return "uploads/" + unique_filename

    content_type = file_object.mimetype
    if not content_type:
        content_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{object_path}"

    file_object.stream.seek(0)
    file_bytes = file_object.read()

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true"
    }

    response = requests.post(upload_url, headers=headers, data=file_bytes, timeout=60)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Supabase photo upload failed: {response.status_code} - {response.text}"
        )

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{object_path}"
    return public_url


def build_status_filter_query():
    selected_status = request.args.get("status", "total")
    keyword = request.args.get("keyword", "").strip()
    ward = request.args.get("ward", "").strip()
    category = request.args.get("category", "").strip()
    zonal_office = request.args.get("zonal_office", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()

    where_clauses = []
    params = []

    if selected_status == "open":
        where_clauses.append("""
            (final_resolution_status IS NULL
             OR final_resolution_status=''
             OR final_resolution_status='Open')
        """)
    elif selected_status == "in_progress":
        where_clauses.append("final_resolution_status='In Progress'")
    elif selected_status == "resolved":
        where_clauses.append("""
            (final_resolution_status='Resolved'
             OR final_resolution_status='Closed'
             OR status='Resolved')
        """)

    if keyword:
        where_clauses.append("""
            (complaint_no LIKE ?
             OR petitioner_name LIKE ?
             OR mobile LIKE ?
             OR ward_no LIKE ?
             OR category LIKE ?
             OR zonal_office LIKE ?
             OR description LIKE ?
             OR response_details LIKE ?
             OR remarks_and_notes LIKE ?)
        """)
        search_value = f"%{keyword}%"
        params.extend([search_value] * 9)

    if ward:
        where_clauses.append("ward_no = ?")
        params.append(ward)

    if category:
        where_clauses.append("category = ?")
        params.append(category)

    if zonal_office:
        where_clauses.append("zonal_office = ?")
        params.append(zonal_office)

    if from_date:
        where_clauses.append("complaint_date >= ?")
        params.append(from_date)

    if to_date:
        where_clauses.append("complaint_date <= ?")
        params.append(to_date)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    return selected_status, keyword, ward, category, zonal_office, from_date, to_date, where_sql, params



def get_dashboard_data(complaint_type="Complaint"):
    selected_status, keyword, ward, category, zonal_office, from_date, to_date, where_sql, params = build_status_filter_query()
    complaint_type = request.args.get("complaint_type", "Complaint")
    if complaint_type not in ("Complaint", "Needs"):
        complaint_type = "Complaint"
    if where_sql:
        where_sql = where_sql + " AND complaint_type = ?"
    else:
        where_sql = "WHERE complaint_type = ?"
    params.append(complaint_type)

    if where_sql:
        where_sql = where_sql + " AND complaint_type = ?"
    else:
        where_sql = "WHERE complaint_type = ?"

    params = params + [complaint_type]

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE complaint_type=?",
        (complaint_type,)
    ).fetchone()[0]

    open_count = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE complaint_type=?
          AND (
                final_resolution_status IS NULL
             OR final_resolution_status=''
             OR final_resolution_status='Open'
          )
    """, (complaint_type,)).fetchone()[0]

    in_progress = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE complaint_type=?
          AND final_resolution_status='In Progress'
    """, (complaint_type,)).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE complaint_type=?
          AND (
                final_resolution_status='Resolved'
             OR final_resolution_status='Closed'
             OR status='Resolved'
          )
    """, (complaint_type,)).fetchone()[0]

    complaints = conn.execute(
        f"""
        SELECT
            id,
            complaint_no,
            complaint_date,
            zonal_office,
            petitioner_name,
            mobile,
            ward_no,
            category,
            description,
            ward_notification_status,
            ward_representative,
            response_details,
            informed_to_department,
            progress_update_status,
            final_resolution_status,
            remarks_and_notes,
            before_photo,
            petitioner_application,
            after_photo,
            status,
            complaint_type
        FROM complaints
        {where_sql}
        ORDER BY id DESC
        """,
        params
    ).fetchall()

    wards = conn.execute("""
        SELECT DISTINCT ward_no
        FROM complaints
        WHERE complaint_type=?
          AND ward_no IS NOT NULL AND ward_no != ''
        ORDER BY ward_no
    """, (complaint_type,)).fetchall()

    zones = conn.execute("""
        SELECT DISTINCT zonal_office
        FROM complaints
        WHERE complaint_type=?
          AND zonal_office IS NOT NULL AND zonal_office != ''
        ORDER BY zonal_office
    """, (complaint_type,)).fetchall()

    categories = conn.execute("""
        SELECT DISTINCT category
        FROM complaints
        WHERE complaint_type=?
          AND category IS NOT NULL AND category != ''
        ORDER BY category
    """, (complaint_type,)).fetchall()

    conn.close()

    return dict(
        total=total,
        open_count=open_count,
        in_progress=in_progress,
        resolved=resolved,
        complaints=complaints,
        selected_status=selected_status,
        keyword=keyword,
        selected_ward=ward,
        selected_category=category,
        selected_zone=zonal_office,
        from_date=from_date,
        to_date=to_date,
        wards=wards,
        zones=zones,
        categories=categories,
        complaint_type=complaint_type,
        dashboard_title="Needs Dashboard" if complaint_type == "Needs" else "Complaint Dashboard",
        is_needs_dashboard=(complaint_type == "Needs")
    )



def validate_required_complaint_fields():
    required_fields = {
        "Complaint Attender": request.form.get("complaint_attender", "").strip(),
        "Complaint Date": request.form.get("complaint_date", "").strip(),
        "Petitioner Name": request.form.get("petitioner_name", "").strip(),
        "Mobile Number": request.form.get("mobile", "").strip(),
        "Petitioner Address": request.form.get("petitioner_address", "").strip(),
        "Category": request.form.get("category", "").strip(),
    }

    missing = [name for name, value in required_fields.items() if not value]

    if missing:
        return "Please fill in the mandatory fields: " + ", ".join(missing)

    mobile = request.form.get("mobile", "").strip()

    if not mobile.isdigit() or len(mobile) != 10:
        return "Mobile Number must contain exactly 10 digits."

    return None



def is_admin():
    return session.get("role") == "Admin"


initialize_database()


@app.route("/set_language/<lang>")
def set_language(lang):
    if lang not in ("en", "ta"):
        lang = "en"

    session["lang"] = lang
    return redirect(request.referrer or "/")


@app.context_processor
def inject_language():
    return {
        "current_lang": session.get("lang", "en")
    }


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
        WHERE complaint_type='Complaint' OR complaint_type IS NULL OR complaint_type=''
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template("complaints.html", complaints=complaints)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login_page")

    data = get_dashboard_data("Complaint")
    return render_template("dashboard.html", **data)


@app.route("/needs_dashboard")
def needs_dashboard():
    if "user" not in session:
        return redirect("/login_page")

    data = get_dashboard_data("Needs")
    return render_template("dashboard.html", **data)


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
        WHERE (complaint_type='Complaint' OR complaint_type IS NULL OR complaint_type='')
        AND (
             complaint_no LIKE ?
        OR petitioner_name LIKE ?
        OR mobile LIKE ?
        OR ward_no LIKE ?
        OR category LIKE ?
        OR zonal_office LIKE ?
        )
        """,
        (
            f"%{keyword}%",
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

    return render_template("add_complaint.html", is_needs=False)


@app.route("/needs_add")
def needs_add():
    if "user" not in session:
        return redirect("/login_page")

    return render_template("add_complaint.html", is_needs=True)


@app.route("/save", methods=["POST"])
def save():
    if "user" not in session:
        return redirect("/login_page")

    validation_error = validate_required_complaint_fields()
    if validation_error:
        return validation_error

    before_photo_path = save_uploaded_file(
        request.files.get("before_photo"),
        "before"
    )

    petitioner_application_path = save_uploaded_file(
        request.files.get("petitioner_application"),
        "application"
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

    complaint_type = request.form.get("complaint_type", "Complaint")
    if complaint_type not in ("Complaint", "Needs"):
        complaint_type = "Complaint"

    conn = get_db()
    complaint_no = generate_complaint_no(conn, complaint_type)

    conn.execute(
        """
        INSERT INTO complaints
        (
            complaint_no,
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
            petitioner_application,
            after_photo,
            status,
            complaint_type
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            complaint_no,
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
            petitioner_application_path,
            after_photo_path,
            "Open",
            complaint_type
        )
    )

    conn.commit()
    conn.close()

    if complaint_type == "Needs":
        return redirect("/needs_dashboard")

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

    return render_template("edit_complaint.html", row=row, is_needs=(row and row["complaint_type"] == "Needs"))


@app.route("/update/<int:id>", methods=["POST"])
def update(id):
    if "user" not in session:
        return redirect("/login_page")

    validation_error = validate_required_complaint_fields()
    if validation_error:
        return validation_error

    conn = get_db()

    existing_row = conn.execute(
        """
        SELECT before_photo, petitioner_application, after_photo, complaint_type
        FROM complaints
        WHERE id=?
        """,
        (id,)
    ).fetchone()

    before_photo_path = existing_row["before_photo"] if existing_row else ""
    petitioner_application_path = existing_row["petitioner_application"] if existing_row else ""
    after_photo_path = existing_row["after_photo"] if existing_row else ""

    new_before_photo = save_uploaded_file(
        request.files.get("before_photo"),
        "before"
    )

    if new_before_photo:
        before_photo_path = new_before_photo

    new_petitioner_application = save_uploaded_file(
        request.files.get("petitioner_application"),
        "application"
    )

    if new_petitioner_application:
        petitioner_application_path = new_petitioner_application

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
                petitioner_application=?,
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
                petitioner_application_path,
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
                before_photo=?,
                petitioner_application=?
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
                petitioner_application_path,
                id
            )
        )

    conn.commit()
    complaint_type = existing_row["complaint_type"] if existing_row and existing_row["complaint_type"] else "Complaint"
    conn.close()

    if complaint_type == "Needs":
        return redirect("/needs_dashboard")

    return redirect("/")


@app.route("/resolve/<int:id>")
def resolve(id):
    if "user" not in session:
        return redirect("/login_page")

    if not is_admin():
        return redirect("/")

    conn = get_db()

    type_row = conn.execute("SELECT complaint_type FROM complaints WHERE id=?", (id,)).fetchone()
    complaint_type = type_row["complaint_type"] if type_row and type_row["complaint_type"] else "Complaint"

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

    if complaint_type == "Needs":
        return redirect("/needs_dashboard")

    return redirect("/")


@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/login_page")

    if not is_admin():
        return redirect("/")

    conn = get_db()

    type_row = conn.execute("SELECT complaint_type FROM complaints WHERE id=?", (id,)).fetchone()
    complaint_type = type_row["complaint_type"] if type_row and type_row["complaint_type"] else "Complaint"

    conn.execute(
        """
        DELETE FROM complaints
        WHERE id=?
        """,
        (id,)
    )

    conn.commit()
    conn.close()

    if complaint_type == "Needs":
        return redirect("/needs_dashboard")

    return redirect("/")


@app.route("/photo-link/<int:id>/<photo_type>")
def photo_link(id, photo_type):
    if "user" not in session:
        return redirect("/login_page")

    if photo_type not in ("before", "after"):
        return "Invalid photo type", 400

    column_name = "before_photo" if photo_type == "before" else "after_photo"

    conn = get_db()
    row = conn.execute(
        f"SELECT {column_name} FROM complaints WHERE id=?",
        (id,)
    ).fetchone()
    conn.close()

    if not row or not row[column_name]:
        return "Photo not available", 404

    photo_path = row[column_name]

    if photo_path.startswith("http://") or photo_path.startswith("https://"):
        return redirect(photo_path)

    return redirect("/static/" + photo_path)


@app.route("/export_status_details")
def export_status_details():
    if "user" not in session:
        return redirect("/login_page")

    if not is_admin():
        return redirect("/dashboard")

    (
        selected_status,
        keyword,
        ward,
        category,
        zonal_office,
        from_date,
        to_date,
        where_sql,
        params
    ) = build_status_filter_query()

    conn = get_db()

    query = f"""
        SELECT
            complaint_no AS "Complaint No",
            complaint_date AS "Complaint Date",
            ward_no AS "Ward No",
            zonal_office AS "Zonal Office",
            category AS "Category",
            petitioner_name AS "Petitioner Name",
            mobile AS "Mobile",
            description AS "Description",
            response_details AS "Ward Response",
            informed_to_department AS "Informed To Department",
            progress_update_status AS "Progress",
            final_resolution_status AS "Final Resolution Status",
            remarks_and_notes AS "Remarks And Comments",
            before_photo AS "Before Photo",
            after_photo AS "After Photo",
            status AS "Status"
        FROM complaints
        {where_sql}
        ORDER BY id DESC
    """

    df = pd.read_sql_query(query.replace("?", "%s"), conn.raw, params=params)
    conn.close()

    df.insert(0, "S.No", range(1, len(df) + 1))

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Status Details")

    output.seek(0)

    status_name = selected_status.replace("_", "-")
    filename = f"complaint_status_details_{status_name}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



def export_complaints_by_type(complaint_type="Complaint"):
    if "user" not in session:
        return redirect("/login_page")

    if complaint_type not in ("Complaint", "Needs"):
        complaint_type = "Complaint"

    conn = get_db()

    if is_admin():
        query = """
        SELECT
            id AS 'ID',
            complaint_no AS 'Complaint No',
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
            petitioner_application AS 'Petitioner Application',
            informed_to_department AS 'Informed To Department',
            inital_action_status AS 'Initial Action Status',
            progress_update_status AS 'Progress Update Status',
            final_resolution_status AS 'Final Resolution Status',
            after_photo AS 'After Resolution Photo',
            remarks_and_notes AS 'Remarks And Notes',
            status AS 'Status',
            complaint_type AS 'Complaint Type'
        FROM complaints
        WHERE complaint_type=%s
        ORDER BY id DESC
        """
    else:
        query = """
        SELECT
            id AS 'ID',
            complaint_no AS 'Complaint No',
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
            petitioner_application AS 'Petitioner Application',
            status AS 'Status',
            complaint_type AS 'Complaint Type'
        FROM complaints
        WHERE complaint_type=%s
        ORDER BY id DESC
        """

    df = pd.read_sql_query(query, conn.raw, params=(complaint_type,))
    conn.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=complaint_type)

    output.seek(0)

    filename = "needs_complaints.xlsx" if complaint_type == "Needs" else "complaints.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/export")
def export():
    return export_complaints_by_type("Complaint")


@app.route("/export_needs")
def export_needs():
    return export_complaints_by_type("Needs")


@app.route("/storage-test")
def storage_test():
    if not SUPABASE_URL:
        return "SUPABASE_URL is missing"
    if not SUPABASE_SERVICE_ROLE_KEY:
        return "SUPABASE_SERVICE_ROLE_KEY is missing"
    return f"Supabase Storage configured. Bucket: {SUPABASE_STORAGE_BUCKET}"


@app.route("/db-test")
def db_test():
    try:
        conn = get_db()
        cur = conn.execute("SELECT COUNT(*) FROM complaints")
        count = cur.fetchone()[0]
        conn.close()
        return f"Supabase connected successfully. Complaints count: {count}"
    except Exception as e:
        return f"Database error: {str(e)}"


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login_page")


if __name__ == "__main__":
    app.run(debug=True)
