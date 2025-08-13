import sqlite3
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

# Jeśli masz plik .env lokalnie
load_dotenv()

# URL do PostgreSQL z Rendera
POSTGRES_URL = os.getenv("DATABASE_URL")

# Połączenie z SQLite
sqlite_conn = sqlite3.connect("database.db")
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

# Połączenie z PostgreSQL
pg_conn = psycopg2.connect(POSTGRES_URL, cursor_factory=psycopg2.extras.RealDictCursor)
pg_cur = pg_conn.cursor()

# Tabele do migracji
tables = ['users', 'urlopy']

for table in tables:
    print(f"Migruję tabelę: {table}")

    # Pobierz dane z SQLite
    sqlite_cur.execute(f"SELECT * FROM {table}")
    rows = sqlite_cur.fetchall()

    # Pobierz kolumny
    columns = [desc[0] for desc in sqlite_cur.description]
    col_names = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    for row in rows:
        values = [row[col] for col in columns]
        pg_cur.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            values
        )

pg_conn.commit()
pg_cur.close()
pg_conn.close()
sqlite_cur.close()
sqlite_conn.close()

print("✅ Migracja zakończona.")
