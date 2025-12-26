import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

class RAGSystem:
    """
    Encapsulates the RAG (Retrieval Augmented Generation) system,
    including loading the vector database, the embedding model,
    and the LLM, and providing a method to get answers.
    """
    def __init__(self):
        print("--- RAGSystem 초기화 중: 필요한 모델과 DB를 로드합니다. (시간 소요) ---")
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'MCP-Minecraft', '.env')
        load_dotenv(dotenv_path=dotenv_path)

        self.persist_dir = "./chroma_hs_rules_db"
        self.db_path = os.path.join(self.persist_dir, "chroma.sqlite3")

        # Check if the database exists
        if not os.path.exists(self.db_path):
            print("="*50)
            print(f"오류: Vector DB를 찾을 수 없습니다. '{self.persist_dir}'")
            print("`create_db.py` 스크립트를 실행하여 Vector DB를 먼저 생성해주세요.")
            print("="*50)
            raise FileNotFoundError(f"Vector DB not found at {self.db_path}")

        # Embedding model (must be the same as the one used for DB creation)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask"
        )

        self.vectorstore = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
        )
        print("--- Vector DB 로드 완료. ---")

        # Create a retriever
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})
        
        # Initialize LLM
        self.chat_model = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-flash",
            temperature=0,
        )

        # Define a prompt template
        self.prompt = ChatPromptTemplate.from_template(
"""
        다음 **컨텍스트**를 사용하여 마지막 질문에 답변하십시오.
        만약 컨텍스트에서 답변을 찾을 수 없다면, 모른다고 답변하십시오.
        **답변은 핵심만 간추려 한 문장으로 요약해줘.**

        **컨텍스트**:
        {context}

        **질문**:
        {question}
        """
        )

        # Function to combine retrieved documents (list of Document objects) into a single string
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Define the RAG chain (using LCEL)
        self.rag_chain = (
            {
                "context": self.retriever | format_docs,
                "question": RunnablePassthrough()
            }
            | self.prompt
            | self.chat_model
            | StrOutputParser()
        )
        print("--- RAGSystem 초기화 완료. ---")

    def get_answer(self, question: str) -> str:
        """
        Retrieves an answer for the given question using the RAG chain.
        """
        if not question.strip():
            return "질문을 입력해주세요."
        return self.rag_chain.invoke(question)

    def stream_answer(self, question: str):
        """
        Streams the answer for the given question using the RAG chain.
        """
        if not question.strip():
            yield "질문을 입력해주세요."
            return
        yield from self.rag_chain.stream(question)
