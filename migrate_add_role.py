import sqlite3

db = 'database.db'
conn = sqlite3.connect(db)
c = conn.cursor()

# Sprawdź aktualne kolumny
cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
print("Kolumny w 'users':", cols)

# Dodaj kolumnę 'role' jeśli jej nie ma
if 'role' not in cols:
    c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'")
    conn.commit()
    print("Dodano kolumnę 'role' z domyślną wartością 'employee'.")
else:
    print("Kolumna 'role' już istnieje.")

# Ustaw admina
c.execute("UPDATE users SET role='admin' WHERE username='admin'")
conn.commit()
print("Ustawiono admina.")

conn.close()
print("Migracja zakończona.")
