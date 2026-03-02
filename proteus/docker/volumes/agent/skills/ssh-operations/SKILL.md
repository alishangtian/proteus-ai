---
name: ssh-operations
description: Comprehensive SSH server connection and operations toolkit. Use when users need to connect to SSH servers, execute remote commands, transfer files via SFTP, create SSH tunnels, manage SSH keys, or implement SSH security best practices. Trigger for tasks involving remote server administration, automation scripts, secure file transfer, port forwarding, and SSH configuration management.
---

# SSH Operations Skill

## Overview

This skill provides comprehensive SSH (Secure Shell) operations capabilities for connecting to remote servers, executing commands, transferring files, creating secure tunnels, and managing SSH keys. It includes both Python-based automation scripts (using Paramiko) and command-line guidance for manual SSH operations.

## When to Use This Skill

- **Remote Server Administration**: Connect to Linux/Unix servers for management tasks
- **Command Execution**: Run commands on remote servers and capture output
- **File Transfer**: Upload/download files securely via SFTP
- **SSH Tunneling**: Create secure port forwarding for accessing restricted services
- **SSH Key Management**: Generate SSH key pairs and deploy to servers
- **Security Hardening**: Implement SSH security best practices
- **Automation Scripts**: Build Python scripts for automated SSH operations
- **Troubleshooting**: Debug SSH connection issues and configuration problems

## Quick Start

### Prerequisites

1. **Python Dependencies**: Install required packages:
   ```bash
   pip install paramiko cryptography
   ```
   Or use the included `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

2. **SSH Server Access**: Ensure you have:
   - Remote server hostname/IP address
   - Valid username and authentication method (password or SSH key)

### Basic Connection Test

Use the `ssh_connect.py` script to test connectivity:

```bash
python scripts/ssh_connect.py --hostname example.com --port 22 --username user --key-file ~/.ssh/id_rsa
```

## Core Capabilities

### 1. SSH Connections

**Script**: `ssh_connect.py`

Establish secure SSH connections using either password or key-based authentication.

```python
from scripts.ssh_connect import ssh_connect

client, transport = ssh_connect(
    hostname="example.com",
    port=22,
    username="user",
    key_filename="/path/to/private/key"
)
```

**Best Practices**:
- Prefer key-based authentication over passwords
- Use non-standard ports to reduce scanning
- Implement connection timeouts

### 2. Remote Command Execution

**Script**: `ssh_command.py`

Execute commands on remote servers and capture output.

```bash
python scripts/ssh_command.py --hostname example.com --username user --key-file ~/.ssh/id_rsa --command "ls -la"
```

**Features**:
- Support for interactive commands (with PTY)
- Configurable timeouts
- Exit code and output capture

### 3. File Transfer via SFTP

**Upload**: `sftp_upload.py`
**Download**: `sftp_download.py`

Transfer files and directories securely.

```bash
# Upload single file
python scripts/sftp_upload.py --hostname example.com --username user --key-file ~/.ssh/id_rsa --local local.txt --remote /tmp/remote.txt

# Download directory recursively
python scripts/sftp_download.py --hostname example.com --username user --key-file ~/.ssh/id_rsa --remote /var/log --local ./logs --recursive
```

### 4. SSH Tunneling (Port Forwarding)

**Script**: `ssh_tunnel.py`

Create secure tunnels for accessing services behind firewalls.

```bash
# Forward local port 8080 to remote server's port 80
python scripts/ssh_tunnel.py --hostname example.com --username user --key-file ~/.ssh/id_rsa --local-port 8080 --remote-host localhost --remote-port 80
```

**Use Cases**:
- Access web interfaces on remote servers
- Secure database connections
- Bypass network restrictions

### 5. SSH Key Management

**Generate Keys**: `generate_ssh_key.py`
**Deploy Keys**: `add_public_key.py`

Manage SSH key pairs for secure authentication.

```bash
# Generate new key pair
python scripts/generate_ssh_key.py --type ed25519 --bits 4096 --private-key id_ed25519 --public-key id_ed25519.pub

# Add public key to server
python scripts/add_public_key.py --hostname example.com --username user --password "yourpass" --public-key-file id_ed25519.pub
```

**Security Notes**:
- Always protect private keys with passphrases
- Set proper file permissions (`chmod 600`)
- Regularly rotate keys

## Security Best Practices

For comprehensive SSH security guidance, see [Best Practices](references/best_practices.md).

**Key Recommendations**:

1. **Authentication**: Use key-based auth, disable passwords
2. **Configuration**: Change default port, disable root login
3. **Monitoring**: Review logs, implement fail2ban
4. **Updates**: Keep SSH software current
5. **Access Control**: Restrict by IP, use firewall rules

## Workflow Examples

### Example 1: Deploy Application Updates

```bash
# 1. Connect and execute deployment script
python scripts/ssh_command.py --hostname prod-server --username deploy --key-file deploy_key --command "/opt/deploy.sh"

