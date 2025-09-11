const express = require('express');
const { spawn } = require('child_process');
const app = express();
const PORT = 8080;

// 정적 파일 서빙
app.use(express.static('.'));

// WebRTC 시그널링을 위한 간단한 서버
app.post('/whep', (req, res) => {
  // GStreamer로 비디오 스트림 생성
  const gst = spawn('gst-launch-1.0', [
    'libcamerasrc',
    '!', 'video/x-raw,width=640,height=480,framerate=15/1',
    '!', 'videoconvert',
    '!', 'vp8enc',
    '!', 'rtpvp8pay',
    '!', 'udpsink', 'host=127.0.0.1', 'port=5004'
  ]);

  // 간단한 SDP 응답 (실제로는 더 복잡한 WebRTC 시그널링 필요)
  const sdp = `v=0
o=- 0 0 IN IP4 127.0.0.1
s=GStreamer WebRTC
t=0 0
m=video 5004 RTP/AVP 96
c=IN IP4 127.0.0.1
a=rtpmap:96 VP8/90000`;

  res.set('Content-Type', 'application/sdp');
  res.send(sdp);
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`WebRTC server running on http://0.0.0.0:${PORT}`);
});
