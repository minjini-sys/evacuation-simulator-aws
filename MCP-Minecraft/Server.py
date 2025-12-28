import asyncio
import requests
import os
import sys
from dotenv import load_dotenv
from mcrcon import MCRcon

# RAG 시스템 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'AI'))
from rag_core import RAGSystem

# ============================================================
# Server.py - 제스처 기반 마인크래프트 제어 + 2단계 퀴즈
# ============================================================

load_dotenv()

# ==========================================
# 1. 설정
# ==========================================

MOBIUS_HOST = os.getenv("MOBIUS_HOST") 
MOBIUS_CSE = os.getenv("MOBIUS_CSE")
MOBIUS_AE = os.getenv("MOBIUS_AE")
MOBIUS_ORIGIN = os.getenv("MOBIUS_ORIGIN")
MOBIUS_PORT = int(os.getenv("MOBIUS_PORT", "7579"))
MC_HOST = os.getenv("MC_HOST", "168.107.59.104")
MC_RCON_PORT = int(os.getenv("MC_RCON_PORT", "25575"))
MC_RCON_PASSWORD = os.getenv("MC_RCON_PASSWORD", "1234")

# 필수 설정값 검증
required_vars = [
    ("MOBIUS_HOST", MOBIUS_HOST),
    ("MOBIUS_CSE", MOBIUS_CSE),
    ("MOBIUS_AE", MOBIUS_AE),
    ("MOBIUS_ORIGIN", MOBIUS_ORIGIN),
]

for var_name, var_value in required_vars:
    if not var_value:
        sys.stderr.write(f"[Critical Error] .env 파일에 '{var_name}' 설정이 없습니다.\n")
        sys.exit(1)

# ==========================================
# 2. 퀴즈 시스템 설정
# ==========================================

# 게임 상태 (전역)
current_quiz_stage = 0  # 0: 대기, 1: Stage1, 2: Stage2, 3: 완료
chatbot_enabled = True  # AI 챗봇 활성화 여부

# Minecraft 연결 (전역)
mc_connection = None

def get_minecraft_connection():
    """Minecraft RCON 연결 가져오기"""
    global mc_connection
    try:
        if mc_connection is None:
            mc_connection = MCRcon(MC_HOST, MC_RCON_PASSWORD, MC_RCON_PORT)
            mc_connection.connect()
            sys.stderr.write("[MC] RCON 새 연결 생성\n")
        return mc_connection
    except Exception as e:
        sys.stderr.write(f"[MC] RCON 연결 실패: {e}\n")
        mc_connection = None
        return None

def send_chat_message(mc, message: str, color: str = "white", bold: bool = False):
    """채팅 메시지 전송 (RCON 방식 with 색상)"""
    try:
        # /tellraw 명령어로 JSON 포맷 사용
        json_text = '{"text":"' + message + '","color":"' + color + '"'
        if bold:
            json_text += ',"bold":true'
        json_text += '}'
        mc.command(f"tellraw @a {json_text}")
    except Exception as e:
        sys.stderr.write(f"[MC] 채팅 전송 실패: {e}\n")

# 스테이지 정보
QUIZ_STAGES = {
    1: {
        "name": "가정집 (화재 상황)",
        "question": "화재 발생 시 가장 먼저 해야 할 행동은?",
        "options": [
            "1번 소화기를 찾으러 간다",
            "2번 불이 난 장소를 촬영한다",
            '3번 "불이야"라고 외쳐 주변에 알린다',
            "4번 창문을 닫고 연기를 막는다",
            "5번 엘리베이터를 타고 대피한다"
        ],
        "answer": 3,  # 3번 = "불이야"라고 외쳐 주변에 알린다
        "next_location": {"x": 200, "y": 70, "z": 200}
    },
    2: {
        "name": "학교 (지진 상황)",
        "question": "지진 발생 후 건물 밖으로 대피했을 때 올바른 행동은?",
        "options": [
            "1번 건물 벽에 기대어 상황을 지켜본다",
            "2번 간판 아래에서 비를 피한다",
            "3번 건물과 담장에서 최대한 멀리 떨어진다",
            "4번 전봇대를 잡고 균형을 유지한다",
            "5번 차량 안에서 대기한다"
        ],
        "answer": 3,  # 3번 = 건물과 담장에서 최대한 멀리 떨어진다
        "next_location": None
    }
}