# 2. Upload configuration files
python scripts/sftp_upload.py --hostname prod-server --username deploy --key-file deploy_key --local configs/ --remote /opt/app/configs/ --recursive

# 3. Restart service
python scripts/ssh_command.py --hostname prod-server --username deploy --key-file deploy_key --command "sudo systemctl restart app-service"
```

### Example 2: Secure Database Access via Tunnel

```bash
# Create tunnel to database server
python scripts/ssh_tunnel.py --hostname db-gateway --username admin --key-file admin_key --local-port 3307 --remote-host db-internal --remote-port 3306

# Now connect locally to forwarded port
mysql -h 127.0.0.1 -P 3307 -u dbuser -p
```

### Example 3: Audit SSH Configuration

```bash
# Check current SSH configuration
python scripts/ssh_command.py --hostname target-server --username audit --key-file audit_key --command "sudo cat /etc/ssh/sshd_config"

# Compare against best practices (see references/best_practices.md)
```

## Troubleshooting

### Common Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| Connection refused | Firewall blocking, SSH service down | Check firewall, verify sshd running |
| Authentication failed | Wrong credentials, key permissions | Verify key, check `authorized_keys` |
| Host key mismatch | Server changed, MITM attack | Verify server identity, update known_hosts |
| Slow connections | DNS resolution, network issues | Set `UseDNS no`, check latency |

### Debug Mode

Add verbose output to diagnose issues:

```bash
python scripts/ssh_connect.py --hostname example.com --username user --key-file ~/.ssh/id_rsa -v
```

Or use SSH command-line with verbose flags:

```bash
ssh -vvv -i ~/.ssh/id_rsa user@example.com
```

## Reference Materials

### Included References

1. **[Best Practices](references/best_practices.md)**: Comprehensive SSH security guidelines
   - Top 10 best practices
   - Common mistakes to avoid
   - Configuration examples
   - Audit checklist

### External Resources

- [OpenSSH Documentation](https://www.openssh.com/)
- [Paramiko Documentation](http://www.paramiko.org/)
- [SSH.com Academy](https://www.ssh.com/academy/ssh)

## Script Details

### Available Scripts

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `ssh_connect.py` | Establish SSH connections | paramiko |
| `ssh_command.py` | Execute remote commands | paramiko |
| `sftp_upload.py` | Upload files via SFTP | paramiko |
| `sftp_download.py` | Download files via SFTP | paramiko |
| `ssh_tunnel.py` | Create SSH tunnels | paramiko |
| `generate_ssh_key.py` | Generate SSH key pairs | paramiko |
| `add_public_key.py` | Deploy public keys to servers | paramiko |

### Script Usage Patterns

All scripts follow consistent patterns:

```bash
python scripts/<script_name>.py --hostname HOST --username USER [--key-file KEY] [options]
```

**Common Options**:
- `--hostname`: Remote server address (required)
- `--port`: SSH port (default: 22)
- `--username`: SSH username (required)
- `--password`: Password (if using password auth)
- `--key-file`: Path to private key file

## Skill Integration

### With Other Skills

This skill complements:

- **`roo-coder`**: For editing remote files via SSH
- **`security-threat-model`**: For SSH security assessment
- **`memory-system`**: For storing SSH connection details
- **`planning-with-files`**: For complex multi-step SSH operations

### In Automation Workflows

Combine with Python scripting for advanced automation:

```python
from scripts.ssh_connect import ssh_connect
from scripts.ssh_command import execute_remote_command

def deploy_to_servers(servers, command):
    for server in servers:
        client, _ = ssh_connect(**server)
        result = execute_remote_command(client, command)
        print(f"{server['hostname']}: {result['exit_code']}")
        client.close()
```

## Development Notes

### Testing SSH Scripts

1. **Local Testing**: Use Docker with SSH server container
2. **Integration Testing**: Test against staging servers
3. **Security Testing**: Validate against security benchmarks

### Adding New Scripts

Follow the existing pattern:

1. Use argparse for command-line interface
2. Include comprehensive error handling
3. Document function signatures
4. Add to SKILL.md documentation

## Limitations and Considerations

- **Network Dependencies**: Requires network connectivity to target servers
- **Authentication**: Proper credential management is essential
- **Security**: SSH keys must be protected with appropriate permissions
- **Performance**: Large file transfers may require optimization

## Version History

- **1.0.0**: Initial release with core SSH operations
- **Future**: Planned additions include SSH jump hosts, agent forwarding, and certificate-based authentication

---

**Note**: Always follow security best practices when working with SSH. Never hardcode credentials in scripts, use secure credential storage, and regularly audit SSH configurations.
