import sqlite3
from flask import g

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Tabela users (z kolumną role)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee'
        )
    ''')

    # Spróbuj dodać kolumnę role, jeśli stara tabela była bez niej
    try:
        c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee'")
    except Exception:
        pass  # kolumna już istnieje

    # Tabela urlopy (jak masz — zostaw; w razie czego tworzymy)
    c.execute('''
        CREATE TABLE IF NOT EXISTS urlopy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
    ''')

    # Seed admina (tylko jeśli nie istnieje)
    c.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )

    conn.commit()
    conn.close()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('database.db')
        g.db.row_factory = sqlite3.Row
    return g.db

if __name__ == '__main__':
    init_db()
    print("Baza danych zaktualizowana. Admin: admin/admin123")