def show_stage_quiz_sync(stage_num: int) -> None:
    stage = QUIZ_STAGES[stage_num]
    mc = get_minecraft_connection()
    if mc is None:
        sys.stderr.write("[Quiz] Minecraft 연결 실패\n")
        return
    send_chat_message(mc, "")
    send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
    send_chat_message(mc, f"📍 STAGE {stage_num}: {stage['name']}", color="gold", bold=True)
    send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
    send_chat_message(mc, "")
    send_chat_message(mc, f"❓ {stage['question']}", color="yellow", bold=True)
    send_chat_message(mc, "")
    for option in stage['options']:
        send_chat_message(mc, f"   {option}", color="white")
    send_chat_message(mc, "")


# 제스처-답변 매핑 (카메라 좌우반전 고려)
# 카메라: 실제 오른손 = Left로 인식, 실제 왼손 = Right로 인식
GESTURE_TO_ANSWER = {
    # Left (실제 오른손)
    "Left_Pointing_Up": 3,      # 실제 오른손 검지 = 3번
    "Left_Victory": 4,          # 실제 오른손 브이 = 4번
    "Left_Thumb_Up": 5,         # 실제 오른손 엄지척 = 5번
    # Right (실제 왼손)
    "Right_Pointing_Up": 1,     # 실제 왼손 검지 = 1번
    "Right_Victory": 2,         # 실제 왼손 브이 = 2번
}

# 퀴즈 시작 제스처 (카메라 반전: 실제 왼손 = Right로 인식)
START_GESTURE = "Right_Thumb_Up"  # 실제 왼손 엄지척

# AI 챗봇 제스처 (둘 다 채팅 로그 읽기)
CHATBOT_GESTURES = ["Right_Open_Palm", "Left_Open_Palm"]

# ==========================================
# 3. Helper 함수 (퀴즈 로직)
# ==========================================

def fetch_gesture_sync() -> str:
    """Mobius에서 제스처 가져오기"""
    try:
        url = f"http://{MOBIUS_HOST}:{MOBIUS_PORT}/{MOBIUS_CSE}/{MOBIUS_AE}/hand_gestures/la"
        headers = {
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": MOBIUS_ORIGIN,
        }
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()

        body = resp.json()
        cin = body.get("m2m:cin")
        if not cin:
            return "None"
        return str(cin.get("con", "None"))
    except Exception as e:
        sys.stderr.write(f"[Fetch] Error: {e}\n")
        return "Unknown"

