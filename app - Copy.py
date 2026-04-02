from flask import Flask, request, jsonify, session
import os
import json
import numpy as np
from tensorflow.keras.models import load_model
import sys
import time
from flask import send_from_directory

# access preprocess
sys.path.append(os.path.abspath("../utils"))
from preprocess import prepare_image

# database functions
from database import (
    init_db,
    insert_history,
    get_history,
    get_disease_info,
    register_user,
    login_user,
    get_all_users,
    update_disease_info,
    promote_to_admin,
    delete_user,
    get_all_history
)

app = Flask(__name__)
app.secret_key = "skin_ai_secret_key"

# initialize database
init_db()

# load trained CNN model
MODEL_PATH = "../model/skin_disease_model.h5"
model = load_model(MODEL_PATH)

# load class labels
with open("../model/class_indices.json", "r") as f:
    class_indices = json.load(f)

# reverse dictionary: index -> label
labels = {v: k for k, v in class_indices.items()}

# upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------- HOME ----------------
@app.route("/")
def home():
    return "Skin Disease AI Server Running"


# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"error": "All fields required"})

    if register_user(username, email, password):
        return jsonify({"message": "User registered successfully"})
    else:
        return jsonify({"error": "Username or email already exists"})


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    user = login_user(username, password)

    if user:
        session["user_id"] = user[0]
        session["role"] = user[1]
        return jsonify({"message": "Login successful", "role": user[1]})
    else:
        return jsonify({"error": "Invalid username or password"})


# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


# ---------------- PREDICT ----------------
@app.route("/predict", methods=["POST"])
def predict():

    # login required
    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    # check image
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"})

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"})

    # save image uniquely
    unique_name = str(int(time.time())) + "_" + file.filename
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(filepath)

    try:
        # preprocess
        img = prepare_image(filepath)

        # predict
        prediction = model.predict(img)
        class_id = np.argmax(prediction)
        confidence = float(np.max(prediction)) * 100
        disease_key = labels[class_id]

        # ---------- MEDICAL TRIAGE DECISION SYSTEM ----------

        # 1. Healthy skin special rule (very important)
        if disease_key == "healthy_skin":
            if confidence < 70:
                return jsonify({
                    "Disease": "Disease Undefined",
                    "Confidence": round(confidence, 2),
                    "Description": "The uploaded image does not clearly match healthy skin.",
                    "Medical Recommendation": "Consult a dermatologist for proper evaluation.",
                    "Skincare Advice": "Avoid self-medication and keep the area clean."
                })

        # 2. Very low confidence
        if confidence < 40:
            return jsonify({
                "Disease": "Disease Undefined",
                "Confidence": round(confidence, 2),
                "Description": "The uploaded image does not match any disease in the trained dataset.",
                "Medical Recommendation": "Please consult a dermatologist for accurate medical diagnosis.",
                "Skincare Advice": "Do not apply random medications and keep the area clean and dry."
            })

        # get disease info from database
        info = get_disease_info(disease_key)

        if info is None: 
           return jsonify({"error": "Disease info missing in database"})

        display_name, description, medical_rec, skincare = info

        # 3. Medium confidence (possible disease)
        if 40 <= confidence < 60:
            display_name = "Possible " + display_name
            description = description + " The model confidence is moderate. Medical confirmation is recommended."

        # save history
        insert_history(session["user_id"], unique_name, disease_key,confidence)

        return jsonify({
            "Disease": display_name,
            "Confidence": round(confidence, 2),
            "Description": description,
            "Medical Recommendation": medical_rec,
            "Skincare Advice": skincare
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- HISTORY ----------------
@app.route("/history", methods=["GET"])
def history():

    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    records = get_history(session["user_id"])

    history_list = []
    for row in records:
        info = get_disease_info(row[2])
        display_name = info[0] if info else row[2]
        history_list.append({
            "id": row[0],
            "image": f"http://127.0.0.1:5000/uploads/{row[1]}",
            "disease": display_name,
            "confidence": row[3],
            "date": row[4]
        })

    return jsonify(history_list)

# ---------------- ADMIN: VIEW ALL USERS ----------------
@app.route("/admin/users", methods=["GET"])
def admin_users():

    # check login
    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    # check admin role
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"})

    users = get_all_users()

    user_list = []
    for u in users:
        user_list.append({
            "id": u[0],
            "username": u[1],
            "email": u[2],
            "role": u[3]
        })

    return jsonify(user_list)

# ---------------- ADMIN: UPDATE DISEASE INFO ----------------
@app.route("/admin/disease", methods=["PUT"])
def admin_update_disease():

    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"})

    data = request.json

    disease_name = data.get("disease_name")
    description = data.get("description")
    medical_rec = data.get("medical_recommendation")
    skincare = data.get("skincare_advice")

    if not disease_name:
        return jsonify({"error": "Disease name required"})

    update_disease_info(disease_name, description, medical_rec, skincare)

    return jsonify({"message": "Disease information updated successfully"})

# ---------------- ADMIN: PROMOTE USER ----------------
@app.route("/admin/promote", methods=["PUT"])
def promote_user():

    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"})

    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "User ID required"})

    promote_to_admin(user_id)

    return jsonify({"message": "User promoted to admin successfully"})


# ---------------- ADMIN: DELETE USER ----------------
@app.route("/admin/delete_user", methods=["DELETE"])
def admin_delete_user():

    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"})

    data = request.json
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "User ID required"})

    delete_user(user_id)

    return jsonify({"message": "User deleted successfully"})



# ---------------- ADMIN: VIEW ALL HISTORY ----------------
@app.route("/admin/history", methods=["GET"])
def admin_history():

    # login check
    if "user_id" not in session:
        return jsonify({"error": "Please login first"})

    # admin check
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"})

    records = get_all_history()

    history_list = []
    for row in records:
        info = get_disease_info(row[3])
        display_name = info[0] if info else row[3]
        history_list.append({
            "id": row[0],
            "username": row[1],
            "image": f"http://127.0.0.1:5000/uploads/{row[2]}",
            "disease": display_name,
            "confidence": row[4],
            "date": row[5]
        })

    return jsonify(history_list)


# ---------------- SERVE UPLOADED IMAGE ----------------
@app.route("/uploads/<filename>")
def get_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(debug=True)