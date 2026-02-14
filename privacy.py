import re
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os

logger = logging.getLogger(__name__)

class PrivacyFilter:
    """Remove or anonymize PII from text/audio before cloud offloading."""
    
    def __init__(self, encryption_password: str):
        self.encryption_password = encryption_password
        self.fernet = self._init_fernet()
        # Simple regex patterns (extend as needed)
        self.patterns = {
            "email": r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
            "phone": r'\b\+?[\d\-\(\)]{10,}\b',
            "name": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # very naive
        }
        
    def _init_fernet(self):
        salt = b'local_ai_salt'  # in production use a random salt stored securely
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_password.encode()))
        return Fernet(key)
    
    def anonymize_text(self, text: str) -> tuple[str, dict]:
        """Replace PII with placeholders; return (anonymized_text, mapping)."""
        mapping = {}
        for pii_type, pattern in self.patterns.items():
            def repl(match):
                placeholder = f"[{pii_type.upper()}_{len(mapping)}]"
                mapping[placeholder] = match.group(0)
                return placeholder
            text = re.sub(pattern, repl, text)
        return text, mapping
    
    def deanonymize_text(self, anonymized: str, mapping: dict) -> str:
        """Restore original text (only needed locally)."""
        for placeholder, original in mapping.items():
            anonymized = anonymized.replace(placeholder, original)
        return anonymized
    
    def encrypt_file(self, filepath: str) -> str:
        """Encrypt file and return path to encrypted version."""
        enc_path = filepath + ".enc"
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            encrypted = self.fernet.encrypt(data)
            with open(enc_path, 'wb') as f:
                f.write(encrypted)
            logger.info(f"Encrypted {filepath} -> {enc_path}")
            return enc_path
        except Exception as e:
            logger.error(f"Encryption failed for {filepath}: {e}")
            raise
    
    def decrypt_file(self, enc_path: str, output_path: str):
        """Decrypt file back to original."""
        try:
            with open(enc_path, 'rb') as f:
                encrypted = f.read()
            data = self.fernet.decrypt(encrypted)
            with open(output_path, 'wb') as f:
                f.write(data)
            logger.info(f"Decrypted {enc_path} -> {output_path}")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
