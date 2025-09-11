RC카 뷰어

사용법
1) 라즈베리파이에서 최소 지연시간 스트리밍 실행
   - `chmod +x run_low_latency_stream.sh`
   - `./run_low_latency_stream.sh` 실행

2) Flask 서버 실행
   - `py -m pip install -r requirements.txt`
   - `py app.py`

3) 브라우저에서 `http://localhost:8000` 접속
   - 자동으로 라즈베리파이(100.84.162.124)에 연결
   - 연결 실패 시 2초마다 재시도

참고: pi-webrtc 크래시 문제로 인해 libcamera-vid 기반 최소 지연시간 스트리밍을 사용합니다.
