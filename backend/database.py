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
                fullname      TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0
            );
            ALTER TABLE teachers ADD COLUMN IF NOT EXISTS is_admin INTEGER NOT NULL DEFAULT 0;
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
        
        # Upgrade existing 'sonali' user to core admin instantly for Postgres (Render)
        cur.execute("UPDATE teachers SET is_admin = 1 WHERE username = 'sonali'")
        
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
                fullname      TEXT NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0
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
        try:
            db.execute("ALTER TABLE teachers ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except:
            pass # ignore if already exists

        # Upgrade existing 'sonali' user to core admin automatically if she already exists
        _execute(db, "UPDATE teachers SET is_admin = 1 WHERE username = 'sonali'")

        if db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0] == 0:
            _seed(db)
        db.commit()

    db.close()

# ═══════════════════════════════════════════════════════
#  SEED DATA
# ═══════════════════════════════════════════════════════
def _seed(db):
    p = PH
    _execute(db, f"INSERT INTO teachers (username,password_hash,fullname,is_admin) VALUES ({p},{p},{p},1)",
             ("sonali", hash_password("sonali"), "Sonali Deshpande"))
    db.commit()
    print("[OK] Seeded | Teacher: sonali/sonali (Admin)")

