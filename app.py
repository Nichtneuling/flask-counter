# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, session, send_file
import os, json, qrcode, io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "data.json"

# -------------------
# Hilfsfunktionen
# -------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "users": {
                "Leroy": {"password": "admin"},
                "QR-Code": {"password": "123456"}
            },
            "counters": {}
        }
        save_data(data)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# -------------------
# Login / Logout
# -------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = load_data()
        user = request.form["username"]
        pwd = request.form["password"]
        if user in data["users"] and data["users"][user]["password"] == pwd:
            session["username"] = user
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Falscher Benutzername oder Passwort")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -------------------
# Dashboard
# -------------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")
    data = load_data()
    user = session["username"]
    return render_template("dashboard.html", data=data, user=user)

# -------------------
# Zähler hinzufügen
# -------------------
@app.route("/add_counter", methods=["POST"])
def add_counter():
    if "username" not in session:
        return redirect("/")
    name = request.form["name"]
    color = request.form["color"]
    reset_day = request.form["reset_day"]
    data = load_data()
    data["counters"][name] = {
        "color": color,
        "reset_day": reset_day,
        "weekly_count": 0,
        "total_count": 0,
        "weekly_clicks": [],
        "all_clicks": []
    }
    save_data(data)
    return redirect("/dashboard")

# -------------------
# Zähler löschen (nur Leroy)
# -------------------
@app.route("/delete/<counter>")
def delete(counter):
    if "username" not in session:
        return redirect("/")
    user = session["username"]
    if user != "Leroy":
        return "Keine Berechtigung!"
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/dashboard")

# -------------------
# Klick (+1)
# -------------------
@app.route("/click/<counter>")
def click(counter):
    data = load_data()
    c = data["counters"].get(counter)
    if not c:
        return "Zähler nicht gefunden!"
    
    user = session.get("username") or request.args.get("user")
    if not user:
        return redirect("/")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c["weekly_count"] += 1
    if c["weekly_count"] > 6:
        c["weekly_count"] = 6
    c["total_count"] += 1
    c["weekly_clicks"].append({"user": user, "time": now})
    c["all_clicks"].append({"user": user, "time": now})
    save_data(data)

    # Wenn QR-Code verwendet wird:
    if user == "QR-Code":
        return """
        <html>
        <head><meta charset='utf-8'><title>Gezählt!</title></head>
        <body style='font-family:sans-serif; text-align:center; background:#f8f9fa;'>
            <h2 style='color:green;'>✅ Der Trocknervorgang wurde gezählt!</h2>
            <p>Vielen Dank!</p>
        </body>
        </html>
        """

    return redirect("/dashboard")

# -------------------
# Reset-Funktionen (nur Leroy)
# -------------------
@app.route("/reset_week")
def reset_week():
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    for c in data["counters"].values():
        c["weekly_count"] = 0
        c["weekly_clicks"].clear()
    save_data(data)
    return redirect("/dashboard")

@app.route("/reset_all")
def reset_all():
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    for c in data["counters"].values():
        c["weekly_count"] = 0
        c["total_count"] = 0
        c["weekly_clicks"].clear()
        c["all_clicks"].clear()
    save_data(data)
    return redirect("/dashboard")

# -------------------
# QR-Code-Seite
# -------------------
@app.route("/qrcode/<counter>")
def qrcode_view(counter):
    if "username" not in session:
        return redirect("/")
    return render_template("qrcode.html", counter=counter)

# -------------------
# QR-Code generieren
# -------------------
@app.route("/qrcode_image/<counter>")
def qrcode_image(counter):
    base_url = request.host_url.rstrip("/")
    qr_url = f"{base_url}/click/{counter}?user=QR-Code"
    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# -------------------
# Start
# -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
