from typing import Any, Dict, Optional

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore


class OpenCVCamera:
    """라즈베리파이 카메라 또는 USB 카메라를 OpenCV로 읽어 MJPEG 프레임을 제공."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cap: Optional["cv2.VideoCapture"] = None
        self._open()

    def _open(self) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV(cv2)가 설치되어 있지 않습니다. 'pip install opencv-python' 필요")
        cam_cfg = self.config.get("camera", {})
        index = int(cam_cfg.get("index", 0))
        width = int(cam_cfg.get("width", 640))
        height = int(cam_cfg.get("height", 480))
        fps = int(cam_cfg.get("fps", 30))

        # V4L2 백엔드 사용(라즈베리파이 권장) + MJPG FOURCC 설정
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass
        self.cap = cap

    def read_jpeg(self) -> Optional[bytes]:
        assert self.cap is not None
        ok, frame = self.cap.read()
        if not ok:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return None
        return buf.tobytes()

    def __del__(self) -> None:  # pragma: no cover
        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass


