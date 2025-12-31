"""
인프라 레이어
- Minecraft RCON 연결 및 명령어 전송
- MQTT 제스처 실시간 수신
- Flask API 챗봇 통신
- 메인 이벤트 루프
"""

import asyncio
import requests
import os
import sys
import time
import re
import json
from dotenv import load_dotenv
from mcrcon import MCRcon
import aiomqtt

# RAG 시스템 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
from rag_core import RAGSystem

# 게임 로직 레이어 import
from game_controller import (
    game_state, QUIZ_STAGES, GESTURE_TO_ANSWER, START_GESTURE, CHATBOT_GESTURES,
    show_stage_quiz, process_quiz_gesture, start_quiz_game,
    check_stage2_arrival, check_safe_zone_arrival,
    handle_chatbot_gesture, toggle_chatbot, auto_enable_chatbot
)

# ============================================================
# Server.py - 인프라 레이어 (통신 + 실행)
# ============================================================

load_dotenv()

# ==========================================
# 1. 설정
# ==========================================

# MQTT 설정
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
AE_NAME_GESTURE = os.getenv("AE_NAME_GESTURE", "ae-gesture")

# MQTT Subscribe 토픽
MQTT_SUB_TOPIC = f"/oneM2M/req/{AE_NAME_GESTURE}/#"

# Minecraft 설정
MC_HOST = os.getenv("MC_HOST", "168.107.59.104")
MC_RCON_PORT = int(os.getenv("MC_RCON_PORT", "25575"))
MC_RCON_PASSWORD = os.getenv("MC_RCON_PASSWORD", "1234")

# Flask API URL
FLASK_API = os.getenv("FLASK_API", "http://168.107.59.104:5000/get_chats")

# ==========================================
# 2. Minecraft 연결 및 명령어 전송
# ==========================================

# Minecraft 연결 (전역)
mc_connection = None

def get_minecraft_connection():
    """Minecraft RCON 연결 가져오기"""
    global mc_connection
    try:
        if mc_connection is None:
            mc_connection = MCRcon(MC_HOST, MC_RCON_PASSWORD, port=MC_RCON_PORT)
            mc_connection.connect()
            sys.stderr.write(f"[MC] 새 연결 생성: {MC_HOST}:{MC_RCON_PORT}\n")
        return mc_connection
    except Exception as e:
        sys.stderr.write(f"[MC] 연결 실패: {e}\n")
        mc_connection = None
        return None

def send_chat_message(mc, message: str, color: str = "white", bold: bool = False):
    """Minecraft 채팅 메시지 전송"""
    try:
        # 색상 코드 매핑
        color_map = {
            "white": "white", "gray": "gray", "red": "red", "green": "green",
            "blue": "blue", "yellow": "yellow", "gold": "gold", "aqua": "aqua"
        }
        color_code = color_map.get(color.lower(), "white")
        bold_tag = '"bold":true,' if bold else ''
        
        escaped = message.replace('"', '\\"').replace('\\', '\\\\')
        cmd = f'tellraw @a [{{"text":"{escaped}","color":"{color_code}",{bold_tag}"italic":false}}]'
        mc.command(cmd)
    except Exception as e:
        sys.stderr.write(f"[MC] 채팅 전송 실패: {e}\n")

def check_player_near_location(target_x: int, target_y: int, target_z: int, radius: int = 10) -> bool:
    """플레이어가 목표 위치 근처에 있는지 체크"""
    try:
        mc = get_minecraft_connection()
        if mc is None:
            return False
        
        # 플레이어 위치 가져오기
        try:
            result = mc.command("execute as @p run data get entity @s Pos")
            sys.stderr.write(f"[Position] RCON 응답: {result}\n")
            
            # 응답 파싱: "[123.5d, 64.0d, -456.7d]"
            if '[' in result and ']' in result:
                start = result.rindex('[')
                end = result.rindex(']') + 1
                pos_str = result[start:end]
                coords = pos_str.replace('d', '').replace('[', '').replace(']', '').split(',')
                if len(coords) >= 3:
                    px, py, pz = float(coords[0].strip()), float(coords[1].strip()), float(coords[2].strip())
                    
                    # 거리 계산
                    distance_xz = ((px - target_x)**2 + (pz - target_z)**2)**0.5
                    distance_y = abs(py - target_y)
                    
                    sys.stderr.write(f"[Position] 플레이어: ({px:.1f}, {py:.1f}, {pz:.1f}), 목표: ({target_x}, {target_y}, {target_z}), 거리 XZ: {distance_xz:.1f}, Y: {distance_y:.1f}\n")
                    
                    if distance_xz <= radius and distance_y <= radius:
                        return True
        except Exception as e:
            sys.stderr.write(f"[Position] 위치 확인 실패: {e}\n")
        
        return False
    except Exception as e:
        sys.stderr.write(f"[Position] Error: {e}\n")
        return False

