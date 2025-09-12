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

import config
import hardware
from automission import VirtualTransmission

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- 애플리케이션 상태 관리 ---
# FastAPI의 app.state를 사용하여 애플리케이션의 생명주기 동안 상태를 안전하게 관리합니다.
app.state.controller = None  # 현재 연결된 웹소켓 클라이언트
app.state.transmission = VirtualTransmission()  # 가상 변속기 인스턴스
app.state.prev_engine_running = False  # 이전 tick의 엔진 상태
app.state.tick_task = None  # 메인 제어 루프 태스크

# --- 클라이언트 입력 상태 ---
# 웹소켓을 통해 들어온 최신 입력값을 저장합니다.
app.state.requested_gear = None
app.state.axis = 0.0
app.state.steer_dir = 0

def read_index_html() -> str:
    """index.html 파일을 찾아 비디오 소스를 설정하여 반환합니다."""
    html_path = BASE_DIR / "index.html"
    if not html_path.exists():
        logging.error("index.html 파일을 찾을 수 없습니다!")
        return "<h1>Error: index.html not found.</h1>"
    
    txt = html_path.read_text(encoding="utf-8")
    video_src = getattr(config, "VIDEO_IFRAME_SRC", "about:blank")
    return txt.replace("%%VIDEO_SRC%%", video_src)

@app.get("/")
async def root():
    return HTMLResponse(read_index_html())

@app.get("/health")
async def health():
    return PlainTextResponse("ok")

@app.get("/esc-status")
async def esc_status():
    """ESC 현재 상태를 반환하는 디버깅 엔드포인트"""
    status = hardware.get_esc_status()
    return status

def _is_braking_now() -> bool:
    """
    현재 사용자가 브레이크를 밟고 있는지 판단합니다.
    axis 값이 -5 이하면 브레이크로 판단합니다.
    """
    return app.state.axis <= -config.AXIS_DEADZONE_UNITS


async def tick_loop():
    """가상 변속기 및 하드웨어 제어를 담당하는 메인 루프입니다."""
    dt = config.TICK_S
    transmission = app.state.transmission
    
    while True:
        # 1. axis 입력을 하드웨어에 전달하여 vrpm 계산
        hardware.update_hardware_control(app.state.axis)
        current_vrpm = hardware.get_current_vrpm()
        
        # 2. 가상 변속기 업데이트 (vrpm → ESC 신호)
        gear_input = app.state.requested_gear
        if gear_input:
            app.state.requested_gear = None  # 한 번만 처리
        transmission.update(dt, current_vrpm, gear_input)

        # 3. 엔진 상태 변화 감지 및 하드웨어 아밍/디스아밍 처리
        if transmission.engine_running != app.state.prev_engine_running:
            try:
                if transmission.engine_running:
                    logging.info("엔진 시동. ESC 아밍 절차를 시작합니다...")
                    await hardware.set_engine_enabled_async(True)
                    transmission.set_engine_state(True, True)  # 엔진 실행, ESC 아밍
                    logging.info("ESC 아밍 완료.")
                else:
                    logging.info("엔진 정지. ESC 디스아밍을 시작합니다...")
                    await hardware.set_engine_enabled_async(False)
                    transmission.set_engine_state(False, False)  # 엔진 정지, ESC 디스아밍
                    logging.info("ESC 디스아밍 완료.")
                app.state.prev_engine_running = transmission.engine_running
            except Exception as e:
                logging.error(f"ESC 아밍/디스아밍 중 오류 발생: {e}")

        # 4. 가상 변속기에서 계산된 ESC 신호를 하드웨어에 적용
        esc_output = transmission.get_esc_output()
        try:
            # 조향은 별도 처리 (기존 로직 유지)
            steer_dir = app.state.steer_dir
            if steer_dir == -1:
                hardware.set_steering(config.STEER_LEFT_US)
            elif steer_dir == 1:
                hardware.set_steering(config.STEER_RIGHT_US)
            else:
                hardware.set_steering(config.STEER_CENTER_US)
            
            # ESC는 가상 변속기에서 계산된 값 사용
            hardware.set_esc_speed(esc_output)
            
            # 조명 제어 (간단한 로직)
            hardware.set_headlight(1.0 if getattr(transmission, 'head_on', False) else 0.0)
            hardware.set_taillight(0.5 if transmission.engine_running else 0.0)
        except Exception as e:
            logging.error(f"하드웨어 제어 중 오류 발생: {e}")

        # 5. 웹소켓 클라이언트에 현재 상태 전송
        controller: WebSocket = app.state.controller
        if controller:
            snap = transmission.get_state_snapshot()
            # 기존 형식과 호환성을 위해 추가 정보 포함
            snap.update({
                "virtual_rpm": snap["input_vrpm"] / 8000.0,  # 0..1로 정규화
                "speed_pct": int(snap["current_speed"] * 100),
                "head_on": getattr(transmission, 'head_on', False),
                "sport_mode_on": getattr(transmission, 'sport_mode_on', False),
            })
            try:
                await controller.send_text(json.dumps(snap))
                # 주기적으로 상태 로그 출력 (5초마다)
                if int(time.time()) % 5 == 0:
                    logging.info(f"상태 전송: vRPM={snap['input_vrpm']:.0f}, Speed={snap['speed_pct']}%, Gear={snap['gear']}, Engine={snap['engine_running']}")
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

            # 클라이언트로부터 받은 통합 입력 처리
            if isinstance(data.get("axis"), (int, float)):
                app.state.axis = max(-50.0, min(50.0, float(data["axis"])))
            if isinstance(data.get("steer_dir"), int):
                app.state.steer_dir = data["steer_dir"]

            # 기어 변경 요청 처리
            g = data.get("gear")
            if g in ("P", "R", "N", "D"):
                # R/D 변경 시 브레이크를 밟고 있는지 확인
                if g in ("R", "D") and not _is_braking_now():
                    await ws.send_text(json.dumps({"brake_hint": "브레이크를 밟으세요!"}))
                else:
                    app.state.requested_gear = g

            # 토글 버튼 입력 처리
            if data.get("head_toggle"):
                if not hasattr(app.state.transmission, 'head_on'):
                    app.state.transmission.head_on = False
                app.state.transmission.head_on = not app.state.transmission.head_on
            if data.get("sport_mode_toggle"):
                if not hasattr(app.state.transmission, 'sport_mode_on'):
                    app.state.transmission.sport_mode_on = False
                app.state.transmission.sport_mode_on = not app.state.transmission.sport_mode_on
            if data.get("engine_toggle"):
                handle_engine_toggle(app.state.transmission, ws)
                        
    except WebSocketDisconnect:
        logging.info("클라이언트 연결이 끊어졌습니다.")
        if app.state.controller is ws:
            app.state.controller = None
        # 안전을 위해 하드웨어를 안전 상태로 전환
        hardware.set_safe_state()

