import asyncio
import requests
import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from mcpi.minecraft import Minecraft
from mcp.server.fastmcp import FastMCP, Context
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

# ============================================================
# Server.py (MCP Server: Tools / Resources / Prompts 제공)
# ------------------------------------------------------------
# ✅ 역할
# - Mobius(oneM2M IoT 서버)에서 데이터를 가져오는 기능을 제공한다.
# - Minecraft를 조작하는 기능을 제공한다.
# - 위 기능을 MCP "Resource" / "Tool" / "Prompt" 형태로 외부(Host)에게 공개한다.
#
# ✅ 가장 많이 수정하는 파일 ✅
# - (1) Mobius에서 가져올 데이터/리소스를 바꾸기: AE, Container, 파싱 로직 수정
# - (2) Minecraft에서 할 행동(조작)을 늘리기: 새로운 @mcp.tool() 추가
# - (3) 표준 절차를 추가/개선: @mcp.prompt() 추가
# ============================================================

# .env 파일 로드
# - 민감한 정보(API 키, 서버 주소 등)는 코드에 박지 말고 .env에서 읽는다.
load_dotenv()

# ==========================================
# 1. 설정 (Configuration)
# ==========================================

# [1] 민감한 정보: 값이 없으면 None
# - Mobius 접속 정보: IP/호스트, CSE 이름, AE 이름, Container 이름, Origin(인증 주체)
MOBIUS_HOST = os.getenv("MOBIUS_HOST") 
MOBIUS_CSE = os.getenv("MOBIUS_CSE")
MOBIUS_AE = os.getenv("MOBIUS_AE")
MOBIUS_CONTAINER = os.getenv("MOBIUS_CONTAINER")
MOBIUS_ORIGIN = os.getenv("MOBIUS_ORIGIN")

# [2] 덜 민감한 정보: 기본값 허용
# - 포트나 로컬 마인크래프트 주소는 기본값을 둔다.
MOBIUS_PORT = int(os.getenv("MOBIUS_PORT", "7579"))
MC_HOST = os.getenv("MC_HOST", "localhost")
MC_PORT = int(os.getenv("MC_PORT", "4711"))

# ==========================================
# [중요] 필수 설정값 검증 (Validation)
# ==========================================
# - 수업 중 실수(예: .env 누락)를 빠르게 잡아내기 위한 안전장치.
required_vars = [
    ("MOBIUS_HOST", MOBIUS_HOST),
    ("MOBIUS_CSE", MOBIUS_CSE),
    ("MOBIUS_AE", MOBIUS_AE)
]

for var_name, var_value in required_vars:
    if not var_value:
        sys.stderr.write(f"[Critical Error] .env 파일에 '{var_name}' 설정이 없습니다.\n")
        sys.exit(1)

# ==========================================
# 2. 동기 Helper 함수
# ==========================================
# ------------------------------------------------------------
# ✅ 왜 "동기(sync) 함수"로 만들어두나?
# - requests, mcpi 같은 라이브러리는 보통 동기 I/O로 동작한다.
# - 그런데 MCP tool 함수는 async로 작성하는 경우가 많아서,
#   async 함수에서 sync 함수를 안전하게 실행하려고 asyncio.to_thread(...)로 감싼다.
# ------------------------------------------------------------

def fetch_emotion_sync() -> str:
    """Mobius에서 감정 값을 가져옵니다."""
    # ------------------------------------------------------------
    # ✅ 현재 로직:
    # - oneM2M의 "la" (latest contentInstance) 엔드포인트에서 최신 값을 읽는다.
    # - 응답 JSON에서 m2m:cin → con 값을 꺼내 문자열로 반환한다.
    #
    # ✅ 학생 확장 포인트(중요):
    # - 감정(emotion) 대신 "다른 AE / 다른 Container"로 바꾸려면:
    #   1) .env에서 MOBIUS_AE, MOBIUS_CONTAINER 를 바꾸고
    #   2) 아래 URL이 자동으로 새 경로를 보게 된다.
    # - 값 구조가 다르면(cin['con']이 JSON 문자열이거나 dict일 수도 있음)
    #   → 여기서 파싱 로직을 바꾸면 된다.
    # ------------------------------------------------------------
    try:
        url = f"http://{MOBIUS_HOST}:{MOBIUS_PORT}/{MOBIUS_CSE}/{MOBIUS_AE}/{MOBIUS_CONTAINER}/la"
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
            return "Neutral"
        return str(cin.get("con", "Neutral"))
    except Exception as e:
        sys.stderr.write(f"[Server Log] Mobius Fetch Failed: {e}\n")
        return "Unknown"