# ==========================================
# 3. MQTT 제스처 수신
# ==========================================

# 최신 제스처 저장 (전역)
latest_gesture = "None"
gesture_lock = asyncio.Lock()

async def mqtt_gesture_listener():
    """MQTT로부터 제스처 메시지 수신"""
    global latest_gesture
    
    sys.stderr.write(f"[MQTT] 브로커 연결 중: {MQTT_HOST}:{MQTT_PORT}\n")
    sys.stderr.write(f"[MQTT] 구독 토픽: {MQTT_SUB_TOPIC}\n")
    
    while True:
        try:
            async with aiomqtt.Client(MQTT_HOST, MQTT_PORT) as client:
                sys.stderr.write("[MQTT] 브로커 연결 성공\n")
                await client.subscribe(MQTT_SUB_TOPIC)
                sys.stderr.write(f"[MQTT] 토픽 구독 완료: {MQTT_SUB_TOPIC}\n")
                
                async for message in client.messages:
                    try:
                        payload = message.payload.decode('utf-8')
                        sys.stderr.write(f"[MQTT] 메시지 수신: {payload[:100]}...\n")
                        
                        # oneM2M notification 파싱
                        data = json.loads(payload)
                        
                        # 제스처 데이터 추출
                        gesture_value = None
                        
                        # oneM2M request 구조 파싱 (m2m:rqp)
                        if "m2m:rqp" in data:
                            rqp = data["m2m:rqp"]
                            if "pc" in rqp and "m2m:cin" in rqp["pc"]:
                                cin = rqp["pc"]["m2m:cin"]
                                gesture_value = cin.get("con")
                        # oneM2M notification 구조 파싱 (m2m:sgn)
                        elif "pc" in data and "m2m:sgn" in data["pc"]:
                            sgn = data["pc"]["m2m:sgn"]
                            if "nev" in sgn and "rep" in sgn["nev"]:
                                rep = sgn["nev"]["rep"]
                                if "m2m:cin" in rep:
                                    cin = rep["m2m:cin"]
                                    gesture_value = cin.get("con")
                        
                        if gesture_value:
                            async with gesture_lock:
                                latest_gesture = gesture_value
                            sys.stderr.write(f"[MQTT] 제스처 업데이트: {gesture_value}\n")
                        
                    except json.JSONDecodeError as e:
                        sys.stderr.write(f"[MQTT] JSON 파싱 오류: {e}\n")
                    except Exception as e:
                        sys.stderr.write(f"[MQTT] 메시지 처리 오류: {e}\n")
        
        except Exception as e:
            sys.stderr.write(f"[MQTT] 연결 오류: {e}\n")
            sys.stderr.write("[MQTT] 5초 후 재연결 시도...\n")
            await asyncio.sleep(5)

# ==========================================
# 4. AI 챗봇 통신 (Flask API + RAG)
# ==========================================

# 채팅 패턴
QUESTION_PATTERN = r'!\s*질문\s*(.+)'

# 마지막으로 처리한 채팅
last_processed_chat = None

# RAG 시스템 인스턴스
rag_system = None

def init_rag_system():
    """RAG 시스템 초기화 (싱글톤)"""
    global rag_system
    if rag_system is None:
        try:
            rag_system = RAGSystem()
            sys.stderr.write(f"[RAG] 초기화 완료\n")
        except Exception as e:
            sys.stderr.write(f"[RAG] 초기화 실패: {e}\n")
            rag_system = None
    return rag_system