def process_quiz_gesture_sync(gesture: str) -> str:
    """퀴즈 제스처 처리 (핵심 로직)"""
    global current_quiz_stage

    # Left_Thumb_Up으로 퀴즈 시작
    if gesture == START_GESTURE and current_quiz_stage == 0:
        return "START_REQUESTED"
    
    
    # 퀴즈 진행 중이 아니면 무시
    if current_quiz_stage == 0:
        return "퀴즈 대기 중"
    
    if current_quiz_stage >= 3:
        return "게임 완료됨"
    
    # 제스처를 답변 번호로 변환
    if gesture not in GESTURE_TO_ANSWER:
        return f"알 수 없는 제스처: {gesture}"
    
    answer_num = GESTURE_TO_ANSWER[gesture]
    stage_info = QUIZ_STAGES[current_quiz_stage]
    correct_answer = stage_info["answer"]
    
    try:
        mc = get_minecraft_connection()
        if mc is None:
            sys.stderr.write("[Quiz] Minecraft 연결 실패, 상태 유지\n")
            return "MC_CONNECTION_FAILED"
        
        send_chat_message(mc, "")
        send_chat_message(mc, f"🎯 [선택] {answer_num}번 선택!", color="gray", bold=True)
        send_chat_message(mc, "")
        
        # 정답 체크
        if answer_num == correct_answer:
            sys.stderr.write(f"[Quiz] Stage {current_quiz_stage} 정답!\n")
            
            if current_quiz_stage == 1:
                # Stage 1 정답 → Stage 2 좌표 전송
                next_loc = stage_info["next_location"]
                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="green")
                send_chat_message(mc, "✓ [정답!] 잘하셨습니다!", color="green", bold=True)
                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="green")
                send_chat_message(mc, "")
                send_chat_message(mc, f"📍 다음 장소로 이동하세요:", color="yellow", bold=True)
                send_chat_message(mc, f"   X={next_loc['x']}, Y={next_loc['y']}, Z={next_loc['z']}", color="gold")
                send_chat_message(mc, "")
                current_quiz_stage = 2
                return "STAGE1_CORRECT"
                
            elif current_quiz_stage == 2:
                # Stage 2 정답 → CLEAR
                send_chat_message(mc, "")
                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_chat_message(mc, "✓ [정답!] 완벽합니다!", color="green", bold=True)
                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_chat_message(mc, "")
                send_chat_message(mc, "🎉 ★★★ CLEAR ★★★ 🎉", color="gold", bold=True)
                send_chat_message(mc, "재난 안전 교육을 완료했습니다!", color="yellow")
                send_chat_message(mc, "")
                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                current_quiz_stage = 3
                sys.stderr.write("[Quiz] 게임 클리어!\n")
                return "STAGE2_CLEAR"
        
        else:
            # 오답 → X 표시
            send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="red")
            send_chat_message(mc, "✗ [오답] 틀렸습니다!", color="red", bold=True)
            send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="red")
            send_chat_message(mc, "💪 다시 한번 생각해보세요!", color="yellow")
            send_chat_message(mc, "")
            sys.stderr.write(f"[Quiz] Stage {current_quiz_stage} 오답\n")
            return "WRONG_ANSWER"
            
    except Exception as e:
        sys.stderr.write(f"[Quiz] Error: {e}\n")
        return f"오류: {e}"

# ==========================================
# 4. 제스처 기반 AI 챗봇
# ==========================================

# Flask API 설정 (채팅 로그 읽기)
FLASK_API = "http://168.107.59.104:5000/get_chats"
QUESTION_PATTERN = r'!\s*질문\s*(.+)'

# 마지막으로 처리한 채팅
last_processed_chat = None

# RAG 시스템 초기화 (전역)
rag_system = None

def init_rag_system():
    """RAG 시스템 초기화 (한 번만 실행)"""
    global rag_system
    if rag_system is None:
        try:
            sys.stderr.write("[RAG] 시스템 초기화 중...\n")
            rag_system = RAGSystem()
            sys.stderr.write("[RAG] 초기화 완료!\n")
        except Exception as e:
            sys.stderr.write(f"[RAG] 초기화 실패: {e}\n")
            sys.stderr.write("[RAG] 기본 키워드 답변 모드로 전환합니다.\n")
    return rag_system

def get_latest_question():
    """Flask API에서 최신 !질문 가져오기"""
    global last_processed_chat
    import re
    
    try:
        response = requests.get(FLASK_API, timeout=5)
        
        if response.status_code == 200:
            chats = response.json()
            
            if chats:
                # 최신 채팅부터 역순으로 확인
                for chat in reversed(chats):
                    # 이미 처리한 채팅은 스킵
                    if chat == last_processed_chat:
                        break
                    
                    message = chat['message']
                    player = chat['player']
                    
                    # !질문 패턴 확인
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

