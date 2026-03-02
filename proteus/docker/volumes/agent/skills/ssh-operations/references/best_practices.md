# SSH Best Practices and Common Mistakes

## Overview
Secure Shell (SSH) is a critical protocol for secure remote access. Following best practices ensures security, reliability, and maintainability of SSH connections.

## Top 10 SSH Best Practices

### 1. Use Key-Based Authentication (Not Passwords)
- **Why**: Passwords are vulnerable to brute-force attacks and phishing
- **How**: Generate SSH keys with `ssh-keygen -t ed25519` or `ssh-keygen -t rsa -b 4096`
- **Implementation**: 
  - Copy public key to server: `ssh-copy-id user@host`
  - Disable password authentication in `/etc/ssh/sshd_config`:
    ```
    PasswordAuthentication no
    PubkeyAuthentication yes
    ```

### 2. Disable Root Login
- **Why**: Root account is a high-value target for attackers
- **How**: In `/etc/ssh/sshd_config`:
  ```
  PermitRootLogin no
  ```
- **Alternative**: Use `sudo` with regular user accounts

### 3. Change Default SSH Port
- **Why**: Reduces automated scanning and brute-force attacks
- **How**: Change `Port 22` to a non-standard port (e.g., 2222, 7822)
- **Note**: Update firewall rules accordingly

### 4. Use SSH Protocol 2 Only
- **Why**: SSHv1 has known vulnerabilities
- **How**: In `/etc/ssh/sshd_config`:
  ```
  Protocol 2
  ```

### 5. Implement Fail2Ban
- **Why**: Automatically blocks IPs after failed login attempts
- **How**: Install and configure Fail2Ban with SSH jail
- **Result**: Reduces brute-force attack effectiveness

### 6. Use Strong Key Algorithms
- **Preferred**: Ed25519 (modern, fast, secure)
- **Acceptable**: RSA with at least 4096 bits
- **Avoid**: DSA (insecure), RSA with <2048 bits

### 7. Implement Two-Factor Authentication (2FA)
- **Why**: Adds an extra layer of security beyond keys
- **Options**: 
  - Google Authenticator (TOTP)
  - Hardware tokens (YubiKey)
  - Duo Security

### 8. Regularly Rotate SSH Keys
- **Frequency**: Every 6-12 months for user keys, more frequently for service accounts
- **Process**: Generate new keys, distribute, then revoke old keys
- **Tool**: Use `ssh-keygen` to generate replacement keys

### 9. Monitor SSH Logs
- **Where**: `/var/log/auth.log` (Ubuntu/Debian) or `/var/log/secure` (RHEL/CentOS)
- **What to look for**: Failed login attempts, unknown IP addresses, unusual patterns
- **Tools**: `grep`, `fail2ban`, `logwatch`, SIEM integration

### 10. Use SSH Agent Forwarding Cautiously
- **Risk**: Compromised remote server can use forwarded agent
- **Best practice**: Use `-A` flag only when necessary, consider `ProxyJump` instead

## 11 Common SSH Mistakes to Avoid

### 1. Password-Only Authentication
- **Problem**: Vulnerable to brute-force attacks
- **Fix**: Implement key-based authentication

### 2. Allowing Root Login
- **Problem**: Direct root access increases attack surface
- **Fix**: Disable root login, use sudo

### 3. Using Default Port 22
- **Problem**: Constant scanning by bots
- **Fix**: Change to non-standard port

### 4. Weak Key Algorithms
- **Problem**: RSA 1024-bit keys are crackable
- **Fix**: Use Ed25519 or RSA 4096-bit

### 5. No Key Passphrases
- **Problem**: Stolen private key provides immediate access
- **Fix**: Always use strong passphrases, use SSH agent

### 6. Excessive Permissions on Key Files
- **Problem**: Private key world-readable
- **Fix**: `chmod 600 ~/.ssh/id_*`

### 7. No Monitoring/Auditing
- **Problem**: Breaches go undetected
- **Fix**: Regular log review, intrusion detection

### 8. SSH Service Exposed to Internet
- **Problem**: Unnecessary attack surface
- **Fix**: Restrict with firewall, use VPN or bastion host

### 9. Outdated SSH Software
- **Problem**: Known vulnerabilities unpatched
- **Fix**: Regular updates, security patches

### 10. No Connection Timeouts
- **Problem**: Idle sessions remain open
- **Fix**: Set `ClientAliveInterval` and `ClientAliveCountMax`

### 11. Using .rhosts or /etc/hosts.equiv
- **Problem**: Weak authentication mechanisms
- **Fix**: Disable in `sshd_config`: `IgnoreRhosts yes`

## Real-World Examples

### Good Practice Example
```
# Generate strong key
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519 -C "work-laptop"

# Copy to server
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server.example.com -p 2222

# Connect securely
ssh -p 2222 -i ~/.ssh/id_ed25519 user@server.example.com
```

### Bad Practice Example
```
# Weak key generation
ssh-keygen -t rsa -b 1024 -N "" -f ~/.ssh/id_rsa

# Password authentication (in config)
PasswordAuthentication yes
PermitRootLogin yes
```

## Configuration Recommendations

### Client Configuration (`~/.ssh/config`)
```
Host myserver
    HostName server.example.com
    Port 2222
    User myuser
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ForwardAgent no
```

### Server Configuration (`/etc/ssh/sshd_config`)
```
Port 2222
Protocol 2
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
UsePAM yes
AllowUsers myuser adminuser
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
LoginGraceTime 60
```

## Troubleshooting Common Issues

### Connection Refused
- Check firewall: `sudo ufw status`
- Verify SSH service: `sudo systemctl status ssh`
- Confirm port: `netstat -tlnp | grep :22`

### Authentication Failed
- Verify key permissions: `ls -la ~/.ssh/`
- Check authorized_keys: `cat ~/.ssh/authorized_keys`
- Test with verbose: `ssh -vvv user@host`

### Slow Connections
- Disable DNS resolution: `UseDNS no` in sshd_config
- Check network latency: `ping host`
- Consider compression: `-C` flag or `Compression yes`

## Security Audit Checklist
- [ ] Key-based authentication enabled
- [ ] Root login disabled
- [ ] Password authentication disabled
- [ ] Non-default port in use
- [ ] Fail2Ban or similar installed
- [ ] SSH service updated regularly
- [ ] Logs being monitored
- [ ] Firewall restricts access
- [ ] Two-factor authentication considered
- [ ] Key rotation process established

## Additional Resources
- OpenSSH Official Documentation: https://www.openssh.com/
- SSH Communications Security: https://www.ssh.com/
- Mozilla SSH Guidelines: https://infosec.mozilla.org/guidelines/openssh
