import sys
from rag_core import RAGSystem

def main():
    try:
        rag_system = RAGSystem()
    except FileNotFoundError as e:
        print(f"오류: RAGSystem 초기화 실패 - {e}")
        print("`create_db.py` 스크립트를 실행하여 Vector DB를 먼저 생성해주세요.")
        sys.exit(1)
    except Exception as e:
        print(f"오류: RAGSystem 초기화 중 예상치 못한 오류 발생 - {e}")
        sys.exit(1)

    # Prompt for a single question, then exit
    print("\n--- 챗봇이 준비되었습니다. 질문을 입력하세요. ---")
    try:
        question = input("\n질문: ")
        
        if not question.strip():
            print("질문이 입력되지 않았습니다. 종료합니다.")
            sys.exit(0) # Exit if no question is provided
            
        print("\n답변:")
        # Use stream_answer for real-time response
        for chunk in rag_system.stream_answer(question):
            print(chunk, end="", flush=True)
        print() # Newline after streamed answer
        print("="*50)

    except KeyboardInterrupt:
        print("\n--- 챗봇이 강제 종료됩니다. ---")
        sys.exit(1) # Exit with error code on forced termination
    except Exception as e:
        print(f"--- 오류가 발생했습니다: {e} ---")
        sys.exit(1) # Exit with error code on other exceptions

if __name__ == "__main__":
    main()
