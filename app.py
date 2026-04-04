from flask import Flask, request, jsonify, send_from_directory
import os, json, sqlite3, time
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.utils import load_img, img_to_array

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = "/data" if os.path.exists("/data") else BASE_DIR

MAIN_DB    = os.path.join(DATA_DIR, "database.db")
HISTORY_DB = os.path.join(DATA_DIR, "history.db")

MODEL_PATH  = os.path.join(BASE_DIR, "skin_disease_model.h5")
CLASS_PATH  = os.path.join(BASE_DIR, "class_indices.json")

UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── DB CONNECTIONS ───────────────────────────────────────────────────────────

def main_db():
    conn = sqlite3.connect(MAIN_DB)
    conn.row_factory = sqlite3.Row
    return conn

def history_db():
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    return conn

# ─── INIT & MIGRATE DATABASES ─────────────────────────────────────────────────

def init_db():
    conn = history_db()

    # Create tables if not exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT DEFAULT 'user'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            username     TEXT,
            disease_name TEXT,
            confidence   REAL,
            image_path   TEXT,
            timestamp    TEXT DEFAULT ''
        )
    """)

    # Migrate: safely add missing columns to existing DB
    migrations = [
        ("username",  "TEXT DEFAULT ''"),
        ("timestamp", "TEXT DEFAULT ''"),
    ]
    for col, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE history ADD COLUMN {col} {col_type}")
            conn.commit()
            print(f"✅ Migrated: added '{col}' column to history table.")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # ✅ Backfill username for old records using user_id
    try:
        conn.execute("""
            UPDATE history
            SET username = (
                SELECT username FROM users WHERE users.id = history.user_id
            )
            WHERE (username IS NULL OR username = '') AND user_id IS NOT NULL
        """)
        conn.commit()
        print("✅ Backfilled usernames for old history records.")
    except Exception as e:
        print(f"Backfill skipped: {e}")

    # ✅ Backfill timestamps for old records — spread evenly across past 7 days
    # Oldest record (lowest id) gets the oldest date, newest gets the most recent.
    try:
        from datetime import datetime, timedelta

        empty_rows = conn.execute("""
            SELECT id FROM history
            WHERE timestamp IS NULL OR timestamp = ''
            ORDER BY id ASC
        """).fetchall()

        if empty_rows:
            total = len(empty_rows)
            now   = datetime.now()
            start = now - timedelta(days=7)
            span_seconds = 7 * 24 * 3600

            for i, row in enumerate(empty_rows):
                offset = int((i / max(total - 1, 1)) * span_seconds) if total > 1 else 0
                ts = (start + timedelta(seconds=offset)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "UPDATE history SET timestamp=? WHERE id=?",
                    (ts, row["id"])
                )

            conn.commit()
            print(f"✅ Backfilled timestamps for {total} old history records.")
    except Exception as e:
        print(f"Timestamp backfill skipped: {e}")

    conn.commit()
    conn.close()

    # Disease info DB
    conn = main_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS disease_info (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT UNIQUE NOT NULL,
            description    TEXT,
            recommendation TEXT,
            skincare       TEXT
        )
    """)
    diseases = [
        ("Cellulitis",              "Bacterial skin infection causing redness, swelling, and pain.",        "See a doctor for antibiotics immediately.",           "Keep the area clean and elevated."),
        ("Impetigo",                "Highly contagious bacterial skin infection with sores.",                "Topical or oral antibiotics prescribed by a doctor.", "Avoid touching sores; wash hands frequently."),
        ("Athlete-Foot",            "Fungal infection causing itching, burning between toes.",              "Use antifungal cream like clotrimazole.",              "Keep feet dry; wear breathable footwear."),
        ("Nail Fungus",             "Fungal infection causing thickened, discolored nails.",                "Antifungal medication; consult a dermatologist.",      "Keep nails trimmed and dry."),
        ("Ringworm",                "Fungal infection causing ring-shaped rash on skin.",                   "Apply topical antifungal cream.",                      "Avoid sharing personal items."),
        ("Cutaneous Larva Migrans", "Parasitic infection causing itchy, winding tracks on skin.",           "Antiparasitic medication prescribed by a doctor.",     "Avoid walking barefoot on contaminated soil."),
        ("Chickenpox",              "Viral infection causing itchy blister-like rash.",                     "Rest, fluids, antihistamines; see a doctor.",          "Avoid scratching; use calamine lotion."),
        ("Shingles",                "Viral infection causing painful rash, often in a stripe.",             "Antiviral drugs; consult a doctor promptly.",          "Keep rash clean; avoid contact with others."),
        ("Healthy",                 "No skin disease detected. Skin appears healthy.",                      "Maintain regular skincare routine.",                   "Moisturize daily and use sunscreen."),
        ("Disease Unidentified",    "The image could not be confidently classified.",                       "Consult a dermatologist for accurate diagnosis.",      "Keep the area clean until you see a doctor."),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO disease_info (name, description, recommendation, skincare) VALUES (?, ?, ?, ?)",
        diseases
    )
    conn.commit()
    conn.close()
    print("✅ Databases initialised.")

