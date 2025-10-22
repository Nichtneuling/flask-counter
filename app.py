# -*- coding: utf-8 -*-
from flask import Flask, render_template, render_template_string, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "data.json"

# ---------------- Datenverwaltung ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}, "counters": {}}, f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------- Scheduler ----------------
def schedule_reset(counter_name, weekday):
    weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    def job():
        data = load_data()
        c = data["counters"].get(counter_name)
        if c:
            c["weekly_count"] = 0
            c["weekly_clicks"] = []
            save_data(data)
            print(f"[AUTO] {counter_name} weekly reset executed on {datetime.now()}")
    if 0 <= weekday <= 6:
        schedule.every().__getattribute__(weekdays[weekday]).at("00:00").do(job)

def start_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=start_scheduler, daemon=True).start()

# ---------------- Login ----------------
def require_login():
    return "username" not in session

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        user = data["users"].get(username)
        if not user or not check_password_hash(user["password"], password):
            error = "Falscher Benutzername oder Passwort!"
        else:
            session["username"] = username
            return redirect("/")
    return render_template_string(TEMPLATE_LOGIN, error=error)

@app.route("/register", methods=["GET","POST"])
def register():
    error = None
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        if username in data["users"]:
            error = "Benutzer existiert bereits!"
        else:
            data["users"][username] = {"password": generate_password_hash(password), "clicks":0}
            save_data(data)
            session["username"] = username
            return redirect("/")
    return render_template_string(TEMPLATE_REGISTER, error=error)

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

# ---------------- Zähler Aktionen ----------------
@app.route("/create_counter", methods=["POST"])
def create_counter():
    if require_login() or session["username"]!="Leroy":
        return redirect("/login")
    name = request.form["counter_name"].strip()
    color = request.form.get("color","#3498db")
    reset_day = int(request.form.get("reset_day",0))
    data = load_data()
    if name in data["counters"]:
        return "Zähler existiert bereits!"
    data["counters"][name] = {
        "name": name,
        "color": color,
        "weekly_count":0,
        "total_count":0,
        "weekly_clicks":[],
        "all_clicks":[],
        "reset_day": reset_day
    }
    save_data(data)
    schedule_reset(name, reset_day)
    return redirect("/")

@app.route("/click/<counter>")
def click(counter):
    if require_login():
        return redirect("/login")
    data = load_data()
    c = data["counters"].get(counter)
    if not c:
        return "Zähler nicht gefunden!"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c["weekly_count"] += 1
    if c["weekly_count"]>6: c["weekly_count"]=6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user":session["username"],"time":now})
    c["all_clicks"].append({"user":session["username"],"time":now})
    save_data(data)
    return redirect("/")

@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if require_login() or session["username"]!="Leroy":
        return redirect("/login")
    data = load_data()
    c = data["counters"].get(counter)
    if c:
        c["weekly_count"] = 0
        c["weekly_clicks"] = []
        save_data(data)
    return redirect("/")

@app.route("/reset_total/<counter>")
def reset_total(counter):
    if require_login() or session["username"]!="Leroy":
        return redirect("/login")
    data = load_data()
    c = data["counters"].get(counter)
    if c:
        c["total_count"] = 0
        c["all_clicks"] = []
        save_data(data)
    return redirect("/")

@app.route("/delete/<counter>")
def delete_counter(counter):
    if require_login() or session["username"]!="Leroy":
        return redirect("/login")
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/")

# ---------------- HTML Templates ----------------
TEMPLATE_LOGIN = """<!doctype html>
<html><head><title>Login</title></head>
<body>
<h2>Login</h2>
{% if error %}<p style="color:red">{{error}}</p>{% endif %}
<form method="POST">
<input name="username" placeholder="Benutzername" required><br>
<input type="password" name="password" placeholder="Passwort" required><br>
<button>Login</button>
</form>
<p>Noch kein Konto? <a href="/register">Registrieren</a></p>
</body></html>"""

TEMPLATE_REGISTER = """<!doctype html>
<html><head><title>Registrieren</title></head>
<body>
<h2>Registrieren</h2>
{% if error %}<p style="color:red">{{error}}</p>{% endif %}
<form method="POST">
<input name="username" placeholder="Benutzername" required><br>
<input type="password" name="password" placeholder="Passwort" required><br>
<button>Konto erstellen</button>
</form>
<p>Schon registriert? <a href="/login">Login</a></p>
</body></html>"""

# ---------------- Start ----------------
if __name__ == "__main__":
    data = load_data()
    for cname,c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day",0))
    app.run(host="0.0.0.0", port=5000)