async def handle_chatbot_gesture(gesture: str):
    """Open_Palm 제스처로 AI 챗봇 호출"""
    sys.stderr.write(f"[Chatbot] Open_Palm 감지! 채팅 확인 중...\n")
    
    # 최신 !질문 가져오기
    player, question = await asyncio.to_thread(get_latest_question)
    
    if player and question:
        sys.stderr.write(f"[Chatbot] 질문 발견: {player} - {question}\n")
        
        # LLM 호출
        answer = await asyncio.to_thread(get_ai_answer, question)
        sys.stderr.write(f"[Chatbot] 답변 완료\n")
        
        # 마인크래프트에 전송
        try:
            mc = get_minecraft_connection()
            if mc:
                send_chat_message(mc, "")
                send_chat_message(mc, f"[AI → {player}]", color="aqua", bold=True)
                
                # 답변을 60자씩 나누어 전송
                chunks = [answer[i:i+60] for i in range(0, len(answer), 60)][:8]
                for chunk in chunks:
                    escaped = chunk.replace('"', '\\"').replace("'", "\\'")
                    send_chat_message(mc, escaped, color="white")
                
                if len(answer) > 480:
                    send_chat_message(mc, "...(답변이 너무 길어 일부 생략됨)", color="gray")
                send_chat_message(mc, "")
                sys.stderr.write(f"[Chatbot] 마인크래프트에 전송 완료\n")
        except Exception as e:
            sys.stderr.write(f"[Chatbot] 전송 실패: {e}\n")
    else:
        sys.stderr.write(f"[Chatbot] 처리할 !질문이 없습니다\n")

# ==========================================
# 5. 퀴즈 시작 함수
# ==========================================

async def start_quiz_game():
    """퀴즈 게임 시작"""
    global current_quiz_stage
    
    sys.stderr.write("[Quiz] 퀴즈 시작!\n")
    
    try:
        mc = get_minecraft_connection()
        if mc is None:
            sys.stderr.write("[Quiz] Minecraft 연결 실패\n")
            return
        
        # 게임 시작 안내
        send_chat_message(mc, "")
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "🚨  재난 안전 퀴즈 시작  🚨", color="yellow", bold=True)
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "")
        send_chat_message(mc, "📌 제스처로 정답을 선택하세요:", color="green", bold=True)
        send_chat_message(mc, "")
        send_chat_message(mc, "   [실제 왼손]", color="aqua", bold=True)
        send_chat_message(mc, "   ☝️ 검지 = 1번", color="white")
        send_chat_message(mc, "   ✌️ 브이 = 2번", color="white")
        send_chat_message(mc, "")
        send_chat_message(mc, "   [실제 오른손]", color="yellow", bold=True)
        send_chat_message(mc, "   ☝️ 검지 = 3번 ⭐", color="white")
        send_chat_message(mc, "   ✌️ 브이 = 4번", color="white")
        send_chat_message(mc, "   👍 엄지척 = 5번", color="white")
        send_chat_message(mc, "")
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "")
        
        # Stage 1 퀴즈 표시
        current_quiz_stage = 1
        await asyncio.sleep(1.0)
        await asyncio.to_thread(show_stage_quiz_sync, 1)
        
    except Exception as e:
        current_quiz_stage = 0
        sys.stderr.write(f"[Quiz] 시작 오류: {e}\n")

# ==========================================
# 6. 백그라운드 모니터
# ==========================================

