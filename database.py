import sqlite3
import os

# ── Use /data/ on Render (persistent disk), fall back to script dir locally ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/data" if os.path.exists("/data") else BASE_DIR
DB_NAME  = os.path.join(DATA_DIR, "history.db")

print("ACTUAL DATABASE USED:", DB_NAME)

# ---------------- DATABASE INITIALIZATION ----------------

def init_db():
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ---------- USERS TABLE ----------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email    TEXT UNIQUE,
            password TEXT,
            role     TEXT DEFAULT 'user'
        )
    """)

    # ---------- HISTORY TABLE ----------
    # username stored directly — no JOIN needed for admin view
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            username     TEXT,
            image_name   TEXT,
            disease      TEXT,
            confidence   REAL,
            date         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # ── Migrate existing DB: add username column if missing ──
    try:
        cursor.execute("ALTER TABLE history ADD COLUMN username TEXT")
        conn.commit()
        print("✅ Migrated: added username column to history.")
    except sqlite3.OperationalError:
        pass  # Already exists

    # ---------- DISEASE INFORMATION TABLE ----------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disease_info (
            disease_name           TEXT PRIMARY KEY,
            display_name           TEXT,
            description            TEXT,
            medical_recommendation TEXT,
            skincare_advice        TEXT
        )
    """)

    conn.commit()
    conn.close()

# ---------------- HISTORY FUNCTIONS ----------------

def insert_history(user_id, username, image_name, disease, confidence):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO history (user_id, username, image_name, disease, confidence)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, image_name, disease, confidence))
    conn.commit()
    conn.close()


def get_history(user_id):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, image_name, disease, confidence, date
        FROM history
        WHERE user_id=?
        ORDER BY date DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ---------------- DISEASE KNOWLEDGE BASE ----------------

def get_disease_info(disease_name):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT display_name, description, medical_recommendation, skincare_advice
        FROM disease_info
        WHERE disease_name=?
    """, (disease_name,))
    result = cursor.fetchone()
    conn.close()
    return result

# ---------------- USER AUTHENTICATION ----------------

def register_user(username, email, password):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login_user(username, password):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()
    conn.close()
    return user

# ---------------- ADMIN FUNCTIONS ----------------

def get_all_users():
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, role
        FROM users
        ORDER BY id
    """)
    users = cursor.fetchall()
    conn.close()
    return users


def update_disease_info(disease_name, description, medical_rec, skincare):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE disease_info
        SET description=?, medical_recommendation=?, skincare_advice=?
        WHERE disease_name=?
    """, (description, medical_rec, skincare, disease_name))
    conn.commit()
    conn.close()


def promote_to_admin(user_id):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role='admin' WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def get_all_history():
    conn   = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # ── Use stored username — no JOIN, never returns null usernames ──
    cursor.execute("""
        SELECT id, username, image_name, disease, confidence, date
        FROM history
        ORDER BY date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


print("DATABASE PATH:", DB_NAME)

if __name__ == "__main__":
    init_db()