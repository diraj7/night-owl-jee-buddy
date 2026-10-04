"""Night Owl JEE Buddy - a tiny local server that sits between a web page and Ollama.

Only the Python standard library is used, so there is nothing to pip install.
Run:  python server.py
"""
import json
import os
import random
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "qwen3:8b")
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:7b")
PORT = int(os.environ.get("PORT", "8000"))

ROOT = Path(__file__).parent
INDEX = ROOT / "static" / "index.html"
LOG = ROOT / "doubts.json"
LOCK = threading.Lock()

SYSTEM = (
    "You are a patient, friendly JEE Main/Advanced tutor talking to a student "
    "who studies late at night. Explain step by step. Structure every answer as: "
    "1) What the question is really asking, 2) The concept or formula needed, "
    "3) Worked steps, 4) Final answer, 5) One common trap to avoid. "
    "Write maths in plain text or unicode (x^2, sqrt(3), ∫, π). Never use LaTeX. "
    "Be concise. If a photo is unclear, say what you could not read."
)


def load_doubts():
    with LOCK:
        if LOG.exists():
            try:
                return json.loads(LOG.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
        return []


def save_doubts(items):
    with LOCK:
        LOG.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def open_ollama(body, think_off=False, timeout=300):
    """Call Ollama /api/chat. Qwen3 gets thinking switched off for speed."""

    def go(b):
        req = urllib.request.Request(
            OLLAMA + "/api/chat",
            json.dumps(b).encode(),
            {"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=timeout)

    if think_off:
        try:
            return go({**body, "think": False})
        except urllib.error.HTTPError as e:
            if e.code != 400:  # model does not support the think flag -> retry plain
                raise
    return go(body)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    # ---------- helpers ----------
    def read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- routes ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            data = INDEX.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/doubts":
            self.send_json(list(reversed(load_doubts())))
        else:
            self.send_error(404)

    def do_POST(self):
        d = self.read_json()
        if self.path == "/api/chat":
            self.chat(d)
        elif self.path == "/api/quiz":
            self.quiz(d)
        elif self.path == "/api/doubts/mastered":
            items = load_doubts()
            for it in items:
                if it["id"] == d.get("id"):
                    it["mastered"] = True
            save_doubts(items)
            self.send_json({"ok": True})
        else:
            self.send_error(404)

    # ---------- features ----------
    def chat(self, d):
        q = (d.get("question") or "").strip()
        img = d.get("image")
        subject = d.get("subject", "")
        model = VISION_MODEL if img else TEXT_MODEL
        text = f"[{subject}] {q}" if q else f"[{subject}] Solve the problem in the photo."
        user = {"role": "user", "content": text}
        if img:
            user["images"] = [img]
        body = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM}, user],
            "stream": True,
            "options": {"temperature": 0.3},
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        answer = []
        try:
            resp = open_ollama(body, think_off=not img)
            for line in resp:
                if not line.strip():
                    continue
                t = json.loads(line).get("message", {}).get("content", "")
                if t:
                    answer.append(t)
                    self.wfile.write(t.encode())
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except (urllib.error.URLError, OSError) as e:
            msg = (
                f"Could not reach Ollama at {OLLAMA} ({e}). "
                f"Is it running, and did you run: ollama pull {model} ?"
            )
            try:
                self.wfile.write(msg.encode())
            except OSError:
                pass
            return
        full = "".join(answer).strip()
        if full:
            items = load_doubts()
            items.append(
                {
                    "id": int(time.time() * 1000),
                    "ts": time.strftime("%Y-%m-%d %H:%M"),
                    "subject": subject,
                    "question": q or "(photo question)",
                    "answer": full,
                    "photo": bool(img),
                    "mastered": False,
                }
            )
            save_doubts(items)

    def quiz(self, d):
        items = [i for i in load_doubts() if not i.get("mastered")]
        if d.get("id"):
            items = [i for i in items if i["id"] == d["id"]] or items
        if not items:
            return self.send_json({"error": "No doubts to practise yet. Ask something first!"})
        item = random.choice(items)
        prompt = (
            "A JEE student had this doubt:\n"
            f"Subject: {item['subject']}\nQuestion: {item['question']}\n\n"
            "Write ONE new, similar practice problem at JEE Main level that tests the same "
            "concept with different numbers or a small twist. Plain text maths, no LaTeX. "
            'Reply as JSON: {"problem": "...", "answer": "short worked answer"}'
        )
        body = {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7},
        }
        try:
            resp = open_ollama(body, think_off=True)
            content = json.loads(resp.read())["message"]["content"]
            out = json.loads(content)
            self.send_json(
                {
                    "id": item["id"],
                    "source": item["question"],
                    "problem": str(out.get("problem", "")),
                    "answer": str(out.get("answer", "")),
                }
            )
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as e:
            self.send_json({"error": f"Could not make a practice problem: {e}"})


if __name__ == "__main__":
    print(f"Text model:   {TEXT_MODEL}\nVision model: {VISION_MODEL}")
    print(f"On this laptop: http://localhost:{PORT}")
    print(f"On your phone (same Wi-Fi): http://{lan_ip()}:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
