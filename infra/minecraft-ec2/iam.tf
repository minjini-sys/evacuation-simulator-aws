data "aws_caller_identity" "current" {}

locals {
  ssm_parameter_names = [
    var.rcon_password_parameter_name,
    var.iot_ca_parameter_name,
    var.iot_cert_parameter_name,
    var.iot_private_key_parameter_name,
  ]

  ssm_parameter_arns = [
    for name in local.ssm_parameter_names :
    "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${startswith(name, "/") ? name : "/${name}"}"
  ]
}

resource "aws_iam_role" "minecraft" {
  name = "${var.project_name}-minecraft-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name    = "${var.project_name}-minecraft-role"
    Project = var.project_name
  }
}

resource "aws_iam_role_policy" "ssm_parameters" {
  name = "${var.project_name}-read-runtime-parameters"
  role = aws_iam_role.minecraft.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = local.ssm_parameter_arns
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.minecraft.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "minecraft" {
  name = "${var.project_name}-minecraft-profile"
  role = aws_iam_role.minecraft.name
}
