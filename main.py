import asyncio
from quart import Quart, request, jsonify, send_from_directory
from quart_cors import cors
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
import os

app = Quart(__name__)
app = cors(app, allow_origin="*")
pcs = set()

@app.route('/')
async def index():
    return await send_from_directory('static', 'index.html')

@app.route('/<path:path>')
async def static_files(path):
    return await send_from_directory('static', path)

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

    # MediaPlayer 설정: h264 형식으로 출력
    player = MediaPlayer(
        file=None,
        format='pipe',
        options={
            'video_size': '640x480',
            'framerate': '30'
        },
        args=['rpicam-vid', '--inline', '-o', '-', '--width', '640', '--height', '480', '--libav-format', 'h264']
    )
    pc.addTrack(player.video)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)