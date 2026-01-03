"""
게임 로직 레이어
- 퀴즈 시스템 (데이터 + 진행)
- Stage 관리 및 전환
- 게임 연출 (지진, 폭죽, 버프 등)
- AI 챗봇 통합
"""

import sys
import asyncio
import math

# ==========================================
# 게임 상태
# ==========================================

class GameState:
    """게임 전역 상태 관리"""
    def __init__(self):
        self.current_quiz_stage = 0  # 0=대기, 1=Stage1, 1.5=이동중, 2=Stage2, 2.5=안전지역이동, 3=완료
        self.stage2_shown = False
        self.earthquake_active = False
        self.game_clear_triggered = False
        self.chatbot_enabled = False
        self.chatbot_processing = False
    
    def reset(self):
        """게임 재시작 시 초기화"""
        self.stage2_shown = False
        self.earthquake_active = False
        self.game_clear_triggered = False
        # chatbot 설정은 유지


# 전역 게임 상태
game_state = GameState()


# ==========================================
# 퀴즈 데이터
# ==========================================

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
        "answer": 3,
        "next_location": {"x": -44, "y": -53, "z": -36}
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
        "answer": 3,
        "next_location": {"x": -54, "y": -60, "z": -61}
    }
}

# 제스처 매핑 (카메라 좌우반전 고려)
GESTURE_TO_ANSWER = {
    "Left_Pointing_Up": 3,   # 실제 오른손 검지 = 3번
    "Left_Victory": 4,       # 실제 오른손 브이 = 4번
    "Left_Thumb_Up": 5,      # 실제 오른손 엄지척 = 5번
    "Right_Pointing_Up": 1,  # 실제 왼손 검지 = 1번
    "Right_Victory": 2,      # 실제 왼손 브이 = 2번
}

START_GESTURE = "Right_Thumb_Up"  # 실제 왼손 엄지척으로 퀴즈 시작
CHATBOT_GESTURES = ["Right_Open_Palm", "Left_Open_Palm"]


# ==========================================
# 퀴즈 로직
# ==========================================

def show_stage_quiz(stage_num: int, get_connection_func, send_message_func):
    """퀴즈 출력 (동기 함수)"""
    if stage_num not in QUIZ_STAGES:
        sys.stderr.write(f"[Quiz] 잘못된 Stage 번호: {stage_num}\n")
        return
    
    stage = QUIZ_STAGES[stage_num]
    mc = get_connection_func()
    if mc is None:
        sys.stderr.write(f"[Quiz] Stage {stage_num} 표시 실패 - MC 연결 없음\n")
        return
    
    send_message_func(mc, "")
    send_message_func(mc, f"📍 STAGE {stage_num}: {stage['name']}", color="gold", bold=True)
    send_message_func(mc, "")
    send_message_func(mc, f"❓ {stage['question']}", color="yellow", bold=True)
    send_message_func(mc, "")
    
    for option in stage['options']:
        send_message_func(mc, f"   {option}", color="white")
    
    send_message_func(mc, "")
    sys.stderr.write(f"[Quiz] Stage {stage_num} 퀴즈 표시 완료\n")


