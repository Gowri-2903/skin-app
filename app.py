from flask import Flask, request, jsonify, send_from_directory
import os, json, sqlite3, time
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.utils import load_img, img_to_array

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAIN_DB = os.path.join(BASE_DIR, "database.db")
HISTORY_DB = os.path.join(BASE_DIR, "history.db")

MODEL_PATH = os.path.join(BASE_DIR, "skin_disease_model.h5")
CLASS_PATH = os.path.join(BASE_DIR, "class_indices.json")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

model = load_model(MODEL_PATH)

with open(CLASS_PATH) as f:
    class_indices = json.load(f)

labels = {v: k for k, v in class_indices.items()}


def main_db():
    conn = sqlite3.connect(MAIN_DB)
    conn.row_factory = sqlite3.Row
    return conn


def history_db():
    conn = sqlite3.connect(HISTORY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_disease(name):
    conn = main_db()
    row = conn.execute("SELECT * FROM diseases WHERE name=?", (name,)).fetchone()
    conn.close()
    return row


# 🔐 LOGIN (FINAL FIXED)
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    print("LOGIN INPUT:", username, password)

    # Admin login
    if username == "admin" and password == "admin123":
        return jsonify({"message": "Login successful", "role": "admin"})

    conn = history_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()
    conn.close()

    print("DB USER:", user)

    if user:
        db_password = user["password"].strip()
        print("DB PASSWORD:", db_password)

        if db_password == password:
            return jsonify({"message": "Login successful", "role": user["role"]})

    return jsonify({"error": "Invalid credentials"})


# 🔐 CHANGE PASSWORD
@app.route("/change_password", methods=["PUT"])
def change_password():
    data = request.get_json()

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = history_db()
    conn.execute(
        "UPDATE users SET password=? WHERE username=?",
        (password, username)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Password updated"})


# 📝 REGISTER (FIXED)
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = history_db()

    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, "user")
        )
        conn.commit()
        return jsonify({"message": "Registered"})
    except Exception as e:
        print("REGISTER ERROR:", e)
        return jsonify({"error": "User exists"})
    finally:
        conn.close()


# 🤖 PREDICT
@app.route("/predict", methods=["POST"])
def predict():
    file = request.files["image"]
    username = request.form.get("username")

    filename = str(int(time.time())) + "_" + file.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    img = load_img(path, target_size=(224, 224))
    img = img_to_array(img) / 255.0
    img = np.expand_dims(img, axis=0)

    preds = model.predict(img)
    idx = int(np.argmax(preds))
    confidence = float(np.max(preds)) * 100

    disease_key = labels[idx]

    mapping = {
        "BA-cellulitis": "Cellulitis",
        "BA-impetigo": "Impetigo",
        "FU-athlete-foot": "Athlete-Foot",
        "FU-nail-fungus": "Nail Fungus",
        "FU-ringworm": "Ringworm",
        "PA-cutaneous-larva-migrans": "Cutaneous Larva Migrans",
        "VI-chickenpox": "Chickenpox",
        "VL-shingles": "Shingles",
        "healthy_skin": "Healthy"
    }

    disease_name = mapping.get(disease_key, "Unknown") if confidence >= 70 else "Unknown"

    data = get_disease(disease_name)

    if not data:
        data = {
            "name": "Disease Unidentified",
            "description": "Not recognized clearly",
            "recommendation": "Consult a dermatologist",
            "skincare": "Keep area clean and avoid self-diagnosis"
        }

    conn = history_db()
    user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    user_id = user["id"] if user else 1

    conn.execute(
        "INSERT INTO history (user_id, disease_name, confidence, image_path) VALUES (?, ?, ?, ?)",
        (user_id, data["name"], confidence, filename)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "Disease": data["name"],
        "Confidence": round(confidence, 2),
        "Description": data["description"],
        "Medical Recommendation": data["recommendation"],
        "Skincare Advice": data["skincare"]
    })


# 📜 HISTORY
@app.route("/history", methods=["GET"])
def history():
    conn = history_db()
    rows = conn.execute("SELECT * FROM history ORDER BY id DESC").fetchall()
    conn.close()

    result = []
    for r in rows:
        disease = get_disease(r["disease_name"])

        result.append({
            "disease": r["disease_name"],
            "confidence": r["confidence"],
            "image": request.host_url + "uploads/" + os.path.basename(r["image_path"]),
            "description": disease["description"] if disease else "",
            "recommendation": disease["recommendation"] if disease else "",
            "skincare": disease["skincare"] if disease else "",
        })

    return jsonify(result)


# 👥 USERS
@app.route("/admin/users", methods=["GET"])
def users():
    conn = history_db()
    rows = conn.execute("SELECT username, role FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/delete_user", methods=["DELETE"])
def delete_user():
    data = request.get_json()
    conn = history_db()
    conn.execute("DELETE FROM users WHERE username=?", (data["username"],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})


@app.route("/admin/promote_user", methods=["PUT"])
def promote_user():
    data = request.get_json()
    conn = history_db()
    conn.execute("UPDATE users SET role='admin' WHERE username=?", (data["username"],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Promoted"})


@app.route("/admin/demote_user", methods=["PUT"])
def demote_user():
    data = request.get_json()
    conn = history_db()
    conn.execute("UPDATE users SET role='user' WHERE username=?", (data["username"],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Demoted"})


# 📊 ADMIN HISTORY
@app.route("/admin/history", methods=["GET"])
def admin_history():
    conn = history_db()
    rows = conn.execute("""
        SELECT users.username, history.disease_name, history.confidence
        FROM history
        JOIN users ON history.user_id = users.id
        ORDER BY history.id DESC
    """).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


# 🦠 DISEASES
@app.route("/admin/diseases", methods=["GET"])
def diseases():
    conn = main_db()
    rows = conn.execute("SELECT * FROM diseases").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/update_disease", methods=["PUT"])
def update_disease():
    data = request.get_json()
    conn = main_db()
    conn.execute(
        "UPDATE diseases SET description=?, recommendation=?, skincare=? WHERE name=?",
        (data["description"], data["recommendation"], data["skincare"], data["name"])
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Updated"})


@app.route("/uploads/<filename>")
def upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)