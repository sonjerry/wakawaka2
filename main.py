import asyncio
from quart import Quart, request, jsonify
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

app = Quart(__name__)
pcs = set()

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

    player = MediaPlayer("rpicam-vid --inline -o - --width 640 --height 480")
    pc.addTrack(player.video)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)