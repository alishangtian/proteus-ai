#!/usr/bin/env python3
import paramiko
import sys
import argparse
import threading
import socket
import time

class SSHTunnel:
    def __init__(self, client, local_port, remote_host, remote_port):
        self.client = client
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.transport = client.get_transport()
        self.server_socket = None
        self.running = False
        
    def start(self):
        """Start the SSH tunnel (local port forwarding)."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', self.local_port))
        self.server_socket.listen(10)
        
        self.running = True
        print(f"Tunnel started: localhost:{self.local_port} -> {self.remote_host}:{self.remote_port}")
        print("Press Ctrl+C to stop.")
        
        try:
            while self.running:
                client_socket, client_addr = self.server_socket.accept()
                print(f"New connection from {client_addr}")
                
                # Forward the connection through SSH tunnel
                channel = self.transport.open_channel(
                    'direct-tcpip',
                    (self.remote_host, self.remote_port),
                    client_addr
                )
                
                if channel is None:
                    print(f"Failed to open channel to {self.remote_host}:{self.remote_port}")
                    client_socket.close()
                    continue
                
                # Start bidirectional forwarding
                threading.Thread(target=self.forward, args=(client_socket, channel)).start()
                
        except KeyboardInterrupt:
            print("\nShutting down tunnel...")
        except Exception as e:
            print(f"Tunnel error: {e}")
        finally:
            self.stop()
    
    def forward(self, source, dest):
        """Forward data between source and destination sockets/channels."""
        try:
            while True:
                data = source.recv(1024)
                if not data:
                    break
                dest.send(data)
        except:
            pass
        finally:
            source.close()
            dest.close()
    
    def stop(self):
        """Stop the tunnel."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Tunnel stopped.")

def main():
    parser = argparse.ArgumentParser(description='Create SSH tunnel (port forwarding)')
    parser.add_argument('--hostname', required=True, help='Remote SSH hostname or IP')
    parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    parser.add_argument('--username', required=True, help='Username')
    parser.add_argument('--password', help='Password (if using password auth)')
    parser.add_argument('--key-file', help='Path to private key file')
    
    parser.add_argument('--local-port', type=int, required=True, help='Local port to listen on')
    parser.add_argument('--remote-host', required=True, help='Remote host to forward to')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote port to forward to')
    
    args = parser.parse_args()
    
    # Connect to SSH server
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=args.hostname, port=args.port,
                      username=args.username, password=args.password,
                      key_filename=args.key_file)
        
        print(f"Connected to {args.hostname}:{args.port}")
        
        tunnel = SSHTunnel(client, args.local_port, args.remote_host, args.remote_port)
        tunnel.start()
        
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