async def gesture_monitor():
    """제스처 자동 감지 및 퀴즈 처리"""
    last_gesture = await asyncio.to_thread(fetch_gesture_sync)
    sys.stderr.write(f"[Monitor] 초기 제스처 무시: {last_gesture}\n")
    
    sys.stderr.write("[Monitor] 제스처 모니터링 시작...\n")
    
    while True:
        try:
            current_gesture = await asyncio.to_thread(fetch_gesture_sync)
            
            # 제스처 변경 감지
            if current_gesture != last_gesture and current_gesture not in ["None", "Unknown"]:
                sys.stderr.write(f"[Monitor] 감지: {current_gesture}\n")
                last_gesture = current_gesture  # 즉시 업데이트하여 중복 방지

                # Thumb_Down 제스처로 AI 챗봇 토글 (퀴즈는 계속 진행)
                if current_gesture in ["Right_Thumb_Down", "Left_Thumb_Down"]:
                    global chatbot_enabled
                    chatbot_enabled = not chatbot_enabled
                    sys.stderr.write(f"\n[Monitor] 👎 Thumb_Down 감지! AI 챗봇: {'활성화' if chatbot_enabled else '비활성화'}\n")
                    mc = get_minecraft_connection()
                    if mc:
                        send_chat_message(mc, "")
                        if chatbot_enabled:
                            send_chat_message(mc, "🤖 [AI 챗봇 활성화] Open_Palm으로 질문하세요.", color="green", bold=True)
                        else:
                            send_chat_message(mc, "🚫 [AI 챗봇 비활성화] 퀴즈는 계속 진행됩니다.", color="red", bold=True)
                        send_chat_message(mc, "")
                    continue

                # AI 챗봇 제스처 감지 (Right_Open_Palm, Left_Open_Palm)
                if current_gesture in CHATBOT_GESTURES:
                    if chatbot_enabled:
                        sys.stderr.write(f"[Monitor] 챗봇 제스처 감지: {current_gesture}\n")
                        await handle_chatbot_gesture(current_gesture)
                        await asyncio.sleep(2.0)  # 답변 처리 대기
                    else:
                        sys.stderr.write(f"[Monitor] 챗봇 비활성화 상태 - Open_Palm 무시\n")
                    continue

                # Left_Thumb_Up으로 퀴즈 시작 (대기 중일 때만)
                if current_gesture == START_GESTURE and current_quiz_stage == 0:
                    sys.stderr.write("[Monitor] 퀴즈 시작 요청\n")
                    asyncio.create_task(start_quiz_game())
                    await asyncio.sleep(1.0)
                    continue
                    
                # 퀴즈 진행 중일 때만 제스처 처리
                elif current_quiz_stage > 0 and current_quiz_stage < 3:
                    result = await asyncio.to_thread(
                        process_quiz_gesture_sync, 
                        current_gesture
                    )
                    sys.stderr.write(f"[Monitor] 결과: {result}\n")
                    
                    # Stage 1 정답 후 Stage 2 퀴즈 표시 (UX 개선)
                    if result == "STAGE1_CORRECT":
                        await asyncio.sleep(3.0)  # 좌표 확인 시간
                        try:
                            mc = get_minecraft_connection()
                            if mc is not None:
                                stage2 = QUIZ_STAGES[2]
                                send_chat_message(mc, "")
                                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                                send_chat_message(mc, f"📍 STAGE {2}: {stage2['name']}", color="gold", bold=True)
                                send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                                send_chat_message(mc, "")
                                send_chat_message(mc, f"❓ {stage2['question']}", color="yellow", bold=True)
                                send_chat_message(mc, "")
                                for option in stage2['options']:
                                    send_chat_message(mc, f"   {option}", color="white")
                                send_chat_message(mc, "")
                            else:
                                sys.stderr.write(f"[Monitor] Stage2 표시 실패: MC 연결 없음\n")
                        except Exception as e:
                            sys.stderr.write(f"[Monitor] Stage2 표시 실패: {e}\n")
            
            await asyncio.sleep(1.0)
            
        except Exception as e:
            sys.stderr.write(f"[Monitor] Error: {e}\n")
            await asyncio.sleep(2.0)

# ==========================================
# 6. 메인 실행
# ==========================================

if __name__ == "__main__":
    sys.stderr.write("\n" + "="*60 + "\n")
    sys.stderr.write("🎮 마인크래프트 제스처 퀴즈 + AI 챗봇 시스템 시작\n")
    sys.stderr.write("="*60 + "\n")
    sys.stderr.write(f"📡 Mobius: {MOBIUS_HOST}:{MOBIUS_PORT}\n")
    sys.stderr.write(f"🎮 Minecraft: {MC_HOST}:{MC_RCON_PORT}\n")
    sys.stderr.write(f"🤖 Flask API: {FLASK_API}\n")
    sys.stderr.write("="*60 + "\n\n")
    
    try:
        asyncio.run(gesture_monitor())
    except KeyboardInterrupt:
        sys.stderr.write("\n\n👋 프로그램이 정상적으로 종료되었습니다.\n")
    except Exception as e:
        sys.stderr.write(f"\n\n❌ 오류 발생: {e}\n") 
