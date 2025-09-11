import io
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


class SimulatedCamera:
    """간단한 프레임 생성기로 MJPEG용 JPEG 바이트를 반환."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        sim_cfg = config.get("simulate", {})
        self.width = int(sim_cfg.get("width", 640))
        self.height = int(sim_cfg.get("height", 360))
        self.tick_ms = int(sim_cfg.get("tick_ms", 200))
        self.counter = 0

    def read_jpeg(self) -> Optional[bytes]:
        if Image is None:
            return None
        self.counter += 1
        img = Image.new("RGB", (self.width, self.height), (12, 16, 38))
        draw = ImageDraw.Draw(img)
        text = f"Sim #{self.counter}"
        draw.rectangle((20, 20, self.width - 20, self.height - 20), outline=(108, 196, 255), width=3)
        draw.text((30, 30), text, fill=(234, 238, 251))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()


