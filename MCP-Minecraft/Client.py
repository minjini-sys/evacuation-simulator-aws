import asyncio
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ============================================================
# Client.py (MCP Client Wrapper)
# ------------------------------------------------------------
# ✅ 역할
# - Host.py가 "MCP 서버"와 통신할 때 쓰는 얇은 래퍼 클래스.
# - Server.py를 '별도 프로세스'로 실행(표준입출력 기반)하고,
#   MCP 프로토콜로 list_tools / call_tool / read_resource 등을 호출한다.
#
# ✅ 수정하는 파일인가?
# - 보통은 ❌
# - Server.py에 도구/리소스를 추가하면 Host가 자동으로 탐색하기 때문에,
#   Client는 거의 손댈 필요가 없다.
# ============================================================

class MCPClientWrapper:
    """
    MCP 서버와의 통신을 전담하는 래퍼 클래스.
    서버 연결, 도구/리소스/프롬프트 조회 및 실행을 담당합니다.
    """
    def __init__(self, script_path: str):
        # ------------------------------------------------------------
        # StdioServerParameters:
        # - command: 서버를 실행할 인터프리터(여기선 python)
        # - args: 실행할 서버 파일 경로
        #
        # ✅ 학생 확장 포인트(선택)
        # - python 대신 sys.executable을 쓰면 가상환경 파이썬을 자동 사용 가능
        # - args=[script_path]에 서버 파일명을 바꾸면 다른 서버로 교체 가능
        # ------------------------------------------------------------
        self.server_params = StdioServerParameters(
            command="python",  # 또는 sys.executable
            args=["-X", "utf8", script_path],
        )
        self.session = None
        self._exit_stack = None

    @asynccontextmanager
    async def connect(self):
        """서버와 연결을 맺고 세션을 초기화하는 Context Manager"""
        # ------------------------------------------------------------
        # stdio_client: 서버 프로세스를 실행하고 (read, write) 스트림을 제공
        # ClientSession: MCP 프로토콜 세션(초기화 포함)
        # ------------------------------------------------------------
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                await session.initialize()
                yield self

    async def get_capabilities(self):
        """서버가 가진 모든 능력(도구, 리소스, 프롬프트)을 조회"""
        if not self.session: raise RuntimeError("Not connected")

        # ------------------------------------------------------------
        # list_tools / list_resources / list_prompts:
        # Server.py에 등록된 것들이 그대로 노출된다.
        # ------------------------------------------------------------
        return {
            "tools": await self.session.list_tools(),
            "resources": await self.session.list_resources(),
            "prompts": await self.session.list_prompts(),
        }

    async def call_tool(self, name: str, arguments: dict):
        """도구 실행 요청"""
        if not self.session: raise RuntimeError("Not connected")
        return await self.session.call_tool(name, arguments=arguments)

    async def read_resource(self, uri: str):
        """리소스 읽기 요청"""
        if not self.session: raise RuntimeError("Not connected")
        return await self.session.read_resource(uri)
