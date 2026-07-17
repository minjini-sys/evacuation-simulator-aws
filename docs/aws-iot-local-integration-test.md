# AWS IoT Local Integration Test

This document records the local verification path for replacing the Mobius MQTT path with AWS IoT Core.

## Verified Flow

```text
gesture_recognition/run_hands.py
  -> AWS IoT Core MQTT topic: evacuation/gesture
  -> MCP-Minecraft/Mcp_Server.py subscriber
  -> Minecraft RCON localhost:25575
  -> quiz start command
```

Verified on `ap-northeast-2` with:

- AWS IoT endpoint: `a3ed2j3l7hp73c-ats.iot.ap-northeast-2.amazonaws.com`
- Topic: `evacuation/gesture`
- Publisher client ID: `gesture-recognition-client`
- Controller client ID: `minecraft-controller`
- Local Minecraft server: `localhost:25575`

## 1. Start Local Minecraft Server

The local Minecraft runtime is intentionally ignored under `.runtime/`.

Minimum server properties:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=test
server-port=25565
online-mode=false
```

Use Java 21 with Minecraft server `1.21.8`.

## 2. Start MCP Controller

From the repository root:

```powershell
cd .\MCP-Minecraft
.\.venv-mcp\Scripts\python.exe .\Mcp_Server.py
```

Expected log:

```text
[MQTT] 브로커 연결 성공
[MQTT] 토픽 구독 완료: evacuation/gesture
```

## 3. Publish a Test Gesture

From the repository root:

```powershell
.\gesture_recognition\.venv311\Scripts\python.exe .\scripts\test_aws_iot_gesture.py --gesture Right_Open_Palm
```

Expected MCP log:

```text
[MQTT] 제스처 업데이트: Right_Open_Palm
[Monitor] 감지: Right_Open_Palm
[Monitor] 퀴즈 시작 요청
[Game] 퀴즈 시작!
[MC] 새 연결 생성: localhost:25575
[Quiz] Stage 1 퀴즈 표시 완료
```

## Current Result

The following has been verified:

- Terraform created AWS IoT Core resources and certificate files.
- AWS IoT MQTT test client receives messages on `evacuation/gesture`.
- `run_hands.py` publishes detected gestures to AWS IoT Core.
- `Mcp_Server.py` subscribes to AWS IoT Core over MQTT/TLS.
- MCP receives `Right_Open_Palm`, starts the quiz flow, and connects to Minecraft through RCON.

Next work:

- Run Minecraft client and join the local server to visually confirm in-game quiz messages.
- Replace local `.env`-only setup with documented examples.
- Add an EC2 or ECS deployment path for the Minecraft/MCP side.