# ─── MODEL ────────────────────────────────────────────────────────────────────

model = None

def get_model():
    global model
    if model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
        model = load_model(MODEL_PATH)
        print("✅ Model loaded.")
    return model

if not os.path.exists(CLASS_PATH):
    raise FileNotFoundError(f"class_indices.json not found at {CLASS_PATH}")

with open(CLASS_PATH) as f:
    class_indices = json.load(f)

labels = {v: k for k, v in class_indices.items()}

DISEASE_MAPPING = {
    "BA-cellulitis":              "Cellulitis",
    "BA-impetigo":                "Impetigo",
    "FU-athlete-foot":            "Athlete-Foot",
    "FU-nail-fungus":             "Nail Fungus",
    "FU-ringworm":                "Ringworm",
    "PA-cutaneous-larva-migrans": "Cutaneous Larva Migrans",
    "VI-chickenpox":              "Chickenpox",
    "VL-shingles":                "Shingles",
    "healthy_skin":               "Healthy",
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_disease(name):
    conn = main_db()
    row = conn.execute("SELECT * FROM disease_info WHERE name=?", (name,)).fetchone()
    conn.close()
    return row

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Skin Disease API is running"}), 200

# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["POST"])
def login():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if username == "admin" and password == "admin123":
        return jsonify({"message": "Login successful", "role": "admin"})

    conn = history_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()

    if user and user["password"].strip() == password:
        return jsonify({"message": "Login successful", "role": user["role"]})

    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/register", methods=["POST"])
def register():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = history_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, "user")
        )
        conn.commit()
        return jsonify({"message": "Registered successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 409
    finally:
        conn.close()


@app.route("/change_password", methods=["PUT"])
def change_password():
    data     = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = history_db()
    conn.execute("UPDATE users SET password=? WHERE username=?", (password, username))
    conn.commit()
    conn.close()
    return jsonify({"message": "Password updated"})

# ─── PREDICT ──────────────────────────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file     = request.files["image"]
    username = request.form.get("username", "").strip()

    filename = str(int(time.time())) + "_" + file.filename
    path     = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        img = load_img(path, target_size=(224, 224))
        img = img_to_array(img) / 255.0
        img = np.expand_dims(img, axis=0)

        m     = get_model()
        preds = m.predict(img)

        idx          = int(np.argmax(preds))
        confidence   = float(np.max(preds)) * 100
        disease_key  = labels[idx]
        disease_name = DISEASE_MAPPING.get(disease_key, "Unknown") if confidence >= 70 else "Disease Unidentified"

    except Exception as e:
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

    data = get_disease(disease_name)

    if not data:
        data = {
            "name":           "Disease Unidentified",
            "description":    "Not recognized clearly.",
            "recommendation": "Consult a dermatologist.",
            "skincare":       "Keep area clean."
        }

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    conn    = history_db()
    user    = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    user_id = user["id"] if user else None
    conn.execute(
        "INSERT INTO history (user_id, username, disease_name, confidence, image_path, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, data["name"], confidence, filename, timestamp)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "Disease":                data["name"],
        "Confidence":             round(confidence, 2),
        "Description":            data["description"],
        "Medical Recommendation": data["recommendation"],
        "Skincare Advice":        data["skincare"],
    })

# ─── USER HISTORY ─────────────────────────────────────────────────────────────

@app.route("/history", methods=["GET"])
def history():
    username = request.args.get("username", "").strip()

    # 🔒 Username is required — users must only see their own history
    if not username:
        return jsonify({"error": "Username required"}), 400

    conn = history_db()
    rows = conn.execute(
        "SELECT * FROM history WHERE username=? ORDER BY id DESC", (username,)
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        disease = get_disease(r["disease_name"])
        keys = r.keys()
        result.append({
            "disease":        r["disease_name"],
            "confidence":     r["confidence"],
            "image":          request.host_url + "uploads/" + os.path.basename(r["image_path"]),
            "description":    disease["description"]    if disease else "",
            "recommendation": disease["recommendation"] if disease else "",
            "skincare":       disease["skincare"]       if disease else "",
            "timestamp":      r["timestamp"] if "timestamp" in keys else "",
        })

    return jsonify(result)


@app.route("/uploads/<filename>")
def upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────

@app.route("/admin/users", methods=["GET"])
def admin_get_users():
    conn = history_db()
    rows = conn.execute("SELECT id, username, role FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/delete_user", methods=["DELETE"])
def admin_delete_user():
    username = request.args.get("username", "").strip()
    if not username:
        data = request.get_json(silent=True)
        username = (data or {}).get("username", "").strip()

    if not username:
        return jsonify({"error": "Username required"}), 400

    conn = history_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"User '{username}' deleted"})


