data "aws_caller_identity" "current" {}

data "aws_iot_endpoint" "data_ats" {
  endpoint_type = "iot:Data-ATS"
}

data "http" "amazon_root_ca_1" {
  url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
}

locals {
  account_id      = data.aws_caller_identity.current.account_id
  topic_arn       = "arn:aws:iot:${var.aws_region}:${local.account_id}:topic/${var.gesture_topic}"
  topicfilter_arn = "arn:aws:iot:${var.aws_region}:${local.account_id}:topicfilter/${var.gesture_topic}"
  client_arns = [
    for client_id in var.allowed_client_ids :
    "arn:aws:iot:${var.aws_region}:${local.account_id}:client/${client_id}"
  ]
}

resource "aws_iot_thing" "gesture_client" {
  name = var.thing_name
}

resource "aws_iot_certificate" "gesture_client" {
  active = true
}

resource "aws_iot_policy" "gesture_events" {
  name = var.iot_policy_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["iot:Connect"]
        Resource = local.client_arns
      },
      {
        Effect   = "Allow"
        Action   = ["iot:Publish", "iot:Receive"]
        Resource = [local.topic_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["iot:Subscribe"]
        Resource = [local.topicfilter_arn]
      }
    ]
  })
}

resource "aws_iot_policy_attachment" "gesture_events" {
  policy = aws_iot_policy.gesture_events.name
  target = aws_iot_certificate.gesture_client.arn
}

resource "aws_iot_thing_principal_attachment" "gesture_client" {
  thing     = aws_iot_thing.gesture_client.name
  principal = aws_iot_certificate.gesture_client.arn
}

resource "local_sensitive_file" "device_certificate" {
  filename        = "${var.certificate_output_dir}/device.pem.crt"
  content         = aws_iot_certificate.gesture_client.certificate_pem
  file_permission = "0600"
}

resource "local_sensitive_file" "private_key" {
  filename        = "${var.certificate_output_dir}/private.pem.key"
  content         = aws_iot_certificate.gesture_client.private_key
  file_permission = "0600"
}

resource "local_sensitive_file" "public_key" {
  filename        = "${var.certificate_output_dir}/public.pem.key"
  content         = aws_iot_certificate.gesture_client.public_key
  file_permission = "0644"
}

resource "local_file" "amazon_root_ca_1" {
  filename        = "${var.certificate_output_dir}/AmazonRootCA1.pem"
  content         = data.http.amazon_root_ca_1.response_body
  file_permission = "0644"
}
