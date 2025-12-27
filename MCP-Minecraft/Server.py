import asyncio
import requests
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from mcrcon import MCRcon
from mcp.server.fastmcp import FastMCP, Context
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

# RAG 모듈 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../AI"))
try:
    from rag import get_answer
    RAG_AVAILABLE = True
except ImportError as e:
    sys.stderr.write(f"[Warning] RAG 모듈 로드 실패: {e}\n")
    RAG_AVAILABLE = False

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
MC_HOST = os.getenv("MC_HOST", "localhost")
MC_RCON_PORT = int(os.getenv("MC_RCON_PORT", "25575"))
MC_RCON_PASSWORD = os.getenv("MC_RCON_PASSWORD", "minecraft")

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
            "0번 소화기를 찾으러 간다",
            "1번 불이 난 장소를 촬영한다",
            "2번 “불이야”라고 외쳐 주변에 알린다",
            "3번 창문을 닫고 연기를 막는다",
            "4번 엘리베이터를 타고 대피한다"
        ],
        "answer": 3,  
        "next_location": {"x": 200, "y": 70, "z": 200},
        "hint_question": "화재 발생 시 가장 먼저 해야 할 행동은?"
    },
    2: {
        "name": "학교 (지진 상황)",
        "question": "지진 발생 후 건물 밖으로 대피했을 때 올바른 행동은?",
        "options": [
            "0번 건물 벽에 기대어 상황을 지켜본다",
            "1번 간판 아래에서 비를 피한다",
            "2번 건물과 담장에서 최대한 멀리 떨어진다",
            "3번 전봇대를 잡고 균형을 유지한다",
            "4번 차량 안에서 대기한다"
        ],
        "answer": 3,  
        "next_location": None,
        "hint_question": "지진 발생 후 건물 밖으로 대피했을 때 올바른 행동은?"
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


# 제스처-답변 매핑 (원래대로)
GESTURE_TO_ANSWER = {
    "Closed_Fist": 0,      # 주먹 = 0번
    "Pointing_Up": 1,      # 검지 = 1번
    "Victory": 2,          # 브이 = 2번
    "ILoveYou": 3,         # 아이러브유 = 3번
    "Thumb_Up": 4,         # 엄지척 = 4번
}

# ==========================================
# 3. Helper 함수 (퀴즈 로직)
# ==========================================

def fetch_gesture_sync() -> str:
    """Mobius에서 제스처 가져오기"""
    try:
        url = f"http://{MOBIUS_HOST}:{MOBIUS_PORT}/{MOBIUS_CSE}/{MOBIUS_AE}/gesture/la"
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

def handle_llm_hint_request() -> str:
    """Open_Palm 제스처로 LLM 힌트 요청"""
    try:
        mc = get_minecraft_connection()
        if mc is None:
            sys.stderr.write("[LLM] Minecraft 연결 실패\n")
            return "MC_CONNECTION_FAILED"
        
        stage_info = QUIZ_STAGES[current_quiz_stage]
        
        send_chat_message(mc, "")
        send_chat_message(mc, "💡 [LLM 힌트] 요청 중...", color="light_purple", bold=True)
        
        if not RAG_AVAILABLE:
            hint_message = f"💬 {stage_info['hint_question']}"
            send_chat_message(mc, hint_message, color="light_purple")
            sys.stderr.write("[LLM] RAG 모듈을 사용할 수 없습니다.\n")
            return "LLM_HINT_REQUESTED"
        
        # RAG를 사용하여 실제 답변 얻기
        question = stage_info['hint_question']
        sys.stderr.write(f"[LLM] RAG 질문: {question}\n")
        
        answer = get_answer(question)
        sys.stderr.write(f"[LLM] RAG 답변: {answer}\n")
        
        # 답변을 60자 단위로 분할하여 채팅에 표시
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="light_purple")
        send_chat_message(mc, "💡 [LLM 답변]", color="light_purple", bold=True)
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="light_purple")
        lines = [answer[i:i+60] for i in range(0, len(answer), 60)]
        for line in lines[:5]:  # 최대 5줄
            send_chat_message(mc, f"  {line}", color="aqua")
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="light_purple")
        send_chat_message(mc, "")
        
        return "LLM_HINT_REQUESTED"
        
    except Exception as e:
        sys.stderr.write(f"[LLM] Error: {e}\n")
        return f"LLM 오류: {e}"

