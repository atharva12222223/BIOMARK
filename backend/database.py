import os, random
from datetime import datetime, timedelta
from passlib.context import CryptContext

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

# Fix Render's postgres:// → postgresql://
if USE_PG and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw):    return pwd.hash(pw)
def check_password(p, h): return pwd.verify(p, h)

# ═══════════════════════════════════════════════════════
#  DB CONNECTION — PostgreSQL (Render) or SQLite (local)
# ═══════════════════════════════════════════════════════

if USE_PG:
    import psycopg2
    import psycopg2.extras

    def get_db():
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn

    def _execute(conn, sql, params=None):
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        return cur

    def _fetchone(conn, sql, params=None):
        cur = _execute(conn, sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def _fetchall(conn, sql, params=None):
        cur = _execute(conn, sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    PH = "%s"   # placeholder

else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), "biomark.db")

    def get_db():
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _execute(conn, sql, params=None):
        return conn.execute(sql, params or ())

    def _fetchone(conn, sql, params=None):
        return conn.execute(sql, params or ()).fetchone()

    def _fetchall(conn, sql, params=None):
        return conn.execute(sql, params or ()).fetchall()

    PH = "?"    # placeholder

# ═══════════════════════════════════════════════════════
#  HELPERS — dict access for both backends
# ═══════════════════════════════════════════════════════
def row_val(row, key):
    """Get value from a row regardless of backend (dict or sqlite3.Row)."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[key]

# ═══════════════════════════════════════════════════════
#  INIT DB
# ═══════════════════════════════════════════════════════
def init_db():
    db = get_db()
    if USE_PG:
        cur = db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id            SERIAL PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                fullname      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id            SERIAL PRIMARY KEY,
                name          TEXT NOT NULL,
                regno         TEXT UNIQUE NOT NULL,
                cls           TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id         SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                date       TEXT NOT NULL,
                present    INTEGER NOT NULL DEFAULT 0,
                UNIQUE(student_id, date)
            );
            CREATE TABLE IF NOT EXISTS marks (
                id         SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                subject    TEXT NOT NULL,
                marks      INTEGER NOT NULL,
                grade      TEXT NOT NULL,
                UNIQUE(student_id, subject)
            );
            CREATE TABLE IF NOT EXISTS face_scans (
                id         SERIAL PRIMARY KEY,
                student_id INTEGER UNIQUE NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                scan_count INTEGER NOT NULL DEFAULT 0
            );
        """)
        cur.close()
        db.commit()

        # Check if seeded
        count = row_val(_fetchone(db, "SELECT COUNT(*) AS cnt FROM teachers"), "cnt")
        if count == 0:
            _seed(db)
    else:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS teachers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                fullname      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                regno         TEXT UNIQUE NOT NULL,
                cls           TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                date       TEXT NOT NULL,
                present    INTEGER NOT NULL DEFAULT 0,
                UNIQUE(student_id, date)
            );
            CREATE TABLE IF NOT EXISTS marks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                subject    TEXT NOT NULL,
                marks      INTEGER NOT NULL,
                grade      TEXT NOT NULL,
                UNIQUE(student_id, subject)
            );
            CREATE TABLE IF NOT EXISTS face_scans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER UNIQUE NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                scan_count INTEGER NOT NULL DEFAULT 0
            );
        """)
        if db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] == 0:
            _seed(db)
        db.commit()

    db.close()

# ═══════════════════════════════════════════════════════
#  SEED DATA
# ═══════════════════════════════════════════════════════
def _seed(db):
    p = PH
    _execute(db, f"INSERT INTO teachers (username,password_hash,fullname) VALUES ({p},{p},{p})",
             ("sonali", hash_password("sonali"), "Sonali Deshpande"))

    data = [
        ("Parth Kulkarni", "457CS23063", "5th Sem A", "parth123", 78, 20),
        ("Ravi Kumar",     "457CS23041", "5th Sem A", "ravi123",  52, 20),
        ("Priya Shetty",   "457CS23052", "5th Sem A", "priya123", 63, 14),
        ("Arjun Das",      "457CS23017", "5th Sem A", "arjun123", 89, 20),
        ("Meena R",        "457CS23038", "5th Sem A", "meena123", 68, 20),
        ("Sneha Patil",    "457CS23059", "5th Sem A", "sneha123", 92, 20),
    ]
    subjects = ["Maths", "FOC", "IT Skills", "FEEE", "IT Lab", "FEEE Lab"]

    for name, regno, cls, pw, rate, scans in data:
        _execute(db, f"INSERT INTO students (name,regno,cls,password_hash) VALUES ({p},{p},{p},{p})",
                 (name, regno, cls, hash_password(pw)))

        if USE_PG:
            sid = row_val(_fetchone(db, "SELECT currval(pg_get_serial_sequence('students','id')) AS id"), "id")
        else:
            sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        base = datetime.now() - timedelta(days=90)
        for d in range(90):
            dt = (base + timedelta(days=d)).strftime("%Y-%m-%d")
            _execute(db,
                f"INSERT INTO attendance (student_id,date,present) VALUES ({p},{p},{p}) "
                f"ON CONFLICT(student_id,date) DO NOTHING",
                (sid, dt, 1 if random.random() < rate/100 else 0))

        for s in subjects:
            m = random.randint(50, 98)
            g = "A+" if m >= 90 else "A" if m >= 80 else "B+" if m >= 70 else "B" if m >= 60 else "C"
            _execute(db, f"INSERT INTO marks (student_id,subject,marks,grade) VALUES ({p},{p},{p},{p})",
                     (sid, s, m, g))

        _execute(db, f"INSERT INTO face_scans (student_id,scan_count) VALUES ({p},{p})",
                 (sid, scans))

    db.commit()
    print("✅ Seeded | Teacher: sonali/sonali | Student: 457CS23063/parth123")
