import time
from typing import Generator, Dict

from quart import Quart, Response, jsonify, request, send_from_directory
from aiortc import RTCPeerConnection, RTCSessionDescription  # type: ignore

from config import load_config
from hardware import Camera
from webrtc import CameraVideoTrack

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

    @app.post("/offer")
    async def webrtc_offer() -> Response:
        try:
            offer = await request.get_json()
            if not offer or "sdp" not in offer or "type" not in offer:
                return jsonify({"error": "Invalid offer: 'sdp' or 'type' missing"}), 400

            # RTCSessionDescription에 sdp와 type을 명시적으로 전달
            sdp = offer["sdp"]
            offer_type = offer["type"]
            if not isinstance(sdp, str) or not isinstance(offer_type, str):
                return jsonify({"error": "Invalid offer: 'sdp' and 'type' must be strings"}), 400

            pc = RTCPeerConnection()
            pc.addTrack(CameraVideoTrack(camera))
            await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=offer_type))
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})
        except Exception as e:
            return jsonify({"error": f"Failed to process offer: {str(e)}"}), 500

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