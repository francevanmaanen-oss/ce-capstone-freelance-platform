import os
import urllib.request
from flask import Flask, request, session, redirect, url_for, render_template_string

app = Flask(__name__)
# Shared secret so signed-cookie sessions work across all instances behind the ALB.
app.secret_key = os.environ.get("SECRET_KEY", "demo-secret-key-not-for-production-2026")

# --- Demo auth (single hardcoded login, checked server-side). Demo only. ---
DEMO_USER = "admin"
DEMO_PASS = "freelance2026"

JOBS = [
    {"title": "Graphic Designer", "company": "Studio Vela",
     "location": "Remote (EU)", "rate": "EUR 55/hr",
     "tags": ["Branding", "Adobe CC", "Print", "Logo Design"]},
    {"title": "Marketing Consultant", "company": "Northbound Agency",
     "location": "Hybrid - Amsterdam", "rate": "EUR 70/hr",
     "tags": ["Strategy", "SEO", "Campaigns", "Analytics"]},
    {"title": "UX/UI Designer", "company": "Pixel & Co",
     "location": "Remote", "rate": "EUR 65/hr",
     "tags": ["Figma", "Design Systems", "Prototyping", "User Research"]},
    {"title": "Customer Journey Consultant", "company": "Flowmap",
     "location": "Rotterdam", "rate": "EUR 75/hr",
     "tags": ["CX Mapping", "Service Design", "Workshops"]},
    {"title": "Content Strategist", "company": "Wordcraft",
     "location": "Remote (EU)", "rate": "EUR 60/hr",
     "tags": ["Copywriting", "Content Planning", "Brand Voice"]},
    {"title": "Brand Designer", "company": "Atelier Nova",
     "location": "Hybrid - Utrecht", "rate": "EUR 68/hr",
     "tags": ["Identity", "Typography", "Art Direction"]},
]


def get_metadata(path):
    try:
        token_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            method="PUT")
        token = urllib.request.urlopen(token_req, timeout=2).read().decode()
        req = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/" + path,
            headers={"X-aws-ec2-metadata-token": token})
        return urllib.request.urlopen(req, timeout=2).read().decode()
    except Exception:
        return "local"


