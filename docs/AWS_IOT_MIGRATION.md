# AWS IoT Core migration plan

## Why migrate

The original simulator sends gesture events through this path:

```text
run_hands.py -> TAS TCP server -> Mobius -> MQTT notification -> Mcp_Server.py -> Minecraft RCON
```

This is useful for a oneM2M/Mobius prototype, but it has operational limits:

- The flow depends on fixed IP addresses for Mobius, Minecraft, and the Flask chat API.
- Mobius becomes a single relay point for gesture events.
- Real-time game control takes a long path: TCP, TAS, Mobius, MQTT notification, then controller.
- Secrets such as RCON passwords and API keys need to be managed outside source code.
- Logs are split across local scripts and servers, which makes failures harder to trace.

## Target flow

The AWS path keeps webcam processing on the user's computer and sends only gesture events to AWS IoT Core:

```text
run_hands.py -> AWS IoT Core MQTT topic -> Mcp_Server.py -> Minecraft RCON
```

The first migration step keeps the controller compatible with both formats:

- Mobius oneM2M notification payloads
- AWS IoT JSON payloads such as `{"gesture": "Right_Open_Palm"}`

## Environment mode

### Existing local TAS mode

```text
GESTURE_OUTPUT_MODE=tas
TAS_HOST=127.0.0.1
TAS_PORT=3105
```

### AWS IoT Core publish mode

```text
GESTURE_OUTPUT_MODE=aws_iot
AWS_IOT_ENDPOINT=your-iot-endpoint-ats.iot.ap-northeast-2.amazonaws.com
AWS_IOT_PORT=8883
AWS_IOT_TOPIC=evacuation/gesture
AWS_IOT_CLIENT_ID=gesture-recognition-client
AWS_IOT_CA_PATH=./certs/AmazonRootCA1.pem
AWS_IOT_CERT_PATH=./certs/device.pem.crt
AWS_IOT_KEY_PATH=./certs/private.pem.key
```

### Controller subscribe mode

```text
MQTT_HOST=your-iot-endpoint-ats.iot.ap-northeast-2.amazonaws.com
MQTT_PORT=8883
MQTT_SUB_TOPIC=evacuation/gesture
MQTT_USE_TLS=true
MQTT_CA_PATH=../certs/AmazonRootCA1.pem
MQTT_CERT_PATH=../certs/device.pem.crt
MQTT_KEY_PATH=../certs/private.pem.key
```

## AWS resources to create next

1. AWS IoT Thing and policy
2. Device certificate, private key, and Amazon Root CA
3. IoT topic: `evacuation/gesture`
4. EC2 Minecraft server with RCON enabled
5. Secrets Manager or Parameter Store values for RCON and API keys
6. CloudWatch log collection for the controller

## Terraform

The first three items can be created with Terraform in [`infra/iot-core`](../infra/iot-core):

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\iot-core
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

The Terraform stack uses Seoul region (`ap-northeast-2`), creates the Thing `gesture-recognition-client`, and grants access to the topic `evacuation/gesture`.

Terraform writes `AmazonRootCA1.pem`, `device.pem.crt`, `private.pem.key`, and `public.pem.key` to `certs/`.

## Portfolio summary

The project improves the original fixed-IP Mobius relay architecture by adding an AWS IoT Core MQTT path. Gesture recognition remains at the edge for low latency and privacy, while gesture events can be routed through AWS with certificate-based authentication and environment-based configuration.
