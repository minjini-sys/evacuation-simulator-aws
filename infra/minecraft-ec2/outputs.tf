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
