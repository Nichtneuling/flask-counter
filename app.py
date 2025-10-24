# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json, os
from datetime import datetime

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET", "supersecretkey")

DATA_FILE = "data.json"


# ---------------- Data helpers ----------------
def load_data():
    """
    Lädt data.json. Falls nicht vorhanden, legt eine Default-Datei an mit Leroy.
    Falls Benutzerspasswörter in Klartext vorliegen (sehr wahrscheinliches Muster, keine ':' oder '$'),
    werden diese beim Laden in sichere Hashes umgewandelt und gespeichert.
    """
    if not os.path.exists(DATA_FILE):
        default = {
            "users": {
                "Leroy": {"password": generate_password_hash("leroypass"), "clicks": 0},
                "QR-Code": {"password": generate_password_hash("123456"), "clicks": 0}
            },
            "counters": {}
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If users exist and some passwords are stored plaintext, convert them to hashes.
    changed = False
    for uname, udata in list(data.get("users", {}).items()):
        pw = udata.get("password", "")
        if isinstance(pw, str):
            # Heuristik: if there's no '$' or ':' it's probably plaintext (not a hash)
            if ('$' not in pw) and (':' not in pw) and pw != "":
                # convert to hash
                data["users"][uname]["password"] = generate_password_hash(pw)
                changed = True
    if changed:
        save_data(data)
    return data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------- Auth helpers ----------------
def logged_in():
    return "username" in session


def current_user():
    return session.get("username")


def require_login_redirect():
    if not logged_in():
        return redirect(url_for("login"))


def is_leroy():
    return logged_in() and session.get("username") == "Leroy"


# ---------------- Routes: Auth ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login: prüft hashed passwords (werkzeug).
    Zeigt bei Fehler eine Fehlermeldung im Template (wenn dein template 'error' erwartet).
    """
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        data = load_data()
        user = data.get("users", {}).get(username)
        if not user:
            error = "Falscher Benutzername oder Passwort!"
        else:
            stored = user.get("password", "")
            # Prüfen: falls stored evtl. plaintext (wurde aber beim load konvertiert) - check_password_hash erwartet hash
            try:
                ok = check_password_hash(stored, password)
            except Exception:
                # Falls check fehl schlägt (unwahrscheinlich), fallback: direkter Vergleich
                ok = (stored == password)
            if not ok:
                error = "Falscher Benutzername oder Passwort!"
            else:
                session["username"] = username
                return redirect(url_for("dashboard"))
    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registrieren: legt neuen Benutzer mit gehashtem Passwort an.
    Falls Benutzer existiert -> Fehlermeldung.
    """
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Benutzername und Passwort erforderlich."
        else:
            data = load_data()
            if username in data.get("users", {}):
                error = "Benutzer existiert bereits!"
            else:
                data.setdefault("users", {})[username] = {
                    "password": generate_password_hash(password),
                    "clicks": 0
                }
                save_data(data)
                session["username"] = username
                return redirect(url_for("dashboard"))
    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


# ---------------- Dashboard / counters ----------------
@app.route("/")
def dashboard():
    if not logged_in():
        return redirect(url_for("login"))
    data = load_data()
    return render_template("dashboard.html", data=data, user=current_user())


# create counter (only Leroy)
@app.route("/add_counter", methods=["POST"])
def add_counter():
    if not is_leroy():
        return redirect(url_for("dashboard"))
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#3498db")
    reset_day = int(request.form.get("reset_day", 0))
    if not name:
        return redirect(url_for("dashboard"))
    data = load_data()
    if name in data.get("counters", {}):
        return redirect(url_for("dashboard"))
    data.setdefault("counters", {})[name] = {
        "name": name,
        "color": color,
        "weekly_count": 0,
        "total_count": 0,
        "weekly_clicks": [],
        "all_clicks": [],
        "reset_day": reset_day
    }
    save_data(data)
    return redirect(url_for("dashboard"))


# increment routes (AJAX and QR)
@app.route("/increment/<counter>", methods=["POST"])
def increment_ajax(counter):
    # used by dashboard +1 (AJAX)
    if not logged_in():
        return jsonify(success=False, error="not_logged_in"), 401
    data = load_data()
    c = data.get("counters", {}).get(counter)
    if not c:
        return jsonify(success=False, error="counter_not_found"), 404
    user = current_user()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c["weekly_count"] = min(c.get("weekly_count", 0) + 1, 6)
    c["total_count"] = c.get("total_count", 0) + 1
    c.setdefault("weekly_clicks", []).append({"user": user, "time": now})
    c.setdefault("all_clicks", []).append({"user": user, "time": now})
    # increment user's click counter if stored
    if user in data.get("users", {}):
        data["users"][user]["clicks"] = data["users"][user].get("clicks", 0) + 1
    save_data(data)
    return jsonify(success=True, weekly_count=c["weekly_count"], total_count=c["total_count"])


@app.route("/click/<counter>")
def click_qr(counter):
    # Called by QR scan: increments and shows success page
    data = load_data()
    c = data.get("counters", {}).get(counter)
    if not c:
        return "Zähler nicht gefunden", 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # treat QR scans as user "QR-Code"
    user = "QR-Code"
    c["weekly_count"] = min(c.get("weekly_count", 0) + 1, 6)
    c["total_count"] = c.get("total_count", 0) + 1
    c.setdefault("weekly_clicks", []).append({"user": user, "time": now})
    c.setdefault("all_clicks", []).append({"user": user, "time": now})
    data.setdefault("users", {})
    # ensure QR-Code user exists: if not, create with safe default password '123456' hashed
    if "QR-Code" not in data["users"]:
        data["users"]["QR-Code"] = {"password": generate_password_hash("123456"), "clicks": 0}
    data["users"]["QR-Code"]["clicks"] = data["users"]["QR-Code"].get("clicks", 0) + 1
    save_data(data)
    # render success template (only for QR)
    return render_template("qr_success.html", counter=counter)


@app.route("/delete/<counter>")
def delete_counter(counter):
    if not is_leroy():
        return redirect(url_for("dashboard"))
    data = load_data()
    if counter in data.get("counters", {}):
        del data["counters"][counter]
        save_data(data)
    return redirect(url_for("dashboard"))


@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if not is_leroy():
        return redirect(url_for("dashboard"))
    data = load_data()
    c = data.get("counters", {}).get(counter)
    if c:
        c["weekly_count"] = 0
        c["weekly_clicks"] = []
        save_data(data)
    return redirect(url_for("dashboard"))


@app.route("/reset_total/<counter>")
def reset_total(counter):
    if not is_leroy():
        return redirect(url_for("dashboard"))
    data = load_data()
    c = data.get("counters", {}).get(counter)
    if c:
        c["total_count"] = 0
        c["all_clicks"] = []
        save_data(data)
    return redirect(url_for("dashboard"))


# ---------------- Admin tools (Leroy only) ----------------
@app.route("/admin/users")
def admin_users():
    """Zeigt nur die Usernamen (keine Passwörter). Nur Leroy darf das sehen."""
    if not is_leroy():
        return redirect(url_for("dashboard"))
    data = load_data()
    users = list(data.get("users", {}).keys())
    return render_template("admin_users.html", users=users)


@app.route("/admin/reset_password", methods=["GET", "POST"])
def admin_reset_password():
    """Leroy kann hier das Passwort eines beliebigen Benutzers setzen (z.B. QR-Code)."""
    if not is_leroy():
        return redirect(url_for("dashboard"))
    message = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        newpw = request.form.get("password", "")
        data = load_data()
        if username not in data.get("users", {}):
            message = f"Benutzer {username} existiert nicht."
        else:
            data["users"][username]["password"] = generate_password_hash(newpw)
            save_data(data)
            message = f"Passwort für {username} wurde gesetzt."
    return render_template("admin_reset_password.html", message=message)


# ---------------- small utility to ensure templates exist if you used different names ----------------
@app.route("/debug/templates")
def debug_templates():
    # only for debugging local dev
    return "templates path: " + os.path.abspath("templates")


if __name__ == "__main__":
    # Load once to trigger any automatic conversions and show status
    d = load_data()
    print("Loaded data.json - users:", list(d.get("users", {}).keys()))
    app.run(host="0.0.0.0", port=5000, debug=False)
