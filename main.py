#!/usr/bin/env python3
import os
from pathlib import Path
from flask import Flask, request, send_from_directory, Response
import requests

# ===== 설정 =====
BASE_DIR = Path(__file__).parent.resolve()
WEB_HOST = "0.0.0.0"
WEB_PORT = int(os.environ.get("WEB_PORT", "8000"))
PI_WEBRTC_PORT = int(os.environ.get("PI_WEBRTC_PORT", "8080"))
WHEP_UPSTREAM = f"http://127.0.0.1:{PI_WEBRTC_PORT}/whep"
# ===============

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.get("/app.js")
def js():
    return send_from_directory(BASE_DIR, "app.js")

@app.get("/style.css")
def css():
    return send_from_directory(BASE_DIR, "style.css")

# --- 브라우저는 동일 출처 /whep 로 POST (Flask가 pi-webrtc 로 중계) ---
@app.post("/whep")
def whep_proxy():
    sdp = request.get_data()  # 순수 SDP 텍스트
    try:
        r = requests.post(
            WHEP_UPSTREAM,
            data=sdp,
            headers={"Content-Type": "application/sdp"},
            timeout=10,
        )
    except requests.RequestException as e:
        return Response(f"upstream error: {e}", status=502, mimetype="text/plain")

    # pi-webrtc 가 돌려준 answer SDP 그대로 반환 + Location 헤더도 전달
    headers = {}
    loc = r.headers.get("Location")
    if loc:
        headers["Location"] = loc
    return Response(r.text, status=r.status_code, headers=headers, mimetype="application/sdp")

if __name__ == "__main__":
    app.run(host=WEB_HOST, port=WEB_PORT)