def _check_engine_start_conditions(transmission: VirtualTransmission) -> tuple[bool, str]:
    """엔진 시동 조건을 검사하고 (성공여부, 오류메시지)를 반환합니다."""
    if transmission.gear != "P":
        return False, getattr(config, "ENGINE_STOP_HINT_KO", "P단으로 변경하세요!")
    if not _is_braking_now():
        return False, "브레이크를 밟으세요!"
    return True, ""

def _check_engine_stop_conditions(transmission: VirtualTransmission) -> tuple[bool, str]:
    """엔진 정지 조건을 검사하고 (성공여부, 오류메시지)를 반환합니다."""
    require_p_to_stop = bool(getattr(config, "ENGINE_STOP_REQUIRE_P", True))
    if require_p_to_stop and transmission.gear != "P":
        return False, getattr(config, "ENGINE_STOP_HINT_KO", "P단으로 변경하세요!")
    return True, ""

def handle_engine_toggle(transmission: VirtualTransmission, ws: WebSocket):
    """엔진 시동/정지 토글 로직을 처리하는 보조 함수"""
    if not transmission.engine_running:
        # 시동 시도
        success, error_msg = _check_engine_start_conditions(transmission)
        if success:
            logging.info("엔진 시동 시작")
            transmission.set_engine_state(True, True)  # 엔진 실행, ESC 아밍
        else:
            asyncio.create_task(ws.send_text(json.dumps({
                "engine_stop_hint" if "P단" in error_msg else "brake_hint": error_msg
            })))
    else:
        # 정지 시도
        success, error_msg = _check_engine_stop_conditions(transmission)
        if success:
            logging.info("엔진 정지 시작")
            transmission.set_engine_state(False, False)  # 엔진 정지, ESC 디스아밍
        else:
            asyncio.create_task(ws.send_text(json.dumps({
                "engine_stop_hint": error_msg
            })))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 호출되는 생명주기 관리 함수"""
    logging.info("애플리케이션 시작...")
    try:
        hardware.init()
        logging.info("하드웨어 초기화 완료.")
    except Exception as e:
        logging.error(f"하드웨어 초기화 실패: {e}")

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
        
        try:
            hardware.shutdown()
            logging.info("하드웨어 종료 및 안전 상태 전환 완료.")
        except Exception as e:
            logging.error(f"하드웨어 종료 중 오류 발생: {e}")

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    logging.info("서버를 시작합니다. http://0.0.0.0:8000 에서 접속하세요.")
    uvicorn.run(app, host="0.0.0.0", port=8000)