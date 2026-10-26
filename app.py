import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# ========= GLOBAL STATE =========
STATE = {
    "running": False, "name": "", "last_name": "", "api_token": "",
    "page_id": "", "interval": 60, "posts": [], "current_index": 0,
    "logs": [], "post_count": 0, "owner": "MR SURAJ"
}
LOCK = threading.Lock()

# ========= HTML (अंदर ही अंदर) =========
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FB Auto Poster | MR SURAJ</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI',sans-serif; }
  body { background: linear-gradient(135deg,#0f0c29,#302b63,#24243e); color:#fff; min-height:100vh; padding:20px; }
  .owner-bar { text-align:center; padding:12px; background:linear-gradient(90deg,#ff6b6b,#ffd93d,#6bcB77,#4d96ff); -webkit-background-clip:text; background-clip:text; color:transparent; font-weight:900; font-size:22px; letter-spacing:2px; margin-bottom:20px; }
  .container { max-width:1100px; margin:0 auto; display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  @media(max-width:800px){ .container{grid-template-columns:1fr;} }
  .card { background:rgba(255,255,255,0.08); backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,0.15); border-radius:16px; padding:20px; }
  .card h2 { font-size:16px; margin-bottom:15px; color:#ffd93d; }
  label { display:block; font-size:12px; margin:10px 0 4px; color:#bbb; }
  input, textarea { width:100%; padding:10px; border-radius:8px; border:1px solid rgba(255,255,255,0.2); background:rgba(0,0,0,0.3); color:#fff; font-size:14px; outline:none; }
  input:focus, textarea:focus { border-color:#4d96ff; }
  textarea { resize:vertical; min-height:90px; font-family:monospace; }
  .btn-group { display:flex; gap:10px; margin-top:20px; }
  button { flex:1; padding:12px; border:none; border-radius:10px; font-weight:700; cursor:pointer; font-size:14px; transition:all .2s; }
  .btn-start { background:linear-gradient(135deg,#6bcB77,#4d96ff); color:#fff; }
  .btn-stop { background:linear-gradient(135deg,#ff6b6b,#c0392b); color:#fff; }
  .btn-test { background:linear-gradient(135deg,#ffd93d,#ff9a00); color:#000; }
  button:hover { transform:translateY(-2px); box-shadow:0 5px 15px rgba(0,0,0,0.4); }
  button:disabled { opacity:0.4; cursor:not-allowed; transform:none; }
  .live-panel { display:flex; flex-direction:column; height:100%; }
  .stats { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:15px; }
  .stat { background:rgba(0,0,0,0.3); border-radius:10px; padding:12px; text-align:center; }
  .stat .val { font-size:20px; font-weight:900; color:#ffd93d; }
  .stat .lbl { font-size:11px; color:#aaa; margin-top:4px; }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; margin-right:6px; }
  .dot.on { background:#6bcB77; box-shadow:0 0 10px #6bcB77; animation:pulse 1.5s infinite; }
  .dot.off { background:#666; }
  @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
  #console { flex:1; background:#000; border-radius:10px; padding:12px; font-family:'Courier New',monospace; font-size:12px; height:320px; overflow-y:auto; white-space:pre-wrap; border:1px solid rgba(107,203,119,0.3); }
  #console::-webkit-scrollbar { width:6px; }
  #console::-webkit-scrollbar-thumb { background:#4d96ff; border-radius:3px; }
  .toast { position:fixed; top:20px; right:20px; padding:12px 20px; border-radius:10px; font-weight:600; z-index:999; animation:slideIn .3s; }
  @keyframes slideIn { from{transform:translateX(400px);} to{transform:translateX(0);} }
  .toast.ok { background:#6bcB77; color:#000; }
  .toast.err { background:#ff6b6b; color:#fff; }
</style>
</head>
<body>
<div class="owner-bar">👑 OWNER: {{ owner }} 👑</div>
<div class="container">
  <div class="card">
    <h2>⚙️ Configuration</h2>
    <label>Name (First Name)</label><input id="name" placeholder="Enter first name">
    <label>Last Name</label><input id="last_name" placeholder="Enter last name">
    <label>Facebook API Token (Page Access Token)</label><input id="api_token" type="password" placeholder="EAAB...paste token here">
    <label>Page ID</label><input id="page_id" placeholder="1234567890">
    <label>Time Interval (seconds)</label><input id="interval" type="number" value="60" min="10">
    <label>Import File (प्रत्येक पंक्ति = एक पोस्ट)</label><input type="file" id="file_input" accept=".txt,.csv">
    <textarea id="import_content" placeholder="यहाँ आयातित कंटेंट दिखेगा... या सीधे लिखें"></textarea>
    <div class="btn-group">
      <button class="btn-start" id="btnStart" onclick="startBot()">▶ START</button>
      <button class="btn-stop" id="btnStop" onclick="stopBot()" disabled>⏹ STOP</button>
    </div>
    <div class="btn-group">
      <button class="btn-test" onclick="testPost()">🧪 Test Post</button>
    </div>
  </div>
  <div class="card live-panel">
    <h2>📊 Desbord Live Monitor</h2>
    <div class="stats">
      <div class="stat"><div class="val" id="statStatus"><span class="dot off"></span>OFF</div><div class="lbl">Status</div></div>
      <div class="stat"><div class="val" id="statCount">0</div><div class="lbl">Posts Made</div></div>
      <div class="stat"><div class="val" id="statName">-</div><div class="lbl">Name</div></div>
      <div class="stat"><div class="val" id="statInterval">-</div><div class="lbl">Interval (s)</div></div>
    </div>
    <div id="console">[Waiting for logs...]</div>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
function toast(msg, ok=true){ const t = document.createElement('div'); t.className = 'toast ' + (ok?'ok':'err'); t.textContent = msg; document.body.appendChild(t); setTimeout(()=>t.remove(), 2500); }
$('file_input').addEventListener('change', e => { const f = e.target.files[0]; if(!f) return; const reader = new FileReader(); reader.onload = ev => { $('import_content').value = ev.target.result; toast('File imported: ' + f.name); }; reader.readAsText(f); });
async function startBot(){ const body = { name: $('name').value, last_name: $('last_name').value, api_token: $('api_token').value, page_id: $('page_id').value, interval: parseInt($('interval').value) || 60, import_content: $('import_content').value }; if(!body.api_token || !body.page_id){ toast('API Token और Page ID ज़रूरी है', false); return; } const r = await fetch('/api/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) }); const d = await r.json(); if(d.ok){ toast('Bot Started ✅'); $('btnStart').disabled=true; $('btnStop').disabled=false; } else { toast(d.msg, false); } }
async function stopBot(){ await fetch('/api/stop', {method:'POST'}); toast('Bot Stopped'); $('btnStart').disabled=false; $('btnStop').disabled=true; }
async function testPost(){ const r = await fetch('/api/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:'Test post by MR SURAJ'}) }); const d = await r.json(); toast(d.ok ? 'Test Post OK' : 'Test Post Failed', d.ok); }
async function poll(){ try{ const r = await fetch('/api/status'); const d = await r.json(); $('statStatus').innerHTML = d.running ? '<span class="dot on"></span>LIVE' : '<span class="dot off"></span>OFF'; $('statCount').textContent = d.post_count; $('statName').textContent = (d.name || '-') + ' ' + (d.last_name || ''); $('statInterval').textContent = d.interval; if(d.logs && d.logs.length){ $('console').textContent = d.logs.join('\\n'); $('console').scrollTop = $('console').scrollHeight; } $('btnStart').disabled = d.running; $('btnStop').disabled = !d.running; }catch(e){} }
setInterval(poll, 2000); poll();
</script>
</body>
</html>
"""

# ========= LOG HELPER =========
def add_log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"info": "ℹ️", "success": "✅", "error": "❌", "warn": "⚠️"}.get(level, "•")
    line = f"[{ts}] {icon} {msg}"
    with LOCK:
        STATE["logs"].append(line)
        if len(STATE["logs"]) > 300: STATE["logs"] = STATE["logs"][-300:]
    print(line, flush=True)

# ========= FACEBOOK POST =========
def post_to_facebook(message):
    token, page_id = STATE["api_token"], STATE["page_id"]
    if not token or not page_id: return False
    url = f"https://graph.facebook.com/v24.0/{page_id}/feed"
    try:
        r = requests.post(url, data={"message": message, "access_token": token}, timeout=15)
        data = r.json()
        if "id" in data:
            STATE["post_count"] += 1
            add_log(f"पोस्ट सफल | ID: {data['id']}", "success")
            return True
        else:
            add_log(f"पोस्ट विफल: {data.get('error', {}).get('message', 'Unknown')}", "error")
            return False
    except Exception as e:
        add_log(f"नेटवर्क त्रुटि: {e}", "error")
        return False

# ========= WORKER =========
def worker():
    add_log("Worker शुरू हुआ - Non-stop mode", "success")
    while True:
        with LOCK:
            if not STATE["running"]: time.sleep(1); continue
        posts = STATE["posts"]
        if not posts: post_to_facebook(f"Auto post by {STATE['owner']} | {datetime.now()}")
        else:
            with LOCK:
                idx = STATE["current_index"] % len(posts)
                msg = posts[idx]
                STATE["current_index"] = (idx + 1) % len(posts)
            post_to_facebook(f"{msg}\n\n— {STATE['name']} {STATE['last_name']}".strip())
        interval = STATE["interval"]
        for _ in range(interval):
            with LOCK:
                if not STATE["running"]: break
            time.sleep(1)

# ========= ROUTES =========
@app.route("/")
def index(): return render_template_string(HTML_TEMPLATE, owner=STATE["owner"])

@app.route("/api/start", methods=["POST"])
def start():
    d = request.json or {}
    if not d.get("api_token") or not d.get("page_id"): return jsonify({"ok": False, "msg": "Token/PageID missing"}), 400
    with LOCK:
        STATE.update({"name": d.get("name",""), "last_name": d.get("last_name",""), "api_token": d.get("api_token","").strip(), "page_id": d.get("page_id","").strip(), "interval": max(10, int(d.get("interval",60))), "current_index": 0})
        content = d.get("import_content", "").strip()
        STATE["posts"] = [ln.strip() for ln in content.splitlines() if ln.strip()] if content else []
        STATE["running"] = True
    add_log(f"START | Name: {STATE['name']} | Interval: {STATE['interval']}s", "success")
    return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def stop():
    with LOCK: STATE["running"] = False
    add_log("STOP - रोका गया", "warn"); return jsonify({"ok": True})

@app.route("/api/status")
def status():
    with LOCK: return jsonify({k: STATE[k] for k in ["running","logs","post_count","name","last_name","interval"]})

@app.route("/api/test", methods=["POST"])
def test():
    ok = post_to_facebook("Test post by MR SURAJ")
    return jsonify({"ok": ok})

threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))