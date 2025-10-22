# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, schedule, threading, time
from datetime import datetime
import qrcode

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "data.json"
QR_FOLDER = "static/qr"

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

# ---------------- QR-Code erzeugen ----------------
def generate_qr(counter_name):
    if not os.path.exists(QR_FOLDER):
        os.makedirs(QR_FOLDER)
    url = f"{request.url_root}click/{counter_name}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=5,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    filepath = os.path.join(QR_FOLDER, f"qr_{counter_name}.png")
    img.save(filepath)
    return f"/{filepath.replace(os.sep, '/')}"

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
    qr_codes = {}
    for name in counters.keys():
        qr_codes[name] = generate_qr(name)
    return render_template_string(TEMPLATE_INDEX, counters=counters, qr_codes=qr_codes, user=session.get("username",""))

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
    if require_login() or session["username"] != "Leroy":
        return redirect("/login")
    name = request.form["counter_name"].strip()
    color = request.form.get("color", "#3498db")
    reset_day = int(request.form.get("reset_day", 0))
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
    if c["weekly_count"] > 6: c["weekly_count"] = 6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user": session.get("username","Gast"), "time": now})
    c["all_clicks"].append({"user": session.get("username","Gast"), "time": now})
    save_data(data)
    return redirect("/")

@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if require_login() or session["username"] != "Leroy":
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
    if require_login() or session["username"] != "Leroy":
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
    if require_login() or session["username"] != "Leroy":
        return redirect("/login")
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/")

# ---------------- HTML ----------------
TEMPLATE_INDEX = """<!doctype html>
<html>
<head>
<title>Zähler Übersicht</title>
<style>
body{font-family:sans-serif;background:#f5f6fa;margin:0;padding:20px;}
.card{
  background:#3498db;color:white;padding:20px;border-radius:12px;margin:10px;width:300px;display:inline-block;position:relative;text-align:center;
}
.btn-full{width:100%;padding:15px;margin-top:10px;background:#2ecc71;border:none;color:white;font-weight:bold;border-radius:10px;cursor:pointer;transition:0.3s;font-size:18px;}
.btn-full:hover{background:#27ae60;}
.history{display:none;background:white;color:black;padding:10px;margin-top:10px;border-radius:6px;max-height:150px;overflow:auto;}
.delete-btn{position:absolute;top:10px;right:10px;color:white;text-decoration:none;font-weight:bold;}
.progress-bar-container{width:100%; background: rgba(255,255,255,0.3); height:25px; border-radius:10px; margin-bottom:10px; overflow:hidden;}
.progress-bar-fill{height:100%; width:0%; background:#fff; border-radius:10px; transition: width 0.5s ease; color:black; text-align:center; font-weight:bold; line-height:25px;}
.qr{margin-top:10px;}
</style>
<script>
function toggleForm(){document.getElementById('form').style.display='block';}
function toggleHistory(id){var h=document.getElementById(id);h.style.display=(h.style.display=='none')?'block':'none';}

// Confetti Animation (länger sichtbar + langsam ausblenden)
function createConfetti(card){
    for(let i=0;i<50;i++){
        let div = document.createElement('div');
        div.style.width='8px';
        div.style.height='8px';
        div.style.position='absolute';
        div.style.background=['#f1c40f','#e74c3c','#2ecc71','#3498db','#9b59b6'][Math.floor(Math.random()*5)];
        div.style.left=Math.random()*card.offsetWidth+'px';
        div.style.top='0px';
        div.style.opacity = 1;
        div.style.borderRadius = "50%";
        card.appendChild(div);
        animateConfetti(div, card);
    }
}

function animateConfetti(div, card){
    let top = 0;
    let left = parseFloat(div.style.left);
    let speedY = Math.random()*2 + 1; 
    let speedX = (Math.random()-0.5)*1.5;
    let opacity = 1;
    let startTime = performance.now();

    function frame(now){
        let elapsed = now - startTime;
        top += speedY;
        left += speedX;
        div.style.top = top + 'px';
        div.style.left = left + 'px';
        if(elapsed < 5000){ // 5 Sekunden fliegen
            requestAnimationFrame(frame);
        } else if(elapsed < 7000){ // 2 Sekunden ausblenden
            opacity = 1 - (elapsed - 5000)/2000;
            div.style.opacity = opacity;
            requestAnimationFrame(frame);
        } else {
            div.remove();
        }
    }
    requestAnimationFrame(frame);
}

function clickButton(el){
    createConfetti(el.parentNode);
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
  <a href="/delete/{{c.name}}" class="delete-btn">🗑</a>
  <h3>{{c.name}}</h3>
  <div class="progress-bar-container">
    <div class="progress-bar-fill" data-count="{{c.weekly_count}}" style="width:{{(c.weekly_count/6*100)}}%">{{c.weekly_count}}/6</div>
  </div>
  <p>Woche: {{c.weekly_count}} | Gesamt: {{c.total_count}}</p>
  <a href="/click/{{c.name}}" onclick="clickButton(this)"><button class="btn-full">+1</button></a>
  {% if user=='Leroy' %}
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
  <img src="{{qr_codes[c.name]}}" class="qr" title="Scan für +1">
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
    for cname,c in data["counters"].items():
        schedule_reset(cname, c.get("reset_day",0))
    app.run(host="0.0.0.0", port=5000, debug=True)