def process_quiz_gesture(gesture: str, get_connection_func, send_message_func) -> str:
    """
    퀴즈 제스처 처리 및 게임 진행
    Returns: 처리 결과 문자열
    """
    # 퀴즈 시작 요청
    if gesture == START_GESTURE and game_state.current_quiz_stage == 0:
        return "START_REQUESTED"
    
    # 퀴즈 진행 중이 아니면 무시
    if game_state.current_quiz_stage == 0:
        return "퀴즈 대기 중"
    
    if game_state.current_quiz_stage >= 3:
        return "게임 완료됨"
    
    # 제스처를 답변 번호로 변환
    if gesture not in GESTURE_TO_ANSWER:
        return f"알 수 없는 제스처: {gesture}"
    
    answer_num = GESTURE_TO_ANSWER[gesture]
    stage_info = QUIZ_STAGES[game_state.current_quiz_stage]
    correct_answer = stage_info["answer"]
    
    try:
        mc = get_connection_func()
        if mc is None:
            sys.stderr.write("[Quiz] Minecraft 연결 실패, 상태 유지\n")
            return "MC_CONNECTION_FAILED"
        
        send_message_func(mc, "")
        send_message_func(mc, f"🎯 [선택] {answer_num}번 선택!", color="gray", bold=True)
        send_message_func(mc, "")
        
        # 정답 체크
        if answer_num == correct_answer:
            sys.stderr.write(f"[Quiz] Stage {game_state.current_quiz_stage} 정답!\n")
            
            if game_state.current_quiz_stage == 1:
                # Stage 1 정답 → 물병 지급 + Stage 2 좌표 전송
                next_loc = stage_info["next_location"]
                
                # 물병 지급
                try:
                    cmd = 'give @a minecraft:splash_potion[potion_contents={potion:"minecraft:water"}] 6'
                    mc.command(cmd)
                    sys.stderr.write("[Quiz] 투척용 물병 6개 지급 완료\n")
                except Exception as e:
                    sys.stderr.write(f"[Quiz] 물약 지급 실패: {e}\n")
                
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="green")
                send_message_func(mc, "✓ [정답!] 잘하셨습니다!", color="green", bold=True)
                send_message_func(mc, "🎁 투척용 물병 6개를 획득했습니다!", color="aqua", bold=True)
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="green")
                send_message_func(mc, "")
                send_message_func(mc, "💡 불을 끈 뒤 나오는 버튼을 눌러 학교 복도로 나가세요!", color="yellow", bold=True)
                send_message_func(mc, "")
                send_message_func(mc, f"📍 다음 장소로 이동하세요:", color="yellow", bold=True)
                send_message_func(mc, f"   X={next_loc['x']}, Y={next_loc['y']}, Z={next_loc['z']}", color="gold")
                send_message_func(mc, "")
                
                game_state.current_quiz_stage = 1.5  # 이동 대기 상태
                return "STAGE1_CORRECT"
                
            elif game_state.current_quiz_stage == 2:
                # Stage 2 정답 → 이동 속도 버프 + 안전지역으로 이동 메시지
                send_message_func(mc, "")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_message_func(mc, "✓ [정답!] 완벽합니다!", color="green", bold=True)
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_message_func(mc, "")
                send_message_func(mc, "⚡ 신속 효과를 받았습니다! (5초)", color="aqua", bold=True)
                mc.command("effect give @a minecraft:speed 5 1")
                send_message_func(mc, "")
                send_message_func(mc, "🏃 지진이 발생했습니다! 빠르게 안전 지역으로 대피하세요!", color="red", bold=True)
                send_message_func(mc, "📍 안전 지역 좌표: X=-54, Y=-60, Z=-61", color="yellow")
                send_message_func(mc, "")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")

                game_state.current_quiz_stage = 2.5
                sys.stderr.write("[Quiz] Stage 2 정답! 안전지역으로 이동 필요\n")
                return "STAGE2_CORRECT"
        
        else:
            # 오답 → X 표시
            send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="red")
            send_message_func(mc, "✗ [오답] 틀렸습니다!", color="red", bold=True)
            send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="red")
            send_message_func(mc, "💪 다시 한번 생각해보세요!", color="yellow")
            send_message_func(mc, "")
            sys.stderr.write(f"[Quiz] Stage {game_state.current_quiz_stage} 오답\n")
            return "WRONG_ANSWER"
            
    except Exception as e:
        sys.stderr.write(f"[Quiz] Error: {e}\n")
        return f"오류: {e}"


# ==========================================
# 게임 시작 및 Stage 관리
# ==========================================

async def start_quiz_game(get_connection_func, send_message_func):
    """퀴즈 게임 시작"""
    sys.stderr.write("[Game] 퀴즈 시작!\n")

    # 게임 상태 초기화
    game_state.reset()
    
    try:
        mc = get_connection_func()
        if mc is None:
            sys.stderr.write("[Game] Minecraft 연결 실패\n")
            return
        
        # 게임 시작 안내
        send_message_func(mc, "")
        send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_message_func(mc, "🚨  재난 안전 퀴즈 시작  🚨", color="yellow", bold=True)
        send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_message_func(mc, "")
        send_message_func(mc, "📌 제스처로 정답을 선택하세요:", color="green", bold=True)
        send_message_func(mc, "")
        send_message_func(mc, "   [실제 왼손]", color="aqua", bold=True)
        send_message_func(mc, "    검지 = 1번", color="white")
        send_message_func(mc, "    브이 = 2번", color="white")
        send_message_func(mc, "")
        send_message_func(mc, "   [실제 오른손]", color="yellow", bold=True)
        send_message_func(mc, "   검지 = 3번 ⭐", color="white")
        send_message_func(mc, "   브이 = 4번", color="white")
        send_message_func(mc, "   엄지척 = 5번", color="white")
        send_message_func(mc, "")
        send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
        send_message_func(mc, "")
        
        # Stage 1 퀴즈 표시
        game_state.current_quiz_stage = 1
        await asyncio.sleep(0.5)
        await asyncio.to_thread(show_stage_quiz, 1, get_connection_func, send_message_func)
        
    except Exception as e:
        game_state.current_quiz_stage = 0
        sys.stderr.write(f"[Game] 시작 오류: {e}\n")


