from flask import Flask, render_template, request, redirect, session, url_for, send_file
import qrcode
import io
import json
import os
from datetime import datetime
from flask import flash

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "data.json"


# =============================
# 🔧 Hilfsfunktionen
# =============================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {"Leroy": "1234"}, "counters": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =============================
# 🏠 Startseite / Login
# =============================
@app.route("/")
def home():
    if "username" in session:
        data = load_data()
        return render_template("dashboard.html", user=session["username"], data=data)
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    data = load_data()
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in data["users"] and data["users"][username] == password:
            session["username"] = username
            return redirect("/")
        else:
            error = "Falscher Benutzername oder Passwort!"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")


# =============================
# ➕ Zählerverwaltung
# =============================
@app.route("/add_counter", methods=["POST"])
def add_counter():
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")

    data = load_data()
    name = request.form["name"]
    color = request.form["color"]
    reset_day = int(request.form["reset_day"])

    data["counters"][name] = {
        "weekly_count": 0,
        "total_count": 0,
        "color": color,
        "reset_day": reset_day
    }

    save_data(data)
    return redirect("/")


@app.route("/click/<counter>")
def click_counter(counter):
    data = load_data()
    if counter in data["counters"]:
        data["counters"][counter]["weekly_count"] += 1
        data["counters"][counter]["total_count"] += 1
        save_data(data)
        return render_template("qr_success.html", counter=counter)
    return "Zähler nicht gefunden", 404


@app.route("/delete/<counter>")
def delete_counter(counter):
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/")


@app.route("/reset_weekly/<counter>")
def reset_weekly(counter):
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    if counter in data["counters"]:
        data["counters"][counter]["weekly_count"] = 0
        save_data(data)
    return redirect("/")


@app.route("/reset_total/<counter>")
def reset_total(counter):
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    if counter in data["counters"]:
        data["counters"][counter]["total_count"] = 0
        save_data(data)
    return redirect("/")


# =============================
# 📱 QR-Code anzeigen
# =============================
@app.route("/show_qrcode/<counter>")
def show_qrcode(counter):
    url = f"https://flask-counter-br47.onrender.com/click/{counter}"
    qr = qrcode.make(url)
    img_io = io.BytesIO()
    qr.save(img_io, "PNG")
    img_io.seek(0)
    return send_file(img_io, mimetype="image/png")


# =============================
# 🚀 App starten
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
