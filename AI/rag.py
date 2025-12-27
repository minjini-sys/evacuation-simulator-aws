# llm/rag.py

# 외부 패키지 설치(DLL 오류 방지)
# https://aka.ms/vc14/vc_redist.x64.exe
#
# PDF 파일을 텍스트로 변환하고 청킹(Chunking)하여 문서 조각(청크)을 생성

import os
from dotenv import load_dotenv

_RAG_CHAIN = None
_RAG_ERROR = None


def _init_rag() -> None:
    """RAG 초기화 (최초 호출 시점에만 수행)."""
    global _RAG_CHAIN, _RAG_ERROR
    if _RAG_CHAIN is not None or _RAG_ERROR is not None:
        return

    try:
        # 1) 환경 변수 로드 (.env는 MCP-Minecraft 폴더에 있음)
        load_dotenv(
            dotenv_path=os.path.join(
                os.path.dirname(__file__), "../MCP-Minecraft", ".env"
            )
        )

        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

        # LangChain 브릿지 변수 (ChatGoogleGenerativeAI에서 사용)
        os.environ.setdefault("GOOGLE_API_KEY", gemini_key)

        from langchain_community.document_loaders import PyMuPDFLoader
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnablePassthrough
        from langchain_core.output_parsers import StrOutputParser

        chat_model = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-flash",
            temperature=0,
        )

        # 2) 경로 설정 (항상 llm 폴더 기준)
        base_dir = os.path.dirname(os.path.abspath(__file__))   # llm 폴더
        data_dir = base_dir  # PDF 폴더

        persist_dir = os.path.join(base_dir, "chroma_hs_rules_db")
        db_path = os.path.join(persist_dir, "chroma.sqlite3")

        db_exists = os.path.exists(db_path)

        # 3) 임베딩 모델 (DB 생성/로드 시 필요)
        embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask"
        )

        if db_exists:
            print("기존에 생성한 Vector DB가 존재합니다.")
            vectorstore = Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
            )
        else:
            print("기존에 생성한 Vector DB가 존재하지 않습니다.")
            print("PDF 파일을 Load 하여 새로운 Vector DB를 생성합니다.")
            print("PDF 파일 로드 시작")

            pdf_1 = os.path.join(data_dir, "안전보건교육 교재_한국에스웨이_10월 자료.pdf")
            pdf_2 = os.path.join(data_dir, "자연재해대책법 시행규칙 (2).pdf")

            data_hs_rule_2_01 = PyMuPDFLoader(pdf_1).load()
            data_hs_rule_2_02 = PyMuPDFLoader(pdf_2).load()

            print("[청킹] 변환된 텍스트를 청킹(Chunking)하여 문서 조각(청크) 생성")

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=200,
                chunk_overlap=50,
            )

            chunks_hs_rule_2_01 = text_splitter.split_documents(data_hs_rule_2_01)
            chunks_hs_rule_2_02 = text_splitter.split_documents(data_hs_rule_2_02)

            print("[청크 모으기] 변환된 청크들을 모두 합치기")

            all_chunks = chunks_hs_rule_2_01 + chunks_hs_rule_2_02

            print(f"총 {len(all_chunks)}개의 청크(문서 조각)가 생성되었습니다.")

            print("[임베딩] 청크를 벡터로 변환하고 벡터 DB 생성")

            print("[임베딩] 벡터 DB 생성 시작.. (오래 걸림)")
            vectorstore = Chroma.from_documents(
                documents=all_chunks,
                embedding=embeddings,
                persist_directory=persist_dir,
            )

            print("[임베딩] 벡터 데이터베이스가 성공적으로 생성되었습니다.")

        # 4) 검색기 (retriever) 생성
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        print("[리트리버] 벡터 데이터베이스로 리트리버 구성 완료.")

        # 5) 청크 기반 질의응답 (RAG 체인)
        prompt = ChatPromptTemplate.from_template("""
다음 **컨텍스트**를 사용하여 마지막질문에 답하십시오.
만약 컨텍스트에서 답변을 찾을 수 없다면 모른다고 답하십시오.

**컨텍스트**:
{context}

**질문**:
{question}
""")

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain = (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough(),
            }
            | prompt
            | chat_model
            | StrOutputParser()
        )

        _RAG_CHAIN = rag_chain

    except Exception as e:
        _RAG_ERROR = str(e)


def query_with_rag_invoke(question: str):
    _init_rag()
    if _RAG_ERROR:
        print(f"RAG 초기화 실패: {_RAG_ERROR}")
        return

    print("=" * 30)
    print(f"사용자 질문:\n{question}")
    response = _RAG_CHAIN.invoke(question)
    print(f"\nLLM 답변:\n{response}")
    print("=" * 30)


def query_with_rag_stream(question: str):
    _init_rag()
    if _RAG_ERROR:
        print(f"RAG 초기화 실패: {_RAG_ERROR}")
        return

    print("=" * 30)
    print(f"사용자 질문:\n{question}")
    print("\nLLM 답변:")
    for chunk in _RAG_CHAIN.stream(question):
        print(chunk, end="")
    print()
    print("=" * 30)


def get_answer(question: str) -> str:
    """RAG를 사용하여 질문에 대한 답변 반환."""
    _init_rag()
    if _RAG_ERROR:
        return f"RAG 초기화 실패: {_RAG_ERROR}"

    try:
        response = _RAG_CHAIN.invoke(question)
        return response
    except Exception as e:
        return f"RAG 요청 실패: {e}"


if __name__ == "__main__":
    query_with_rag_invoke(
        "한국에스웨이의 안전보건교육 교재에서 안내한 화재 대응 시 가장 중요한 요소는?"
    )
