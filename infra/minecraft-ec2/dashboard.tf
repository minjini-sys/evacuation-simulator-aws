locals {
  dashboard_name = "${var.project_name}-minecraft-dashboard"
}

resource "aws_cloudwatch_dashboard" "minecraft" {
  dashboard_name = local.dashboard_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          title   = "Minecraft EC2 CPU Utilization"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Average"
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.minecraft.id]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          title   = "Minecraft EC2 Network Traffic"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Sum"
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.minecraft.id, { label = "Network In" }],
            [".", "NetworkOut", ".", ".", { label = "Network Out" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          title   = "Minecraft EC2 Status Checks"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          period  = 60
          stat    = "Maximum"
          metrics = [
            ["AWS/EC2", "StatusCheckFailed", "InstanceId", aws_instance.minecraft.id],
            [".", "StatusCheckFailed_Instance", ".", "."],
            [".", "StatusCheckFailed_System", ".", "."]
          ]
        }
      },
      {
        type   = "text"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          markdown = join("\n", [
            "# Minecraft Server",
            "",
            "- Instance ID: `${aws_instance.minecraft.id}`",
            "- Instance type: `${var.instance_type}`",
            "- Minecraft address: `${aws_instance.minecraft.public_ip}:${var.minecraft_port}`",
            "- RCON port: `${var.rcon_port}` (not exposed by security group)",
            "",
            "Use this dashboard to monitor basic EC2 health while the test server is running."
          ])
        }
      }
    ]
  })
}