async def check_stage2_arrival(check_location_func, get_connection_func, send_message_func):
    """Stage 1.5 → Stage 2 전환 (플레이어 도착 체크)"""
    if game_state.current_quiz_stage != 1.5:
        return False
    
    if game_state.stage2_shown:
        return False
    
    stage2_loc = QUIZ_STAGES[1]["next_location"]  # Stage 1의 next_location = Stage 2 시작 지점
    if await asyncio.to_thread(check_location_func, stage2_loc['x'], stage2_loc['y'], stage2_loc['z'], 5):
        game_state.stage2_shown = True
        sys.stderr.write("[Game] 플레이어가 Stage 2 위치 도착! 퀴즈 표시 + 지진 시작\n")
        
        try:
            mc = get_connection_func()
            if mc is not None:
                # 지진 시작
                mc.command("scoreboard players set #system shake 1")
                game_state.earthquake_active = True
                sys.stderr.write("[Game] 지진 시작!\n")

                # 연출 메시지
                send_message_func(mc, "")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_message_func(mc, "📍 도착! Stage 2 시작합니다", color="green", bold=True)
                send_message_func(mc, "🔔 지진이 발생했습니다!", color="red", bold=True)
                send_message_func(mc, "침대에서 일찍 일어난 당신  심상치 않는 진동에 일어나게 되는데", color="yellow")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_message_func(mc, "")

                # Stage 2 퀴즈 표시
                await asyncio.sleep(0.3)
                await asyncio.to_thread(show_stage_quiz, 2, get_connection_func, send_message_func)
                game_state.current_quiz_stage = 2
                
        except Exception as e:
            sys.stderr.write(f"[Game] Stage2 표시 실패: {e}\n")
        
        return True
    
    return False


async def check_safe_zone_arrival(check_location_func, get_connection_func, send_message_func):
    """Stage 2.5 → Stage 3 전환 (안전지역 도착 + 게임 클리어)"""
    if game_state.current_quiz_stage != 2.5:
        return False
    
    if game_state.game_clear_triggered:
        return False
    
    safe_zone = {"x": -54, "y": -60, "z": -61}
    if await asyncio.to_thread(check_location_func, safe_zone['x'], safe_zone['y'], safe_zone['z'], 3):
        game_state.game_clear_triggered = True
        game_state.current_quiz_stage = 3
        sys.stderr.write("[Game] 플레이어가 안전지역 도착! 지진 종료 + 밤 + 폭죽\n")
        
        try:
            mc = get_connection_func()
            if mc is not None:
                # 지진 종료
                if game_state.earthquake_active:
                    mc.command("scoreboard players set #system shake 0")
                    game_state.earthquake_active = False
                    sys.stderr.write("[Game] 지진 종료!\n")

                # 밤으로 변경
                mc.command("time set midnight")
                sys.stderr.write("[Game] 시간대를 밤으로 변경\n")

                # 폭죽 발사 (원형 배치)
                firework_colors = [
                    16711680,  # Red
                    16753920,  # Orange
                    16776960,  # Yellow
                    65280,     # Green
                    65535,     # Cyan
                    255,       # Blue
                    8388736,   # Purple
                    16711935,  # Magenta
                ]

                center_forward = 6.0
                radius = 3.0
                up = 1.0
                points = 12

                for i in range(points):
                    angle = (2.0 * math.pi * i) / points
                    left = radius * math.cos(angle)
                    forward = center_forward + (radius * math.sin(angle))
                    color = firework_colors[i % len(firework_colors)]

                    nbt = (
                        "{LifeTime:40,FireworksItem:{id:\"minecraft:firework_rocket\",Count:1b,tag:{Fireworks:{Flight:2b,Explosions:[{Type:1b,Colors:[I;"
                        + str(color)
                        + "]}]}}}}"
                    )

                    cmd = (
                        "execute as @p at @s positioned ^"
                        + f"{left:.2f}"
                        + " ^"
                        + f"{up:.2f}"
                        + " ^"
                        + f"{forward:.2f}"
                        + " run summon minecraft:firework_rocket ~ ~ ~ "
                        + nbt
                    )
                    mc.command(cmd)
                    await asyncio.sleep(0.12)

                sys.stderr.write("[Game] 폭죽 발사 완료\n")

                # 클리어 메시지
                send_message_func(mc, "")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                send_message_func(mc, "🎉 ★★★ CLEAR ★★★ 🎉", color="gold", bold=True)
                send_message_func(mc, "안전 지역에 도착했습니다!", color="green")
                send_message_func(mc, "재난 안전 교육을 완료했습니다!", color="yellow")
                send_message_func(mc, "")
                send_message_func(mc, "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", color="gold")
                sys.stderr.write("[Game] 게임 클리어!\n")
                
        except Exception as e:
            sys.stderr.write(f"[Game] 안전지역 처리 실패: {e}\n")
        
        return True
    
    return False


