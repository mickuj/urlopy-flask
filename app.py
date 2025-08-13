from flask import Flask, render_template, redirect, request, abort, url_for, session, flash, jsonify
import psycopg2
import psycopg2.extras
from init_db import get_db
from flask import g
from functools import wraps
from datetime import timedelta, datetime, date
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tajny_klucz'

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def get_current_user():
    return session.get("user_id"), session.get("role", "employee")

def login_required():
    return "user_id" in session

def is_admin():
    return session.get("role") == "admin"

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Tylko administrator ma dostęp do tej strony!", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def add_yearly_vacation_days():
    current_year = datetime.today().year
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET total_days = total_days + annual_limit,
            last_updated_year = %s
        WHERE username != 'admin' AND last_updated_year < %s
    """, (current_year, current_year))
    conn.commit()
    conn.close()

add_yearly_vacation_days()


@app.route('/add_leave', methods=['GET', 'POST'])
def add_leave():
    if not login_required():
        return redirect(url_for('login'))

    user_id, role = get_current_user()
    conn = get_db_connection()

    users = []
    if role == 'admin':
        users = conn.execute("SELECT id, username FROM users WHERE role != 'admin' ORDER BY username").fetchall()

    if request.method == 'POST':
        start = request.form['start_date']
        end = request.form['end_date']

        if role == 'admin':
            selected_user_id = request.form.get('user_id')
        else:
            selected_user_id = user_id

        if end < start:
            conn.close()
            flash(f"Data końcowa nie może być wcześniejsza niż początkowa.", "danger")
            return redirect(url_for("add_leave"))

        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        days_taken = (end_date - start_date).days + 1

        current_days = conn.execute(
            'SELECT total_days FROM users WHERE id = %s', (selected_user_id,)
        ).fetchone()['total_days']

        if current_days < days_taken:
            conn.close()
            flash(f"Nie masz wystarczającej liczby dni urlopowych (pozostało {current_days}).", "danger")
            return redirect(url_for("add_leave"))

        conn.execute(
            'INSERT INTO urlopy (user_id, start_date, end_date) VALUES (%s, %s, %s)',
            (selected_user_id, start, end)
        )

        conn.execute(
            'UPDATE users SET total_days = total_days - %s WHERE id = %s',
            (days_taken, selected_user_id)
        )

        conn.commit()
        conn.close()
        return redirect(url_for('vacations'))

    # Pokaż dotychczasowe urlopy (dla danego użytkownika)
    leaves = conn.execute(
        'SELECT start_date, end_date FROM urlopy WHERE user_id = %s ORDER BY start_date',
        (user_id,)
    ).fetchall()
    conn.close()

    return render_template('add_leave.html', leaves=leaves, users=users, role=role)



@app.route('/vacations')
def vacations():
    if not login_required():
        return redirect(url_for('login'))

    user_id, role = get_current_user()

    today = date.today().isoformat()

    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.id, u.user_id, u.start_date, u.end_date,
               COALESCE(us.username, 'użytkownik') AS username
        FROM urlopy u
        LEFT JOIN users us ON us.id = u.user_id
        WHERE u.end_date >= %s
        ORDER BY u.start_date
    ''', (today,)).fetchall()
    conn.close()
    return render_template(
        'vacations.html',
        leaves=rows,
        current_user_id=user_id,
        is_admin=(role == 'admin')
    )


@app.route('/leave/edit/<int:leave_id>', methods=['GET','POST'])
def edit_leave(leave_id):
    if not login_required():
        return redirect(url_for('login'))

    user_id, role = get_current_user()
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM urlopy WHERE id = %s', (leave_id,)).fetchone()
    if not row:
        conn.close(); abort(404)

    if role != 'admin' and row['user_id'] != user_id:
        conn.close(); abort(403)

    if request.method == 'POST':
        start = request.form['start_date']
        end = request.form['end_date']

        if end < start:
            conn.close()
            flash(f"Data końcowa nie może być wcześniejsza niż początkowa.", "danger")
            return redirect(url_for("edit_leave", leave_id=leave_id))

        old_start = datetime.strptime(row['start_date'], "%Y-%m-%d")
        old_end = datetime.strptime(row['end_date'], "%Y-%m-%d")
        old_days = (old_end - old_start).days + 1

        new_start = datetime.strptime(start, "%Y-%m-%d")
        new_end = datetime.strptime(end, "%Y-%m-%d")
        new_days = (new_end - new_start).days + 1

        diff = old_days - new_days
        conn.execute(
            'UPDATE users SET total_days = total_days + %s WHERE id = %s',
            (diff, row['user_id'])
        )

        conn.execute(
            'UPDATE urlopy SET start_date = %s, end_date = %s WHERE id = %s',
            (start, end, leave_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('vacations'))

    conn.close()
    return render_template('edit_leave.html', leave=row)

@app.route('/leave/delete/<int:leave_id>')
def delete_leave(leave_id):
    if not login_required():
        return redirect(url_for('login'))

    user_id, role = get_current_user()
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM urlopy WHERE id = %s', (leave_id,)).fetchone()
    if not row:
        conn.close(); abort(404)

    if role != 'admin' and row['user_id'] != user_id:
        conn.close(); abort(403)

    start_date = datetime.strptime(row['start_date'], "%Y-%m-%d")
    end_date = datetime.strptime(row['end_date'], "%Y-%m-%d")
    days = (end_date - start_date).days + 1

    conn.execute(
        'UPDATE users SET total_days = total_days + %s WHERE id = %s',
        (days, row['user_id'])
    )

    conn.execute('DELETE FROM urlopy WHERE id = %s', (leave_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('vacations'))


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            return redirect(url_for('vacations'))
        else:
            return render_template('login.html', error="Nieprawidłowy login lub hasło")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/")
def home():
    if not login_required():
        return redirect(url_for('login'))
    return redirect(url_for('vacations'))

@app.route('/users')
def users_list():
    # tylko admin
    if "user_id" not in session or session.get("role") != "admin":
        flash("Dostęp tylko dla administratora", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    rows = conn.execute('SELECT id, username, role, total_days, annual_limit FROM users ORDER BY username COLLATE NOCASE').fetchall()
    conn.close()
    return render_template('users.html', users=rows)

@app.route('/users/new', methods=['GET','POST'])
def users_new():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Dostęp tylko dla administratora", "danger")
        return redirect(url_for("login"))


    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = request.form['role'].strip()  # 'admin' lub 'employee'
        annual_limit = int(request.form["annual_limit"])

        if not username or not password or role not in ('admin','employee'):
            flash("Uzupełnij poprawnie wszystkie pola.", "danger")
            return redirect(url_for('users_new'))

        conn = get_db_connection()
        # sprawdź, czy istnieje
        exists = conn.execute('SELECT 1 FROM users WHERE username = %s', (username,)).fetchone()
        if exists:
            conn.close()
            flash("Taki login już istnieje.", "warning")
            return redirect(url_for('users_new'))

        total_days = request.form.get('total_days')
        if not total_days:
            total_days = annual_limit
        total_days = int(total_days)

        conn.execute('INSERT INTO users (username, password, role, total_days, last_updated_year, annual_limit) VALUES (%s, %s, %s, %s, %s, %s)',
                    (username, password, role, total_days, datetime.today().year, annual_limit))

        conn.commit()
        conn.close()
        flash("Użytkownik dodany.", "success")
        return redirect(url_for('users_list'))

    return render_template('user_form.html', mode='new', user=None)

@app.route('/users/<int:user_id>/edit', methods=['GET','POST'])
def users_edit(user_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Dostęp tylko dla administratora", "danger")
        return redirect(url_for("login"))


    conn = get_db_connection()
    user = conn.execute('SELECT id, username, role, total_days, annual_limit FROM users WHERE id = %s', (user_id,)).fetchone()

    if not user:
        conn.close()
        abort(404)

    if request.method == 'POST':
        role = request.form['role'].strip()
        new_password = request.form.get('password', '').strip()
        total_days = request.form.get('total_days')
        annual_limit = request.form.get('annual_limit')


        if role not in ('admin','employee'):
            conn.close()
            flash("Nieprawidłowa rola.", "danger")
            return redirect(url_for('users_edit', user_id=user_id))

        updates = []
        params = []

        if new_password:
            updates.append('password = %s')
            params.append(new_password)

        if total_days:
            updates.append('total_days = %s')
            params.append(int(total_days))

        if annual_limit:
            updates.append('annual_limit = %s')
            params.append(int(annual_limit))

        updates.append('role = %s')
        params.append(role)

        params.append(user_id)

        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        conn.execute(sql, params)

        conn.commit()
        conn.close()
        flash("Zapisano zmiany.", "success")
        return redirect(url_for('users_list'))

    conn.close()
    return render_template('user_form.html', mode='edit', user=user)

@app.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_only
def delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if user is None:
        flash("Użytkownik nie istnieje", "danger")
        return redirect(url_for("users_list"))

    if user["role"] == "admin":
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        admin_count = cursor.fetchone()[0]

        if admin_count <= 1:
            flash("Nie można usunąć ostatniego administratora", "danger")
            return redirect(url_for("users_list"))

    cursor.execute("DELETE FROM urlopy WHERE user_id=%s", (user_id,))

    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    flash("Użytkownik usunięty", "success")
    return redirect(url_for("users_list"))


@app.route('/stats')
def stats():
    # if session.get("role") != "admin":
    #     flash("Tylko dla administratora", "danger")
    #     return redirect(url_for("login"))

    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM urlopy").fetchone()[0]
    today = conn.execute("""
        SELECT users.username FROM urlopy u
        JOIN users ON u.user_id = users.id
        WHERE CURRENT_DATE BETWEEN u.start_date AND u.end_date
    """).fetchall()
    upcoming = conn.execute("""
        SELECT COUNT(*) FROM urlopy
        WHERE start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
    """).fetchone()[0]
    available_days = conn.execute("""
        SELECT username, total_days
        FROM users
        WHERE role != 'admin'
        ORDER BY username
    """).fetchall()

    conn.close()

    return render_template("stats.html", total=total, today=today, upcoming=upcoming, available_days=available_days)

@app.route('/calendar')
def calendar():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT u.start_date, u.end_date, users.username
        FROM urlopy u JOIN users ON u.user_id = users.id
    """).fetchall()
    conn.close()

    events = []
    for row in rows:
        events.append({
            "title": row["username"],
            "start": row["start_date"],
            "end": row["end_date"]
        })

    return render_template("calendar.html", events=events)

