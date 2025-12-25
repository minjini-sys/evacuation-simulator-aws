import asyncio
import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from google.ai.generativelanguage import Part, FunctionResponse

# ============================================================
# Host.py (MCP Host / Agent)
# ------------------------------------------------------------
# ✅ 역할
# - 사용자의 자연어 입력을 받는다.
# - MCP 서버(Server.py)가 제공하는 "도구/리소스/프롬프트" 목록을 조회한다.
# - 그 도구들을 Gemini(LLM)에 등록하고,
# - Gemini가 "어떤 도구를 어떤 인자로 실행할지" 결정하면,
#   실제 실행은 MCP 클라이언트(Client.py)를 통해 서버에 위임한다.
#
# ✅ 주로 수정하는 파일인가?
# - 보통은 ❌ (기본 구조는 그대로 두는 편이 안전)
# - 사용자의 주된 수정 포인트는 .env(Server 쪽 설정) + Server.py(리소스/툴 추가) 쪽이다.
# - 다만, "새로운 MCP 서버 파일로 바꾸기" 같은 경우 script_path만 바꿀 수 있다.
# ============================================================

# [분리된 모듈 가져오기]  → MCP 서버와 통신하는 전용 래퍼(Client.py)
from Client import MCPClientWrapper

# 1. 설정
# ------------------------------------------------------------
# - .env에서 GEMINI_API_KEY를 읽어 Gemini SDK에 등록한다.
# ------------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# 2. 유틸리티 (Gemini에게 “이 도구(tool)를 쓸 때, 어떤 입력(파라미터)을 어떤 형태로 넣어야 하는지”를 알려주는 ‘입력 설명서’를 정리해주는 함수)
def sanitize_schema(schema):
    """Gemini가 이해할 수 있도록 JSON Schema 변환"""
    # ------------------------------------------------------------
    # MCP 도구는 inputSchema(JSON Schema 형태)를 갖는데,
    # Gemini SDK는 일부 필드를 싫어하거나 type 표기 방식이 달라서 변환이 필요할 수 있다.
    # - default/title/anyOf 같은 항목 제거
    # - type을 대문자 형태로 맞춤
    # - properties 내부도 재귀적으로 변환
    # ------------------------------------------------------------
    # ... (기존 sanitize_schema 코드와 동일, 생략) ...
    if isinstance(schema, dict):
        new_schema = {}
        for k, v in schema.items():
            if k in ["default", "title", "anyOf"]: continue
            if k == "type":
                if isinstance(v, str): new_schema[k] = v.upper()
                elif isinstance(v, list): 
                    valid = [t for t in v if t != "null"]
                    new_schema[k] = valid[0].upper() if valid else "STRING"
                continue
            if k == "properties":
                new_schema[k] = {pk: sanitize_schema(pv) for pk, pv in v.items()}
                continue
            if isinstance(v, dict): new_schema[k] = sanitize_schema(v)
            elif isinstance(v, list): new_schema[k] = [sanitize_schema(i) for i in v]
            else: new_schema[k] = v
        return new_schema
    return schema

