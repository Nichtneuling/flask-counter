# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime
import qrcode
from io import BytesIO

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
        getattr(schedule.every(), weekdays[weekday]).at("00:00").do(job)

def start_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=start_scheduler, daemon=True).start()

# ---------------- Login ----------------
def require_login():
    return "username" not in session

@app.route("/")
def root():
    return redirect("/dashboard")

# ---------------- Dashboard ----------------
@app.route("/dashboard")
def dashboard():
    if require_login():
        return redirect("/login")
    data = load_data()
    return render_template("dashboard.html", data=data, user=session["username"])

# ---------------- Login ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        user = data["users"].get(username)
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="❌ Falscher Benutzername oder Passwort!")
        session["username"] = username
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

# ---------------- Registrierung ----------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        if username in data["users"]:
            return render_template("register.html", error="Benutzer existiert bereits!")
        data["users"][username] = {"password": generate_password_hash(password), "clicks": 0}
        save_data(data)
        return redirect("/login")
    return render_template("register.html")

# ---------------- Zähler ----------------
@app.route("/click/<counter>")
def click(counter):
    data = load_data()

    # Falls kein Benutzer eingeloggt -> QR-Code-User verwenden
    if "username" not in session:
        username = "QR-Code"
        if "QR-Code" not in data["users"]:
            data["users"]["QR-Code"] = {"password": generate_password_hash("123456"), "clicks": 0}
    else:
        username = session["username"]

    c = data["counters"].get(counter)
    if not c:
        return "Zähler nicht gefunden!"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c["weekly_count"] += 1
    if c["weekly_count"] > 6:
        c["weekly_count"] = 6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user": username, "time": now})
    c["all_clicks"].append({"user": username, "time": now})
    save_data(data)

    if username == "QR-Code":
        return "<h3>✅ Trocknervorgang gezählt!</h3>"
    return redirect("/dashboard")

@app.route("/reset_week")
def reset_week():
    if require_login() or session["username"] != "Leroy":
        return redirect("/dashboard")
    data = load_data()
    for c in data["counters"].values():
        c["weekly_count"] = 0
        c["weekly_clicks"] = []
    save_data(data)
    return redirect("/dashboard")

@app.route("/reset_all")
def reset_all():
    if require_login() or session["username"] != "Leroy":
        return redirect("/dashboard")
    data = load_data()
    for c in data["counters"].values():
        c["total_count"] = 0
        c["all_clicks"] = []
    save_data(data)
    return redirect("/dashboard")

# ---------------- Zähler hinzufügen ----------------
@app.route("/add_counter", methods=["POST"])
def add_counter():
    if require_login() or session["username"] != "Leroy":
        return redirect("/dashboard")
    name = request.form["name"].strip()
    color = request.form["color"]
    reset_day = request.form.get("reset_day", "Samstag")
    days = {"Montag":0,"Dienstag":1,"Mittwoch":2,"Donnerstag":3,"Freitag":4,"Samstag":5,"Sonntag":6}
    data = load_data()
    if name in data["counters"]:
        return "Zähler existiert bereits!"
    data["counters"][name] = {
        "name": name,
        "color": color,
        "weekly_count": 0,
        "total_count": 0,
        "weekly_clicks": [],
        "all_clicks": [],
        "reset_day": days.get(reset_day,5)
    }
    save_data(data)
    schedule_reset(name, days.get(reset_day,5))
    return redirect("/dashboard")

# ---------------- QR-Code ----------------
@app.route("/qrcode/<counter>")
def qrcode_page(counter):
    if require_login():
        return redirect("/login")
    data = load_data()
    if counter not in data["counters"]:
        return "Zähler nicht gefunden!"
    return render_template("qrcode.html", counter=counter)

@app.route("/qrcode_image/<counter>")
def qrcode_image(counter):
    url = request.host_url + f"click/{counter}"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# ---------------- START ----------------
if __name__ == "__main__":
    data = load_data()
    for cname, c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day", 0))
    app.run(host="0.0.0.0", port=5000)