@app.route("/api/events")
def get_events():
    conn = get_db_connection()
    urlopy = conn.execute("""
        SELECT 
            TO_CHAR(u.start_date, 'YYYY-MM-DD') as start_date,
            TO_CHAR(u.end_date, 'YYYY-MM-DD') as end_date,
            users.username
        FROM urlopy u
        JOIN users ON users.id = u.user_id
    """).fetchall()
    conn.close()

    kolory = {
        'Natalia': 'blue',
        'Robert': 'green',
        'Klaudia': 'orange',
        'Paulina': 'purple',
        'Asia': 'pink',
        'Sylwia': 'yellow',
        'Zarząd': 'red',
        'admin': 'gray'
    }

    losowe_kolory = [
        '#f8c291', '#82ccdd', '#b8e994',
        '#f6e58d', '#ffbe76', '#dff9fb',
        '#c7ecee', '#fad390', '#f9ca24'
    ]

    events = []
    for u in urlopy:
        nazwa = u['username']
        if nazwa not in kolory:
            kolory[nazwa] = random.choice(losowe_kolory)
        kolor = kolory[nazwa]
        events.append({
            "title": f"{nazwa}",
            "start": u["start_date"],
            "end": (datetime.strptime(u["end_date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
            "color": kolor
        })

    return jsonify(events)



@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)