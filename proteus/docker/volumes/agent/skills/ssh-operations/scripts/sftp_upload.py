#!/usr/bin/env python3
import paramiko
import sys
import os
import argparse
from stat import S_ISDIR, S_ISREG

def upload_file_sftp(client: paramiko.SSHClient, local_path: str, remote_path: str):
    """
    Upload a file to remote server via SFTP.
    
    Args:
        client: Connected SSHClient instance
        local_path: Path to local file
        remote_path: Path on remote server
    """
    sftp = client.open_sftp()
    try:
        sftp.put(local_path, remote_path)
        print(f"Uploaded {local_path} to {remote_path}")
    finally:
        sftp.close()

def upload_directory_sftp(client: paramiko.SSHClient, local_dir: str, remote_dir: str):
    """
    Upload a directory recursively to remote server via SFTP.
    
    Args:
        client: Connected SSHClient instance
        local_dir: Local directory path
        remote_dir: Remote directory path
    """
    sftp = client.open_sftp()
    
    def upload_recursive(local_path, remote_path):
        if os.path.isdir(local_path):
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass  # Directory may already exist
            
            for item in os.listdir(local_path):
                local_item = os.path.join(local_path, item)
                remote_item = remote_path + '/' + item
                upload_recursive(local_item, remote_item)
        else:
            sftp.put(local_path, remote_path)
            print(f"Uploaded {local_path} to {remote_path}")
    
    try:
        upload_recursive(local_dir, remote_dir)
    finally:
        sftp.close()

def main():
    parser = argparse.ArgumentParser(description='Upload files/directories via SFTP')
    parser.add_argument('--hostname', required=True, help='Remote hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    parser.add_argument('--local', required=True, help='Local file or directory path')
    parser.add_argument('--remote', required=True, help='Remote file or directory path')
    parser.add_argument('--recursive', action='store_true', help='Upload directories recursively')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.local):
        print(f"Local path does not exist: {args.local}")
        sys.exit(1)
    
    # Connect to SSH server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=args.hostname, port=args.port,
                      username=args.username, password=args.password,
                      key_filename=args.key_file)
        
        if args.recursive and os.path.isdir(args.local):
            upload_directory_sftp(client, args.local, args.remote)
        else:
            if os.path.isdir(args.local) and not args.recursive:
                print("Local path is a directory. Use --recursive to upload directories.")
                sys.exit(1)
            upload_file_sftp(client, args.local, args.remote)
            
        print("Upload completed successfully.")
        
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
