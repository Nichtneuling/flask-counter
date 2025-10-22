# -*- coding: utf-8 -*-
from flask import Flask, render_template, render_template_string, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime
import qrcode
from io import BytesIO
import base64

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

# ---------------- Routes ----------------
@app.route("/")
def home():
    if require_login():
        return redirect("/login")
    data = load_data()
    counters = data["counters"]
    return render_template("index.html", counters=counters, username=session["username"])

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        user = data["users"].get(username)
        if not user or not check_password_hash(user["password"], password):
            return "Falscher Benutzername oder Passwort!"
        session["username"] = username
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

# ---------------- Zähler Aktionen ----------------
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
    if session["username"]=="QR-Code":
        return "Trocknervorgang gezählt!"
    return redirect("/")

@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if require_login() or session["username"]!="Leroy":
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
    if require_login() or session["username"]!="Leroy":
        return redirect("/")
    data = load_data()
    c = data["counters"].get(counter)
    if c:
        c["total_count"] = 0
        c["all_clicks"] = []
        save_data(data)
    return redirect("/")

# ---------------- QR-Code anzeigen ----------------
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
    return f'<img src="data:image/png;base64,{img_str}"><br><a href="/">Zurück</a>'

# ---------------- START ----------------
if __name__ == "__main__":
    data = load_data()
    for cname,c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day",0))
    app.run(host="0.0.0.0", port=5000)
