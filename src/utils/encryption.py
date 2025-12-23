"""Field-level encryption utilities for sensitive PII data.

Implements AES-256 encryption with secure key management and rotation capabilities.
"""

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


# =============================================================================
# Constants
# =============================================================================

ALGORITHM = "AES-256-GCM"
KEY_SIZE = 32  # 256 bits
IV_SIZE = 12   # 96 bits for GCM
TAG_SIZE = 16  # 128 bits authentication tag
DEFAULT_KEY_ROTATION_DAYS = 90


# =============================================================================
# Key Management
# =============================================================================

class EncryptionKeyManager:
    """
    Manages encryption keys with rotation support.
    
    In production, integrate with a proper key management system (KMS)
    like AWS KMS, HashiCorp Vault, or Azure Key Vault.
    """
    
    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._active_key_id: Optional[str] = None
        self._rotation_callback = None
    
    def generate_key(self) -> Tuple[str, bytes]:
        """Generate a new encryption key with ID."""
        key_id = secrets.token_hex(8)
        key = secrets.token_bytes(KEY_SIZE)
        return key_id, key
    
    def register_key(
        self,
        key_id: str,
        key: bytes,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> None:
        """Register an encryption key."""
        if len(key) != KEY_SIZE:
            raise ValueError(f"Key must be {KEY_SIZE} bytes")
        
        now = datetime.utcnow()
        
        self._keys[key_id] = {
            "key": key,
            "created_at": created_at or now,
            "expires_at": expires_at or (now + timedelta(days=DEFAULT_KEY_ROTATION_DAYS)),
            "is_active": is_active,
            "is_primary": False,
        }
        
        if is_active and not self._active_key_id:
            self.set_active_key(key_id)
    
    def set_active_key(self, key_id: str) -> None:
        """Set the active key for encryption."""
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id} not found")
        
        # Mark previous primary as not primary
        if self._active_key_id and self._active_key_id in self._keys:
            self._keys[self._active_key_id]["is_primary"] = False
        
        self._active_key_id = key_id
        self._keys[key_id]["is_primary"] = True
    
    def get_active_key(self) -> Tuple[str, bytes]:
        """Get the currently active encryption key."""
        if not self._active_key_id:
            # Auto-generate if none exists
            key_id, key = self.generate_key()
            self.register_key(key_id, key, is_active=True)
        
        return self._active_key_id, self._keys[self._active_key_id]["key"]
    
    def get_key(self, key_id: str) -> bytes:
        """Get a key by ID."""
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id} not found")
        return self._keys[key_id]["key"]
    
    def rotate_keys(self) -> str:
        """
        Rotate to a new encryption key.
        
        Returns the new active key ID.
        """
        # Generate new key
        new_key_id, new_key = self.generate_key()
        
        # Mark old key as inactive (but keep for decryption)
        if self._active_key_id:
            self._keys[self._active_key_id]["is_active"] = False
        
        # Register and activate new key
        self.register_key(new_key_id, new_key, is_active=True)
        
        # Call rotation callback if set
        if self._rotation_callback:
            self._rotation_callback(self._active_key_id, new_key_id)
        
        return new_key_id
    
    def get_keys_for_rotation(self) -> list:
        """Get keys that should be rotated based on expiration."""
        now = datetime.utcnow()
        return [
            key_id for key_id, info in self._keys.items()
            if info["is_active"] and info["expires_at"] <= now
        ]
    
    def cleanup_expired_keys(self, retention_days: int = 365) -> int:
        """Remove expired keys past retention period."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        expired_keys = [
            key_id for key_id, info in self._keys.items()
            if not info["is_active"] and info["created_at"] < cutoff
        ]
        
        for key_id in expired_keys:
            del self._keys[key_id]
        
        return len(expired_keys)
    
    def set_rotation_callback(self, callback) -> None:
        """Set callback for key rotation events."""
        self._rotation_callback = callback


# Global key manager instance
_key_manager: Optional[EncryptionKeyManager] = None


def get_key_manager() -> EncryptionKeyManager:
    """Get or create key manager singleton."""
    global _key_manager
    if _key_manager is None:
        _key_manager = EncryptionKeyManager()
    return _key_manager


# =============================================================================
# Field-Level Encryption
# =============================================================================

class FieldEncryption:
    """
    Provides field-level encryption for sensitive data.
    
    Uses AES-256-GCM for authenticated encryption.
    """
    
    def __init__(self, key_manager: Optional[EncryptionKeyManager] = None):
        self.key_manager = key_manager or get_key_manager()
        self._backend = default_backend()
    
    def encrypt(
        self,
        plaintext: str,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Encrypt a string value.
        
        Args:
            plaintext: The data to encrypt
            associated_data: Optional AAD for authenticated encryption
            
        Returns:
            Encrypted data as base64 string with format:
            {key_id}:{iv}:{ciphertext}:{tag}
        """
        if not plaintext:
            return plaintext
        
        key_id, key = self.key_manager.get_active_key()
        
        # Generate random IV
        iv = os.urandom(IV_SIZE)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=self._backend,
        )
        encryptor = cipher.encryptor()
        
        # Add associated data if provided
        if associated_data:
            encryptor.authenticate_additional_data(associated_data)
        
        # Encrypt
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
        tag = encryptor.tag
        
        # Encode and format
        encoded_iv = base64.b64encode(iv).decode("ascii")
        encoded_ciphertext = base64.b64encode(ciphertext).decode("ascii")
        encoded_tag = base64.b64encode(tag).decode("ascii")
        
        return f"{key_id}:{encoded_iv}:{encoded_ciphertext}:{encoded_tag}"
    
    def decrypt(
        self,
        encrypted_data: str,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Decrypt an encrypted string value.
        
        Args:
            encrypted_data: The encrypted data string
            associated_data: Optional AAD for authenticated encryption
            
        Returns:
            Decrypted plaintext string
        """
        if not encrypted_data or ":" not in encrypted_data:
            return encrypted_data
        
        # Parse encrypted data
        try:
            parts = encrypted_data.split(":")
            if len(parts) != 4:
                raise ValueError("Invalid encrypted data format")
            
            key_id, encoded_iv, encoded_ciphertext, encoded_tag = parts
            
            key = self.key_manager.get_key(key_id)
            iv = base64.b64decode(encoded_iv)
            ciphertext = base64.b64decode(encoded_ciphertext)
            tag = base64.b64decode(encoded_tag)
            
        except (ValueError, KeyError) as e:
            raise ValueError(f"Failed to parse encrypted data: {e}")
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=self._backend,
        )
        decryptor = cipher.decryptor()
        
        # Add associated data if provided
        if associated_data:
            decryptor.authenticate_additional_data(associated_data)
        
        # Decrypt
        plaintext_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext_bytes.decode("utf-8")
    
    def re_encrypt(
        self,
        encrypted_data: str,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Re-encrypt data with the current active key.
        
        Used during key rotation to update encrypted values.
        """
        plaintext = self.decrypt(encrypted_data, associated_data)
        return self.encrypt(plaintext, associated_data)
    
    def is_encrypted(self, value: str) -> bool:
        """Check if a value appears to be encrypted."""
        if not value or ":" not in value:
            return False
        parts = value.split(":")
        return len(parts) == 4 and len(parts[0]) == 16


# Global encryption instance
_field_encryption: Optional[FieldEncryption] = None


def get_field_encryption() -> FieldEncryption:
    """Get or create field encryption singleton."""
    global _field_encryption
    if _field_encryption is None:
        _field_encryption = FieldEncryption()
    return _field_encryption


# =============================================================================
# Encrypted Field Descriptor
# =============================================================================

class EncryptedField:
    """
    Descriptor for automatically encrypting/decrypting model fields.
    
    Usage:
        class Employee(Base):
            ssn = EncryptedField("_ssn_encrypted")
    """
    
    def __init__(self, storage_attr: str, associated_data_attr: Optional[str] = None):
        self.storage_attr = storage_attr
        self.associated_data_attr = associated_data_attr
        self.encryption = get_field_encryption()
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        encrypted_value = getattr(obj, self.storage_attr, None)
        if encrypted_value is None:
            return None
        
        associated_data = self._get_associated_data(obj)
        return self.encryption.decrypt(encrypted_value, associated_data)
    
    def __set__(self, obj, value):
        if value is None:
            setattr(obj, self.storage_attr, None)
        else:
            associated_data = self._get_associated_data(obj)
            encrypted_value = self.encryption.encrypt(value, associated_data)
            setattr(obj, self.storage_attr, encrypted_value)
    
    def _get_associated_data(self, obj) -> Optional[bytes]:
        if self.associated_data_attr:
            aad = getattr(obj, self.associated_data_attr, None)
            if aad:
                return str(aad).encode("utf-8")
        return None


# =============================================================================
# Data Masking Utilities
# =============================================================================

def mask_pii(value: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """
    Mask PII data for display, showing only last few characters.
    
    Args:
        value: The value to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to leave visible at the end
        
    Returns:
        Masked string
    """
    if not value:
        return value
    
    if len(value) <= visible_chars:
        return mask_char * len(value)
    
    masked_length = len(value) - visible_chars
    return (mask_char * masked_length) + value[-visible_chars:]


def hash_pii(value: str, salt: Optional[str] = None) -> str:
    """
    Create a one-way hash of PII for searching/matching.
    
    Args:
        value: The value to hash
        salt: Optional salt for the hash
        
    Returns:
        Hashed value as hex string
    """
    if not value:
        return value
    
    normalized = value.lower().strip()
    
    if salt:
        normalized = f"{salt}:{normalized}"
    
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

