import time
from typing import Generator, Dict

from quart import Quart, Response, jsonify, request, send_from_directory

from config import load_config
from hardware import Camera
from webrtc import CameraVideoTrack
from aiortc import RTCPeerConnection  # type: ignore


def create_app() -> Quart:
    config = load_config()
    camera = Camera(config=config)

    app = Quart(
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
    async def root() -> Response:
        return await send_from_directory(".", "index.html")

    # MJPEG는 유지하지 않고, WebRTC 시그널링 엔드포인트만 노출
    @app.post("/offer")
    async def webrtc_offer() -> Response:
        offer = await request.get_json()
        pc = RTCPeerConnection()
        pc.addTrack(CameraVideoTrack(camera))
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

    return app


def run() -> None:
    app = create_app()
    cfg = load_config()
    host = cfg.get("stream", {}).get("host", "0.0.0.0")
    port = int(cfg.get("stream", {}).get("port", 8000))
    debug = bool(cfg.get("stream", {}).get("debug", False))
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run()


