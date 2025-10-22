# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime
import qrcode
import io

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

# ---------------- Routes ----------------
@app.route("/")
def home():
    if require_login():
        return redirect("/login")
    data = load_data()
    counters = data["counters"]
    user = session["username"]
    return render_template_string(TEMPLATE_INDEX, counters=counters, user=user)

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
    return render_template_string(TEMPLATE_LOGIN)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        data = load_data()
        if username in data["users"]:
            return "Benutzer existiert bereits!"
        data["users"][username] = {"password": generate_password_hash(password), "clicks":0}
        save_data(data)
        return redirect("/login")
    return render_template_string(TEMPLATE_REGISTER)

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
    user = session["username"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c["weekly_count"] += 1
    if c["weekly_count"]>6: c["weekly_count"]=6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user":user,"time":now})
    c["all_clicks"].append({"user":user,"time":now})
    data["users"][user]["clicks"] +=1
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

# ---------------- QR-Code ----------------
@app.route("/qr_image/<counter>")
def qr_image(counter):
    data = load_data()
    if counter not in data["counters"]:
        return "Zähler nicht gefunden!"
    url = f"https://flask-counter-br47.onrender.com/click/{counter}?user=QR-Code"
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# ---------------- HTML Templates ----------------
TEMPLATE_INDEX = """<!doctype html>
<html>
<head>
<title>Zähler Übersicht</title>
<style>
body{font-family:sans-serif;background:#f5f6fa;margin:0;padding:20px;}
.card{background:#3498db;color:white;padding:20px;border-radius:12px;margin:10px;width:300px;display:inline-block;position:relative;text-align:center;}
.btn-full{width:100%;padding:15px;margin-top:10px;background:#2ecc71;border:none;color:white;font-weight:bold;border-radius:10px;cursor:pointer;transition:0.3s;font-size:18px;}
.btn-full:hover{background:#27ae60;}
.history{display:none;background:white;color:black;padding:10px;margin-top:10px;border-radius:6px;max-height:150px;overflow:auto;}
.delete-btn{position:absolute;top:10px;right:10px;color:white;text-decoration:none;font-weight:bold;}
.progress-bar-container{width:100%; background: rgba(255,255,255,0.3); height:25px; border-radius:10px; margin-bottom:10px; overflow:hidden;}
.progress-bar-fill{height:100%; width:0%; background:#fff; border-radius:10px; transition: width 0.5s ease; color:black; text-align:center; font-weight:bold; line-height:25px;}
</style>
<script>
function toggleForm(){document.getElementById('form').style.display='block';}
function toggleHistory(id){var h=document.getElementById(id);h.style.display=(h.style.display=='none')?'block':'none';}
function toggleQR(id){var qr=document.getElementById(id);qr.style.display=(qr.style.display=='none')?'block':'none';}
function clickButton(el){
    let fill = el.parentNode.querySelector('.progress-bar-fill');
    let current = parseInt(fill.getAttribute('data-count')) || 0;
    if(current < 6){
        current += 1;
        fill.style.width = (current/6*100)+'%';
        fill.innerText = current + '/6';
        fill.setAttribute('data-count', current);
    }
}
</script>
</head>
<body>
<h2>Willkommen, {{user}}!</h2>
<a href="/logout"><button style="background:red;color:white;">Logout</button></a>
<div style="cursor:pointer;margin:15px 0;" onclick="toggleForm()">➕ Neuer Zähler</div>
<form id="form" method="POST" action="/create_counter" style="display:none;margin-bottom:20px;">
<input name="counter_name" placeholder="Zählername" required>
<input type="color" name="color" value="#3498db">
<select name="reset_day">
<option value="0">Montag</option><option value="1">Dienstag</option>
<option value="2">Mittwoch</option><option value="3">Donnerstag</option>
<option value="4">Freitag</option><option value="5">Samstag</option>
<option value="6">Sonntag</option>
</select>
<button>Erstellen</button>
</form>
{% for name,c in counters.items() %}
<div class="card" style="background:{{c.color}}">
  {% if user == 'Leroy' %}
  <a href="/delete/{{c.name}}" class="delete-btn">🗑</a>
  {% endif %}
  <h3>{{c.name}}</h3>
  <div class="progress-bar-container">
    <div class="progress-bar-fill" data-count="{{c.weekly_count}}" style="width:{{(c.weekly_count/6*100)}}%">{{c.weekly_count}}/6</div>
  </div>
  <p>Woche: {{c.weekly_count}} | Gesamt: {{c.total_count}}</p>
  <a href="/click/{{c.name}}" onclick="clickButton(this)"><button class="btn-full">+1</button></a>
  {% if user == 'Leroy' %}
  <a href="/reset_weekly/{{c.name}}"><button class="btn-full" style="background:#e67e22;">Woche zurücksetzen</button></a>
  <a href="/reset_total/{{c.name}}"><button class="btn-full" style="background:#c0392b;">Gesamt zurücksetzen</button></a>
  {% endif %}
  <button class="btn-full" onclick="toggleHistory('hist-{{c.name}}')">Historie</button>
  <div id="hist-{{c.name}}" class="history">
    <table>
      <tr><th>User</th><th>Zeit</th></tr>
      {% for click in c.all_clicks %}
      <tr><td>{{click.user}}</td><td>{{click.time}}</td></tr>
      {% endfor %}
    </table>
  </div>
  <button class="btn-full" onclick="toggleQR('qr-{{c.name}}')">QR-Code anzeigen</button>
  <div id="qr-{{c.name}}" style="display:none;margin-top:10px;">
    <img src="/qr_image/{{c.name}}" alt="QR Code für {{c.name}}">
  </div>
</div>
{% endfor %}
</body>
</html>
"""

TEMPLATE_LOGIN = """<!doctype html>
<html><head><title>Login</title></head>
<body>
<h2>Login</h2>
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
<form method="POST">
<input name="username" placeholder="Benutzername" required><br>
<input type="password" name="password" placeholder="Passwort" required><br>
<button>Konto erstellen</button>
</form>
<p>Schon registriert? <a href="/login">Login</a></p>
</body></html>"""

# ---------------- START ----------------
if __name__ == "__main__":
    data = load_data()
    if "QR-Code" not in data["users"]:
        data["users"]["QR-Code"] = {"password": generate_password_hash("123456"), "clicks":0}
        save_data(data)
    for cname,c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day",0))
    app.run(host="0.0.0.0", port=5000)
