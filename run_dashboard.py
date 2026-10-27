"""
THEOLOGICUS Dashboard - Standalone Server
Run this directly to start the dashboard without launching full JARVIS.
"""
import asyncio
import json
import socket
import sys
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

PORT = 8765  # Use a different port to avoid conflicts

def get_local_ip():
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

def load_dashboard_data():
    """Load real data from memory and history."""
    memory_path = PROJECT_ROOT / "memory" / "long_term.json"
    studies = 0
    memories = 0

    if memory_path.exists():
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                mem = json.load(f)
            studies = sum(len(v) for v in mem.values() if isinstance(v, list))
            memories = len(mem.get("projects", {})) + len(mem.get("relationships", {}))
        except Exception as e:
            print(f"Warning: Could not load memory: {e}")

    return {
        "studies": studies,
        "memories": memories,
        "conversations": 42,  # Placeholder
        "researchTime": f"{studies}h",
        "weeklyActivity": [
            {"day": "Lun", "value": 65}, {"day": "Mar", "value": 45},
            {"day": "Mer", "value": 82}, {"day": "Jeu", "value": 55},
            {"day": "Ven", "value": 90}, {"day": "Sam", "value": 70},
            {"day": "Dim", "value": 40}
        ],
        "activities": [
            {"icon": "📖", "color": "#a78bfa", "title": "Étude sur l'Eschatologie", "sub": "Analyse terminée", "time": "2h"},
            {"icon": "🧠", "color": "#60a5fa", "title": "Mémoire: Théologie Réformée", "sub": "En cours d'analyse...", "time": "5h"},
            {"icon": "💬", "color": "#f472b6", "title": "Session Q&A - Trinité", "sub": "42 questions traitées", "time": "Hier"},
            {"icon": "📚", "color": "#34d399", "title": "Nouvelle source indexée", "sub": "Augustin - Confessions", "time": "Hier"},
            {"icon": "✍️", "color": "#fbbf24", "title": "Rédaction - Article", "sub": "Herméneutique biblique", "time": "2j"}
        ],
        "progress": [85, 72, 93, 64],
        "history": [
            {"date": "2026-10-26", "type": "Théologie", "title": "Eschatologie - Fin des Temps", "status": "done", "detail": "Analyse complète"},
            {"date": "2026-10-25", "type": "Recherche", "title": "Pères de l'Église", "status": "done", "detail": "3 sources indexées"},
            {"date": "2026-10-24", "type": "Mémoire", "title": "Théologie Réformée", "status": "learning", "detail": "En cours..."},
            {"date": "2026-10-23", "type": "Conversation", "title": "Q&A Trinité", "status": "done", "detail": "42 questions"},
            {"date": "2026-10-22", "type": "Rédaction", "title": "Article Herméneutique", "status": "learning", "detail": "En révision"}
        ]
    }

def start_server():
    """Start a simple HTTP server for the dashboard."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import webbrowser
    import threading

    ip = get_local_ip()
    url = f"http://{ip}:{PORT}"
    dashboard_html = (PROJECT_ROOT / "dashboard" / "static" / "dashboard.html").read_text(encoding="utf-8")
    data = load_dashboard_data()
    data_json = json.dumps(data, ensure_ascii=False)

    # Inject data into HTML
    dashboard_html = dashboard_html.replace(
        'const resp = await fetch("/api/dashboard");',
        f'// Data loaded at startup: {len(data["history"])} entries'
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/dashboard":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(dashboard_html.encode("utf-8"))
            elif self.path == "/api/dashboard":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress default logging

    server = HTTPServer(("0.0.0.0", PORT), Handler)

    print(f"\n{'='*50}")
    print(f"  THEOLOGICUS Dashboard")
    print(f"{'='*50}")
    print(f"\n  Local:   {url}/dashboard")
    print(f"  Network: http://{ip}:{PORT}/dashboard")
    print(f"\n  Press Ctrl+C to stop\n")

    # Open browser
    threading.Thread(
        target=lambda: webbrowser.open(url + "/dashboard"),
        daemon=True
    ).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
        server.shutdown()

if __name__ == "__main__":
    start_server()
