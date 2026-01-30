import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()  # charge les variables depuis .env (pour le local)

def get_db_connection():
    try:
        # 1. On cherche d'abord l'URL complète (C'est ce que Render utilise)
        database_url = os.getenv("DATABASE_URL")
        
        if database_url:
            # CAS PRODUCTION (Render)
            conn = psycopg2.connect(
                database_url,
                cursor_factory=RealDictCursor,
                sslmode='require' # Souvent nécessaire pour les connexions distantes sécurisées
            )
            print("✅ [DB] Connexion Render (URL) OK")
        else:
            # CAS LOCAL (Tes champs séparés)
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=os.getenv("DB_PORT", 5432),
                cursor_factory=RealDictCursor
            )
            print("✅ [DB] Connexion Locale (Champs) OK")

        return conn

    except Exception as e:
        print("❌ [DB] ERREUR Connexion :", e)
        return None