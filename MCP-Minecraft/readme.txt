파이썬 버전 3.11의 가상환경 생성하고 실행하기
py -3.11 –m venv 가상환경이름
가상환경이름\Scripts\Activate.ps1

외부 라이브러리 설치
pip install -r requirements.txt --user
(pip install 설치시 --user를 붙혀 관리자 권한으로 설치할 것 (혹은 Anaconda Prompt 관리자 권한으로 실행))

.env 설정하기
나의 gemini api key로 수정하고 저장 [필수]
나의 ae와 cnt 이름으로 수정하고 저장 => 실습 제외, 응용하여 나의 프로젝트 진행 시 수정

MCP 에이전트 실행
python agent.py