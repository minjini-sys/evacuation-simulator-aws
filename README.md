# Evacuation Simulator AWS Migration

Minecraft 기반 재난 대피 시뮬레이터의 제스처 전달 구조를 분석하고, 기존 TAS/Mobius 중심 흐름을 AWS IoT Core 기반 MQTT 흐름으로 개선한 프로젝트입니다.

원본 프로젝트는 웹캠 제스처 인식, Mobius 서버, MQTT, Minecraft RCON, RAG 챗봇이 결합된 구조입니다. 이 fork에서는 제스처 이벤트 전달 경로와 Minecraft 서버 운영 환경을 AWS 기반으로 재설계하는 데 집중했습니다.

## What Changed

기존 흐름은 다음과 같이 TAS와 Mobius를 거쳐 Minecraft 제어 서버로 제스처를 전달했습니다.

```text
run_hands.py
  -> TAS TCP server
  -> Mobius
  -> MQTT notification
  -> Mcp_Server.py
  -> Minecraft RCON
```

AWS 전환 후에는 웹캠 영상 처리는 사용자 PC에 유지하고, 인식된 제스처 이벤트만 AWS IoT Core로 전송합니다.

```text
run_hands.py
  -> AWS IoT Core MQTT topic
  -> MCP controller
  -> Minecraft RCON
  -> Stage quiz trigger
```

이 구조는 원본 영상을 클라우드로 보내지 않고 제스처 결과만 전달하므로 네트워크 사용량과 개인정보 노출 가능성을 줄일 수 있습니다. 또한 인증서 기반 MQTT 연결, Terraform 기반 인프라 재현, EC2 기반 Minecraft 서버 운영을 경험할 수 있도록 구성했습니다.

## Why AWS

이 프로젝트에서 AWS를 적용한 이유는 단순히 배포하기 위해서가 아니라, 기존 구조의 운영상 한계를 개선하기 위해서입니다.

- 고정 IP와 로컬 실행 환경에 의존하던 메시지 전달 구조 개선
- Mobius를 거치는 긴 제스처 전달 경로 단순화
- MQTT 인증서, RCON 비밀번호 같은 민감 정보 분리
- Minecraft 서버와 MCP controller를 재현 가능한 인프라로 배포
- CloudWatch와 systemd를 활용한 서버 상태 확인
- Terraform으로 같은 실험 환경을 다시 만들 수 있는 구조 확보

## Architecture

```text
Local PC
  - webcam
  - MediaPipe gesture recognition
  - run_hands.py
        |
        | MQTT over TLS
        v
AWS IoT Core
  - topic: evacuation/gesture
        |
        | subscribe
        v
EC2
  - Minecraft Java Server
  - MCP controller
  - RCON on localhost:25575
        |
        v
Minecraft Client
  - team member connects to <public-ip>:25565
```

## Verified Result

다음 흐름까지 실제로 검증했습니다.

1. AWS IoT Core MQTT 테스트 클라이언트에서 `evacuation/gesture` topic 구독
2. 로컬 `run_hands.py`에서 웹캠 제스처 인식
3. `Right_Open_Palm` 제스처를 AWS IoT Core로 publish
4. EC2의 MCP controller가 MQTT 메시지 subscribe
5. EC2 Minecraft 서버에 팀원 Minecraft Java 클라이언트 접속
6. 제스처 이벤트 수신 후 Stage 1 퀴즈가 Minecraft 화면에 표시됨

테스트가 끝난 뒤 비용 방지를 위해 Minecraft EC2 stack은 `terraform destroy`로 삭제했습니다. 따라서 현재 접속 가능한 Minecraft 서버는 실행 중이 아닙니다.

## Repository Structure

```text
AI/                    RAG 기반 챗봇 관련 코드
IoT_Server/            기존 TAS/Mobius 연동 코드
MCP-Minecraft/         Minecraft RCON 제어 및 MCP controller
gesture_recognition/   MediaPipe 기반 손 제스처 인식
infra/iot-core/        AWS IoT Core Terraform
infra/minecraft-ec2/   Minecraft EC2 + MCP controller Terraform
scripts/               AWS IoT 테스트 스크립트
docs/                  AWS 전환 설계 문서
```

## AWS Resources

### IoT Core

`infra/iot-core` Terraform stack은 다음 리소스를 생성합니다.

