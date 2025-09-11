import time
from typing import Generator

from flask import Flask, Response, jsonify, request, send_from_directory

from config import load_config
from hardware import Camera
from webrtc import CameraVideoTrack
from aiortc import RTCPeerConnection  # type: ignore
from aiortc.contrib.signaling import BYE  # type: ignore


def create_app() -> Flask:
    config = load_config()
    camera = Camera(config=config)

    app = Flask(
        __name__,
        static_folder=".",
        static_url_path="",
    )

    def mjpeg_generator() -> Generator[bytes, None, None]:
        boundary = b"--frame"
        while True:
            frame = camera.read_jpeg()
            if frame is None:
                time.sleep(0.01)
                continue
            yield boundary + b"\r\n" + b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    @app.get("/")
    def root() -> Response:
        return send_from_directory(".", "index.html")

    # MJPEG는 유지하지 않고, WebRTC 시그널링 엔드포인트만 노출
    @app.post("/offer")
    def webrtc_offer() -> Response:
        offer = request.get_json(force=True)
        pc = RTCPeerConnection()
        pc.addTrack(CameraVideoTrack(config))

        async def run() -> Dict[str, str]:
            await pc.setRemoteDescription(offer)
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(run())
        return jsonify(result)

    return app


def run() -> None:
    app = create_app()
    cfg = load_config()
    host = cfg.get("stream", {}).get("host", "0.0.0.0")
    port = int(cfg.get("stream", {}).get("port", 8000))
    debug = bool(cfg.get("stream", {}).get("debug", False))
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run()


