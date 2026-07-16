output "aws_region" {
  description = "AWS region used for the deployment."
  value       = var.aws_region
}

output "iot_endpoint" {
  description = "AWS IoT Core data endpoint hostname."
  value       = data.aws_iot_endpoint.data_ats.endpoint_address
}

output "gesture_topic" {
  description = "MQTT topic for gesture events."
  value       = var.gesture_topic
}

output "thing_name" {
  description = "AWS IoT Thing name."
  value       = aws_iot_thing.gesture_client.name
}

output "publisher_client_id" {
  description = "Client ID to use from gesture_recognition/run_hands.py."
  value       = var.thing_name
}

output "controller_client_id" {
  description = "Client ID to use from MCP-Minecraft/Mcp_Server.py."
  value       = "minecraft-controller"
}

output "certificate_output_dir" {
  description = "Local directory where Terraform writes IoT certificate files."
  value       = abspath(var.certificate_output_dir)
}