def process_quiz_gesture_sync(gesture: str) -> str:
    """퀴즈 제스처 처리 (핵심 로직)"""
    global current_quiz_stage

    if gesture == "Thumb_Down" and current_quiz_stage == 0:
        return "START_REQUESTED"
    
    # 무시할 제스처 (Thumb_Down, None, Unknown 등)
    if gesture in ["None", "Unknown"]:
        return f"무시: {gesture}"
    
    # 퀴즈 진행 중이 아니면 무시
    if current_quiz_stage == 0:
        return "퀴즈 대기 중"
    
    if current_quiz_stage >= 3:
        return "게임 완료됨"
    
    # Open_Palm: LLM 힌트 요청
    if gesture == "Open_Palm":
        return handle_llm_hint_request()
    
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
# 4. Helper 함수 (블록 건설 - RCON 미지원)
# ==========================================

def build_block_sync(gesture: str) -> str:
    """RCON은 블록 건설을 지원하지 않습니다"""
    return "오류: RCON 방식에서는 블록 건설을 지원하지 않습니다. /give 명령어를 사용하세요."

# ==========================================
# 5. 백그라운드 모니터
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

                # Thumb_Down으로 퀴즈 시작 (대기 중일 때만)
                if current_gesture == "Thumb_Down" and current_quiz_stage == 0:
                    sys.stderr.write("[Monitor] 퀴즈 시작 요청\n")
                    asyncio.create_task(start_quiz())
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
# 6. MCP 서버 정의
# ==========================================

@asynccontextmanager
async def lifespan(ctx: Context):
    """MCP 서버 생명주기 관리"""
    sys.stderr.write("[MCP Server] Starting...\n")


    # 제스처 모니터 백그라운드 실행
    monitor_task = asyncio.create_task(gesture_monitor())
    
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        sys.stderr.write("[MCP Server] Shutdown.\n")

# FastMCP 인스턴스 생성 (단 한 번만!)
mcp = FastMCP("Minecraft_Quiz_Server", lifespan=lifespan)

# ==========================================
# 7. MCP Resources
# ==========================================

@mcp.resource("mobius://gesture/current")
def get_current_gesture_resource() -> str:
    """현재 제스처 상태"""
    return fetch_gesture_sync()

# ==========================================
# 8. MCP Tools (퀴즈 관련)
# ==========================================

