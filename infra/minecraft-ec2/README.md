# Minecraft EC2 Terraform

This stack creates a small EC2-based Minecraft Java server for the evacuation simulator.

The goal is to move the Minecraft/RCON side away from a local-only `localhost` setup:

```text
gesture_recognition on local PC
  -> AWS IoT Core
  -> MCP controller
  -> Minecraft Java server on EC2
```

This first step provisions the Minecraft server itself. The MCP controller can then be moved onto the same EC2 instance or deployed separately.

## Resources

- Default VPC lookup
- Security group
  - opens Minecraft port `25565`
  - does not open RCON `25575` to the internet
  - optionally opens SSH `22` only when `ssh_cidrs` is set
- Ubuntu 24.04 EC2 instance
- Encrypted gp3 root EBS volume
- cloud-init user data that installs Java 21 and Minecraft server `1.21.8`
- systemd service: `minecraft.service`
- CloudWatch Dashboard
  - CPU utilization
  - Network In/Out
  - EC2 status checks
  - Minecraft connection address summary

## Cost Notes

This stack creates billable AWS resources.

- EC2 charges while the instance is running.
- EBS charges while the volume exists.
- Public IPv4 usage may also be charged.

For short tests, run `terraform destroy` when finished.

## Usage

```powershell
cd C:\GitHub\evacuation-simulator-aws\infra\minecraft-ec2
copy terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars
terraform init
terraform plan
terraform apply
```

If your default AWS CLI profile is not the target account, set this in `terraform.tfvars`:

```hcl
aws_profile = "minjin"
```

After apply:

```powershell
terraform output minecraft_server_address
terraform output cloudwatch_dashboard_url
```

Use that value in Minecraft Java Edition:

```text
Multiplayer -> Direct Connection -> <public-ip>:25565
```

Open the CloudWatch dashboard URL to monitor the EC2 server while the test is running.

## RCON

RCON is enabled for the MCP controller, but port `25575` is not exposed in the security group.

Recommended deployment path:

1. Keep `MC_HOST=localhost` on the EC2 instance.
2. Run `MCP-Minecraft/Mcp_Server.py` on the same EC2 instance.
3. Configure AWS IoT certificates and `.env` on the EC2 instance.

This keeps RCON private to the instance while exposing only the Minecraft gameplay port.

## Stop or Destroy

To stop paying for compute while keeping the server disk:

```powershell
aws ec2 stop-instances --instance-ids <instance-id> --region ap-northeast-2
```

To delete all resources created by this stack:

```powershell
terraform destroy
```