BASE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FreelanceHub</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: #0f1117; color: #e8eaf0; min-height: 100vh; display: flex;
           flex-direction: column; }
    a { color: inherit; text-decoration: none; }
    .nav { display: flex; justify-content: space-between; align-items: center;
           padding: 18px 32px; border-bottom: 1px solid #232733; }
    .brand { font-weight: 700; font-size: 20px; letter-spacing: -0.5px; }
    .brand span { color: #6c8cff; }
    .btn { background: #6c8cff; color: #fff; padding: 10px 20px; border-radius: 8px;
           font-weight: 600; border: none; cursor: pointer; font-size: 15px; display: inline-block; }
    .btn:hover { background: #5a78e8; }
    .btn-ghost { background: transparent; border: 1px solid #343a49; }
    .btn-ghost:hover { background: #1a1e29; }
    .wrap { flex: 1; max-width: 1000px; margin: 0 auto; padding: 48px 32px; width: 100%; }
    .hero { text-align: center; padding: 64px 0 48px; }
    .hero h1 { font-size: 48px; letter-spacing: -1.5px; line-height: 1.1; margin-bottom: 18px; }
    .hero h1 span { background: linear-gradient(90deg, #6c8cff, #a06cff);
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .hero p { font-size: 19px; color: #9aa3b5; max-width: 560px; margin: 0 auto 32px; }
    .card { background: #161a24; border: 1px solid #232733; border-radius: 14px;
            padding: 22px 24px; margin-bottom: 16px; transition: border-color 0.15s; }
    .card:hover { border-color: #39405a; }
    .job-top { display: flex; justify-content: space-between; align-items: flex-start; }
    .job-title { font-size: 18px; font-weight: 650; margin-bottom: 4px; }
    .job-company { color: #9aa3b5; font-size: 15px; }
    .job-rate { color: #6cffa0; font-weight: 650; font-size: 16px; white-space: nowrap; }
    .job-meta { color: #707a8f; font-size: 14px; margin-top: 6px; }
    .tags { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    .tag { background: #1f2433; color: #aab4cc; padding: 4px 12px; border-radius: 20px; font-size: 13px; }
    .login-box { max-width: 380px; margin: 40px auto; background: #161a24;
                 border: 1px solid #232733; border-radius: 14px; padding: 36px; }
    .login-box h2 { font-size: 24px; margin-bottom: 6px; }
    .login-box p { color: #9aa3b5; font-size: 14px; margin-bottom: 24px; }
    label { display: block; font-size: 14px; color: #aab4cc; margin-bottom: 6px; margin-top: 16px; }
    input { width: 100%; padding: 12px 14px; background: #0f1117; border: 1px solid #2b3140;
            border-radius: 8px; color: #e8eaf0; font-size: 15px; }
    input:focus { outline: none; border-color: #6c8cff; }
    .login-box .btn { width: 100%; margin-top: 24px; padding: 13px; }
    .error { background: #2a1620; border: 1px solid #5a2233; color: #ff8aa3;
             padding: 12px 14px; border-radius: 8px; font-size: 14px; margin-top: 18px; }
    .hint { font-size: 13px; color: #707a8f; margin-top: 18px; text-align: center; }
    .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .section-head h2 { font-size: 28px; letter-spacing: -0.5px; }
    .footer { border-top: 1px solid #232733; padding: 16px 32px; text-align: center;
              color: #5a6177; font-size: 13px; }
    .footer code { color: #6c8cff; background: #161a24; padding: 2px 7px; border-radius: 5px; }
  </style>
</head>
<body>
  <div class="nav">
    <a href="/" class="brand">Freelance<span>Hub</span></a>
    {{ nav | safe }}
  </div>
  {{ body | safe }}
  <div class="footer">
    Served by instance <code>{{ instance_id }}</code> in <code>{{ az }}</code> &middot; env: {{ env }}
  </div>
</body>
</html>
"""


def render(body, nav=""):
    return render_template_string(
        BASE, body=body, nav=nav,
        instance_id=get_metadata("instance-id"),
        az=get_metadata("placement/availability-zone"),
        env=os.environ.get("ENVIRONMENT", "dev"))


@app.route("/")
def index():
    nav = '<a href="/jobs" class="btn">Browse jobs</a>'
    body = """
    <div class="wrap">
      <div class="hero">
        <h1>Find your next <span>creative gig</span></h1>
        <p>FreelanceHub connects independent designers, marketers, and creative
           consultants with companies hiring on flexible terms.</p>
        <a href="/jobs" class="btn">Browse open roles</a>
      </div>
    </div>
    """
    return render(body, nav)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("username") == DEMO_USER and request.form.get("password") == DEMO_PASS:
            session["logged_in"] = True
            return redirect(url_for("jobs"))
        error = '<div class="error">Incorrect username or password.</div>'
    body = """
    <div class="wrap">
      <div class="login-box">
        <h2>Sign in</h2>
        <p>Log in to view available freelance roles.</p>
        <form method="post">
          <label>Username</label>
          <input name="username" autocomplete="off" autofocus>
          <label>Password</label>
          <input name="password" type="password">
          <button class="btn" type="submit">Sign in</button>
        </form>
        ERROR
        <div class="hint">Demo login &mdash; username: admin &middot; password: freelance2026</div>
      </div>
    </div>
    """.replace("ERROR", error)
    return render(body)


@app.route("/jobs")
def jobs():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    cards = ""
    for j in JOBS:
        tags = "".join('<span class="tag">' + t + "</span>" for t in j["tags"])
        cards += """
        <div class="card">
          <div class="job-top">
            <div>
              <div class="job-title">TITLE</div>
              <div class="job-company">COMPANY</div>
            </div>
            <div class="job-rate">RATE</div>
          </div>
          <div class="job-meta">LOCATION</div>
          <div class="tags">TAGS</div>
        </div>
        """.replace("TITLE", j["title"]).replace("COMPANY", j["company"]) \
           .replace("RATE", j["rate"]).replace("LOCATION", j["location"]).replace("TAGS", tags)
    nav = '<a href="/logout" class="btn btn-ghost">Log out</a>'
    body = '<div class="wrap"><div class="section-head"><h2>Open roles</h2></div>' + cards + "</div>"
    return render(body, nav)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "healthy"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
