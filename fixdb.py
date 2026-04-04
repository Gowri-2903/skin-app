import sqlite3
import os

# ── Same path logic as app.py ──────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = "/data" if os.path.exists("/data") else BASE_DIR
HISTORY_DB = os.path.join(DATA_DIR, "history.db")

print(f"Using database: {HISTORY_DB}")

conn = sqlite3.connect(HISTORY_DB)
conn.row_factory = sqlite3.Row

# ── Fix 'unknown' / blank disease names ───────────────────────────────────
try:
    cursor = conn.execute("""
        SELECT COUNT(*) as count FROM history
        WHERE LOWER(TRIM(disease_name)) = 'unknown'
           OR disease_name IS NULL
           OR TRIM(disease_name) = ''
    """)
    count = cursor.fetchone()["count"]
    print(f"Found {count} records with unknown/blank disease name.")

    conn.execute("""
        UPDATE history
        SET disease_name = 'Disease Unidentified'
        WHERE LOWER(TRIM(disease_name)) = 'unknown'
           OR disease_name IS NULL
           OR TRIM(disease_name) = ''
    """)
    conn.commit()
    print(f"✅ Fixed {count} records → 'Disease Unidentified'.")
except Exception as e:
    print(f"❌ Fix failed: {e}")

conn.close()
print("Done.")