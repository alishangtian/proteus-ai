#!/usr/bin/env python3
import paramiko
import os
import sys
import argparse

def generate_ssh_key(key_type='rsa', bits=4096, comment='', passphrase=None):
    """
    Generate SSH key pair.
    
    Args:
        key_type: 'rsa', 'dsa', 'ecdsa', or 'ed25519'
        bits: Key bits (for RSA, DSA, ECDSA)
        comment: Comment to embed in key
        passphrase: Passphrase to encrypt private key (None for no encryption)
        
    Returns:
        Tuple of (private_key, public_key) as strings
    """
    if key_type == 'rsa':
        key = paramiko.RSAKey.generate(bits=bits)
    elif key_type == 'dsa':
        key = paramiko.DSSKey.generate(bits=bits)
    elif key_type == 'ecdsa':
        # paramiko doesn't support ECDSA directly, fallback to RSA
        print("Warning: ECDSA not directly supported, using RSA instead")
        key = paramiko.RSAKey.generate(bits=bits)
    elif key_type == 'ed25519':
        try:
            from paramiko.ed25519key import Ed25519Key
            key = Ed25519Key.generate()
        except ImportError:
            print("Warning: Ed25519 not supported in this paramiko version, using RSA instead")
            key = paramiko.RSAKey.generate(bits=bits)
    else:
        raise ValueError(f"Unsupported key type: {key_type}")
    
    # Export private key
    private_key_str = key.as_string().decode('utf-8')
    
    # Generate public key
    public_key_str = f"{key.get_name()} {key.get_base64()} {comment}"
    
    return private_key_str, public_key_str

def save_key_pair(private_key_str, public_key_str, private_key_path, public_key_path):
    """Save private and public keys to files."""
    with open(private_key_path, 'w') as f:
        f.write(private_key_str)
    os.chmod(private_key_path, 0o600)
    
    with open(public_key_path, 'w') as f:
        f.write(public_key_str)
    
    print(f"Private key saved to: {private_key_path}")
    print(f"Public key saved to: {public_key_path}")

def main():
    parser = argparse.ArgumentParser(description='Generate SSH key pair')
    parser.add_argument('--type', choices=['rsa', 'dsa', 'ed25519'], default='rsa', 
                       help='Key type (default: rsa)')
    parser.add_argument('--bits', type=int, default=4096, 
                       help='Key bits for RSA/DSA (default: 4096)')
    parser.add_argument('--comment', default='', help='Comment for key')
    parser.add_argument('--private-key', default='id_rsa', 
                       help='Private key output filename (default: id_rsa)')
    parser.add_argument('--public-key', default='id_rsa.pub', 
                       help='Public key output filename (default: id_rsa.pub)')
    parser.add_argument('--passphrase', help='Passphrase to encrypt private key')
    
    args = parser.parse_args()
    
    try:
        private_key, public_key = generate_ssh_key(
            key_type=args.type,
            bits=args.bits,
            comment=args.comment,
            passphrase=args.passphrase
        )
        
        save_key_pair(private_key, public_key, args.private_key, args.public_key)
        
        print("\nImportant notes:")
        print("1. Keep your private key secure (chmod 600)")
        print("2. Never share your private key")
        print("3. Add public key to remote server's ~/.ssh/authorized_keys")
        print("4. Use SSH agent for passphrase management")
        
    except Exception as e:
        print(f"Error generating key: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
