# 재배포 가능 패키지 설치(DLL 오류 예방)
# https://aka.ms/vc14/vc_redist.x64.exe

# PDF 파일을 텍스트로 변환하고 청킹(Chunking) 과정을 통해 문서 조각(청크)을 생성

import os
# import sys
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
#PyMuPDFLoader가 PDF를 페이지 단위 텍스트로 반환하고 결과 타입은 Document 객체 리스트 
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
#GEMINI_API_KEY이 환경변수로 메모리에 올라간다 

PERSIST_DIR = "./chroma_hs_rules_db"
DB_PATH = os.path.join(PERSIST_DIR, "chroma.sqlite3")

db_exists = os.path.exists(DB_PATH)

# 임베딩 모델 (DB 생성/로드 시 반드시 동일해야 함)
embeddings = HuggingFaceEmbeddings(
    model_name="jhgan/ko-sroberta-multitask"
)

if db_exists:
    print("기존에 생성한 Vector DB가 존재합니다.")
    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
    )
else:
    print("기존에 생성한 Vector DB가 존재하지 않습니다.")
    print("PDF 파일들을 Load 하여 새로운 Vector DB를 생성합니다.")
    print("PDF 파일 로드 시작")
    data_hs_rule_2_01  = PyMuPDFLoader("./자연재해대책법 시행규칙 (2).pdf").load()
    data_hs_rule_2_02  = PyMuPDFLoader("./안전보건교육 교재_한국에스웨이_10월 자료.pdf").load()
    print("PDF 파일 로드 완료")

    print("[청킹] 변환된 텍스트를 청킹(Chunking)하여 문서 조각(청크) 생성")

    # 2) 변환된 텍스트를 청킹(Chunking)하여 문서 조각(청크) 생성
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    # 텍스트 데이터를 200자 단위로 분할, 겹치는 부분(overlap)은 50자로 (필요에 따라 조정)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)

    chunks_hs_rule_2_01  = text_splitter.split_documents(data_hs_rule_2_01)
    chunks_hs_rule_2_02  = text_splitter.split_documents(data_hs_rule_2_02)

    print("[청크 머지] 텍스트 데이터로 변환된 청크들을 모두 합치기")

    # 텍스트 데이터로 변환된 청크들을 모두 합치기
    all_chunks = (
        chunks_hs_rule_2_01
        + chunks_hs_rule_2_02
    )

    # 결과 출력
    print(f"총 {len(all_chunks)}개의 청크(문서 조각)가 생성되었습니다.")

    # for i, chunk in enumerate(all_chunks[:3]):  # 처음 3개의 청크만 출력
    #     print(f"청크 {i+1}: {chunk.page_content}")

    # print("\n...\n")  # 생략된 부분 표시

    # for i, chunk in enumerate(all_chunks[-3:]):  # 마지막 3개의 청크만 출력
    #     print(f"청크 {i+1}: {chunk.page_content}")

    print("[임베딩] 청크를 벡터로 변환(임베딩) 및 벡터 데이터베이스에 저장")

    # 임베딩 모델 설정 (한국어 모델 사용)

    print("[임베딩] 벡터 DB 저장 시작.. (오래 걸림)")
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )

    print("[임베딩] 벡터 데이터베이스에 청크가 성공적으로 저장되었습니다.")

# 4) 검색기 (retriever) 생성
retriever = vectorstore.as_retriever(search_kwargs={"k": 3}) # k는 검색할 유사 청크의 개수

print("[리트리버] 벡터 데이터 베이스로 리트리버 구성을 완료했습니다.")

# 5) 청크를 기반으로 질의응답 수행
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
#from langchain_google_genai import ChatGoogleGenerativeAI

chat_model = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash", 
    temperature=0,)

# 프롬프트 템플릿 정의
prompt = ChatPromptTemplate.from_template("""
다음 **컨텍스트**를 사용하여 마지막 질문에 답변하십시오.
만약 컨텍스트에서 답변을 찾을 수 없다면, 모른다고 답변하십시오.

**컨텍스트**:
{context}

**질문**:
{question}
""")

# 검색된 문서 (Document 객체 리스트)를 하나의 문자열로 결합하는 함수
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# RAG 체인 정의 (LCEL 사용)
rag_chain = (
    # 1. 입력 (질문)을 받아 두 개의 키 ('context'와 'question')로 나눕니다.
    {
        "context": retriever | format_docs, # 'context' 키에는 retriever를 통해 문서를 검색하고 format_docs로 문자열화한 결과가 들어갑니다.
        "question": RunnablePassthrough() # 'question' 키에는 사용자의 원본 입력 (질문)이 그대로 들어갑니다.
    }
    # 2. 결과 딕셔너리를 prompt에 대입합니다.
    | prompt
    # 3. 프롬프트를 LLM에 전달하여 답변을 생성합니다.
    | chat_model
    # 4. LLM의 출력을 문자열로 파싱합니다.
    | StrOutputParser()
)

def query_with_rag_invoke(question: str):
    print("="*30)
    print(f"사용자 질문:\n{question}")
    response = rag_chain.invoke(question)
    print(f"\nLLM 답변:\n{response}")
    print("="*30)

def query_with_rag_stream(question: str):
    print("="*30)
    print(f"사용자 질문:\n{question}")
    print(f"\nLLM 답변:")
    for chunk in rag_chain.stream(question):
        print(chunk, end="")
    print()
    print("="*30)

query_with_rag_invoke("화재시 행동요령 알려줘")
