from typing import Any, Dict, Optional

from picamera2 import Picamera2  # type: ignore
import cv2  # type: ignore


class Camera:
    """Picamera2 단일 경로. 라즈베리파이5 전용 포트 카메라 전제."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.picam: Optional["Picamera2"] = None
        self._open()

    def _open(self) -> None:
        cam_cfg = self.config.get("camera", {})
        width = int(cam_cfg.get("width", 640))
        height = int(cam_cfg.get("height", 480))

        picam = Picamera2()
        cfg = picam.create_preview_configuration(main={"size": (width, height)})
        picam.configure(cfg)
        picam.start()
        self.picam = picam

    def read_jpeg(self) -> Optional[bytes]:
        assert self.picam is not None
        arr = self.picam.capture_array()
        ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return buf.tobytes() if ok else None

    def read_frame_bgr(self):
        assert self.picam is not None
        arr = self.picam.capture_array()
        # Picamera2는 기본 RGB를 반환하는 경우가 많음. OpenCV용 BGR로 변환.
        if arr.shape[-1] == 3:
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return arr

    def __del__(self) -> None:  # pragma: no cover
        try:
            if self.picam is not None:
                self.picam.stop()
        except Exception:
            pass