# ==========================================
# AI 챗봇 통합
# ==========================================

async def handle_chatbot_gesture(gesture: str, get_question_func, get_answer_func, 
                                  get_connection_func, send_message_func):
    """AI 챗봇 제스처 처리 (Open_Palm)"""
    # 이미 처리 중이면 무시
    if game_state.chatbot_processing:
        sys.stderr.write(f"[Chatbot] 이미 처리 중 - 중복 호출 무시\n")
        return
    
    game_state.chatbot_processing = True
    sys.stderr.write(f"[Chatbot] Open_Palm 감지! 채팅 확인 중...\n")
    
    try:
        # 퀴즈 진행 중이면 stage 저장
        saved_quiz_stage = game_state.current_quiz_stage
        
        # 최신 !질문 가져오기
        player, question = await asyncio.to_thread(get_question_func)
        
        if player and question:
            sys.stderr.write(f"[Chatbot] 질문 발견: {player} - {question}\n")
            
            # LLM 호출
            answer = await asyncio.to_thread(get_answer_func, question)
            sys.stderr.write(f"[Chatbot] 답변 완료\n")
            
            # 마인크래프트에 전송
            mc = get_connection_func()
            if mc:
                send_message_func(mc, "")
                send_message_func(mc, f"[AI → {player}]", color="aqua", bold=True)
                
                # 답변을 60자씩 나누어 전송
                chunks = [answer[i:i+60] for i in range(0, len(answer), 60)][:8]
                for chunk in chunks:
                    escaped = chunk.replace('"', '\\"').replace("'", "\\'")
                    send_message_func(mc, escaped, color="white")
                
                if len(answer) > 480:
                    send_message_func(mc, "...(답변이 너무 길어 일부 생략됨)", color="gray")
                send_message_func(mc, "")
                sys.stderr.write(f"[Chatbot] 마인크래프트에 전송 완료\n")
                
                # 답변 완료 후 퀴즈가 진행 중이었다면 안내 메시지만 표시
                if saved_quiz_stage > 0 and saved_quiz_stage < 3:
                    send_message_func(mc, "")
                    send_message_func(mc, "💡 제스처로 답을 선택해주세요!", color="yellow", bold=True)
                    send_message_func(mc, "")
                    sys.stderr.write(f"[Chatbot] 퀴즈 Stage {saved_quiz_stage} 계속 진행 중\n")
        else:
            sys.stderr.write(f"[Chatbot] 처리할 !질문이 없습니다\n")
    
    except Exception as e:
        sys.stderr.write(f"[Chatbot] 오류 발생: {e}\n")
    
    finally:
        # 처리 완료
        game_state.chatbot_processing = False
        sys.stderr.write(f"[Chatbot] 처리 완료 - 다음 호출 가능\n")


def toggle_chatbot(get_connection_func, send_message_func):
    """챗봇 활성화/비활성화 토글"""
    game_state.chatbot_enabled = not game_state.chatbot_enabled
    sys.stderr.write(f"\n[Game] 👎 Thumb_Down 감지! AI 챗봇: {'활성화' if game_state.chatbot_enabled else '비활성화'}\n")
    
    mc = get_connection_func()
    if mc:
        send_message_func(mc, "")
        if game_state.chatbot_enabled:
            send_message_func(mc, "🤖 [AI 챗봇 활성화] Open_Palm으로 질문하세요.", color="green", bold=True)
        else:
            send_message_func(mc, "🚫 [AI 챗봇 비활성화] 퀴즈는 계속 진행됩니다.", color="red", bold=True)
        send_message_func(mc, "")


def auto_enable_chatbot(get_connection_func, send_message_func):
    """챗봇 자동 활성화 (Open_Palm 감지 시)"""
    if not game_state.chatbot_enabled:
        game_state.chatbot_enabled = True
        sys.stderr.write(f"[Game] 🤖 Open_Palm 감지 - AI 챗봇 자동 활성화!\n")
        
        mc = get_connection_func()
        if mc:
            send_message_func(mc, "")
            send_message_func(mc, "🤖 [AI 챗봇 활성화] 질문을 처리합니다.", color="green", bold=True)
            send_message_func(mc, "")
