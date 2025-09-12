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
from simulation import VehicleModel

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- 애플리케이션 상태 관리 ---
# FastAPI의 app.state를 사용하여 애플리케이션의 생명주기 동안 상태를 안전하게 관리합니다.
app.state.controller = None  # 현재 연결된 웹소켓 클라이언트
app.state.vehicle = VehicleModel()  # 차량 시뮬레이션 모델 인스턴스
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

def build_inputs_from_state() -> dict:
    """앱 상태로부터 시뮬레이션에 필요한 입력 딕셔너리를 구성합니다."""
    inputs = {
        "axis": app.state.axis,
        "steer_dir": app.state.steer_dir,
    }
    if app.state.requested_gear:
        inputs["gear"] = app.state.requested_gear
        app.state.requested_gear = None  # 기어 요청은 한 번만 처리
    return inputs

async def tick_loop():
    """차량 시뮬레이션 및 하드웨어 제어를 담당하는 메인 루프입니다."""
    dt = config.TICK_S
    vehicle = app.state.vehicle
    
    while True:
        inputs = build_inputs_from_state()
        vehicle.update(dt, inputs)

        # 엔진 상태 변화 감지 및 하드웨어 아밍/디스아밍 처리
        if vehicle.engine_running != app.state.prev_engine_running:
            try:
                if vehicle.engine_running:
                    logging.info("엔진 시동. ESC 아밍 절차를 시작합니다...")
                    await hardware.set_engine_enabled_async(True)
                    vehicle.esc_armed = True  # ESC 아밍 완료 상태 설정
                    logging.info("ESC 아밍 완료.")
                else:
                    logging.info("엔진 정지. ESC 디스아밍을 시작합니다...")
                    await hardware.set_engine_enabled_async(False)
                    vehicle.esc_armed = False  # ESC 디스아밍 상태 설정
                    logging.info("ESC 디스아밍 완료.")
                app.state.prev_engine_running = vehicle.engine_running
            except Exception as e:
                logging.error(f"ESC 아밍/디스아밍 중 오류 발생: {e}")
        
        # 크랭킹 시작 시 즉시 ESC 아밍 (시동 걸 때 비프음이 들리도록)
        if vehicle.engine_cranking_timer > 0.0 and app.state.prev_engine_running == False:
            try:
                logging.info("시동 크랭킹 시작. ESC 아밍을 즉시 수행합니다...")
                await hardware.set_engine_enabled_async(True)
                vehicle.esc_armed = True  # ESC 아밍 완료 상태 설정
                logging.info("ESC 아밍 완료 (크랭킹 중).")
            except Exception as e:
                logging.error(f"크랭킹 중 ESC 아밍 오류 발생: {e}")


        # 시뮬레이션 결과를 실제 하드웨어에 적용
        outs = vehicle.get_hardware_outputs(inputs)
        try:
            hardware.set_steering(outs["steering_us"])
            if vehicle.engine_running:
                hardware.set_esc_speed(outs["esc_norm"])
            hardware.set_headlight(outs["head_brightness"])
            hardware.set_taillight(outs["tail_brightness"])
        except Exception as e:
            logging.error(f"하드웨어 제어 중 오류 발생: {e}")

        # 웹소켓 클라이언트에 현재 상태 전송
        controller: WebSocket = app.state.controller
        if controller:
            snap = vehicle.get_state_snapshot(inputs)
            try:
                await controller.send_text(json.dumps(snap))
                # 주기적으로 상태 로그 출력 (5초마다)
                if int(time.time()) % 5 == 0:
                    logging.info(f"상태 전송: RPM={snap.get('virtual_rpm', 0):.2f}, Speed={snap.get('speed_pct', 0)}%, Gear={snap.get('gear', 'P')}, Engine={snap.get('engine_running', False)}")
            except WebSocketDisconnect:
                # 연결이 끊어진 경우를 대비하여 명시적으로 처리
                app.state.controller = None
                logging.info("데이터 전송 중 클라이언트 연결 끊김 감지.")
            except Exception as e:
                # 기타 예외 상황 처리
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
                app.state.vehicle.head_on = not app.state.vehicle.head_on
            if data.get("sport_mode_toggle"):
                app.state.vehicle.sport_mode_on = not app.state.vehicle.sport_mode_on
            if data.get("engine_toggle"):
                handle_engine_toggle(app.state.vehicle, ws)
                        
    except WebSocketDisconnect:
        logging.info("클라이언트 연결이 끊어졌습니다.")
        if app.state.controller is ws:
            app.state.controller = None
        # 안전을 위해 하드웨어를 안전 상태로 전환
        hardware.set_safe_state()

def _check_engine_start_conditions(vehicle: VehicleModel) -> tuple[bool, str]:
    """엔진 시동 조건을 검사하고 (성공여부, 오류메시지)를 반환합니다."""
    if vehicle.gear != "P":
        return False, getattr(config, "ENGINE_STOP_HINT_KO", "P단으로 변경하세요!")
    if not _is_braking_now():
        return False, "브레이크를 밟으세요!"
    if vehicle.engine_cranking_timer > 0:
        return False, "이미 시동 중입니다..."
    return True, ""

def _check_engine_stop_conditions(vehicle: VehicleModel) -> tuple[bool, str]:
    """엔진 정지 조건을 검사하고 (성공여부, 오류메시지)를 반환합니다."""
    require_p_to_stop = bool(getattr(config, "ENGINE_STOP_REQUIRE_P", True))
    if require_p_to_stop and vehicle.gear != "P":
        return False, getattr(config, "ENGINE_STOP_HINT_KO", "P단으로 변경하세요!")
    return True, ""

def handle_engine_toggle(vehicle: VehicleModel, ws: WebSocket):
    """엔진 시동/정지 토글 로직을 처리하는 보조 함수"""
    if not vehicle.engine_running:
        # 시동 시도
        success, error_msg = _check_engine_start_conditions(vehicle)
        if success:
            logging.info("엔진 시동 시작 (크랭킹)")
            vehicle.engine_cranking_timer = getattr(config, "CRANKING_DURATION_S", 0.8)
        else:
            asyncio.create_task(ws.send_text(json.dumps({
                "engine_stop_hint" if "P단" in error_msg else "brake_hint": error_msg
            })))
    else:
        # 정지 시도
        success, error_msg = _check_engine_stop_conditions(vehicle)
        if success:
            logging.info("엔진 정지 시작")
            vehicle.engine_running = False
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