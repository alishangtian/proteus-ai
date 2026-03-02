#!/usr/bin/env python3
import paramiko
import sys
import os
import argparse

def add_public_key_to_server(client: paramiko.SSHClient, public_key: str, 
                             remote_user: str = None):
    """
    Add public key to remote server's authorized_keys file.
    
    Args:
        client: Connected SSHClient instance
        public_key: Public key string (format: "ssh-rsa AAAA... comment")
        remote_user: Remote username (default: same as SSH connection username)
    """
    if remote_user is None:
        # Get username from connection
        remote_user = client.get_transport().get_username()
    
    # Ensure public key is properly formatted
    public_key = public_key.strip()
    
    # Remote path to authorized_keys
    remote_auth_keys = f"/home/{remote_user}/.ssh/authorized_keys"
    
    # Check if .ssh directory exists, create if not
    stdin, stdout, stderr = client.exec_command(f"mkdir -p ~/.ssh && chmod 700 ~/.ssh")
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"Failed to create .ssh directory: {stderr.read().decode()}")
        return False
    
    # Check if key already exists
    stdin, stdout, stderr = client.exec_command(f"grep -Fx '{public_key}' {remote_auth_keys} 2>/dev/null || true")
    existing_key = stdout.read().decode().strip()
    
    if existing_key:
        print("Public key already exists in authorized_keys")
        return True
    
    # Add key to authorized_keys
    stdin, stdout, stderr = client.exec_command(f'echo "{public_key}" >> {remote_auth_keys}')
    exit_code = stdout.channel.recv_exit_status()
    
    if exit_code == 0:
        # Set proper permissions
        client.exec_command(f"chmod 600 {remote_auth_keys}")
        print(f"Public key added to {remote_auth_keys}")
        return True
    else:
        print(f"Failed to add public key: {stderr.read().decode()}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Add public key to remote server')
    parser.add_argument('--hostname', required=True, help='Remote hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    
    # Options for public key
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--public-key-file', help='Path to public key file')
    group.add_argument('--public-key-string', help='Public key as string')
    
    parser.add_argument('--remote-user', help='Remote username (default: same as SSH username)')
    
    args = parser.parse_args()
    
    # Read public key
    if args.public_key_file:
        if not os.path.exists(args.public_key_file):
            print(f"Public key file not found: {args.public_key_file}")
            sys.exit(1)
        with open(args.public_key_file, 'r') as f:
            public_key = f.read().strip()
    else:
        public_key = args.public_key_string.strip()
    
    # Connect to SSH server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=args.hostname, port=args.port,
                      username=args.username, password=args.password,
                      key_filename=args.key_file)
        
        print(f"Connected to {args.hostname}:{args.port}")
        
        success = add_public_key_to_server(client, public_key, args.remote_user)
        
        if success:
            print("Public key added successfully.")
            print("You can now connect using key-based authentication.")
        else:
            print("Failed to add public key.")
            sys.exit(1)
            
    except paramiko.AuthenticationException:
        print("Authentication failed. Please check credentials.")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
