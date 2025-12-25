import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_vector_db():
    """
    Creates a vector database from PDF files.
    
    IMPORTANT:
    This script requires the following PDF files to be present in the same directory (`AI/`):
    - '자연재해대책법 시행규칙 (2).pdf'
    - '안전보건교육 교재_한국에스웨이_10월 자료.pdf'
    """
    # Load .env file from MCP-Minecraft directory as specified by the user
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'MCP-Minecraft', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    persist_dir = "./chroma_hs_rules_db"
    db_path = os.path.join(persist_dir, "chroma.sqlite3")

    # --- Check if DB already exists ---
    if os.path.exists(db_path):
        print("="*50)
        print(f"Vector DB가 이미 '{db_path}'에 존재합니다.")
        print("새로 생성하려면 기존 'chroma_hs_rules_db' 폴더를 삭제해주세요.")
        print("="*50)
        return

    # --- Check for PDF files ---
    pdf_files = [
        os.path.join(os.path.dirname(__file__), "자연재해대책법 시행규칙 (2).pdf"),
        os.path.join(os.path.dirname(__file__), "안전보건교육 교재_한국에스웨이_10월 자료.pdf")
    ]
    missing_files = [f for f in pdf_files if not os.path.exists(f)]
    
    if missing_files:
        print("="*50)
        print("오류: DB 생성을 위한 PDF 파일이 부족합니다.")
        for f in missing_files:
            print(f"- Missing file: {f}")
        print("\n스크립트 상단 주석을 확인하여 필요한 파일을 준비해주세요.")
        print("="*50)
        # We exit with a specific code for the caller to identify this issue
        exit(99)


    print("--- 새로운 Vector DB 생성을 시작합니다. ---")
    
    # --- 1. Load PDF files ---
    print("--- 1. PDF 파일 로드 중... ---")
    all_docs = []
    for pdf_path in pdf_files:
        try:
            loader = PyMuPDFLoader(pdf_path)
            all_docs.extend(loader.load())
        except Exception as e:
            print(f"오류: '{pdf_path}' 파일 로드에 실패했습니다: {e}")
            return
    print(f"--- 총 {len(all_docs)} 페이지의 문서를 로드했습니다. ---")

    # --- 2. Split documents into chunks ---
    print("--- 2. 문서를 청크(Chunk) 단위로 분할 중... ---")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=50)
    all_chunks = text_splitter.split_documents(all_docs)
    print(f"--- 총 {len(all_chunks)}개의 청크를 생성했습니다. ---")

    # --- 3. Embed chunks and store in Chroma DB ---
    print("--- 3. 임베딩 및 Vector DB 저장 중... (시간이 다소 소요될 수 있습니다) ---")
    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask"
    )

    try:
        Chroma.from_documents(
            documents=all_chunks,
            embedding=embeddings,
            persist_directory=persist_dir,
        )
        print("="*50)
        print(f"성공: Vector DB를 '{persist_dir}'에 성공적으로 생성했습니다.")
        print("="*50)
    except Exception as e:
        print(f"\n오류: Vector DB 생성에 실패했습니다: {e}")
        exit(1) # General error exit code

if __name__ == "__main__":
    create_vector_db()
