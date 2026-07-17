variable "aws_region" {
  description = "AWS region for the Minecraft EC2 server."
  type        = string
  default     = "ap-northeast-2"
}

variable "aws_profile" {
  description = "Optional AWS CLI profile name to use for Terraform operations."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Name prefix used for EC2 resources."
  type        = string
  default     = "evacuation-simulator"
}

variable "instance_type" {
  description = "EC2 instance type. t3.small is enough for light testing; t3.medium is safer for multiple players."
  type        = string
  default     = "t3.small"
}

variable "minecraft_version" {
  description = "Minecraft Java server version to install."
  type        = string
  default     = "1.21.8"
}

variable "minecraft_port" {
  description = "Minecraft Java server port."
  type        = number
  default     = 25565
}

variable "rcon_port" {
  description = "Minecraft RCON port. This is not opened to the internet by default."
  type        = number
  default     = 25575
}

variable "rcon_password_parameter_name" {
  description = "SSM SecureString parameter name containing the Minecraft RCON password."
  type        = string
  default     = "/evacuation-simulator/minecraft/rcon-password"
}

variable "allowed_player_cidrs" {
  description = "CIDR blocks allowed to connect to the Minecraft server."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidrs" {
  description = "CIDR blocks allowed to SSH into the instance. Keep this restricted to your IP when possible."
  type        = list(string)
  default     = []
}

variable "key_name" {
  description = "Optional existing EC2 key pair name for SSH access."
  type        = string
  default     = null
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GB."
  type        = number
  default     = 20
}

variable "server_memory_min" {
  description = "Minimum JVM heap size for Minecraft."
  type        = string
  default     = "512M"
}

variable "server_memory_max" {
  description = "Maximum JVM heap size for Minecraft."
  type        = string
  default     = "1536M"
}

variable "mcp_repo_url" {
  description = "Git repository URL cloned on EC2 for the MCP controller."
  type        = string
  default     = "https://github.com/minjini-sys/evacuation-simulator-aws.git"
}

variable "mcp_repo_branch" {
  description = "Git branch cloned on EC2 for the MCP controller."
  type        = string
  default     = "codex/aws-iot-gesture-path"
}

variable "mcp_mqtt_topic" {
  description = "AWS IoT MQTT topic subscribed by the MCP controller."
  type        = string
  default     = "evacuation/gesture"
}

variable "mcp_mqtt_client_id" {
  description = "MQTT client ID used by the MCP controller."
  type        = string
  default     = "minecraft-controller"
}

variable "iot_ca_parameter_name" {
  description = "SSM SecureString parameter name containing the AWS IoT root CA PEM."
  type        = string
  default     = "/evacuation-simulator/iot/amazon-root-ca"
}

variable "iot_cert_parameter_name" {
  description = "SSM SecureString parameter name containing the AWS IoT device certificate PEM."
  type        = string
  default     = "/evacuation-simulator/iot/device-cert"
}

variable "iot_private_key_parameter_name" {
  description = "SSM SecureString parameter name containing the AWS IoT private key PEM."
  type        = string
  default     = "/evacuation-simulator/iot/private-key"
}
