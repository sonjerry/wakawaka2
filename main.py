#!/usr/bin/env python3
import asyncio
import json
import os
import signal
import subprocess
from pathlib import Path

from quart import Quart, request, send_from_directory
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer

# ====== 기본 설정 ======
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8000))

# rpicam-vid가 쏠 로컬 UDP 주소 (FFmpeg/aiortc가 수신)
UDP_URL = "udp://127.0.0.1:5000"

# rpicam-vid 실행 파라미터: 480p/24fps/H.264
RPICAM_CMD = [
    "rpicam-vid",
    "-t", "0",                 # 무기한
    "--width", "640",
    "--height", "480",
    "--framerate", "24",
    "--codec", "h264",
    "--profile", "baseline",
    "--inline",                # IDR 주기적 포함 (네트워크 스트림용)
    "-o", f"{UDP_URL}"
]

# FFmpeg 옵션 (aiortc MediaPlayer에 전달)
FFMPEG_OPTS = {
    "fflags": "nobuffer",
    "probesize": "32",
    "analyzeduration": "0",
    # UDP 수신 버퍼가 꽉 차도 죽지 않도록 (선택)
    "fifo_size": "5000000",
    "reorder_queue_size": "0",
}

app = Quart(__name__, static_url_path="", static_folder=str(Path(__file__).parent))

rpicam_proc: subprocess.Popen | None = None
player: MediaPlayer | None = None
pcs: set[RTCPeerConnection] = set()


def start_rpicam():
    global rpicam_proc
    if rpicam_proc is None or rpicam_proc.poll() is not None:
        rpicam_proc = subprocess.Popen(
            RPICAM_CMD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid  # 그룹으로 실행해 종료 처리 용이
        )
        print("[rpicam-vid] started:", " ".join(RPICAM_CMD))


def stop_rpicam():
    global rpicam_proc
    if rpicam_proc and rpicam_proc.poll() is None:
        try:
            os.killpg(os.getpgid(rpicam_proc.pid), signal.SIGTERM)
        except Exception:
            pass
    rpicam_proc = None
    print("[rpicam-vid] stopped")


async def get_player():
    """
    UDP로 들어오는 H.264를 FFmpeg로 읽어오는 MediaPlayer (영상만).
    """
    global player
    if player is None:
        # aiortc는 내부적으로 ffmpeg를 사용하므로, 시스템에 ffmpeg 설치 필요.
        player = MediaPlayer(
            UDP_URL,
            format="h264",   # 입력 코덱 힌트
            options=FFMPEG_OPTS
        )
    return player


@app.route("/")
async def index():
    return await send_from_directory(app.static_folder, "index.html")


@app.route("/app.js")
async def js():
    return await send_from_directory(app.static_folder, "app.js")


@app.route("/style.css")
async def css():
    return await send_from_directory(app.static_folder, "style.css")


@app.post("/offer")
async def offer():
    """
    브라우저가 보낸 SDP offer를 받아 answer를 돌려줍니다.
    서버는 rpicam-vid로부터 받은 영상을 단방향으로 송출.
    """
    params = await request.get_json()
    if not params or "sdp" not in params or "type" not in params:
        return {"error": "invalid SDP"}, 400

    # rpicam-vid 보장
    start_rpicam()
    vid_player = await get_player()

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_state_change():
        print("PC state:", pc.connectionState)
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            pcs.discard(pc)
            # 연결이 모두 끊기면 rpicam도 정지(선택)
            if not pcs:
                stop_rpicam()

    # 브라우저 offer 설정
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    await pc.setRemoteDescription(offer)

    # 비디오 트랙만 추가 (단방향)
    if vid_player.video:
        pc.addTrack(vid_player.video)

    # answer 생성
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }


@app.before_serving
async def startup():
    # 서버 시작시 카메라는 lazy-start (첫 offer 때 시작). 원하면 여기서 start_rpicam() 호출해도 됨.
    print("[server] ready at http://{}:{}/".format(HOST, PORT))


@app.after_serving
async def shutdown():
    # 서버 종료시 정리
    for pc in pcs.copy():
        await pc.close()
    pcs.clear()
    if player:
        await player.stop()
    stop_rpicam()


if __name__ == "__main__":
    try:
        # Quart 0.19+ run
        app.run(host=HOST, port=PORT, loop=asyncio.get_event_loop())
    except TypeError:
        # 일부 버전 호환
        app.run(host=HOST, port=PORT)
