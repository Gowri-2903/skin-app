from database import init_db
import sqlite3
import os
from database import DB_NAME

init_db()
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

data = [
("BA-cellulitis","Cellulitis",
"Cellulitis is a bacterial skin infection causing redness and swelling.",
"Consult a doctor. Antibiotics are usually required.",
"Keep the affected area clean and avoid scratching."),

("BA-impetigo","Impetigo",
"Impetigo is a contagious bacterial infection common in children.",
"Topical or oral antibiotics may be prescribed.",
"Gently wash sores and avoid touching them."),

("FU-ringworm","Ringworm",
"Ringworm is a fungal infection causing circular itchy rash.",
"Use antifungal cream regularly.",
"Keep skin dry and do not share towels."),

("FU-athlete-foot","Athlete-Foot",
"Athlete’s foot is a fungal infection affecting the feet.",
"Apply antifungal powder or cream.",
"Wash feet daily and wear breathable footwear."),

("FU-nail-fungus","Nail-Fungus",
"Nail fungus causes thick, discolored nails.",
"Use antifungal medication.",
"Keep nails trimmed and clean."),

("PA-cutaneous-larva-migrans","Cutaneous Larva Migrans",
"A parasitic infection causing winding itchy rash.",
"Medical treatment is required.",
"Avoid walking barefoot on sand."),

("VI-chickenpox","Chickenpox",
"Chickenpox is a viral infection with itchy blisters.",
"Rest and antihistamines help relieve symptoms.",
"Avoid scratching and maintain hygiene."),

("VL-shingles","Shingles",
"Shingles is a painful viral infection causing rash on one side of body.",
"Antiviral medication should be started early.",
"Keep rash covered and avoid contact with others."),

("healthy_skin","Healthy Skin",
"No disease detected.",
"No medical treatment needed.",
"Maintain good hygiene and moisturize regularly.")
]

cursor.executemany("""
INSERT OR REPLACE INTO disease_info
(disease_name, display_name, description, medical_recommendation, skincare_advice)
VALUES (?, ?, ?, ?, ?)
""", data)

conn.commit()
conn.close()

print("Disease knowledge base added!")