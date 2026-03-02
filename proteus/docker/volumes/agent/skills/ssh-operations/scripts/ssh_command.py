#!/usr/bin/env python3
import paramiko
import sys
import argparse

def execute_remote_command(client: paramiko.SSHClient, command: str, 
                           get_pty: bool = False, timeout: int = 30) -> dict:
    """
    Execute a command on the remote server via SSH.
    
    Args:
        client: Connected SSHClient instance
        command: Command to execute
        get_pty: Whether to request a pseudo-terminal (PTY)
        timeout: Command execution timeout in seconds
        
    Returns:
        Dictionary with keys: 'stdout', 'stderr', 'exit_code'
    """
    stdin, stdout, stderr = client.exec_command(command, get_pty=get_pty, timeout=timeout)
    
    # Wait for command to complete and read output
    stdout_str = stdout.read().decode()
    stderr_str = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    
    return {
        'stdout': stdout_str,
        'stderr': stderr_str,
        'exit_code': exit_code
    }

def main():
    parser = argparse.ArgumentParser(description='Execute command on remote SSH server')
    parser.add_argument('--hostname', required=True, help='Remote hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    parser.add_argument('--command', required=True, help='Command to execute')
    parser.add_argument('--pty', action='store_true', help='Request PTY for interactive commands')
    parser.add_argument('--timeout', type=int, default=30, help='Command timeout in seconds')
    
    args = parser.parse_args()
    
    # Connect to SSH server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=args.hostname, port=args.port,
                      username=args.username, password=args.password,
                      key_filename=args.key_file)
        
        print(f"Executing command: {args.command}")
        result = execute_remote_command(client, args.command, args.pty, args.timeout)
        
        print(f"Exit code: {result['exit_code']}")
        if result['stdout']:
            print("STDOUT:")
            print(result['stdout'])
        if result['stderr']:
            print("STDERR:")
            print(result['stderr'])
            
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