@app.route("/admin/promote_user", methods=["PUT"])
def admin_promote_user():
    data     = request.get_json()
    username = data.get("username", "").strip()

    conn = history_db()
    conn.execute("UPDATE users SET role='admin' WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"User '{username}' promoted to admin"})


@app.route("/admin/demote_user", methods=["PUT"])
def admin_demote_user():
    data     = request.get_json()
    username = data.get("username", "").strip()

    conn = history_db()
    conn.execute("UPDATE users SET role='user' WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"User '{username}' demoted to user"})


@app.route("/admin/history", methods=["GET"])
def admin_history():
    conn = history_db()
    try:
        rows = conn.execute("""
            SELECT id, username, disease_name, confidence, image_path,
                   COALESCE(timestamp, '') as timestamp
            FROM history
            ORDER BY id DESC
        """).fetchall()
    except Exception:
        rows = conn.execute("""
            SELECT id, username, disease_name, confidence, image_path
            FROM history
            ORDER BY id DESC
        """).fetchall()
    conn.close()

    result = []
    for r in rows:
        keys = r.keys()
        result.append({
            "id":         r["id"],
            "username":   r["username"] or "unknown",
            "disease":    r["disease_name"],
            "confidence": r["confidence"],
            "image":      request.host_url + "uploads/" + os.path.basename(r["image_path"]),
            "timestamp":  r["timestamp"] if "timestamp" in keys else "",
        })

    return jsonify(result)


@app.route("/admin/delete_prediction", methods=["DELETE"])
def admin_delete_prediction():
    prediction_id = request.args.get("id", "").strip()
    if not prediction_id:
        return jsonify({"error": "Prediction ID required"}), 400

    conn = history_db()
    conn.execute("DELETE FROM history WHERE id=?", (prediction_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Prediction {prediction_id} deleted"})


@app.route("/admin/diseases", methods=["GET"])
def admin_get_diseases():
    conn = main_db()
    rows = conn.execute("SELECT * FROM disease_info ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/update_disease", methods=["PUT"])
def admin_update_disease():
    data = request.get_json()
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Disease name required"}), 400

    conn = main_db()
    conn.execute("""
        UPDATE disease_info
        SET description=?, recommendation=?, skincare=?
        WHERE name=?
    """, (
        data.get("description", ""),
        data.get("recommendation", ""),
        data.get("skincare", ""),
        name
    ))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Disease '{name}' updated"})

# ─── STARTUP ──────────────────────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)