- AWS IoT Thing: `gesture-recognition-client`
- AWS IoT certificate and policy
- MQTT topic access: `evacuation/gesture`
- 로컬 인증서 파일 출력: `certs/`

자세한 내용은 [infra/iot-core/README.md](infra/iot-core/README.md)를 참고하세요.

### Minecraft EC2

`infra/minecraft-ec2` Terraform stack은 다음 리소스를 생성합니다.

- Ubuntu EC2 instance
- Minecraft Java Server
- MCP controller systemd service
- IAM role for SSM Parameter Store access
- Security group for Minecraft port `25565`
- CloudWatch Dashboard

RCON port `25575`는 인터넷에 열지 않고 EC2 내부 `localhost`에서만 사용합니다.

자세한 내용은 [infra/minecraft-ec2/README.md](infra/minecraft-ec2/README.md)를 참고하세요.

## Setup

### 1. AWS IoT Core 생성

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\iot-core
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform apply -var="aws_profile=minjin"
```

apply 후 출력되는 `iot_endpoint` 값을 `gesture_recognition/.env`에 넣습니다.

```env
GESTURE_OUTPUT_MODE=aws_iot
AWS_IOT_ENDPOINT=<iot_endpoint>
AWS_IOT_PORT=8883
AWS_IOT_TOPIC=evacuation/gesture
AWS_IOT_CLIENT_ID=gesture-recognition-client
AWS_IOT_CA_PATH=../certs/AmazonRootCA1.pem
AWS_IOT_CERT_PATH=../certs/device.pem.crt
AWS_IOT_KEY_PATH=../certs/private.pem.key
```

### 2. 로컬 제스처 인식 실행

```powershell
cd C:\GitHub\evacuation-simulator-aws\gesture_recognition
copy .env.example .env
py -3.11 -m venv .venv311
.\.venv311\Scripts\pip.exe install -r requirements.txt
.\.venv311\Scripts\python.exe run_hands.py
```

### 3. AWS IoT publish 테스트

```powershell
cd C:\GitHub\evacuation-simulator-aws
.\gesture_recognition\.venv311\Scripts\python.exe scripts\test_aws_iot_gesture.py
```

AWS IoT Console의 MQTT 테스트 클라이언트에서 `evacuation/gesture`를 구독하면 메시지를 확인할 수 있습니다.

### 4. Minecraft EC2 배포

먼저 SSM Parameter Store에 민감 정보를 `SecureString`으로 저장해야 합니다.

```text
/evacuation-simulator/minecraft/rcon-password
/evacuation-simulator/iot/amazon-root-ca
/evacuation-simulator/iot/device-cert
/evacuation-simulator/iot/private-key
```

그 다음 Minecraft EC2 stack을 생성합니다.

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\minecraft-ec2
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform apply -var="aws_profile=minjin"
terraform output minecraft_server_address
terraform output cloudwatch_dashboard_url
```

`minecraft_server_address` 값을 팀원에게 전달하면 Minecraft Java Edition에서 접속할 수 있습니다.

```text
Multiplayer -> Direct Connection -> <public-ip>:25565
```

## Cost Control

Minecraft EC2 stack은 비용이 발생합니다.

- EC2 instance running time
- EBS volume
- Public IPv4
- CloudWatch metric/dashboard usage

테스트가 끝나면 다음 명령으로 stack을 삭제합니다.

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\minecraft-ec2
terraform destroy -var="aws_profile=minjin"
```

IoT Core와 SSM Parameter Store는 별도 stack/리소스이므로 Minecraft EC2 destroy만으로 삭제되지 않습니다. 완전히 정리하려면 `infra/iot-core`도 destroy하고 SSM Parameter를 별도로 삭제해야 합니다.

## Security Notes

- `.env`, Terraform state, 인증서, private key는 Git에 커밋하지 않습니다.
- RCON password와 AWS IoT private key는 Issue, README, commit message에 기록하지 않습니다.
- EC2 보안 그룹은 Minecraft port `25565`만 외부에 열고, RCON port `25575`는 열지 않습니다.
- AWS IoT 인증서는 학습용 로컬 Terraform state에 저장되므로 state 파일은 반드시 비공개로 관리해야 합니다.

## Documentation

- [AWS IoT Core migration plan](docs/AWS_IOT_MIGRATION.md)
- [AWS IoT Core Terraform](infra/iot-core/README.md)
- [Minecraft EC2 Terraform](infra/minecraft-ec2/README.md)

