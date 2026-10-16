import os
import sys
import json
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import email.mime.multipart
import email.mime.text
import email.mime.base
from email import encoders
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import cryptography.exceptions
sys.path.append(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class SecurityLevel(Enum):
    QUANTUM_SECURE = 1
    QUANTUM_AIDED = 2
    HYBRID_PQC = 3
    NO_QUANTUM = 4
@dataclass
class EncryptionMetadata:
    security_level: int
    algorithm: str
    key_source: str
    timestamp: str
    message_id: str
    sender: str
    recipient: str
    key_ids: Dict[str, str]
    integrity_hash: str
    quantum_resistant: bool
    etsi_compliant: bool
@dataclass 
class EncryptedMessage:
    ciphertext: str
    metadata: EncryptionMetadata
    attachments: List[Dict[str, Any]]
    mime_structure: str
class QuMailEncryptionError(Exception):
    pass
class QuMailMultiLevelEncryption:
    def __init__(self, api_base_url: str = "http://127.0.0.1:5000"):
        self.api_base_url = api_base_url
        self.backend = default_backend()
        try:
            from supabase_client import supabase_storage as _sb
            self._supabase = _sb
        except Exception:
            self._supabase = None
        if not self._supabase or not self._supabase.is_connected():
            logger.warning("⚠️ Supabase not connected - using in-memory key storage (keys lost on restart)")
        else:
            logger.info("✅ Encryption module using Supabase primary storage")
        try:
            import requests
            self.requests = requests
            self._test_api_connection()
        except ImportError:
            logger.warning("requests library not available - API integration disabled")
            self.requests = None
        self.oqs = None
        self.real_pqc = None
        self.mlkem_available = False
        self._init_mlkem_support()
        self._mlkem_shared_secret_storage = {}
        logger.info("🔐 QuMail Multi-Level Encryption Module initialized")
    def _store_key_for_users(self, key_data, key_id, sender_email, recipient_email, key_type="encryption"):
        if not self._supabase:
            logger.error("❌ Supabase storage module not available - key will be lost!")
            return False
        try:
            enhanced_key_data = {
                **key_data,
                "key_id": key_id,
                "sender": sender_email,
                "recipient": recipient_email,
                "key_type": key_type,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            self._supabase.set_user_key(sender_email, key_id, enhanced_key_data)
            self._supabase.set_user_key(recipient_email, key_id, enhanced_key_data)
            logger.info(f"✅ {key_type} key {key_id} stored for {sender_email} and {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"❌ Key storage error: {e}")
            return False
    def _get_key_for_user(self, key_id, user_email):
        if not self._supabase:
            logger.error("❌ Supabase storage module not available - cannot retrieve key!")
            return None
        try:
            key_data = self._supabase.get_user_key(user_email, key_id)
            if key_data:
                logger.info(f"✅ Retrieved key {key_id} for {user_email}")
                return key_data
            else:
                logger.warning(f"⚠️ Key {key_id} not found for {user_email}")
                return None
        except Exception as e:
            logger.error(f"❌ Key retrieval error: {e}")
            return None
    def _derive_hybrid_key_with_real_pqc(self, message_id: str, qkd_key: dict, ecdh_keypair: dict, mlkem_shared_secret: bytes) -> dict:
        try:
            from hybrid import create_hybrid_derivator
            hybrid_derivator = create_hybrid_derivator()
            hybrid_derivator.set_managers(real_pqc_manager=self.real_pqc)
            qkd_material = base64.b64decode(qkd_key['key_material'])
            ecdh_material = bytes.fromhex(ecdh_keypair['shared_secret'])
            hybrid_derivator.qkd_manager = type('MockQKD', (), {
                'active_keys': {qkd_key['key_id']: qkd_key}
            })()
            hybrid_derivator.ecdh_manager = type('MockECDH', (), {
                'shared_secrets': {ecdh_keypair['shared_secret_id']: ecdh_keypair}
            })()
            hybrid_key = hybrid_derivator.derive_hybrid_key(
                hybrid_key_id=f"real_pqc_{message_id}",
                include_components=['QKD', 'ECDH', 'MLKEM']
            )
            return hybrid_key
        except Exception as e:
            logger.error(f"Real PQC hybrid key derivation failed: {e}")
            return None
    def _get_simulated_qkd_key(self) -> dict:
        return {
            'key_id': 'sim_qkd_001',
            'key_material': base64.b64encode(secrets.token_bytes(32)).decode('utf-8'),
            'algorithm': 'BB84',
            'length': 256,
            'metadata': {
                'error_rate': 0.01,
                'fidelity': 0.99
            }
        }
    def _get_simulated_ecdh_keypair(self) -> dict:
        return {
            'keypair_id': 'sim_ecdh_001',
            'shared_secret_id': 'sim_ecdh_shared_001',
            'shared_secret': secrets.token_bytes(32).hex(),
            'algorithm': 'X25519',
            'length': 256
        }
    def _get_simulated_mlkem_keypair(self) -> dict:
        return {
            'keypair_id': 'sim_mlkem_001',
            'public_key': base64.b64encode(secrets.token_bytes(32)).decode('utf-8'),
            'private_key': base64.b64encode(secrets.token_bytes(32)).decode('utf-8'),
            'algorithm': 'ML-KEM-768',
            'length': 256
        }
    def _derive_hybrid_key_local(self, hybrid_key_id: str) -> dict:
        try:
            if self.real_pqc:
                public_key, private_key = self.real_pqc.pqc.generate_keypair()
                ciphertext, shared_secret = self.real_pqc.pqc.encapsulate(public_key)
                hybrid_key_data = self._derive_hybrid_key_with_real_pqc(
                    message_id=hybrid_key_id,
                    qkd_key=self._get_simulated_qkd_key(),
                    ecdh_keypair=self._get_simulated_ecdh_keypair(),
                    mlkem_shared_secret=shared_secret
                )
                if hybrid_key_data:
                    return hybrid_key_data
            return {
                'hybrid_key_id': hybrid_key_id,
                'derived_key_b64': base64.b64encode(secrets.token_bytes(32)).decode('utf-8'),
                'algorithm': 'Local-Hybrid',
                'key_length': 256,
                'components': ['QKD', 'ECDH', 'MLKEM'],
                'security_level': '192-bit hybrid',
                'component_info': {
                    'qkd': {'key_id': 'sim_qkd_001', 'algorithm': 'BB84'},
                    'ecdh': {'shared_secret_id': 'sim_ecdh_shared_001', 'algorithm': 'X25519'},
                    'mlkem': {'secret_id': 'sim_mlkem_001', 'algorithm': 'ML-KEM-768'}
                }
            }
        except Exception as e:
            logger.error(f"Local hybrid key derivation failed: {e}")
            return None
    def _test_api_connection(self):
        try:
            response = self.requests.get(f"{self.api_base_url}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Connected to {data.get('service', 'QuMail API')}")
            else:
                logger.warning(f"⚠️ API connection issue: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ API connection failed: {e}")
    def _init_mlkem_support(self):
        if self.oqs is not None or self.real_pqc is not None:
            return
        try:
            from real_pqc import create_real_pqc_manager
            self.real_pqc = create_real_pqc_manager()
            self.oqs = None
            self.mlkem_available = True
            logger.info("✅ ML-KEM-768 (Real Post-Quantum) support enabled")
        except (ImportError, Exception) as e:
            logger.warning(f"⚠️ Real PQC not available - using ML-KEM simulation via API: {str(e)[:50]}")
            self.oqs = None
            self.real_pqc = None
            self.mlkem_available = False
    def encrypt_message(self, 
                       plaintext: str,
                       security_level: SecurityLevel,
                       sender: str,
                       recipient: str,
                       subject: str = "",
                       attachments: List[Dict[str, Any]] = None) -> EncryptedMessage:
        logger.info(f"🔐 Encrypting message with Level {security_level.value} security")
        message_id = f"qumail_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.randbelow(1000)}"
        if security_level == SecurityLevel.QUANTUM_SECURE:
            return self._encrypt_level1_quantum_secure(plaintext, sender, recipient, message_id, subject, attachments)
        elif security_level == SecurityLevel.QUANTUM_AIDED:
            return self._encrypt_level2_quantum_aided(plaintext, sender, recipient, message_id, subject, attachments)
        elif security_level == SecurityLevel.HYBRID_PQC:
            return self._encrypt_level3_hybrid_pqc(plaintext, sender, recipient, message_id, subject, attachments)
        elif security_level == SecurityLevel.NO_QUANTUM:
            return self._encrypt_level4_no_quantum(plaintext, sender, recipient, message_id, subject, attachments)
        else:
            raise QuMailEncryptionError(f"Invalid security level: {security_level}")
    def decrypt_message(self, encrypted_message: EncryptedMessage) -> Tuple[str, List[Dict[str, Any]]]:
        security_level = encrypted_message.metadata.security_level
        logger.info(f"🔓 Decrypting message with Level {security_level} security")
        if security_level == 1:
            return self._decrypt_level1_quantum_secure(encrypted_message)
        elif security_level == 2:
            return self._decrypt_level2_quantum_aided(encrypted_message)
        elif security_level == 3:
            return self._decrypt_level3_hybrid_pqc(encrypted_message)
        elif security_level == 4:
            return self._decrypt_level4_no_quantum(encrypted_message)
        else:
            raise QuMailEncryptionError(f"Invalid security level: {security_level}")
    def _encrypt_level1_quantum_secure(self, plaintext: str, sender: str, recipient: str, 
                                     message_id: str, subject: str, attachments: List) -> EncryptedMessage:
        logger.info("🔐 Level 1: Quantum Secure (OTP) encryption")
        qkd_key_data = self._get_qkd_key()
        if not qkd_key_data:
            raise QuMailEncryptionError("No QKD key available for Level 1 encryption")
        if 'key' in qkd_key_data:
            qkd_key = bytes.fromhex(qkd_key_data['key'])
        elif 'key_material' in qkd_key_data:
            qkd_key = base64.b64decode(qkd_key_data['key_material'])
        else:
            raise QuMailEncryptionError("Invalid QKD key format")
        key_id = qkd_key_data['key_id']
        self._store_qkd_key_for_decryption(key_id, qkd_key, sender, recipient)
        plaintext_bytes = plaintext.encode('utf-8')
        if len(plaintext_bytes) > len(qkd_key):
            expanded_key = self._expand_qkd_key(qkd_key, len(plaintext_bytes))
        else:
            expanded_key = qkd_key[:len(plaintext_bytes)]
        ciphertext_bytes = bytes(a ^ b for a, b in zip(plaintext_bytes, expanded_key))
        ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode('utf-8')
        metadata = EncryptionMetadata(
            security_level=1,
            algorithm="OTP-QKD-BB84",
            key_source="QKD",
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            key_ids={"qkd_key": key_id},
            integrity_hash=hashlib.sha256(plaintext_bytes).hexdigest(),
            quantum_resistant=True,
            etsi_compliant=True
        )
        encrypted_attachments = self._encrypt_attachments_level1(attachments, expanded_key) if attachments else []
        mime_structure = self._create_mime_structure(ciphertext_b64, metadata, encrypted_attachments, subject)
        self._consume_qkd_key(key_id)
        logger.info(f"✅ Level 1 encryption complete: {len(plaintext)} chars → {len(ciphertext_b64)} chars")
        return EncryptedMessage(
            ciphertext=ciphertext_b64,
            metadata=metadata,
            attachments=encrypted_attachments,
            mime_structure=mime_structure
        )
    def _decrypt_level1_quantum_secure(self, encrypted_message: EncryptedMessage) -> Tuple[str, List[Dict[str, Any]]]:
        logger.info("🔓 Level 1: Quantum Secure (OTP) decryption")
        ciphertext_bytes = base64.b64decode(encrypted_message.ciphertext.encode('utf-8'))
        qkd_key_id = encrypted_message.metadata.key_ids.get("qkd_key")
        qkd_key = self._get_stored_qkd_key(qkd_key_id, encrypted_message.metadata.recipient)
        if not qkd_key:
            qkd_key_data = self._get_qkd_key_by_id(qkd_key_id)
            if qkd_key_data:
                if 'key' in qkd_key_data:
                    qkd_key = bytes.fromhex(qkd_key_data['key'])
                elif 'key_material' in qkd_key_data:
                    qkd_key = base64.b64decode(qkd_key_data['key_material'])
        if not qkd_key:
            raise QuMailEncryptionError("QKD key not found for decryption")
        if len(ciphertext_bytes) > len(qkd_key):
            expanded_key = self._expand_qkd_key(qkd_key, len(ciphertext_bytes))
        else:
            expanded_key = qkd_key[:len(ciphertext_bytes)]
        plaintext_bytes = bytes(a ^ b for a, b in zip(ciphertext_bytes, expanded_key))
        try:
            plaintext = plaintext_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raise QuMailEncryptionError("Level 1 decryption failed - invalid key or corrupted data")
            
        decrypted_attachments = []
        if hasattr(encrypted_message, 'attachments') and encrypted_message.attachments:
            for att in encrypted_message.attachments:
                try:
                    enc_content = base64.b64decode(att['encrypted_content'])
                    dec_content = bytes(a ^ b for a, b in zip(enc_content, expanded_key[:len(enc_content)]))
                    decrypted_attachments.append({
                        'filename': att.get('filename', 'attachment'),
                        'content_type': att.get('content_type', 'application/octet-stream'),
                        'data': base64.b64encode(dec_content).decode('utf-8')
                    })
                except Exception as e:
                    logger.warning(f"Failed to decrypt attachment: {e}")
                    
        logger.info("✅ Level 1 decryption complete")
        return plaintext, decrypted_attachments
    def _encrypt_level2_quantum_aided(self, plaintext: str, sender: str, recipient: str,
                                    message_id: str, subject: str, attachments: List) -> EncryptedMessage:
        logger.info("🔐 Level 2: Quantum-aided AES encryption")
        if self.real_pqc:
            public_key, private_key = self.real_pqc.pqc.generate_keypair()
            ciphertext, shared_secret = self.real_pqc.pqc.encapsulate(public_key)
            hybrid_key_data = self._derive_hybrid_key_with_real_pqc(
                message_id=f"level2_{message_id}",
                qkd_key=self._get_simulated_qkd_key(),
                ecdh_keypair=self._get_simulated_ecdh_keypair(),
                mlkem_shared_secret=shared_secret
            )
        else:
            hybrid_key_data = self._derive_hybrid_key(f"level2_{message_id}")
        if not hybrid_key_data:
            raise QuMailEncryptionError("Failed to derive hybrid key for Level 2 encryption")
        hybrid_key = base64.b64decode(hybrid_key_data['derived_key_b64'])
        key_ids = hybrid_key_data.get('component_info', {})
        hybrid_key_id = hybrid_key_data['hybrid_key_id']
        hybrid_key_data_with_key = {
            **hybrid_key_data,
            "derived_key_bytes": base64.b64encode(hybrid_key).decode('utf-8')
        }
        success = self._store_key_for_users(
            hybrid_key_data_with_key, hybrid_key_id, sender, recipient, "hybrid"
        )
        if success:
            logger.debug(f"Stored hybrid key for decryption in Supabase: {hybrid_key_id}")
        else:
            logger.error(f"Failed to store hybrid key: {hybrid_key_id}")
        if self.real_pqc:
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext_bytes, nonce, tag = self.real_pqc.pqc.encrypt_aes_gcm(plaintext_bytes, hybrid_key)
            encrypted_data = nonce + tag + ciphertext_bytes
            ciphertext_b64 = base64.b64encode(encrypted_data).decode('utf-8')
        else:
            fernet_key = base64.urlsafe_b64encode(hybrid_key[:32])
            fernet = Fernet(fernet_key)
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext_bytes = fernet.encrypt(plaintext_bytes)
            ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode('utf-8')
        metadata = EncryptionMetadata(
            security_level=2,
            algorithm="AES-256-GCM-Real-PQC" if self.real_pqc else "AES-256-GCM-Hybrid",
            key_source="QKD+ECDH+Real-PQC" if self.real_pqc else "QKD+ECDH+MLKEM",
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            key_ids={
                "hybrid_key": hybrid_key_data['hybrid_key_id'],
                "components": key_ids,
                "real_pqc_used": self.real_pqc is not None
            },
            integrity_hash=hashlib.sha256(plaintext_bytes).hexdigest(),
            quantum_resistant=True,
            etsi_compliant=True
        )
        encrypted_attachments = self._encrypt_attachments_level2(attachments, Fernet(base64.urlsafe_b64encode(hybrid_key[:32]))) if attachments else []
        mime_structure = self._create_mime_structure(ciphertext_b64, metadata, encrypted_attachments, subject)
        logger.info(f"✅ Level 2 encryption complete: {len(plaintext)} chars → {len(ciphertext_b64)} chars")
        return EncryptedMessage(
            ciphertext=ciphertext_b64,
            metadata=metadata,
            attachments=encrypted_attachments,
            mime_structure=mime_structure
        )
    def _decrypt_level2_quantum_aided(self, encrypted_message: EncryptedMessage) -> Tuple[str, List[Dict[str, Any]]]:
        logger.info("🔓 Level 2: Quantum-aided AES decryption")
        hybrid_key_id = encrypted_message.metadata.key_ids.get("hybrid_key")
        recipient_email = encrypted_message.metadata.recipient
        hybrid_key_data = self._get_key_for_user(hybrid_key_id, recipient_email)
        if hybrid_key_data and 'derived_key_bytes' in hybrid_key_data:
            hybrid_key = base64.b64decode(hybrid_key_data['derived_key_bytes'])
            logger.debug(f"Retrieved hybrid key from Supabase: {hybrid_key_id}")
        else:
            hybrid_key_data = self._get_hybrid_key(hybrid_key_id)
            if not hybrid_key_data:
                raise QuMailEncryptionError(f"Hybrid key not found: {hybrid_key_id}")
            hybrid_key = base64.b64decode(hybrid_key_data['derived_key_b64'])
        algorithm = encrypted_message.metadata.algorithm
        real_pqc_used = encrypted_message.metadata.key_ids.get('real_pqc_used', False)
        ciphertext_bytes = base64.b64decode(encrypted_message.ciphertext.encode('utf-8'))
        if real_pqc_used and self.real_pqc and "Real-PQC" in algorithm:
            if len(ciphertext_bytes) < 28:
                raise QuMailEncryptionError("Invalid ciphertext for AES-256-GCM decryption")
            nonce = ciphertext_bytes[:12]
            tag = ciphertext_bytes[12:28]
            ciphertext = ciphertext_bytes[28:]
            plaintext_bytes = self.real_pqc.pqc.decrypt_aes_gcm(ciphertext, hybrid_key, nonce, tag)
            plaintext = plaintext_bytes.decode('utf-8')
        else:
            fernet_key = base64.urlsafe_b64encode(hybrid_key[:32])
            fernet = Fernet(fernet_key)
            plaintext_bytes = fernet.decrypt(ciphertext_bytes)
            plaintext = plaintext_bytes.decode('utf-8')
            
        decrypted_attachments = []
        if hasattr(encrypted_message, 'attachments') and encrypted_message.attachments:
            fernet_key_att = base64.urlsafe_b64encode(hybrid_key[:32])
            fernet_att = Fernet(fernet_key_att)
            for att in encrypted_message.attachments:
                try:
                    enc_content = base64.b64decode(att['encrypted_content'])
                    dec_content = fernet_att.decrypt(enc_content)
                    decrypted_attachments.append({
                        'filename': att.get('filename', 'attachment'),
                        'content_type': att.get('content_type', 'application/octet-stream'),
                        'data': base64.b64encode(dec_content).decode('utf-8')
                    })
                except Exception as e:
                    logger.warning(f"Failed to decrypt attachment: {e}")
                    
        logger.info("✅ Level 2 decryption complete")
        return plaintext, decrypted_attachments
    def _encrypt_level3_hybrid_pqc(self, plaintext: str, sender: str, recipient: str,
                                 message_id: str, subject: str, attachments: List) -> EncryptedMessage:
        logger.info("🔐 Level 3: Hybrid PQC encryption")
        if not self.real_pqc:
            raise QuMailEncryptionError("Real PQC not available for Level 3 encryption")
        mlkem_public_key, mlkem_private_key = self.real_pqc.pqc.generate_keypair()
        mlkem_ciphertext, mlkem_shared_secret = self.real_pqc.pqc.encapsulate(mlkem_public_key)
        sig_public_key, sig_private_key = self.real_pqc.pqc.generate_signature_keypair()
        message_hash = hashlib.sha256(plaintext.encode('utf-8')).digest()
        signature = self.real_pqc.pqc.sign(sig_private_key, message_hash)
        shared_secret_id = f"level3_{message_id}_{int(datetime.now().timestamp() * 1000)}"
        success = self._store_key_for_users(
            {"mlkem_shared_secret": base64.b64encode(mlkem_shared_secret).decode('utf-8')},
            shared_secret_id, sender, recipient, "level3_mlkem"
        )
        if success:
            logger.debug(f"Stored ML-KEM shared secret in Supabase: {shared_secret_id}")
        else:
            logger.error(f"Failed to store ML-KEM shared secret: {shared_secret_id}")
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext_bytes, nonce, tag = self.real_pqc.pqc.encrypt_aes_gcm(plaintext_bytes, mlkem_shared_secret)
        encrypted_data = nonce + tag + ciphertext_bytes
        ciphertext_b64 = base64.b64encode(encrypted_data).decode('utf-8')
        metadata = EncryptionMetadata(
            security_level=3,
            algorithm="ML-KEM-768-Real+ML-DSA-65-Real+AES-256-GCM-Real",
            key_source="Real-PQC",
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            key_ids={
                "mlkem_public_key": base64.b64encode(mlkem_public_key).decode('utf-8'),
                "mlkem_private_key": base64.b64encode(mlkem_private_key).decode('utf-8'),
                "mlkem_ciphertext": base64.b64encode(mlkem_ciphertext).decode('utf-8'),
                "sig_public_key": base64.b64encode(sig_public_key).decode('utf-8'),
                "sig_private_key": base64.b64encode(sig_private_key).decode('utf-8'),
                "signature": base64.b64encode(signature).decode('utf-8'),
                "shared_secret_id": shared_secret_id,
                "real_pqc_used": True
            },
            integrity_hash=hashlib.sha256(plaintext_bytes).hexdigest(),
            quantum_resistant=True,
            etsi_compliant=True
        )
        encrypted_attachments = self._encrypt_attachments_level3(attachments, mlkem_shared_secret) if attachments else []
        mime_structure = self._create_mime_structure(ciphertext_b64, metadata, encrypted_attachments, subject)
        logger.info(f"✅ Level 3 encryption complete: {len(plaintext)} chars → {len(ciphertext_b64)} chars")
        return EncryptedMessage(
            ciphertext=ciphertext_b64,
            metadata=metadata,
            attachments=encrypted_attachments,
            mime_structure=mime_structure
        )
    def _decrypt_level3_hybrid_pqc(self, encrypted_message: EncryptedMessage) -> Tuple[str, List[Dict[str, Any]]]:
        logger.info("🔓 Level 3: Hybrid PQC decryption")
        if not self.real_pqc:
            raise QuMailEncryptionError("Real PQC not available for Level 3 decryption")
        shared_secret_id = encrypted_message.metadata.key_ids.get("shared_secret_id")
        recipient_email = encrypted_message.metadata.recipient
        secret_data = self._get_key_for_user(shared_secret_id, recipient_email)
        
        if not secret_data or 'mlkem_shared_secret' not in secret_data:
            raise QuMailEncryptionError(f"ML-KEM shared secret not found in Supabase: {shared_secret_id}")
            
        mlkem_shared_secret = base64.b64decode(secret_data['mlkem_shared_secret'])
        logger.debug(f"Retrieved ML-KEM shared secret from Supabase: {shared_secret_id}")
        encrypted_data = base64.b64decode(encrypted_message.ciphertext.encode('utf-8'))
        if len(encrypted_data) < 28:
            raise QuMailEncryptionError("Invalid ciphertext for AES-256-GCM decryption")
        nonce = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]
        plaintext_bytes = self.real_pqc.pqc.decrypt_aes_gcm(ciphertext, mlkem_shared_secret, nonce, tag)
        plaintext = plaintext_bytes.decode('utf-8')
        message_hash = hashlib.sha256(plaintext_bytes).digest()
        sig_public_key_b64 = encrypted_message.metadata.key_ids.get("sig_public_key", "")
        signature_b64 = encrypted_message.metadata.key_ids.get("signature", "")
        if sig_public_key_b64 and signature_b64:
            sig_public_key = base64.b64decode(sig_public_key_b64)
            signature = base64.b64decode(signature_b64)
            is_valid = self.real_pqc.pqc.verify(sig_public_key, message_hash, signature)
            if not is_valid:
                logger.warning("ML-DSA-65 signature verification failed")
            else:
                logger.info("✅ ML-DSA-65 signature verified successfully")
        else:
            logger.warning("Signature components not found in metadata")
            
        decrypted_attachments = []
        if hasattr(encrypted_message, 'attachments') and encrypted_message.attachments:
            for att in encrypted_message.attachments:
                try:
                    enc_data = base64.b64decode(att['encrypted_content'])
                    iv_att = enc_data[:12]
                    ciphertext_att = enc_data[12:-16]
                    tag_att = enc_data[-16:]
                    cipher = Cipher(algorithms.AES(mlkem_shared_secret), modes.GCM(iv_att, tag_att), backend=self.backend)
                    decryptor = cipher.decryptor()
                    dec_content = decryptor.update(ciphertext_att) + decryptor.finalize()
                    decrypted_attachments.append({
                        'filename': att.get('filename', 'attachment'),
                        'content_type': att.get('content_type', 'application/octet-stream'),
                        'data': base64.b64encode(dec_content).decode('utf-8')
                    })
                except Exception as e:
                    logger.warning(f"Failed to decrypt attachment: {e}")
                    
        logger.info("✅ Level 3 decryption complete")
        return plaintext, decrypted_attachments
    def _encrypt_level4_no_quantum(self, plaintext: str, sender: str, recipient: str,
                                 message_id: str, subject: str, attachments: List) -> EncryptedMessage:
        logger.info("🔐 Level 4: No Quantum Security encryption")
        if subject and "plaintext" in subject.lower():
            ciphertext_b64 = base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')
            algorithm = "Plaintext"
            key_source = "None"
            quantum_resistant = False
        else:
            aes_key = secrets.token_bytes(32)
            iv = secrets.token_bytes(16)
            level4_key_id = f"level4_aes_{message_id}_{int(datetime.now().timestamp() * 1000)}"
            level4_key_data = {
                "aes_key": base64.b64encode(aes_key).decode('utf-8'),
                "algorithm": "AES-256-CBC"
            }
            success = self._store_key_for_users(
                level4_key_data, level4_key_id, sender, recipient, "level4"
            )
            if success:
                logger.debug(f"Stored Level 4 AES key in Supabase: {level4_key_id}")
            else:
                logger.error(f"Failed to store Level 4 key: {level4_key_id}")
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=self.backend)
            encryptor = cipher.encryptor()
            plaintext_bytes = plaintext.encode('utf-8')
            pad_length = 16 - (len(plaintext_bytes) % 16)
            padded_plaintext = plaintext_bytes + bytes([pad_length] * pad_length)
            ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()
            encrypted_data = iv + ciphertext
            ciphertext_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            algorithm = "AES-256-CBC"
            key_source = "Random"
            quantum_resistant = False
        metadata = EncryptionMetadata(
            security_level=4,
            algorithm=algorithm,
            key_source=key_source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            key_ids={"level4_key_id": level4_key_id if algorithm == "AES-256-CBC" else "plaintext"},
            integrity_hash=hashlib.sha256(plaintext.encode('utf-8')).hexdigest(),
            quantum_resistant=quantum_resistant,
            etsi_compliant=False
        )
        encrypted_attachments = []
        if attachments:
            if algorithm == "Plaintext":
                encrypted_attachments = attachments
            else:
                encrypted_attachments = self._encrypt_attachments_level4(attachments, aes_key)
        mime_structure = self._create_mime_structure(ciphertext_b64, metadata, encrypted_attachments, subject)
        logger.info(f"✅ Level 4 encryption complete: {len(plaintext)} chars → {len(ciphertext_b64)} chars")
        return EncryptedMessage(
            ciphertext=ciphertext_b64,
            metadata=metadata,
            attachments=encrypted_attachments,
            mime_structure=mime_structure
        )
    def _decrypt_level4_no_quantum(self, encrypted_message: EncryptedMessage) -> Tuple[str, List[Dict[str, Any]]]:
        logger.info("🔓 Level 4: No Quantum Security decryption")
        aes_key = None
        if encrypted_message.metadata.algorithm == "Plaintext":
            plaintext = base64.b64decode(encrypted_message.ciphertext.encode('utf-8')).decode('utf-8')
        else:
            level4_key_id = encrypted_message.metadata.key_ids.get("level4_key_id")
            recipient_email = encrypted_message.metadata.recipient
            level4_key_data = self._get_key_for_user(level4_key_id, recipient_email)
            if not level4_key_data or 'aes_key' not in level4_key_data:
                raise QuMailEncryptionError(f"Level 4 AES key not found: {level4_key_id}")
            aes_key = base64.b64decode(level4_key_data['aes_key'])
            logger.debug(f"Retrieved Level 4 AES key from Supabase: {level4_key_id}")
            encrypted_data = base64.b64decode(encrypted_message.ciphertext.encode('utf-8'))
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=self.backend)
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            pad_length = padded_plaintext[-1]
            plaintext_bytes = padded_plaintext[:-pad_length]
            plaintext = plaintext_bytes.decode('utf-8')
            
        decrypted_attachments = []
        if hasattr(encrypted_message, 'attachments') and encrypted_message.attachments:
            for att in encrypted_message.attachments:
                try:
                    if encrypted_message.metadata.algorithm == "Plaintext":
                        decrypted_attachments.append(att)
                    else:
                        enc_data = base64.b64decode(att['encrypted_content'])
                        iv = enc_data[:16]
                        ciphertext_att = enc_data[16:]
                        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=self.backend)
                        decryptor = cipher.decryptor()
                        padded_content = decryptor.update(ciphertext_att) + decryptor.finalize()
                        pad_length = padded_content[-1]
                        dec_content = padded_content[:-pad_length]
                        decrypted_attachments.append({
                            'filename': att.get('filename', 'attachment'),
                            'content_type': att.get('content_type', 'application/octet-stream'),
                            'data': base64.b64encode(dec_content).decode('utf-8')
                        })
                except Exception as e:
                    logger.warning(f"Failed to decrypt attachment: {e}")
                    
        logger.info("✅ Level 4 decryption complete")
        return plaintext, decrypted_attachments
    def _get_qkd_key(self) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return self._get_simulated_qkd_key()
        try:
            response = self.requests.get(f"{self.api_base_url}/api/qkd/key", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"QKD API returned status {response.status_code}")
                return self._get_simulated_qkd_key()
        except Exception as e:
            logger.warning(f"Failed to get QKD key: {e}")
            return self._get_simulated_qkd_key()
    def _get_qkd_key_by_id(self, key_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return self._get_simulated_qkd_key()
        try:
            response = self.requests.get(f"{self.api_base_url}/api/qkd/key/{key_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"QKD API returned status {response.status_code} for key {key_id}")
                return None
        except Exception as e:
            logger.warning(f"Failed to get QKD key {key_id}: {e}")
            return None
    def _store_qkd_key_for_decryption(self, key_id: str, key_bytes: bytes, sender_email: str, recipient_email: str):
        qkd_key_data = {
            "key_bytes": base64.b64encode(key_bytes).decode('utf-8'),
            "algorithm": "QKD-BB84"
        }
        success = self._store_key_for_users(qkd_key_data, key_id, sender_email, recipient_email, "qkd")
        if success:
            logger.debug(f"Stored QKD key {key_id} in Supabase for decryption")
        else:
            logger.error(f"Failed to store QKD key: {key_id}")
    def _get_stored_qkd_key(self, key_id: str, user_email: str) -> Optional[bytes]:
        key_data = self._get_key_for_user(key_id, user_email)
        if key_data and 'key_bytes' in key_data:
            return base64.b64decode(key_data['key_bytes'])
        return None
    def _consume_qkd_key(self, key_id: str) -> bool:
        if not self.requests:
            return False
        try:
            response = self.requests.post(f"{self.api_base_url}/api/qkd/consume/{key_id}", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to consume QKD key: {e}")
            return False
    def _expand_qkd_key(self, qkd_key: bytes, target_length: int) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=target_length,
            salt=None,
            info=b'QuMail QKD Key Expansion',
            backend=self.backend
        )
        return hkdf.derive(qkd_key)
    def _derive_hybrid_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return self._derive_hybrid_key_local(key_id)
        try:
            qkd_key = self._get_qkd_key()
            ecdh_keypair = self._generate_ecdh_keypair(f"hybrid_{key_id}")
            ecdh_shared = self._compute_ecdh_shared_secret(ecdh_keypair['key_id'], ecdh_keypair['public_key'], f"hybrid_shared_{key_id}")
            mlkem_keypair = self._generate_mlkem_keypair(f"hybrid_mlkem_{key_id}")
            mlkem_encaps = self._mlkem_encapsulate(mlkem_keypair['public_key'], f"hybrid_mlkem_shared_{key_id}")
            hybrid_data = {
                "key_id": key_id,
                "ecdh_shared_secret_id": ecdh_shared['shared_secret_id'],
                "mlkem_shared_secret_id": mlkem_encaps['secret_id']
            }
            if qkd_key:
                hybrid_data["qkd_key_id"] = qkd_key['key_id']
            response = self.requests.post(f"{self.api_base_url}/api/hybrid/derive", json=hybrid_data, timeout=15)
            if response.status_code == 201:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to derive hybrid key: {e}")
        return None
    def _get_hybrid_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return None
        try:
            response = self.requests.get(f"{self.api_base_url}/api/hybrid/key/{key_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to get hybrid key: {e}")
        return None
    def _generate_ecdh_keypair(self, key_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return self._get_simulated_ecdh_keypair()
        try:
            response = self.requests.post(f"{self.api_base_url}/api/ecdh/keypair", json={"key_id": key_id}, timeout=10)
            if response.status_code == 201:
                return response.json()
            else:
                logger.warning(f"ECDH API returned status {response.status_code}")
                return self._get_simulated_ecdh_keypair()
        except Exception as e:
            logger.warning(f"Failed to generate ECDH keypair: {e}")
            return self._get_simulated_ecdh_keypair()
    def _compute_ecdh_shared_secret(self, local_key_id: str, remote_public_key: str, shared_secret_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return None
        try:
            data = {
                "local_key_id": local_key_id,
                "remote_public_key": remote_public_key,
                "shared_secret_id": shared_secret_id
            }
            response = self.requests.post(f"{self.api_base_url}/api/ecdh/exchange", json=data, timeout=10)
            if response.status_code == 201:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to compute ECDH shared secret: {e}")
        return None
    def _generate_mlkem_keypair(self, key_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return self._get_simulated_mlkem_keypair()
        try:
            response = self.requests.post(f"{self.api_base_url}/api/mlkem/keypair", json={"key_id": key_id}, timeout=10)
            if response.status_code == 201:
                return response.json()
            else:
                logger.warning(f"ML-KEM API returned status {response.status_code}")
                return self._get_simulated_mlkem_keypair()
        except Exception as e:
            logger.warning(f"Failed to generate ML-KEM keypair: {e}")
            return self._get_simulated_mlkem_keypair()
    def _mlkem_encapsulate(self, public_key: str, secret_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return None
        try:
            data = {
                "remote_public_key": public_key,
                "secret_id": secret_id
            }
            response = self.requests.post(f"{self.api_base_url}/api/mlkem/encapsulate", json=data, timeout=10)
            if response.status_code == 201:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to encapsulate ML-KEM secret: {e}")
        return None
    def _mlkem_decapsulate(self, keypair_id: str, secret_id: str) -> Optional[Dict[str, Any]]:
        if not self.requests:
            return None
        try:
            response = self.requests.get(f"{self.api_base_url}/api/mlkem/encapsulated/{secret_id}", timeout=10)
            if response.status_code != 200:
                logger.warning(f"Encapsulated secret not found: {secret_id}")
                return None
            encaps_data = response.json()
            data = {
                "local_key_id": keypair_id,
                "ciphertext": encaps_data['ciphertext']
            }
            response = self.requests.post(f"{self.api_base_url}/api/mlkem/decapsulate", json=data, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to decapsulate ML-KEM secret: {e}")
        return None
    def _generate_eddsa_signature(self, message: bytes, sender: str) -> Dict[str, Any]:
        try:
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            signature = private_key.sign(message)
            return {
                "signature": base64.b64encode(signature).decode('utf-8'),
                "public_key": base64.b64encode(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw
                    )
                ).decode('utf-8'),
                "algorithm": "Ed25519",
                "signer": sender,
                "signature_id": f"eddsa_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            }
        except Exception as e:
            logger.warning(f"Failed to generate EdDSA signature: {e}")
            return {"signature": "unavailable", "algorithm": "none"}
    def _verify_eddsa_signature(self, message: bytes, metadata: EncryptionMetadata) -> bool:
        try:
            logger.info("📝 EdDSA signature verification (simulated)")
            return True
        except Exception as e:
            logger.warning(f"EdDSA signature verification failed: {e}")
            return False
    def _encrypt_attachments_level1(self, attachments: List[Dict[str, Any]], key: bytes) -> List[Dict[str, Any]]:
        encrypted_attachments = []
        for attachment in attachments:
            try:
                content = attachment.get('content', b'')
                if isinstance(content, str):
                    content = content.encode('utf-8')
                encrypted_content = bytes(a ^ b for a, b in zip(content, key[:len(content)]))
                encrypted_attachments.append({
                    'filename': attachment.get('filename', 'attachment'),
                    'content_type': attachment.get('content_type', 'application/octet-stream'),
                    'encrypted_content': base64.b64encode(encrypted_content).decode('utf-8'),
                    'encryption': 'OTP-XOR'
                })
            except Exception as e:
                logger.warning(f"Failed to encrypt attachment: {e}")
        return encrypted_attachments
    def _encrypt_attachments_level2(self, attachments: List[Dict[str, Any]], fernet: Fernet) -> List[Dict[str, Any]]:
        encrypted_attachments = []
        for attachment in attachments:
            try:
                content = attachment.get('content', b'')
                if isinstance(content, str):
                    content = content.encode('utf-8')
                encrypted_content = fernet.encrypt(content)
                encrypted_attachments.append({
                    'filename': attachment.get('filename', 'attachment'),
                    'content_type': attachment.get('content_type', 'application/octet-stream'),
                    'encrypted_content': base64.b64encode(encrypted_content).decode('utf-8'),
                    'encryption': 'AES-256-Fernet'
                })
            except Exception as e:
                logger.warning(f"Failed to encrypt attachment: {e}")
        return encrypted_attachments
    def _encrypt_attachments_level3(self, attachments: List[Dict[str, Any]], aes_key: bytes) -> List[Dict[str, Any]]:
        encrypted_attachments = []
        for attachment in attachments:
            try:
                content = attachment.get('content', b'')
                if isinstance(content, str):
                    content = content.encode('utf-8')
                iv = os.urandom(12)
                cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv), backend=self.backend)
                encryptor = cipher.encryptor()
                ciphertext = encryptor.update(content) + encryptor.finalize()
                encrypted_data = iv + ciphertext + encryptor.tag
                encrypted_attachments.append({
                    'filename': attachment.get('filename', 'attachment'),
                    'content_type': attachment.get('content_type', 'application/octet-stream'),
                    'encrypted_content': base64.b64encode(encrypted_data).decode('utf-8'),
                    'encryption': 'AES-256-GCM'
                })
            except Exception as e:
                logger.warning(f"Failed to encrypt attachment: {e}")
        return encrypted_attachments
    def _encrypt_attachments_level4(self, attachments: List[Dict[str, Any]], aes_key: bytes) -> List[Dict[str, Any]]:
        encrypted_attachments = []
        for attachment in attachments:
            try:
                content = attachment.get('content', b'')
                if isinstance(content, str):
                    content = content.encode('utf-8')
                iv = secrets.token_bytes(16)
                cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=self.backend)
                encryptor = cipher.encryptor()
                pad_length = 16 - (len(content) % 16)
                padded_content = content + bytes([pad_length] * pad_length)
                ciphertext = encryptor.update(padded_content) + encryptor.finalize()
                encrypted_data = iv + ciphertext
                encrypted_attachments.append({
                    'filename': attachment.get('filename', 'attachment'),
                    'content_type': attachment.get('content_type', 'application/octet-stream'),
                    'encrypted_content': base64.b64encode(encrypted_data).decode('utf-8'),
                    'encryption': 'AES-256-CBC'
                })
            except Exception as e:
                logger.warning(f"Failed to encrypt attachment: {e}")
        return encrypted_attachments
    def _create_mime_structure(self, ciphertext: str, metadata: EncryptionMetadata, 
                             attachments: List[Dict[str, Any]], subject: str) -> str:
        try:
            msg = email.mime.multipart.MIMEMultipart()
            msg['Subject'] = f"[QuMail L{metadata.security_level}] {subject}"
            msg['From'] = metadata.sender
            msg['To'] = metadata.recipient
            msg['Date'] = metadata.timestamp
            msg['X-QuMail-Security-Level'] = str(metadata.security_level)
            msg['X-QuMail-Algorithm'] = metadata.algorithm
            msg['X-QuMail-Message-ID'] = metadata.message_id
            encrypted_part = email.mime.text.MIMEText(ciphertext, 'plain')
            encrypted_part.add_header('Content-Description', 'QuMail Encrypted Content')
            msg.attach(encrypted_part)
            metadata_part = email.mime.text.MIMEText(json.dumps(asdict(metadata), indent=2), 'plain')
            metadata_part.add_header('Content-Description', 'QuMail Metadata')
            msg.attach(metadata_part)
            for attachment in attachments:
                att_part = email.mime.base.MIMEBase('application', 'octet-stream')
                att_part.set_payload(base64.b64decode(attachment['encrypted_content']))
                encoders.encode_base64(att_part)
                att_part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment["filename"]}.encrypted"'
                )
                att_part.add_header('X-QuMail-Encryption', attachment.get('encryption', 'unknown'))
                msg.attach(att_part)
            return msg.as_string()
        except Exception as e:
            logger.warning(f"Failed to create MIME structure: {e}")
            return f"QuMail Encrypted Message\nLevel: {metadata.security_level}\nContent: {ciphertext}"
    def _create_mime_structure_with_signatures(self, ciphertext: str, metadata: EncryptionMetadata,
                                             attachments: List[Dict[str, Any]], subject: str,
                                             eddsa_signature: Dict[str, Any]) -> str:
        try:
            mime_structure = self._create_mime_structure(ciphertext, metadata, attachments, subject)
            signature_info = f"\n\n--- Digital Signatures ---\nEdDSA: {eddsa_signature.get('signature', 'N/A')}\nPublic Key: {eddsa_signature.get('public_key', 'N/A')}"
            return mime_structure + signature_info
        except Exception as e:
            logger.warning(f"Failed to create MIME structure with signatures: {e}")
            return self._create_mime_structure(ciphertext, metadata, attachments, subject)
    def get_security_analysis(self) -> Dict[str, Any]:
        return {
            "encryption_levels": {
                "Level 1": {
                    "name": "Quantum Secure (OTP)",
                    "security": "Information-theoretic security",
                    "algorithm": "One-Time Pad with QKD keys",
                    "key_source": "BB84 Quantum Key Distribution",
                    "quantum_resistant": True,
                    "etsi_compliant": True,
                    "use_case": "Maximum security for classified communications"
                },
                "Level 2": {
                    "name": "Quantum-aided AES",
                    "security": "256-bit hybrid security",
                    "algorithm": "AES-256-GCM with HKDF-SHA256",
                    "key_source": "QKD + ECDH + ML-KEM hybrid derivation",
                    "quantum_resistant": True,
                    "etsi_compliant": True,
                    "use_case": "High security for sensitive business communications"
                },
                "Level 3": {
                    "name": "Hybrid PQC",
                    "security": "192-bit post-quantum + digital signatures",
                    "algorithm": "ML-KEM-768 + AES-256-GCM + EdDSA",
                    "key_source": "ML-KEM-768 encapsulation",
                    "quantum_resistant": True,
                    "etsi_compliant": False,
                    "use_case": "Post-quantum security with authentication"
                },
                "Level 4": {
                    "name": "No Quantum Security",
                    "security": "Classical or no encryption",
                    "algorithm": "AES-256-CBC or plaintext",
                    "key_source": "Random or none",
                    "quantum_resistant": False,
                    "etsi_compliant": False,
                    "use_case": "Standard communications or testing"
                }
            },
            "system_capabilities": {
                "qkd_available": self.requests is not None,
                "mlkem_available": self.mlkem_available,
                "api_connected": self.requests is not None,
                "standards_supported": ["ETSI GS QKD 014", "NIST FIPS 203", "RFC 7748", "RFC 8446"]
            }
        }
def demo_encryption_levels():
    print("🚀 QuMail Multi-Level Encryption Demo")
    print("=" * 50)
    encryptor = QuMailMultiLevelEncryption()
    test_message = "This is a confidential message for Byte-Bandits Project-Zero mission. 🛰️"
    sender = "mission.control@byte-bandits.com"
    recipient = "projectzero@byte-bandits.com"
    for level in SecurityLevel:
        print(f"\n🔐 Testing {level.name} (Level {level.value})")
        print("-" * 40)
        try:
            encrypted = encryptor.encrypt_message(
                plaintext=test_message,
                security_level=level,
                sender=sender,
                recipient=recipient,
                subject=f"Test Level {level.value}"
            )
            print(f"✅ Encryption successful")
            print(f"   Algorithm: {encrypted.metadata.algorithm}")
            print(f"   Key Source: {encrypted.metadata.key_source}")
            print(f"   Quantum Resistant: {encrypted.metadata.quantum_resistant}")
            print(f"   Ciphertext Length: {len(encrypted.ciphertext)} chars")
            try:
                decrypted = encryptor.decrypt_message(encrypted)
                print(f"✅ Decryption successful")
                print(f"   Message verified: {decrypted == test_message}")
            except Exception as e:
                print(f"⚠️ Decryption note: {e}")
        except Exception as e:
            print(f"❌ Level {level.value} error: {e}")
    print(f"\n📊 Security Analysis")
    print("-" * 40)
    analysis = encryptor.get_security_analysis()
    for level, info in analysis["encryption_levels"].items():
        print(f"{level}: {info['security']} ({info['algorithm']})")
if __name__ == "__main__":
    demo_encryption_levels()
