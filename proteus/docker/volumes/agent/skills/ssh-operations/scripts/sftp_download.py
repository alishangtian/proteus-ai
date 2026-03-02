#!/usr/bin/env python3
import paramiko
import sys
import os
import argparse
from stat import S_ISDIR, S_ISREG

def download_file_sftp(client: paramiko.SSHClient, remote_path: str, local_path: str):
    """
    Download a file from remote server via SFTP.
    
    Args:
        client: Connected SSHClient instance
        remote_path: Path on remote server
        local_path: Local path to save file
    """
    sftp = client.open_sftp()
    try:
        sftp.get(remote_path, local_path)
        print(f"Downloaded {remote_path} to {local_path}")
    finally:
        sftp.close()

def download_directory_sftp(client: paramiko.SSHClient, remote_dir: str, local_dir: str):
    """
    Download a directory recursively from remote server via SFTP.
    
    Args:
        client: Connected SSHClient instance
        remote_dir: Remote directory path
        local_dir: Local directory path
    """
    sftp = client.open_sftp()
    
    def download_recursive(remote_path, local_path):
        try:
            attrs = sftp.stat(remote_path)
        except IOError:
            print(f"Remote path not found: {remote_path}")
            return
        
        if S_ISDIR(attrs.st_mode):
            os.makedirs(local_path, exist_ok=True)
            
            for item in sftp.listdir(remote_path):
                remote_item = remote_path + '/' + item
                local_item = os.path.join(local_path, item)
                download_recursive(remote_item, local_item)
        else:
            sftp.get(remote_path, local_path)
            print(f"Downloaded {remote_path} to {local_path}")
    
    try:
        download_recursive(remote_dir, local_dir)
    finally:
        sftp.close()

def main():
    parser = argparse.ArgumentParser(description='Download files/directories via SFTP')
    parser.add_argument('--hostname', required=True, help='Remote hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    parser.add_argument('--remote', required=True, help='Remote file or directory path')
    parser.add_argument('--local', required=True, help='Local file or directory path')
    parser.add_argument('--recursive', action='store_true', help='Download directories recursively')
    
    args = parser.parse_args()
    
    # Connect to SSH server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=args.hostname, port=args.port,
                      username=args.username, password=args.password,
                      key_filename=args.key_file)
        
        if args.recursive:
            download_directory_sftp(client, args.remote, args.local)
        else:
            download_file_sftp(client, args.remote, args.local)
            
        print("Download completed successfully.")
        
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
