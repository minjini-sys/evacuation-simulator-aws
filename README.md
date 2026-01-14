# evacuation-simulator
Minecraft에서 **제스처 인식**과 **LLM(RAG)** 을 활용해 재난 상황을 체험하며 대피 행동을 학습하는 시뮬레이터입니다.  
손 제스처 입력을 MQTT로 전달하고, Minecraft(RCON) 제어 서버가 이를 받아 **퀴즈/스테이지 진행** 및 **AI 안내(챗봇)** 를 수행합니다.

---

## 폴더 구조
- `gesture_recognition/` : MediaPipe 기반 제스처 인식 → MQTT 발행
- `MCP-Minecraft/` : Minecraft RCON 제어 및 게임 진행(퀴즈/스테이지)
- `AI/` : RAG 기반 답변 생성(룰/법령 문서 기반)
- `IoT_Server/` : Mobius/IoT 연동 및 MQTT 관련 서버 스크립트

---

## 준비물
- Python 3.x
- Node.js (IoT_Server 사용 시)
- MQTT Broker (예: Mosquitto)
- Minecraft Java Server + RCON 활성화

---

## 환경 설정
### 1) MCP-Minecraft `.env`
`MCP-Minecraft/.env.example`을 복사해서 `.env`를 만들고 값 입력:

- Minecraft RCON 호스트/포트/비밀번호
- MQTT 브로커 주소/포트/토픽
- (사용 시) LLM API Key, Mobius 설정

> ⚠️ `.env`는 보안상 Git에 올리지 않습니다.

---

## 설치
### 1) 제스처 인식 모듈
```bash
cd gesture_recognition
pip install -r requirements.txt
