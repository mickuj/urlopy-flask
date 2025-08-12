import sqlite3

conn = sqlite3.connect("database.db")  # lub pełna ścieżka, jeśli inna
c = conn.cursor()

# Dodaj kolumnę total_days, jeśli jej jeszcze nie ma
try:
    c.execute("ALTER TABLE users ADD COLUMN total_days INTEGER DEFAULT 26")
    print("✅ Dodano kolumnę 'total_days' do tabeli users.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("ℹ️ Kolumna 'total_days' już istnieje.")
    else:
        raise

conn.commit()
conn.close()