def get_latest_question():
    """Flask API에서 최신 !질문 가져오기"""
    global last_processed_chat
    try:
        response = requests.get(FLASK_API, timeout=3)
        response.raise_for_status()
        chats = response.json()
        
        # 최신 채팅부터 역순으로 검색
        for chat in reversed(chats):
            if chat == last_processed_chat:
                break
            
            message = chat.get("message", "")
            player = chat.get("player", "Unknown")
            
            if message.strip().startswith("!질문") or message.strip().startswith("! 질문"):
                import re
                match = re.search(QUESTION_PATTERN, message)
                if match:
                    question = match.group(1).strip()
                    last_processed_chat = chat
                    return player, question
        
        return None, None
        
    except Exception as e:
        sys.stderr.write(f"[Chatbot] API 오류: {e}\n")
        return None, None

def get_ai_answer(question: str) -> str:
    """AI 답변 생성 (RAG 시스템 사용)"""
    sys.stderr.write(f"[Chatbot] RAG 호출: {question}\n")
    
    # RAG 시스템 사용
    rag = init_rag_system()
    if rag is not None:
        try:
            answer = rag.get_answer(question)
            sys.stderr.write(f"[Chatbot] RAG 답변 완료: {len(answer)} 글자\n")
            return answer
        except Exception as e:
            sys.stderr.write(f"[Chatbot] RAG 오류: {e}\n")
    
    # Fallback: 키워드 기반 답변
    sys.stderr.write("[Chatbot] Fallback 모드 사용\n")
    question_lower = question.lower()
    
    if "화재" in question or "불" in question:
        return "화재 발생 시 가장 먼저 '불이야!'라고 외쳐 주변에 알리고, 119에 신고해야 합니다. 초기 진화가 가능하면 소화기를 사용하고, 불가능하면 신속히 대피하세요."
    elif "지진" in question:
        return "지진 발생 시 책상 밑으로 들어가 머리를 보호하고, 흔들림이 멈추면 건물 밖으로 대피하세요. 건물과 담장에서 최대한 멀리 떨어지세요."
    elif "대피" in question or "탈출" in question:
        return "재난 시 대피 요령: 침착하게 행동하고, 엘리베이터 사용 금지, 계단 이용, 연기가 있으면 자세를 낮추고 119 신고 후 안전한 장소로 이동하세요."
    else:
        return f"'{question}'에 대한 답변입니다. 재난 안전 정보는 RAG 시스템이 준비 중입니다."

# ==========================================
# 5. 메인 이벤트 루프 (제스처 모니터링)
# ==========================================

