# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATA_FILE = "data.json"

# ---------------- Daten laden/speichern ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}, "counters": {}}, f)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------- Automatische Resets ----------------
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

# ---------------- Login Hilfsfunktion ----------------
def require_login():
    return "username" not in session

# ---------------- Routes ----------------
@app.route("/")
def home():
    if require_login():
        return redirect("/login")
    data = load_data()
    counters = data["counters"]
    username = session["username"]
    return render_template("dashboard.html", data=data, user=username)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        user = data["users"].get(username)
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Falscher Benutzername oder Passwort!")
        session["username"] = username
        return redirect("/")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        if username in data["users"]:
            return render_template("register.html", error="Benutzername existiert bereits!")
        data["users"][username] = {"password": generate_password_hash(password), "clicks": 0}
        save_data(data)
        session["username"] = username
        return redirect("/")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

# ---------------- Zähleraktionen ----------------
@app.route("/add_counter", methods=["POST"])
def add_counter():
    if require_login() or session["username"] != "Leroy":
        return redirect("/")
    name = request.form["name"].strip()
    color = request.form["color"]
    reset_day = int(request.form["reset_day"])
    data = load_data()
    if name in data["counters"]:
        return "Zählername bereits vorhanden!"
    data["counters"][name] = {
        "name": name,
        "color": color,
        "weekly_count": 0,
        "total_count": 0,
        "weekly_clicks": [],
        "all_clicks": [],
        "reset_day": reset_day
    }
    save_data(data)
    return redirect("/")

@app.route("/delete/<counter>")
def delete_counter(counter):
    if require_login() or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/")

@app.route("/click/<counter>")
def click(counter):
    data = load_data()
    if counter not in data["counters"]:
        return "Zähler nicht gefunden!"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = data["counters"][counter]
    c["weekly_count"] += 1
    if c["weekly_count"] > 6:
        c["weekly_count"] = 6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user": "QR-Code", "time": now})
    c["all_clicks"].append({"user": "QR-Code", "time": now})
    save_data(data)
    return render_template("qr_success.html", counter=counter)

@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if require_login() or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    c = data["counters"].get(counter)
    if c:
        c["weekly_count"] = 0
        c["weekly_clicks"] = []
        save_data(data)
    return redirect("/")

@app.route("/reset_total/<counter>")
def reset_total(counter):
    if require_login() or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    c = data["counters"].get(counter)
    if c:
        c["total_count"] = 0
        c["all_clicks"] = []
        save_data(data)
    return redirect("/")

# ---------------- QR-Code ----------------
@app.route("/show_qrcode/<counter>")
def show_qrcode(counter):
    if require_login():
        return redirect("/login")
    data = load_data()
    if counter not in data["counters"]:
        return "Zähler nicht gefunden!"
    click_url = request.host_url + f"click/{counter}"
    img = qrcode.make(click_url)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return render_template("qrcode.html", counter=counter, qrcode_data=img_str)

# ---------------- Start ----------------
if __name__ == "__main__":
    data = load_data()
    for cname, c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day", 0))
    app.run(host="0.0.0.0", port=5000)
