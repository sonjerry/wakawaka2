import subprocess
import numpy as np
import cv2
from typing import Any, Dict, Optional


class Camera:
    """rpicam-vid를 사용한 카메라 프레임 캡처. Raspberry Pi 5와 libcamera 기반."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.width: int = 0
        self.height: int = 0
        self._open()

    def _open(self) -> None:
        """rpicam-vid 실행 및 초기화."""
        cam_cfg = self.config.get("camera", {})
        self.width = int(cam_cfg.get("width", 640))
        self.height = int(cam_cfg.get("height", 480))
        fps = int(cam_cfg.get("fps", 30))

        # rpicam-vid 명령어: raw RGB 스트림 출력
        cmd = [
            "rpicam-vid",
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(fps),
            "-t", "0",  # 무제한 실행
            "--inline",  # 헤더 포함
            "--nopreview",  # 미리보기 비활성화 (Headless 환경)
            "-o", "-",  # stdout으로 출력
            "--codec", "rgb"  # raw RGB 포맷
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
        except Exception as e:
            print(f"Failed to start rpicam-vid: {e}")
            self.process = None

    def read_frame_bgr(self) -> Optional[np.ndarray]:
        """rpicam-vid에서 프레임 읽기 및 BGR 변환."""
        if self.process is None or self.process.stdout is None:
            return None

        try:
            # RGB 프레임 크기: width * height * 3 (RGB)
            frame_size = self.width * self.height * 3
            raw_data = self.process.stdout.read(frame_size)
            if not raw_data or len(raw_data) != frame_size:
                return None

            # raw RGB 데이터를 numpy 배열로 변환
            frame = np.frombuffer(raw_data, dtype=np.uint8)
            frame = frame.reshape((self.height, self.width, 3))

            # RGB에서 BGR로 변환 (OpenCV 및 WebRTC 호환)
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return bgr
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None

    def __del__(self) -> None:
        """프로세스 정리."""
        try:
            if self.process is not None:
                self.process.terminate()
                self.process.wait(timeout=2)
        except Exception:
            pass