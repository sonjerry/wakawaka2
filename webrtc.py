import asyncio
import time
from typing import Any, Dict, Optional

import av  # type: ignore
from aiortc import MediaStreamTrack  # type: ignore
from aiortc.mediastreams import VideoStreamTrack  # type: ignore

from hardware import Camera


class CameraVideoTrack(VideoStreamTrack):
    """Picamera2에서 프레임을 가져와 WebRTC 트랙으로 제공."""

    kind = "video"

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.camera = Camera(config=config)
        self.last_ts = time.time()

    async def recv(self) -> MediaStreamTrack:
        # 간단한 FPS 제어(최대 ~30fps)
        await asyncio.sleep(0)
        jpeg = self.camera.read_jpeg()
        if jpeg is None:
            await asyncio.sleep(0.01)
            # 빈 프레임 회피: 이전 타임스탬프 유지
            raise av.AVError(-1, "no frame")

        # JPEG 디코드하여 VideoFrame으로 변환
        packet = av.Packet(jpeg)
        with av.open(packet, format="mjpeg") as container:  # type: ignore
            for frame in container.decode(video=0):
                frame.pts = None
                frame.time_base = None
                return frame

        raise av.AVError(-1, "decode failed")


