import time
from typing import Generator

from flask import Flask, Response, send_from_directory

from config import load_config
from hardware import Camera


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

    @app.get("/stream.mjpg")
    def stream() -> Response:
        return Response(
            mjpeg_generator(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

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