async def gesture_monitor():
    """제스처 자동 감지 및 게임 진행"""
    global latest_gesture
    
    # 체크 주기
    gesture_check_interval_sec = 0.05  # MQTT는 실시간이므로 체크만 빠르게
    location_check_interval_sec = 0.6
    last_location_check_at = 0.0
    
    # 초기화
    async with gesture_lock:
        latest_gesture = "None"
    last_gesture = "None"
    sys.stderr.write(f"[Monitor] 초기 제스처 무시\n")
    
    previous_stage = 0
    stage_transition_time = 0
    stage_cooldown = 0.5
    
    sys.stderr.write("[Monitor] 제스처 모니터링 시작...\n")
    
    while True:
        try:
            # 현재 제스처 읽기
            async with gesture_lock:
                current_gesture = latest_gesture
            
            now = time.monotonic()
            
            # Stage가 변경되면 쿨다운 시작
            if game_state.current_quiz_stage != previous_stage:
                if game_state.current_quiz_stage in [1, 2]:
                    sys.stderr.write(f"[Monitor] Stage {previous_stage} → {game_state.current_quiz_stage} 전환: {stage_cooldown}초 쿨다운 시작\n")
                    stage_transition_time = now
                    last_gesture = "None"
                previous_stage = game_state.current_quiz_stage
            
            # Stage 전환 쿨다운 중이면 제스처 무시
            if (now - stage_transition_time) < stage_cooldown:
                await asyncio.sleep(gesture_check_interval_sec)
                continue
            
            # Stage 전환 체크 (주기적으로)
            if now - last_location_check_at >= location_check_interval_sec:
                last_location_check_at = now
                
                # Stage 1.5 → 2 체크
                await check_stage2_arrival(
                    check_player_near_location,
                    get_minecraft_connection,
                    send_chat_message
                )
                
                # Stage 2.5 → 3 체크
                await check_safe_zone_arrival(
                    check_player_near_location,
                    get_minecraft_connection,
                    send_chat_message
                )
            
            # 제스처 변경 감지
            if current_gesture != last_gesture and current_gesture not in ["None", "Unknown"]:
                sys.stderr.write(f"[Monitor] 감지: {current_gesture}\n")
                last_gesture = current_gesture
                
                # 제스처 처리 후 리셋 (중복 처리 방지)
                async with gesture_lock:
                    latest_gesture = "None"
                
                # Thumb_Down 제스처로 AI 챗봇 토글
                if current_gesture in ["Right_Thumb_Down", "Left_Thumb_Down"]:
                    toggle_chatbot(get_minecraft_connection, send_chat_message)
                    continue
                
                # AI 챗봇 제스처 감지 (Open_Palm)
                if current_gesture in CHATBOT_GESTURES:
                    auto_enable_chatbot(get_minecraft_connection, send_chat_message)
                    sys.stderr.write(f"[Monitor] 챗봇 제스처 감지: {current_gesture}\n")
                    await handle_chatbot_gesture(
                        current_gesture,
                        get_latest_question,
                        get_ai_answer,
                        get_minecraft_connection,
                        send_chat_message
                    )
                    await asyncio.sleep(0.5)
                    continue
                
                # 퀴즈 시작 요청 (Left_Thumb_Up)
                if current_gesture == START_GESTURE and game_state.current_quiz_stage == 0:
                    sys.stderr.write("[Monitor] 퀴즈 시작 요청\n")
                    asyncio.create_task(start_quiz_game(get_minecraft_connection, send_chat_message))
                    await asyncio.sleep(0.3)
                    continue
                
                # 퀴즈 진행 중 제스처 처리 (Stage 1, 2만)
                elif game_state.current_quiz_stage in [1, 2]:
                    result = await asyncio.to_thread(
                        process_quiz_gesture,
                        current_gesture,
                        get_minecraft_connection,
                        send_chat_message
                    )
                    sys.stderr.write(f"[Monitor] 결과: {result}\n")
            
            await asyncio.sleep(gesture_check_interval_sec)
            
        except Exception as e:
            sys.stderr.write(f"[Monitor] Error: {e}\n")
            await asyncio.sleep(1.0)

# ==========================================
# 6. 메인 실행
# ==========================================

async def main():
    """MQTT 리스너와 제스처 모니터 동시 실행"""
    sys.stderr.write("\n" + "="*60 + "\n")
    sys.stderr.write("🎮 마인크래프트 제스처 퀴즈 + AI 챗봇 시스템 (MQTT 버전)\n")
    sys.stderr.write("="*60 + "\n")
    sys.stderr.write(f"📡 MQTT 브로커: {MQTT_HOST}:{MQTT_PORT}\n")
    sys.stderr.write(f"📡 구독 토픽: {MQTT_SUB_TOPIC}\n")
    sys.stderr.write(f"🎮 Minecraft: {MC_HOST}:{MC_RCON_PORT}\n")
    sys.stderr.write(f"🤖 Flask API: {FLASK_API}\n")
    sys.stderr.write("="*60 + "\n\n")
    
    # MQTT 리스너와 제스처 모니터 병렬 실행
    await asyncio.gather(
        mqtt_gesture_listener(),
        gesture_monitor()
    )

if __name__ == "__main__":
    # Windows에서 MQTT 소켓 작업을 위해 SelectorEventLoop 사용
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.stderr.write("\n\n👋 프로그램이 정상적으로 종료되었습니다.\n")
    except Exception as e:
        sys.stderr.write(f"\n\n❌ 오류 발생: {e}\n")