def build_block_sync(target_emotion: str) -> str:
    """마인크래프트에 블록을 설치합니다."""
    # ------------------------------------------------------------
    # ✅ 현재 로직:
    # - 감정 문자열에 따라 미리 정해둔 블록 ID를 고른 뒤
    # - 플레이어 머리 위(y+2)에 블록을 설치한다.
    #
    # ✅ 학생 확장 포인트(중요):
    # - 감정이 아니라 다른 센서값(예: 온도/습도/집중도 등)에 따라
    #   다른 블록을 놓거나, 다른 위치에 놓거나, 여러 블록을 쌓는 등으로 바꿀 수 있다.
    # - 또는 "블록 설치"가 아니라 "채팅 출력", "텔레포트", "타이틀", "파티클" 등
    #   다른 Minecraft 조작 함수로 확장 가능하다.
    # ------------------------------------------------------------
    EMOTION_BLOCKS = {
        "Happy": (57, 0), "Sad": (8, 0), "Angry": (152, 0),
        "Surprised": (41, 0), "Neutral": (1, 0)
    }
    block_info = EMOTION_BLOCKS.get(target_emotion.capitalize(), (1, 0))

    try:
        # Minecraft.create: Minecraft Pi/raspberryjuice API 서버에 접속
        mc = Minecraft.create(address=MC_HOST, port=MC_PORT)
        # 플레이어의 현재 좌표를 가져온다.
        pos = mc.player.getTilePos()
        # pos.y + 2: 플레이어 머리 위 2칸에 블록을 배치
        mc.setBlock(pos.x, pos.y + 2, pos.z, block_info[0], block_info[1])

        # postToChat: 게임 내 채팅창에 메시지 출력
        mc.postToChat(f"[MCP] Built block for {target_emotion}")
        sys.stderr.write(f"[Server Log] Built block {block_info} for {target_emotion}\n")

        return f"Built block ID {block_info[0]} for {target_emotion}"
    except Exception as e:
        # Host로 전달될 수 있도록 에러를 올림
        raise RuntimeError(f"Minecraft connection failed: {e}")

# ==========================================
# 3. MCP 서버 정의
# ==========================================
@asynccontextmanager
async def lifespan(ctx: Context):
    # ------------------------------------------------------------
    # MCP 서버가 시작/종료될 때 로그를 남긴다.
    # ------------------------------------------------------------
    sys.stderr.write(f"[MCP Server] Starting with Tools, Resources, and Prompts...\n")
    yield
    sys.stderr.write("[MCP Server] Shutting down.\n")

# FastMCP: MCP 서버를 빠르게 만들기 위한 래퍼
mcp = FastMCP("Smart_Minecraft_Agent", lifespan=lifespan)

# -------------------------------------------------------
# [Feature 1] Resources
# -------------------------------------------------------
# Resource는 "읽기 전용 데이터"로 보면 된다.
# Host에서는 read_resource("mobius://emotion/current")처럼 URI로 읽을 수 있다.
@mcp.resource("mobius://emotion/current")
def get_current_emotion_resource() -> str:
    """Mobius 센서의 현재 감정 상태를 반환하는 리소스"""
    return fetch_emotion_sync()

# -------------------------------------------------------
# [Feature 2] Tools
# -------------------------------------------------------
# Tool은 "동작(행동)"에 가깝다. (Minecraft 조작 같은 것)
# Host(LLM)는 tool을 호출해 실제 동작을 발생시킬 수 있다.

@mcp.tool()
async def build_block_action(emotion: str) -> str:
    """주어진 감정에 맞춰 마인크래프트에 블록을 건설합니다."""
    # ------------------------------------------------------------
    # asyncio.to_thread: 동기 함수를 별도 스레드에서 실행하여 event loop를 막지 않는다.
    # ------------------------------------------------------------
    try:
        return await asyncio.to_thread(build_block_sync, emotion)
    except RuntimeError as e:
        # MCP 표준 에러 형태로 변환해서 Host에게 전달
        raise McpError(ErrorData.INTERNAL_ERROR, str(e))

@mcp.tool()
async def get_emotion_tool() -> str:
    """(Tool 버전) 현재 감정을 확인합니다."""
    return await asyncio.to_thread(fetch_emotion_sync)

# -------------------------------------------------------
# [Feature 3] Prompts
# -------------------------------------------------------
# Prompt는 "표준 절차(워크플로우)" 텍스트로,
# LLM이 어떤 순서로 tool을 호출해야 하는지 가이드한다.
@mcp.prompt()
def express_emotion_workflow() -> str:
    """감정을 확인하고 블록을 쌓는 표준 절차 프롬프트"""
    return """
    현재 Mobius 센서의 감정을 확인하고, 그에 맞는 블록을 마인크래프트에 건설하세요.

    단계:
    1. 'get_emotion_tool'을 호출하여 현재 감정을 파악하세요.
    2. 파악된 감정 값을 사용하여 'build_block_action' 도구를 실행하세요.
    3. 사용자에게 어떤 감정이었고 무엇을 만들었는지 한 문장으로 보고하세요.
    """

if __name__ == "__main__":
    # FastMCP 서버 실행 (Host가 stdio로 이 프로세스를 실행한다)
    mcp.run()
