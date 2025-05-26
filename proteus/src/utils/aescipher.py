import os
import base64
from typing import Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class AESCipher:
    @staticmethod
    def generate_key(key_length: int = 32) -> str:
        """
        生成随机AES密钥并返回Base64编码字符串
        :param key_length: 密钥长度（16/24/32对应AES-128/192/256）
        :return: Base64编码的密钥字符串
        """
        if key_length not in (16, 24, 32):
            raise ValueError("Invalid key length, must be 16, 24 or 32 bytes")
        key = os.urandom(key_length)
        return base64.b64encode(key).decode("utf-8")

    @staticmethod
    def encrypt_string(
        plaintext: str, password: Optional[str] = None, key: Optional[str] = None
    ) -> str:
        """
        加密字符串
        :param plaintext: 要加密的明文
        :param password: 加密密码（与密钥二选一）
        :param key: Base64编码的密钥字符串（与密码二选一）
        :return: Base64编码的加密字符串
        """
        if bool(password) == bool(key):
            raise ValueError("必须指定密码或密钥中的一个，且不能同时指定")

        # 处理密钥解码
        raw_key = None
        if key:
            try:
                raw_key = base64.b64decode(key)
            except Exception as e:
                raise ValueError("无效的Base64密钥格式") from e

            if len(raw_key) not in (16, 24, 32):
                raise ValueError("无效的密钥长度，解码后必须是16、24或32字节")

        data = plaintext.encode("utf-8")
        iv = os.urandom(16)
        salt = None

        # 密钥派生处理
        if password:
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend(),
            )
            raw_key = kdf.derive(password.encode("utf-8"))

        # 数据填充
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()

        # 执行加密
        cipher = Cipher(
            algorithms.AES(raw_key), modes.CBC(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # 组装最终数据
        encrypted_data = (salt + iv + ciphertext) if password else (iv + ciphertext)
        return base64.b64encode(encrypted_data).decode("utf-8")

    @staticmethod
    def decrypt_string(
        ciphertext: str, password: Optional[str] = None, key: Optional[str] = None
    ) -> str:
        """
        解密字符串
        :param ciphertext: Base64编码的加密字符串
        :param password: 解密密码（与密钥二选一）
        :param key: Base64编码的密钥字符串（与密码二选一）
        :return: 解密后的原始字符串
        """
        if bool(password) == bool(key):
            raise ValueError("必须指定密码或密钥中的一个，且不能同时指定")

        # 处理密钥解码
        raw_key = None
        if key:
            try:
                raw_key = base64.b64decode(key)
            except Exception as e:
                raise ValueError("无效的Base64密钥格式") from e

            if len(raw_key) not in (16, 24, 32):
                raise ValueError("无效的密钥长度，解码后必须是16、24或32字节")

        encrypted_data = base64.b64decode(ciphertext)

        # 解析加密数据
        if password:
            if len(encrypted_data) < 48:
                raise ValueError("无效的加密数据长度")
            salt = encrypted_data[:16]
            iv = encrypted_data[16:32]
            ciphertext = encrypted_data[32:]

            # 密钥派生
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend(),
            )
            raw_key = kdf.derive(password.encode("utf-8"))
        else:
            if len(encrypted_data) < 16:
                raise ValueError("无效的加密数据长度")
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]

        # 执行解密
        cipher = Cipher(
            algorithms.AES(raw_key), modes.CBC(iv), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # 去除填充
        unpadder = padding.PKCS7(128).unpadder()
        try:
            data = unpadder.update(padded_data) + unpadder.finalize()
        except ValueError:
            raise ValueError("解密失败，可能是密码错误或数据损坏")

        return data.decode("utf-8")


# 使用示例
# if __name__ == "__main__":
    # # 生成并保存密钥
    # base64_key = AESCipher.generate_key(32)
    # print("生成的Base64密钥:", base64_key)

    # # 使用密钥加密示例
    # encrypted = AESCipher.encrypt_string("机密信息", key=base64_key)
    # print("密钥加密结果:", encrypted)
    # decrypted = AESCipher.decrypt_string(encrypted, key=base64_key)
    # print("密钥解密结果:", decrypted)

    # # 密码加密示例
    # encrypted = AESCipher.encrypt_string("敏感信息", password="strong_password")
    # print("密码加密结果:", encrypted)
    # decrypted = AESCipher.decrypt_string(encrypted, password="strong_password")
    # print("密码解密结果:", decrypted)
