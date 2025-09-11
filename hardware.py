import subprocess
import numpy as np
import cv2
import logging
from typing import Any, Dict, Optional

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

        # YUV420은 width와 height가 2의 배수여야 함
        if self.width % 2 != 0 or self.height % 2 != 0:
            logger.warning(f"Adjusting width/height to be even: {self.width}x{self.height}")
            self.width = self.width - (self.width % 2)
            self.height = self.height - (self.height % 2)

        # rpicam-vid 명령어: raw YUV420 스트림 출력
        cmd = [
            "rpicam-vid",
            "--verbose",  # 디버깅 로그 활성화
            "--width", str(self.width),
            "--height", str(self.height),
            "--framerate", str(fps),
            "-t", "0",  # 무제한 실행
            "--inline",  # 헤더 포함
            "--nopreview",  # 미리보기 비활성화
            "-o", "-",  # stdout으로 출력
            "--codec", "yuv420"  # raw YUV420 포맷
        ]

        logger.debug(f"Starting rpicam-vid with command: {' '.join(cmd)}")
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            # stderr 로그 비동기적으로 읽기
            stderr_data = self.process.stderr.read1(1024).decode('utf-8', errors='ignore')
            if stderr_data:
                logger.debug(f"rpicam-vid stderr: {stderr_data}")
        except Exception as e:
            logger.error(f"Failed to start rpicam-vid: {e}")
            self.process = None

    def read_frame_bgr(self) -> Optional[np.ndarray]:
        """rpicam-vid에서 YUV420 프레임 읽기 및 BGR 변환."""
        if self.process is None or self.process.stdout is None:
            logger.error("rpicam-vid process not running")
            return None

        try:
            # YUV420 프레임 크기: width * height * 1.5 (Y + U/4 + V/4)
            frame_size = int(self.width * self.height * 1.5)
            logger.debug(f"Reading frame, expected size: {frame_size} bytes")
            raw_data = self.process.stdout.read(frame_size)
            if not raw_data or len(raw_data) != frame_size:
                logger.warning(f"Invalid frame data: got {len(raw_data)} bytes, expected {frame_size}")
                return None

            # YUV420 데이터를 numpy 배열로 변환
            yuv = np.frombuffer(raw_data, dtype=np.uint8)
            yuv = yuv.reshape((int(self.height * 1.5), self.width))

            # YUV420에서 BGR로 변환
            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV420p2BGR)
            logger.debug(f"Frame shape: {bgr.shape}")
            return bgr
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def __del__(self) -> None:
        """프로세스 정리."""
        try:
            if self.process is not None:
                logger.debug("Terminating rpicam-vid process")
                self.process.terminate()
                self.process.wait(timeout=2)
        except Exception as e:
            logger.error(f"Error terminating process: {e}")