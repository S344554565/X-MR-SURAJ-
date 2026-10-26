import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ========= GLOBAL STATE =========
STATE = {
    "running": False,
    "name": "",
    "last_name": "",
    "api_token": "",
    "page_id": "",
    "interval": 60,
    "posts": [],
    "current_index": 0,
    "logs": [],
    "post_count": 0,
    "owner": "MR SURAJ"
}

LOCK = threading.Lock()

# ========= LOG HELPER =========
def add_log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info": "ℹ️", "success": "✅", "error": "❌", "warn": "⚠️"}.get(level, "•")
    line = f"[{ts}] {icon} {msg}"
    with LOCK:
        STATE["logs"].append(line)
        if len(STATE["logs"]) > 300:
            STATE["logs"] = STATE["logs"][-300:]
    print(line, flush=True)

# ========= FACEBOOK POST =========
def post_to_facebook(message):
    token = STATE["api_token"]
    page_id = STATE["page_id"]
    if not token or not page_id:
        add_log("API Token या Page ID गायब है", "error")
        return False

    url = f"https://graph.facebook.com/v24.0/{page_id}/feed"
    payload = {"message": message, "access_token": token}

    try:
        r = requests.post(url, data=payload, timeout=15)
        data = r.json()
        if "id" in data:
            STATE["post_count"] += 1
            add_log(f"पोस्ट सफल | ID: {data['id']}", "success")
            return True
        else:
            err = data.get("error", {}).get("message", "Unknown error")
            add_log(f"पोस्ट विफल: {err}", "error")
            return False
    except Exception as e:
        add_log(f"नेटवर्क त्रुटि: {e}", "error")
        return False

# ========= WORKER LOOP =========
def worker():
    add_log("Worker शुरू हुआ - Non-stop mode", "success")
    while True:
        with LOCK:
            running = STATE["running"]
        if not running:
            time.sleep(1)
            continue

        posts = STATE["posts"]
        if not posts:
            with LOCK:
                msg = f"Auto post by {STATE['owner']} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            post_to_facebook(msg)
        else:
            with LOCK:
                idx = STATE["current_index"] % len(posts)
                msg = posts[idx]
                STATE["current_index"] = (idx + 1) % len(posts)

            full_msg = f"{msg}\n\n— {STATE['name']} {STATE['last_name']}".strip()
            post_to_facebook(full_msg)

        # Sleep with stop check
        interval = STATE["interval"]
        elapsed = 0
        while elapsed < interval:
            with LOCK:
                if not STATE["running"]:
                    break
            time.sleep(1)
            elapsed += 1

    add_log("Worker बंद हुआ", "warn")

# ========= ROUTES =========
@app.route("/")
def index():
    return render_template("index.html", owner=STATE["owner"])

@app.route("/api/start", methods=["POST"])
def start():
    d = request.json or {}

    if not d.get("api_token"):
        return jsonify({"ok": False, "msg": "API Token ज़रूरी है"}), 400
    if not d.get("page_id"):
        return jsonify({"ok": False, "msg": "Page ID ज़रूरी है"}), 400

    with LOCK:
        STATE["name"] = d.get("name", "")
        STATE["last_name"] = d.get("last_name", "")
        STATE["api_token"] = d.get("api_token", "").strip()
        STATE["page_id"] = d.get("page_id", "").strip()
        STATE["interval"] = max(10, int(d.get("interval", 60)))
        STATE["current_index"] = 0

        # Import file content
        content = d.get("import_content", "").strip()
        if content:
            STATE["posts"] = [ln.strip() for ln in content.splitlines() if ln.strip()]
        else:
            STATE["posts"] = []

        STATE["running"] = True

    add_log(f"START | Name: {STATE['name']} {STATE['last_name']} | Interval: {STATE['interval']}s", "success")
    return jsonify({"ok": True, "msg": "Started"})

@app.route("/api/stop", methods=["POST"])
def stop():
    with LOCK:
        STATE["running"] = False
    add_log("STOP - रोका गया", "warn")
    return jsonify({"ok": True, "msg": "Stopped"})

@app.route("/api/status")
def status():
    with LOCK:
        return jsonify({
            "running": STATE["running"],
            "logs": STATE["logs"][-60:],
            "post_count": STATE["post_count"],
            "name": STATE["name"],
            "last_name": STATE["last_name"],
            "interval": STATE["interval"],
            "owner": STATE["owner"]
        })

@app.route("/api/test", methods=["POST"])
def test():
    d = request.json or {}
    msg = d.get("message", f"Test post by {STATE['owner']}")
    if not STATE["api_token"]:
        return jsonify({"ok": False, "msg": "पहले Start करें"}), 400
    ok = post_to_facebook(msg)
    return jsonify({"ok": ok})

# ========= START WORKER THREAD =========
threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
