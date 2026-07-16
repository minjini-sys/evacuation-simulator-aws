# evacuation-simulator

본 프로젝트는 **제스처 기반 휴먼 디지털 트윈(Human Digital Twin)** 개념을 적용한  
**마인크래프트 재난 대피 훈련 시뮬레이션**이다.

사용자의 **신체 움직임(손 제스처)** 과 **행동 선택 과정**을 디지털 트윈으로 해석하여,  
가상 재난 환경 속에서 **인지–판단–행동 흐름**이 직접 반영되는 훈련 경험을 제공한다.  

LLM은 훈련의 중심이 아닌 **도우미(Assistant)** 역할로 설계되어,  
사용자가 도움을 요청할 때만 안전 교육 문서 기반의 설명을 제공한다.

---


## 시스템 개요

본 시스템은 다음과 같은 흐름으로 구성된다.

1. 사용자가 웹캠 앞에서 손 제스처를 수행
2. 제스처 인식 모듈이 MediaPipe 기반으로 제스처를 분류
3. 제스처 데이터가 Mobius 및 MQTT를 통해 중앙 제어 모듈로 전달
4. 중앙 제어 모듈이 게임 로직을 호출하여 마인크래프트 환경을 제어
5. 필요 시 LLM 도우미가 안전 교육 문서를 근거로 보조 설명 제공

---

## 사용 시나리오 요약

- **1단계 (화재 상황)**  
  제스처로 시나리오 시작 → 화재 대응 퀴즈 → 올바른 행동 시 다음 단계 이동

- **2단계 (연기 가득 찬 복도)**  
  잘못된 행동 시 재도전, 올바른 대피 행동 시 다음 단계로 이동

- **3단계 (지진 상황)**  
  제스처 기반 문제 해결 → 신속 버프 제공 → 안전 지역 도달 시 종료

---

## 폴더 구조
- `gesture_recognition/` : MediaPipe 기반 제스처 인식 → MQTT 발행
- `MCP-Minecraft/` : 중앙 제어 모듈 및 게임 로직 (RCON 제어)
- `AI/` : RAG 기반 답변 생성(룰/법령 문서 기반)
- `IoT_Server/` : Mobius/IoT 연동 및 MQTT 관련 서버 스크립트

---

## AWS IoT Core 전환

기존 Mobius 기반 메시지 중계 구조의 고정 IP 의존성, 단일 중계 지점, 비밀정보 관리 한계를 개선하기 위해 AWS IoT Core 기반 MQTT 경로를 추가했습니다.

자세한 전환 배경과 실행 모드는 [`docs/AWS_IOT_MIGRATION.md`](docs/AWS_IOT_MIGRATION.md)를 참고하세요.

---

## 준비물
- Python 3.x
- Node.js (IoT_Server 사용 시)
- MQTT Broker (예: Mosquitto)
- Minecraft Java Server + RCON 활성화

---

## 환경 설정
### MCP-Minecraft `.env`
`MCP-Minecraft/.env.example`을 복사해서 `.env`를 만들고 값 입력:

- Minecraft RCON 호스트/포트/비밀번호
- MQTT 브로커 주소/포트/토픽
- (사용 시) LLM API Key, Mobius 설정

> ⚠️ `.env`는 보안상 Git에 올리지 않습니다.

---

## 설치
```bash
### 1) mobius 서버 실행
cd IoT_Server
npm install
node .\thyme.js

### 1) 제스처 인식 모듈
cd gesture_recognition
pip install -r requirements.txt
python run_hands.py

### 2) Minecraft 제어 서버
cd MCP-Minecraft
pip install -r requirements.server.txt
python Mcp_Server.py

