import asyncio
import time
from typing import Any, Dict, Optional

import av  # type: ignore
from aiortc import MediaStreamTrack  # type: ignore
from aiortc.mediastreams import VideoStreamTrack  # type: ignore

from hardware import Camera


_shared_camera: Optional[Camera] = None


class CameraVideoTrack(VideoStreamTrack):
    """Picamera2에서 프레임을 가져와 WebRTC 트랙으로 제공."""

    kind = "video"

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        global _shared_camera
        if _shared_camera is None:
            _shared_camera = Camera(config=config)
        self.camera = _shared_camera
        self.last_ts = time.time()

    async def recv(self) -> MediaStreamTrack:
        # 간단한 FPS 제어(최대 ~30fps)
        await asyncio.sleep(0)
        # BGR ndarray를 직접 VideoFrame으로 변환 (JPEG 디코드 제거, 간결/저지연)
        import numpy as np  # type: ignore

        bgr = self.camera.read_frame_bgr()
        if bgr is None:
            await asyncio.sleep(0.01)
            raise av.AVError(-1, "no frame")

        frame = av.VideoFrame.from_ndarray(bgr, format="bgr24")
        frame.pts = None
        frame.time_base = None
        return frame