@mcp.tool()
async def start_quiz() -> str:
    """재난 안전 퀴즈 시작"""
    global current_quiz_stage
    
    sys.stderr.write("[Tool] 퀴즈 시작!\n")
    
    try:
        mc = get_minecraft_connection()
        if mc is None:
            sys.stderr.write("[Tool] Minecraft 연결 실패\n")
            return "오류: Minecraft 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요."
        
        # 게임 시작 안내
        send_chat_message(mc, "")
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "🚨  재난 안전 퀴즈 시작  🚨", color="yellow", bold=True)
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "")
        send_chat_message(mc, "📌 제스처로 정답을 선택하세요:", color="green", bold=True)
        send_chat_message(mc, "")
        send_chat_message(mc, "   ✊ 주먹(Closed_Fist) = 0번", color="white")
        send_chat_message(mc, "   ☝️ 검지(Pointing_Up) = 1번", color="white")
        send_chat_message(mc, "   ✌️ 브이(Victory) = 2번", color="white")
        send_chat_message(mc, "   🤟 아이러브유(ILoveYou) = 3번", color="white")
        send_chat_message(mc, "   👍 엄지척(Thumb_Up) = 4번", color="white")
        send_chat_message(mc, "")
        send_chat_message(mc, "💡 손바닥(Open_Palm) = AI 힌트 요청", color="light_purple", bold=True)
        send_chat_message(mc, "")
        send_chat_message(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_chat_message(mc, "")
        
        # Stage 1 퀴즈 표시
        current_quiz_stage = 1  #Stage1 시작
        await asyncio.sleep(1.0)  # 마크 연결 대기(중요)
        await asyncio.to_thread(show_stage_quiz_sync, 1)
        
        return "퀴즈 게임이 시작되었습니다!"
    except Exception as e:
        # 실패 시 상태 복구
        current_quiz_stage = 0
        sys.stderr.write(f"[Tool] 시작 오류 (상태 복구됨): {e}\n")
        return f"오류: {e}"

@mcp.tool()
async def reset_quiz() -> str:
    """퀴즈 초기화"""
    global current_quiz_stage
    current_quiz_stage = 0
    sys.stderr.write("[Tool] 퀴즈 리셋\n")
    
    try:
        mc = get_minecraft_connection()
        if mc is not None:
            send_chat_message(mc, "")
            send_chat_message(mc, "🔄 [시스템] 퀴즈 초기화 완료", color="yellow", bold=True)
            send_chat_message(mc, "")
            return "퀴즈가 초기화되었습니다."
        else:
            return "퀴즈가 초기화되었습니다. (Minecraft 연결 없음)"
    except Exception as e:
        return f"리셋 완료 (연결 실패: {e})"

@mcp.tool()
async def get_quiz_status() -> str:
    """현재 퀴즈 상태"""
    stages = {
        0: "대기 중 (start_quiz로 시작)",
        1: "Stage 1 진행 중",
        2: "Stage 2 진행 중",
        3: "게임 완료!"
    }
    return stages.get(current_quiz_stage, "알 수 없음")

# ==========================================
# 9. MCP Tools (일반 블록 건설)
# ==========================================

@mcp.tool()
async def build_block_action(gesture: str) -> str:
    """제스처로 블록 건설 (일반 모드)"""
    try:
        return await asyncio.to_thread(build_block_sync, gesture)
    except RuntimeError as e:
        raise McpError(ErrorData.INTERNAL_ERROR, str(e))

@mcp.tool()
async def get_gesture_tool() -> str:
    """현재 제스처 확인"""
    return await asyncio.to_thread(fetch_gesture_sync)

# ==========================================
# 10. MCP Prompts
# ==========================================

@mcp.prompt()
def quiz_workflow() -> str:
    """퀴즈 게임 워크플로우"""
    return """
    재난 안전 퀴즈 게임 안내:
    
    1. 'start_quiz' 도구로 게임을 시작합니다.
    2. 제스처 모니터가 자동으로 감지하고 처리합니다.
    
    Stage 1 (가정집-화재):
    - 정답(3번) 시: Stage 2 좌표 채팅 전송
    - 오답 시: X 표시 (채팅+화면) + 재도전
    
    Stage 2 (학교-지진):
    - 정답(3번) 시: CLEAR 표시
    - 오답 시: X 표시 (채팅+화면) + 재도전
    
    제스처 매핑:
    - 주먹(Closed_Fist) = 0번
    - 검지(Pointing_Up) = 1번 
    - 브이(Victory) = 2번 
    - 아이러브유(ILoveYou) = 3번⭐ ⭐ Stage 1 Stage 2 정답!
    - 엄지척(Thumb_Up) = 4번
    - 손바닥(Open_Palm) = 도움 요청 (LLM)
    - 나머지(Thumb_Down 등) = 무시
    """

@mcp.prompt()
def block_building_workflow() -> str:
    """블록 건설 워크플로우"""
    return """
    제스처로 블록을 건설하는 일반 모드:
    
    1. 'get_gesture_tool'로 현재 제스처를 확인합니다.
    2. 'build_block_action'으로 블록을 건설합니다.
    
    제스처별 블록:
    - Open_Palm: 유리
    - Closed_Fist: 돌
    - Thumb_Up: 다이아몬드
    - Thumb_Down: 흑요석
    - Victory: 금 블록
    - ILoveYou: 청금석 블록
    - Pointing_Up: 참나무 판자
    """

# ==========================================
# 11. 실행
# ==========================================

if __name__ == "__main__":
    mcp.run() 
