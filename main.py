import argparse
import time
from typing import Generator, Literal

from flask import Flask, Response, send_from_directory

from config import load_config
from hardware import OpenCVCamera
from simulate import SimulatedCamera


def create_app(mode: Literal["hardware", "simulate"]) -> Flask:
    config = load_config()

    if mode == "hardware":
        camera = OpenCVCamera(config=config)
    else:
        camera = SimulatedCamera(config=config)

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

    @app.get("/stream.mjpg")
    def stream() -> Response:
        return Response(
            mjpeg_generator(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    return app


def run(mode: Literal["hardware", "simulate"]) -> None:
    app = create_app(mode)
    cfg = load_config()
    host = cfg.get("stream", {}).get("host", "0.0.0.0")
    port = int(cfg.get("stream", {}).get("port", 8000))
    debug = bool(cfg.get("stream", {}).get("debug", False))
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WakaWaka entrypoint")
    parser.add_argument(
        "--mode",
        choices=["hardware", "simulate"],
        default="simulate",
        help="실행 모드 선택 (hardware | simulate)",
    )
    args = parser.parse_args()
    run(mode=args.mode)  # type: ignore[arg-type]


