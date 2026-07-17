output "instance_id" {
  description = "Minecraft EC2 instance ID."
  value       = aws_instance.minecraft.id
}

output "public_ip" {
  description = "Public IPv4 address for Minecraft clients."
  value       = aws_instance.minecraft.public_ip
}

output "minecraft_server_address" {
  description = "Address to use from Minecraft Java Edition."
  value       = "${aws_instance.minecraft.public_ip}:${var.minecraft_port}"
}

output "ssh_command" {
  description = "SSH command when key_name and ssh_cidrs are configured."
  value       = var.key_name == null ? "SSH key pair not configured" : "ssh ubuntu@${aws_instance.minecraft.public_ip}"
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch Dashboard name for the Minecraft EC2 server."
  value       = aws_cloudwatch_dashboard.minecraft.dashboard_name
}

output "cloudwatch_dashboard_url" {
  description = "AWS Console URL for the Minecraft CloudWatch Dashboard."
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.minecraft.dashboard_name}"
}