async def main():
    # MCP 클라이언트 인스턴스 생성 (서버 스크립트 지정)
    # ------------------------------------------------------------
    # ✅ 학생 확장 포인트(선택)
    # - Server.py 말고 Server2.py 같은 파일로 바꾸고 싶다면 아래만 변경하면 된다.
    #   (단, Server2.py도 FastMCP로 실행 가능한 MCP 서버여야 함) => 목적에 따라 여러개의 MCP 서버를 활용할 수 있다.(각각 용도 별로 MCP 서버를 구현)
    # ------------------------------------------------------------
    client_wrapper = MCPClientWrapper(script_path="server.py")

    print("=== Modular MCP Host (Agent) Started ===")

    # 클라이언트 연결 시작
    # ------------------------------------------------------------
    # async with 문을 벗어나면 서버 프로세스/세션도 정리된다.
    # ------------------------------------------------------------
    async with client_wrapper.connect() as mcp:

        # -------------------------------------------------
        # 1. 서버 능력 확인 (Capabilities Discovery)
        # -------------------------------------------------
        # MCP 서버가 제공하는 기능을 "자동 탐색"한다.
        # - tools: 실행 가능한 함수(도구)
        # - resources: 읽을 수 있는 리소스(URI)
        # - prompts: 표준 절차(워크플로우) 텍스트
        caps = await mcp.get_capabilities()
        tools = caps["tools"]
        resources = caps["resources"]
        prompts = caps["prompts"]

        # # -------------------------------------------------
        # # 2. 초기 리소스 읽기 (Context Injection)
        # # -------------------------------------------------
        # 아래 코드는 "처음 시작할 때 상태를 한번 읽어서" 시스템 지침에 넣는 방식.
        # 지금은 수업용으로 '모름'으로 두고, 대화 과정에서 확인하도록 설정되어 있다.
        #
        # try:
        #     res = await mcp.read_resource("mobius://gesture/current")
        #     init_val = res.contents[0].text
        #     state_msg = f"현재 제스처 상태(Resource): {init_val}"
        #     print(f"[System] {state_msg}")
        # except Exception:
        #     state_msg = "현재 제스처 상태: 확인 불가"
        state_msg = "현재 제스처 상태: 모름 (대화 중 확인 필요)"

        # -------------------------------------------------
        # 3. Gemini 구성
        # -------------------------------------------------
        # (1) 서버가 제공하는 '프롬프트 목록'을 시스템 지침에 포함
        # (2) 서버가 제공하는 '도구 목록'을 Gemini에 등록
        # (3) Gemini가 도구 호출을 결정하면, 여기서 실제 실행은 MCP로 위임
        prompt_list_text = "\n".join([f"- {p.name}: {p.description}" for p in prompts.prompts])

        sys_instruct = f"""
        너는 MCP 아키텍처 기반의 IoT 에이전트야.

        [현재 상태]
        {state_msg}

        [사용 가능한 표준 워크플로우]
        {prompt_list_text}

        [지침]
        - 사용자의 의도를 파악하고 적절한 도구(Tool)를 사용해.
        - '제스처 표현' 요청 시 'express_gesture_workflow'를 참고해.
        """

        # 도구 스키마 변환 및 등록
        # ------------------------------------------------------------
        # MCP tool 목록(tools.tools)에 있는 모든 도구를
        # Gemini에 '함수(Function)'처럼 등록한다.
        # → Server.py에 @mcp.tool()을 추가하면, Host는 별도 수정 없이 자동 인식한다.
        # ------------------------------------------------------------
        gemini_tools = [{
            "name": t.name,
            "description": t.description,
            "parameters": sanitize_schema(t.inputSchema)
        } for t in tools.tools]

        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=gemini_tools,
            system_instruction=sys_instruct
        )

        # enable_automatic_function_calling=False
        # ------------------------------------------------------------
        # 자동 호출을 끄고, Host가 "도구 호출 → 실행 → 결과 전달"을 직접 제어한다.
        chat = model.start_chat(enable_automatic_function_calling=False)

        # -------------------------------------------------
        # 4. 대화 루프 (연속 도구 호출 지원)
        # -------------------------------------------------
        # 핵심 아이디어:
        # - 사용자가 채팅으로 요청하면, Gemini가 '도구 호출(function_call)'을 내릴 수 있다.
        # - 그때마다 MCP 서버의 실제 도구를 실행하고, 결과를 Gemini에게 다시 전달한다.
        # - Gemini가 추가 도구 호출을 이어서 할 수도 있으므로 while로 반복한다.
        while True:
            user_input = input("\n[User]: ")
            if user_input.lower() in ["exit", "quit"]: break

            try:
                # (1) Gemini에게 생각 요청 (텍스트 or function_call 응답)
                response = await chat.send_message_async(user_input)

                # Gemini가 도구를 쓰고 싶어하는 동안 계속 반복합니다.
                while response.parts and response.parts[0].function_call:
                    fc = response.parts[0].function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args)

                    print(f" -> [Host] Gemini가 도구 실행 요청: {tool_name}")

                    # (2) MCP 서버 도구 실행을 Client에 위임
                    # ------------------------------------------------------------
                    # 여기서 'tool_name'은 Server.py의 @mcp.tool() 함수명과 동일해야 한다.
                    # 'tool_args'는 그 함수의 입력 파라미터(dict)로 전달된다.
                    # ------------------------------------------------------------
                    try:
                        result = await mcp.call_tool(tool_name, tool_args)
                        # 결과 파싱 (MCP 응답은 content 배열 형태일 수 있음)
                        content = result.content[0].text if result.content else "성공 (반환값 없음)"
                    except Exception as e:
                        content = f"Error: {str(e)}"

                    print(f" -> [Client] 실행 결과: {content}")

                    # (3) 결과를 Gemini에게 보고하고 '다음 행동'을 기다림
                    # ------------------------------------------------------------
                    # Gemini에게 "도구 실행 결과"를 function_response 형태로 전달하면,
                    # Gemini는:
                    # - 사용자에게 최종 답변 텍스트를 줄 수도 있고,
                    # - 추가 도구 호출을 이어서 할 수도 있다.
                    # ------------------------------------------------------------
                    resp_part = Part(function_response=FunctionResponse(
                        name=tool_name, 
                        response={"result": content}
                    ))

                    response = await chat.send_message_async(resp_part)

                # 도구 사용이 끝나면(또는 처음부터 도구 호출이 아니면) 텍스트 출력
                print(f"[Gemini]: {response.text}")

            except Exception as e:
                print(f"[Host Error] {e}")

if __name__ == "__main__":
    # Windows에서는 기본 event loop 정책 이슈가 있어 Selector 정책을 사용한다.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
