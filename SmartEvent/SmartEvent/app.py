from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from functools import wraps
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartevent.db")

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, role TEXT NOT NULL,
        phone TEXT, location TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS worker_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE, skills TEXT, experience TEXT,
        availability TEXT, expected_pay REAL DEFAULT 0, rating REAL DEFAULT 0,
        verified INTEGER DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, name TEXT NOT NULL, event_type TEXT,
        event_date TEXT, event_time TEXT, venue TEXT, location TEXT,
        guests INTEGER DEFAULT 0, budget REAL DEFAULT 0,
        description TEXT, status TEXT DEFAULT 'Planning',
        FOREIGN KEY(owner_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS caterers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT, specialty TEXT,
        price_per_person REAL DEFAULT 0, rating REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caterer_id INTEGER, name TEXT NOT NULL, category TEXT,
        price REAL DEFAULT 0, FOREIGN KEY(caterer_id) REFERENCES caterers(id)
    );
    CREATE TABLE IF NOT EXISTS event_catering (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, caterer_id INTEGER, menu_id INTEGER,
        guests INTEGER, estimated_cost REAL,
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, title TEXT NOT NULL, skill TEXT,
        workers_needed INTEGER DEFAULT 1, pay REAL DEFAULT 0,
        start_time TEXT, end_time TEXT, status TEXT DEFAULT 'Open',
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER, worker_id INTEGER, status TEXT DEFAULT 'Applied',
        UNIQUE(job_id, worker_id)
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER, worker_id INTEGER,
        check_in TEXT, check_out TEXT
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER, job_id INTEGER, amount REAL,
        status TEXT DEFAULT 'Pending', paid_at TEXT
    );
    CREATE TABLE IF NOT EXISTS guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, name TEXT, email TEXT, phone TEXT,
        rsvp TEXT DEFAULT 'Pending', table_no TEXT
    );
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER, reviewer_id INTEGER, worker_id INTEGER,
        rating INTEGER, comment TEXT
    );
    """)
    # Small demo dataset for a fresh install
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.execute("INSERT INTO users(name,email,password,role,phone,location) VALUES(?,?,?,?,?,?)",
                    ("Admin User","admin@smartevent.local",generate_password_hash("admin123"),"admin","9999999999","Mangalore"))
        con.execute("INSERT INTO users(name,email,password,role,phone,location) VALUES(?,?,?,?,?,?)",
                    ("Demo Owner","owner@smartevent.local",generate_password_hash("owner123"),"owner","8888888888","Mangalore"))
        con.execute("INSERT INTO users(name,email,password,role,phone,location) VALUES(?,?,?,?,?,?)",
                    ("Demo Worker","worker@smartevent.local",generate_password_hash("worker123"),"worker","7777777777","Mangalore"))
        worker_id = con.execute("SELECT id FROM users WHERE email='worker@smartevent.local'").fetchone()[0]
        con.execute("INSERT INTO worker_profiles(user_id,skills,experience,availability,expected_pay,verified,rating) VALUES(?,?,?,?,?,?,?)",
                    (worker_id,"Catering, Serving, Kitchen Helper","2 years","Saturday & Sunday, 5 PM - 11 PM",800,1,4.8))
        con.execute("INSERT INTO caterers(name,phone,specialty,price_per_person,rating) VALUES(?,?,?,?,?)",
                    ("Coastal Caterers","9000011111","South Indian & Wedding Catering",250,4.7))
    con.commit()
    con.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You don't have permission to open that page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.context_processor
def inject_user():
    return {"current_user": session}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form["role"]
        phone = request.form.get("phone","")
        location = request.form.get("location","")
        if role not in ("worker","owner","guest"):
            role = "guest"
        con = db()
        try:
            cur = con.execute("INSERT INTO users(name,email,password,role,phone,location) VALUES(?,?,?,?,?,?)",
                              (name,email,generate_password_hash(password),role,phone,location))
            uid = cur.lastrowid
            if role == "worker":
                con.execute("INSERT INTO worker_profiles(user_id,skills,experience,availability,expected_pay) VALUES(?,?,?,?,?)",
                            (uid,request.form.get("skills",""),request.form.get("experience",""),
                             request.form.get("availability",""),float(request.form.get("expected_pay") or 0)))
            con.commit()
            flash("Account created. You can login now.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "danger")
        finally:
            con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    con = db()
    role = session["role"]
    if role == "worker":
        jobs = con.execute("""SELECT j.*, e.name event_name,e.venue,e.location,e.event_date
                              FROM jobs j JOIN events e ON e.id=j.event_id
                              WHERE j.status='Open' ORDER BY e.event_date LIMIT 8""").fetchall()
        profile = con.execute("SELECT * FROM worker_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
        applications = con.execute("""SELECT a.*,j.title,e.name event_name
                                      FROM applications a JOIN jobs j ON j.id=a.job_id
                                      JOIN events e ON e.id=j.event_id
                                      WHERE a.worker_id=? ORDER BY a.id DESC LIMIT 8""",(session["user_id"],)).fetchall()
        con.close()
        return render_template("worker_dashboard.html", jobs=jobs, profile=profile, applications=applications)
    if role == "owner":
        events = con.execute("SELECT * FROM events WHERE owner_id=? ORDER BY event_date", (session["user_id"],)).fetchall()
        con.close()
        return render_template("owner_dashboard.html", events=events)
    if role == "admin":
        stats = {
            "workers": con.execute("SELECT COUNT(*) FROM users WHERE role='worker'").fetchone()[0],
            "owners": con.execute("SELECT COUNT(*) FROM users WHERE role='owner'").fetchone()[0],
            "guests": con.execute("SELECT COUNT(*) FROM users WHERE role='guest'").fetchone()[0],
            "events": con.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "jobs": con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "pending": con.execute("SELECT COUNT(*) FROM applications WHERE status='Applied'").fetchone()[0]
        }
        workers = con.execute("""SELECT u.*,w.skills,w.verified,w.rating,w.availability
                                FROM users u JOIN worker_profiles w ON w.user_id=u.id
                                WHERE u.role='worker' ORDER BY u.id DESC""").fetchall()
        con.close()
        return render_template("admin_dashboard.html", stats=stats, workers=workers)
    con.close()
    return render_template("guest_dashboard.html")

@app.route("/events/new", methods=["GET","POST"])
@login_required
@role_required("owner")
def new_event():
    if request.method == "POST":
        con = db()
        con.execute("""INSERT INTO events(owner_id,name,event_type,event_date,event_time,venue,location,guests,budget,description)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (session["user_id"],request.form["name"],request.form["event_type"],
                     request.form["event_date"],request.form["event_time"],request.form["venue"],
                     request.form["location"],int(request.form.get("guests") or 0),
                     float(request.form.get("budget") or 0),request.form.get("description","")))
        con.commit(); con.close()
        flash("Event created successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("event_form.html")

@app.route("/events/<int:event_id>")
@login_required
def event_detail(event_id):
    con = db()
    event = con.execute("""SELECT e.*,u.name owner_name FROM events e JOIN users u ON u.id=e.owner_id
                           WHERE e.id=?""",(event_id,)).fetchone()
    if not event:
        con.close(); return "Event not found",404
    jobs = con.execute("SELECT * FROM jobs WHERE event_id=?", (event_id,)).fetchall()
    guests = con.execute("SELECT * FROM guests WHERE event_id=?", (event_id,)).fetchall()
    caterers = con.execute("SELECT * FROM caterers ORDER BY rating DESC").fetchall()
    con.close()
    return render_template("event_detail.html",event=event,jobs=jobs,guests=guests,caterers=caterers)

@app.route("/events/<int:event_id>/jobs/new", methods=["POST"])
@login_required
@role_required("owner","admin")
def new_job(event_id):
    con = db()
    con.execute("""INSERT INTO jobs(event_id,title,skill,workers_needed,pay,start_time,end_time)
                   VALUES(?,?,?,?,?,?,?)""",
                (event_id,request.form["title"],request.form["skill"],
                 int(request.form.get("workers_needed") or 1),float(request.form.get("pay") or 0),
                 request.form.get("start_time",""),request.form.get("end_time","")))
    con.commit(); con.close()
    flash("Worker job added.", "success")
    return redirect(url_for("event_detail", event_id=event_id))

@app.route("/jobs/<int:job_id>/apply", methods=["POST"])
@login_required
@role_required("worker")
def apply_job(job_id):
    con = db()
    try:
        con.execute("INSERT INTO applications(job_id,worker_id) VALUES(?,?)",(job_id,session["user_id"]))
        con.commit(); flash("Application sent to the event owner.", "success")
    except sqlite3.IntegrityError:
        flash("You already applied for this job.", "warning")
    con.close()
    return redirect(url_for("dashboard"))

@app.route("/profile/worker", methods=["GET","POST"])
@login_required
@role_required("worker")
def worker_profile():
    con = db()
    if request.method == "POST":
        con.execute("""UPDATE users SET name=?,phone=?,location=? WHERE id=?""",
                    (request.form["name"],request.form["phone"],request.form["location"],session["user_id"]))
        con.execute("""UPDATE worker_profiles SET skills=?,experience=?,availability=?,expected_pay=?
                       WHERE user_id=?""",
                    (request.form["skills"],request.form["experience"],request.form["availability"],
                     float(request.form.get("expected_pay") or 0),session["user_id"]))
        con.commit(); session["name"]=request.form["name"]
        flash("Profile updated.", "success")
    user = con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    profile = con.execute("SELECT * FROM worker_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    con.close()
    return render_template("worker_profile.html",user=user,profile=profile)

@app.route("/admin/verify/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def verify_worker(user_id):
    con=db()
    con.execute("UPDATE worker_profiles SET verified=1 WHERE user_id=?", (user_id,))
    con.commit(); con.close()
    flash("Worker verified.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/applications")
@login_required
@role_required("admin","owner")
def applications():
    con=db()
    rows=con.execute("""SELECT a.id,a.status,w.name worker_name,w.email,j.title,e.name event_name,
                               j.pay,e.event_date
                        FROM applications a
                        JOIN users w ON w.id=a.worker_id
                        JOIN jobs j ON j.id=a.job_id
                        JOIN events e ON e.id=j.event_id
                        ORDER BY a.id DESC""").fetchall()
    con.close()
    return render_template("applications.html",rows=rows)

@app.route("/applications/<int:application_id>/<action>", methods=["POST"])
@login_required
@role_required("admin","owner")
def update_application(application_id, action):
    status = "Accepted" if action == "accept" else "Rejected"
    con=db()
    row=con.execute("SELECT * FROM applications WHERE id=?",(application_id,)).fetchone()
    con.execute("UPDATE applications SET status=? WHERE id=?",(status,application_id))
    if status=="Accepted" and row:
        job=con.execute("SELECT * FROM jobs WHERE id=?",(row["job_id"],)).fetchone()
        con.execute("INSERT INTO payments(worker_id,job_id,amount) VALUES(?,?,?)",
                    (row["worker_id"],row["job_id"],job["pay"]))
    con.commit(); con.close()
    flash(f"Application {status.lower()}.","success")
    return redirect(url_for("applications"))

@app.route("/guests/add/<int:event_id>", methods=["POST"])
@login_required
@role_required("owner","admin")
def add_guest(event_id):
    con=db()
    con.execute("INSERT INTO guests(event_id,name,email,phone,table_no) VALUES(?,?,?,?,?)",
                (event_id,request.form["name"],request.form.get("email",""),
                 request.form.get("phone",""),request.form.get("table_no","")))
    con.commit(); con.close()
    flash("Guest added.","success")
    return redirect(url_for("event_detail",event_id=event_id))

@app.route("/caterers")
@login_required
def caterers():
    con=db()
    rows=con.execute("SELECT * FROM caterers ORDER BY rating DESC").fetchall()
    con.close()
    return render_template("caterers.html",caterers=rows)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
