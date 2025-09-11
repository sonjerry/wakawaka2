WHEP(WebRTC-HTTP Egress Protocol) 뷰어

사용법
1) 라즈베리파이에서 WHEP 서버 실행 (예시)
   - `./run_stream.sh` 실행 후 `http://<PI_IP>:8080/whep` 노출

2) Flask 서버로 실행 (정적 서빙 + 선택적 WHEP 프록시)
   - 파워쉘: `cd C:\Users\leefa\Desktop\WakaWaka`
   - 1회 설치: `py -m pip install -r requirements.txt`
   - 실행: `py app.py`  (기본 포트 8000, 환경변수 HOST/PORT로 변경 가능)

3) 브라우저 열기
   - `http://localhost:8000` 접속 (정적 서빙)
   - 입력창에 라즈베리파이 WHEP URL 입력: `http://<PI_IP>:8080/whep`
   - Tailscale 사용 시: `http://<tailscale_ip>:8080/whep` 또는 `http://<tailscale_name>:8080/whep`

쿼리 파라미터(자동 연결)
   - 예: `http://localhost:8000/?whep=http://<PI_IP>:8080/whep&autoplay=1`

비고
   - 본 페이지는 수신 전용(영상만)입니다. 오디오, 데이터채널 미사용.
   - 단순화를 위해 non-trickle ICE를 사용합니다.
   - CORS 회피가 필요하면 다음 중 하나 사용:
     1) 브라우저에서 직접 PI에 연결(같은 네트워크/허용된 CORS)
     2) Flask 프록시 사용: WHEP URL 대신 `http://localhost:8000/whep-proxy?target=http://<PI_IP>:8080/whep`
        - 최초 POST 응답의 Location 헤더가 프록시로 재작성되어 DELETE도 동일 출처로 동작합니다.
