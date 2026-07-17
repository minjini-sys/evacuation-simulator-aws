data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "minecraft" {
  name        = "${var.project_name}-minecraft-sg"
  description = "Minecraft Java server access"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Minecraft Java server"
    from_port   = var.minecraft_port
    to_port     = var.minecraft_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_player_cidrs
  }

  dynamic "ingress" {
    for_each = length(var.ssh_cidrs) > 0 ? [1] : []

    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.ssh_cidrs
    }
  }

  egress {
    description = "Outbound internet access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-minecraft-sg"
    Project = var.project_name
  }
}

resource "aws_instance" "minecraft" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = var.key_name
  vpc_security_group_ids      = [aws_security_group.minecraft.id]
  associate_public_ip_address = true

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    minecraft_version = var.minecraft_version
    minecraft_port    = var.minecraft_port
    rcon_port         = var.rcon_port
    rcon_password     = var.rcon_password
    memory_min        = var.server_memory_min
    memory_max        = var.server_memory_max
  })

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name    = "${var.project_name}-minecraft"
    Project = var.project_name
  }
}
