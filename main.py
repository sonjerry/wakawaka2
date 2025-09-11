import asyncio
from quart import Quart, request, jsonify
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
from picamera2 import Picamera2
from av import VideoFrame
import cv2

app = Quart(__name__)
pcs = set()

class PiVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_video_configuration(main={"size": (640, 480)}))
        self.camera.start()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.camera.capture_array("main")
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

@app.route('/offer', methods=['POST'])
async def offer():
    params = await request.get_json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(offer)
    pc.addTrack(PiVideoTrack())

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)