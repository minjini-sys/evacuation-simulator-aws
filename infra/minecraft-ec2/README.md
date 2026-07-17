# Minecraft EC2 Terraform

This stack creates a small EC2-based Minecraft Java server and MCP controller for the evacuation simulator.

The goal is to move the Minecraft/RCON side away from a local-only `localhost` setup:

```text
gesture_recognition on local PC
  -> AWS IoT Core
  -> MCP controller on EC2
  -> Minecraft Java server on the same EC2 instance
```

MCP and Minecraft run on the same instance so RCON stays private on `localhost:25575`.

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
- MCP controller deployment
  - clones this repository
  - installs `MCP-Minecraft/requirements.server.txt`
  - writes runtime `.env`
  - starts `mcp-minecraft.service`
- IAM role and instance profile
  - lets EC2 read only the required SSM Parameter Store values
  - enables Session Manager access without opening SSH
- SSM Parameter Store integration
  - RCON password
  - AWS IoT root CA
  - AWS IoT device certificate
  - AWS IoT private key
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

## Sensitive Values

Sensitive runtime values are not stored in Terraform variables, user data, or Git.

Create these SSM Parameter Store parameters before `terraform apply`:

```text
/evacuation-simulator/minecraft/rcon-password
/evacuation-simulator/iot/amazon-root-ca
/evacuation-simulator/iot/device-cert
/evacuation-simulator/iot/private-key
```

Use `SecureString` for all four values.

Example shape:

```powershell
aws ssm put-parameter `
  --profile minjin `
  --region ap-northeast-2 `
  --name "/evacuation-simulator/minecraft/rcon-password" `
  --type "SecureString" `
  --value "<hidden-rcon-password>"
```

For certificate values, store the PEM file contents as the parameter value. Do not commit the PEM files.

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

Keep the SSM parameter names in `terraform.tfvars`. Do not put the secret values there.

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

The MCP service uses:

```text
MC_HOST=localhost
MC_RCON_PORT=25575
```

This keeps RCON private to the instance while exposing only the Minecraft gameplay port `25565`.

## Services

After the instance boots:

```bash
systemctl status minecraft
systemctl status mcp-minecraft
journalctl -u mcp-minecraft -f
```

Prefer AWS Systems Manager Session Manager for shell access. SSH is optional and disabled unless `ssh_cidrs` is set.

## Stop or Destroy

To stop paying for compute while keeping the server disk:

```powershell
aws ec2 stop-instances --instance-ids <instance-id> --region ap-northeast-2
```

To delete all resources created by this stack:

```powershell
terraform destroy
```
