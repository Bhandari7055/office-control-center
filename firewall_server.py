from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Office Network Dashboard")

history_logs = []
blocked_sites = ["facebook.com", "instagram.com"]
active_pcs = {}


class HistoryEntry(BaseModel):
    pc_name: str
    url: str
    title: str
    timestamp: Optional[str] = None


class SiteAction(BaseModel):
    domain: str


def cleanup_old_history():
    global history_logs
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    history_logs = [
        log
        for log in history_logs
        if datetime.fromisoformat(log["timestamp"]) > cutoff
    ]


@app.get("/", response_class=HTMLResponse)
def dashboard():
    cleanup_old_history()
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Office Management Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f0f2f5; }
            h1 { color: #1a1a1a; margin-bottom: 20px; }
            .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
            .container { display: flex; gap: 20px; }
            .left-panel { width: 30%; }
            .right-panel { width: 70%; }
            ul { list-style: none; padding: 0; margin: 0; }
            li { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border-radius: 6px; }
            li:hover { background-color: #f8f9fa; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #e9ecef; padding: 10px; text-align: left; word-break: break-all; }
            th { background-color: #0d6efd; color: white; }
            input[type="text"] { padding: 10px; width: 60%; border: 1px solid #ced4da; border-radius: 5px; }
            button { padding: 10px 15px; cursor: pointer; border: none; border-radius: 5px; color: white; font-weight: bold; }
            .btn-block { background-color: #dc3545; }
            .btn-unblock { background-color: #198754; }
            .badge { background: #0dcaf0; color: #000; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🏢 Office Firewall & PC Monitoring Dashboard</h1>
        
        <div class="card">
            <h3>Website Control</h3>
            <input type="text" id="domainInput" placeholder="Enter domain (e.g. youtube.com)">
            <button class="btn-block" onclick="manageSite('block')">Block Website</button>
            <button class="btn-unblock" onclick="manageSite('unblock')">Unblock Website</button>
            <p><strong>Currently Blocked Sites:</strong> <span id="blockedList">Loading...</span></p>
        </div>

        <div class="container">
            <div class="card left-panel">
                <h3>Connected PCs</h3>
                <ul id="pcList"><li>Detecting systems...</li></ul>
            </div>

            <div class="card right-panel">
                <h3 id="historyHeader">Click any PC to view 3-Month Browser History</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Page Title</th>
                            <th>URL</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable">
                        <tr><td colspan="3">Select a PC from the left side.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadData() {
                const rulesRes = await fetch('/api/rules');
                const rules = await rulesRes.json();
                document.getElementById('blockedList').innerText = rules.join(', ') || 'None';

                const pcsRes = await fetch('/api/pcs');
                const pcs = await pcsRes.json();
                const pcList = document.getElementById('pcList');
                pcList.innerHTML = '';
                
                Object.keys(pcs).forEach(pc => {
                    const li = document.createElement('li');
                    li.innerHTML = `<span>💻 <strong>${pc}</strong></span> <span class="badge">ONLINE</span>`;
                    li.onclick = () => loadHistory(pc);
                    pcList.appendChild(li);
                });
            }

            async function loadHistory(pcName) {
                document.getElementById('historyHeader').innerText = `Browser History: ${pcName}`;
                const res = await fetch(`/api/history?pc_name=${pcName}`);
                const data = await res.json();
                const tbody = document.getElementById('historyTable');
                tbody.innerHTML = '';

                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3">No history logs received yet.</td></tr>';
                    return;
                }

                data.reverse().forEach(item => {
                    const tr = document.createElement('tr');
                    const date = new Date(item.timestamp).toLocaleString();
                    tr.innerHTML = `<td>${date}</td><td>${item.title || 'No Title'}</td><td><a href="${item.url}" target="_blank">${item.url}</a></td>`;
                    tbody.appendChild(tr);
                });
            }

            async function manageSite(action) {
                const domain = document.getElementById('domainInput').value.trim();
                if (!domain) return alert('Please enter a domain name');

                await fetch(`/api/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ domain: domain })
                });

                document.getElementById('domainInput').value = '';
                loadData();
            }

            loadData();
            setInterval(loadData, 10000);
        </script>
    </body>
    </html>
    """


@app.get("/api/rules")
def get_rules():
    return blocked_sites


@app.post("/api/block")
def block_site(action: SiteAction):
    domain = action.domain.lower().strip()
    if domain not in blocked_sites:
        blocked_sites.append(domain)
    return {"status": "success", "blocked_sites": blocked_sites}


@app.post("/api/unblock")
def unblock_site(action: SiteAction):
    domain = action.domain.lower().strip()
    if domain in blocked_sites:
        blocked_sites.remove(domain)
    return {"status": "success", "blocked_sites": blocked_sites}


@app.post("/api/heartbeat")
def receive_heartbeat(data: dict):
    pc_name = data.get("pc_name", "Unknown-PC")
    active_pcs[pc_name] = datetime.now(timezone.utc).isoformat()
    return {"status": "ok"}


@app.get("/api/pcs")
def get_pcs():
    return active_pcs


@app.post("/api/history")
def receive_history(logs: List[HistoryEntry]):
    global history_logs
    for log in logs:
        entry = log.model_dump()
        if not entry.get("timestamp"):
            entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        history_logs.append(entry)
    cleanup_old_history()
    return {"status": "success"}


@app.get("/api/history")
def get_history(pc_name: Optional[str] = None):
    cleanup_old_history()
    if pc_name:
        return [
            log
            for log in history_logs
            if log["pc_name"].lower() == pc_name.lower()
        ]
    return history_logs
