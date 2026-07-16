# AWS IoT Core Terraform

This Terraform stack creates the AWS IoT Core resources used by the simulator's AWS path.

## Resources

- AWS IoT Thing: `gesture-recognition-client`
- AWS IoT certificate
- AWS IoT policy for:
  - `iot:Connect`
  - `iot:Publish`
  - `iot:Subscribe`
  - `iot:Receive`
- Policy attachment
- Thing principal attachment
- Local certificate files under `../../certs`
- Amazon Root CA 1 under `../../certs`

## Apply

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\iot-core
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Important security note

`aws_iot_certificate` generates a device certificate and private key. Terraform stores generated values in `terraform.tfstate`, including sensitive material. This is acceptable for a local learning project only if the state file stays private and is never committed.

The repository `.gitignore` excludes Terraform state and generated certificate files.

## Configure gesture publisher

After `terraform apply`, copy the `iot_endpoint` output into `gesture_recognition/.env`.

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

## Configure Minecraft controller

Copy the same endpoint into `MCP-Minecraft/.env`.

```env
MQTT_HOST=<iot_endpoint>
MQTT_PORT=8883
MQTT_SUB_TOPIC=evacuation/gesture
MQTT_USE_TLS=true
MQTT_CLIENT_ID=minecraft-controller
MQTT_CA_PATH=../certs/AmazonRootCA1.pem
MQTT_CERT_PATH=../certs/device.pem.crt
MQTT_KEY_PATH=../certs/private.pem.key
```
