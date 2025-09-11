#!/usr/bin/env python3
import os
import signal
import subprocess
from pathlib import Path
from contextlib import suppress

from quart import Quart, send_from_directory

# ===== 설정 =====
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000

PI_WEBRTC_BIN = "./pi-webrtc"
PI_WEBRTC_PORT = 8080

WIDTH, HEIGHT, FPS = 640, 480, 24
EXTRA_FLAGS = "--use-whep --no-audio"

BASE_DIR = Path(__file__).parent

# =================

app = Quart(__name__, static_url_path="", static_folder=str(BASE_DIR))
webrtc_proc: subprocess.Popen | None = None


def start_pi_webrtc():
    global webrtc_proc
    if webrtc_proc and webrtc_proc.poll() is None:
        return
    cmd = [
        PI_WEBRTC_BIN,
        f"--camera=libcamera:0",
        f"--width={WIDTH}",
        f"--height={HEIGHT}",
        f"--fps={FPS}",
        f"--http-port={PI_WEBRTC_PORT}",
        *EXTRA_FLAGS.split()
    ]
    webrtc_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    print("[main.py] pi-webrtc started:", " ".join(cmd), flush=True)


def stop_pi_webrtc():
    global webrtc_proc
    if webrtc_proc and webrtc_proc.poll() is None:
        with suppress(Exception):
            os.killpg(os.getpgid(webrtc_proc.pid), signal.SIGTERM)
    webrtc_proc = None
    print("[main.py] pi-webrtc stopped", flush=True)


@app.before_serving
async def on_start():
    start_pi_webrtc()


@app.after_serving
async def on_stop():
    stop_pi_webrtc()


# --- 정적 파일 라우트 ---
@app.route("/")
async def index():
    return await send_from_directory(BASE_DIR, "index.html")


@app.route("/app.js")
async def js():
    return await send_from_directory(BASE_DIR, "app.js")


@app.route("/style.css")
async def css():
    return await send_from_directory(BASE_DIR, "style.css")


if __name__ == "__main__":
    try:
        app.run(host=WEB_HOST, port=WEB_PORT)
    except KeyboardInterrupt:
        pass
    finally:
        stop_pi_webrtc()
