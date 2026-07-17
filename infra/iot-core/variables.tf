variable "aws_region" {
  description = "AWS region for IoT Core resources."
  type        = string
  default     = "ap-northeast-2"
}

variable "thing_name" {
  description = "AWS IoT Thing name for the gesture publisher."
  type        = string
  default     = "gesture-recognition-client"
}

variable "iot_policy_name" {
  description = "AWS IoT policy name."
  type        = string
  default     = "evacuation-simulator-iot-policy"
}

variable "gesture_topic" {
  description = "MQTT topic used by gesture recognition and controller."
  type        = string
  default     = "evacuation/gesture"
}

variable "allowed_client_ids" {
  description = "MQTT client IDs allowed to connect with this certificate policy."
  type        = list(string)
  default = [
    "gesture-recognition-client",
    "minecraft-controller",
  ]
}

variable "certificate_output_dir" {
  description = "Local directory where generated IoT certificate files are written."
  type        = string
  default     = "../../certs"
}
