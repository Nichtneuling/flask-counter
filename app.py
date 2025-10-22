from flask import Flask, render_template, request, redirect, session, send_file
import os, json, io, qrcode

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "data.json"

# -----------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------
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

# -----------------------------------------------------------------
# Login & Registrierung
# -----------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = load_data()
        username = request.form["username"]
        password = request.form["password"]
        if username in data["users"] and data["users"][username]["password"] == password:
            session["username"] = username
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="❌ Falscher Benutzername oder Passwort")
    return render_template("login.html", error=None)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = load_data()
        username = request.form["username"]
        password = request.form["password"]
        if username in data["users"]:
            return render_template("register.html", error="⚠️ Benutzername existiert bereits")
        data["users"][username] = {"password": password}
        save_data(data)
        session["username"] = username
        return redirect("/dashboard")
    return render_template("register.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -----------------------------------------------------------------
# Dashboard & Counter
# -----------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")
    data = load_data()
    user = session["username"]
    return render_template("dashboard.html", data=data, user=user)

@app.route("/add_counter", methods=["POST"])
def add_counter():
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    name = request.form["name"]
    color = request.form["color"]
    reset_day = request.form["reset_day"]
    data["counters"][name] = {"color": color, "reset_day": reset_day, "weekly_count": 0, "total_count": 0}
    save_data(data)
    return redirect("/dashboard")

@app.route("/delete/<counter>")
def delete_counter(counter):
    if "username" not in session or session["username"] != "Leroy":
        return "Keine Berechtigung!"
    data = load_data()
    if counter in data["counters"]:
        del data["counters"][counter]
        save_data(data)
    return redirect("/dashboard")

@app.route("/click/<counter>")
def click_counter(counter):
    data = load_data()
    if counter not in data["counters"]:
        return "Zähler nicht gefunden!"
    user = session.get("username") or request.args.get("user")
    if not user:
        return redirect("/")
    c = data["counters"][counter]
    c["weekly_count"] = min(c["weekly_count"] + 1, 6)
    c["total_count"] += 1
    save_data(data)
    if user == "QR-Code":
        return "<h2 style='text-align:center;color:green;'>✅ Der Trocknervorgang wurde gezählt!</h2>"
    return redirect("/dashboard")

@app.route("/reset_week")
def reset_week():
    if "username" not in session or session["username"] != "Leroy":
        return redirect("/")
    data = load_data()
    for c in data["counters"].values():
        c["weekly_count"] = 0
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
    save_data(data)
    return redirect("/dashboard")

# -----------------------------------------------------------------
# QR-Code
# -----------------------------------------------------------------
@app.route("/qrcode/<counter>")
def show_qrcode(counter):
    if "username" not in session:
        return redirect("/")
    return render_template("qrcode.html", counter=counter)

@app.route("/qrcode_image/<counter>")
def qrcode_image(counter):
    base_url = request.host_url.rstrip("/")
    qr_url = f"{base_url}/click/{counter}?user=QR-Code"
    img = qrcode.make(qr_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# -----------------------------------------------------------------
# Start
# -----------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
