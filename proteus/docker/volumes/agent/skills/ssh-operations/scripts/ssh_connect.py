#!/usr/bin/env python3
import paramiko
import sys
import socket
import logging
from typing import Optional, Tuple

def ssh_connect(hostname: str, port: int = 22, username: str = None, 
                password: str = None, key_filename: str = None, 
                timeout: float = 10.0) -> Tuple[paramiko.SSHClient, paramiko.Transport]:
    """
    Establish an SSH connection to a remote server.
    
    Args:
        hostname: Remote server hostname or IP address
        port: SSH port (default: 22)
        username: Username for authentication
        password: Password for authentication (if using password auth)
        key_filename: Path to private key file (if using key-based auth)
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (SSHClient, Transport) objects
        
    Raises:
        paramiko.AuthenticationException: If authentication fails
        paramiko.SSHException: For SSH protocol errors
        socket.error: For network errors
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=hostname, port=port, username=username,
                      password=password, key_filename=key_filename,
                      timeout=timeout, allow_agent=True, look_for_keys=True)
        transport = client.get_transport()
        return client, transport
    except Exception as e:
        client.close()
        raise

def test_connection():
    """Test the SSH connection with command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(description='Test SSH connection')
    parser.add_argument('--hostname', required=True, help='Remote hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    
    args = parser.parse_args()
    
    try:
        client, transport = ssh_connect(
            hostname=args.hostname,
            port=args.port,
            username=args.username,
            password=args.password,
            key_filename=args.key_file
        )
        print(f"Successfully connected to {args.hostname}:{args.port}")
        print(f"Transport active: {transport.is_active()}")
        
        # Try a simple command
        stdin, stdout, stderr = client.exec_command('echo "Hello from SSH"')
        output = stdout.read().decode().strip()
        print(f"Test command output: {output}")
        
        client.close()
        print("Connection closed.")
        
    except paramiko.AuthenticationException:
        print("Authentication failed. Please check credentials.")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"SSH error: {e}")
        sys.exit(1)
    except socket.error as e:
        print(f"Network error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
