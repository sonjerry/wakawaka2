from typing import Any, Dict, Optional

try:
    from picamera2 import Picamera2  # type: ignore
except Exception:  # pragma: no cover
    Picamera2 = None  # type: ignore

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore


class Camera:
    """라즈베리파이5 전용 포트 카메라: Picamera2 우선, 불가 시 OpenCV 폴백."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._mode: str = ""
        self._picam: Optional["Picamera2"] = None
        self._cap: Optional["cv2.VideoCapture"] = None
        self._open()

    def _open(self) -> None:
        cam_cfg = self.config.get("camera", {})
        width = int(cam_cfg.get("width", 640))
        height = int(cam_cfg.get("height", 480))
        fps = int(cam_cfg.get("fps", 30))

        # 1) Picamera2 (권장: Pi5 libcamera 스택)
        if Picamera2 is not None:
            try:
                picam = Picamera2()
                cfg = picam.create_preview_configuration(main={"size": (width, height)})
                picam.configure(cfg)
                picam.start()
                self._picam = picam
                self._mode = "picamera2"
                return
            except Exception:
                self._picam = None

        # 2) OpenCV V4L2 폴백
        if cv2 is None:
            raise RuntimeError("카메라 초기화 실패: Picamera2 또는 OpenCV 중 하나가 필요합니다.")
        index = int(cam_cfg.get("index", 0))
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass
        self._cap = cap
        self._mode = "opencv"

    def read_jpeg(self) -> Optional[bytes]:
        # Picamera2 경로: numpy 배열을 얻어 JPEG 인코딩
        if self._mode == "picamera2" and self._picam is not None:
            try:
                arr = self._picam.capture_array()
                if cv2 is not None:
                    ok, buf = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    return buf.tobytes() if ok else None
                if Image is not None:
                    from PIL import Image as PILImage  # type: ignore
                    import io

                    img = PILImage.fromarray(arr)
                    bio = io.BytesIO()
                    img.save(bio, format="JPEG", quality=80)
                    return bio.getvalue()
                return None
            except Exception:
                return None

        # OpenCV 경로
        if self._mode == "opencv" and self._cap is not None and cv2 is not None:
            ok, frame = self._cap.read()
            if not ok:
                return None
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            return buf.tobytes() if ok else None

        return None

    def __del__(self) -> None:  # pragma: no cover
        try:
            if self._picam is not None:
                self._picam.stop()
        except Exception:
            pass
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass


