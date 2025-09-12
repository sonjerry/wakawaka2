# main.py
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- 애플리케이션 상태 관리 ---
# FastAPI의 app.state를 사용하여 애플리케이션의 생명주기 동안 상태를 안전하게 관리합니다.
app.state.controller = None  # 현재 연결된 웹소켓 클라이언트
app.state.tick_task = None  # 메인 제어 루프 태스크

# --- 클라이언트 입력 상태 ---
# 웹소켓을 통해 들어온 최신 입력값을 저장합니다.
## 제어 입력 상태 제거 (하드웨어 제어 삭제)

def read_index_html() -> str:
    """index.html 파일을 찾아 비디오 소스를 설정하여 반환합니다."""
    html_path = BASE_DIR / "index.html"
    if not html_path.exists():
        logging.error("index.html 파일을 찾을 수 없습니다!")
        return "<h1>Error: index.html not found.</h1>"
    
    txt = html_path.read_text(encoding="utf-8")
    # config 의존성 제거: 환경변수 또는 기본값 사용
    video_src = "about:blank"
    return txt.replace("%%VIDEO_SRC%%", video_src)

@app.get("/")
async def root():
    return HTMLResponse(read_index_html())

@app.get("/health")
async def health():
    return PlainTextResponse("ok")

# 하드웨어 상태 엔드포인트 제거

## 브레이크 판단 로직 제거


async def tick_loop():
    """네트워크 RTT 확인용 heartbeat 및 단순 상태 전송 루프"""
    dt = 0.05
    while True:
        controller: WebSocket = app.state.controller
        if controller:
            try:
                await controller.send_text(json.dumps({
                    "ts": time.time()
                }))
            except WebSocketDisconnect:
                app.state.controller = None
                logging.info("데이터 전송 중 클라이언트 연결 끊김 감지.")
            except Exception as e:
                app.state.controller = None
                logging.warning(f"데이터 전송 중 오류 발생: {e}")
        await asyncio.sleep(dt)

@app.websocket("/ws")
async def ws_handler(ws: WebSocket):
    logging.info("🔌 웹소켓 연결 요청 수신")
    await ws.accept()
    logging.info("✅ 웹소켓 연결 승인 완료")
    
    # 새로운 클라이언트가 연결되면 기존 연결은 종료 (싱글 컨트롤러 정책)
    if app.state.controller:
        logging.warning("새로운 클라이언트 접속, 기존 연결을 종료합니다.")
        try:
            await app.state.controller.close()
        except Exception:
            pass # 이미 닫혔을 수 있음
    app.state.controller = ws
    logging.info("🎮 웹소켓 클라이언트가 연결되었습니다.")
    
    try:
        while True:
            text = await ws.receive_text()
            data = json.loads(text)

            # RTT 측정을 위한 ping/pong
            if "ping" in data:
                await ws.send_text(json.dumps({"pong": data["ping"]}))
                continue

            # 핑/퐁 외의 입력은 무시
                        
    except WebSocketDisconnect:
        logging.info("클라이언트 연결이 끊어졌습니다.")
        if app.state.controller is ws:
            app.state.controller = None
        # 연결 종료 시 추가 동작 없음 (하드웨어 없음)

## 엔진/변속기 관련 보조 로직 제거

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 호출되는 생명주기 관리 함수"""
    logging.info("애플리케이션 시작...")
    # 하드웨어 초기화 제거

    # 메인 제어 루프를 백그라운드 태스크로 시작
    app.state.tick_task = asyncio.create_task(tick_loop())
    
    try:
        yield
    finally:
        logging.info("애플리케이션 종료 절차 시작...")
        if app.state.tick_task:
            app.state.tick_task.cancel()
            try:
                await app.state.tick_task
            except asyncio.CancelledError:
                logging.info("Tick 루프가 정상적으로 취소되었습니다.")
        
        # 하드웨어 종료 절차 제거

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    logging.info("서버를 시작합니다. http://0.0.0.0:8000 에서 접속하세요.")
    uvicorn.run(app, host="0.0.0.0", port=8000)