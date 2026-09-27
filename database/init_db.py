import sys
from pathlib import Path
import sqlite3

# Ajouter la racine du projet au PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import DATABASE_PATH

# Connexion à la base
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# Création de la table
cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,

    source TEXT,
    date TEXT,

    summary TEXT,
    content TEXT,

    relevant INTEGER DEFAULT 0,

    sentiment TEXT,
    sentiment_score REAL DEFAULT 0,

    confidence REAL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

conn.commit()
conn.close()

print("✅ Base de données créée avec succès.")