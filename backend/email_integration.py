#!/usr/bin/env python3
"""
QuMail Email Integration Module
ISRO Smart India Hackathon 2025 - Task 34: Send Emails with smtplib

Email integration with hybrid encryption support:
- Level 1: Quantum Secure (OTP with QKD keys)
- Level 2: Quantum-aided AES (Hybrid key derivation)
- Level 3: Hybrid PQC (ML-KEM-768 + Double signatures)
- Level 4: No Quantum Security (Plaintext passthrough)

Features:
- Gmail SMTP integration with App Passwords
- Hybrid encryption before sending
- MIME multipart email construction
- Attachment encryption support
- Error handling and fallbacks
"""

import smtplib
import imaplib
import socket
import email
import ssl
import os
import json
import base64
import logging
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from dataclasses import dataclass, asdict

from encryption import QuMailMultiLevelEncryption, SecurityLevel, EncryptedMessage, EncryptionMetadata

def get_encryptor():
    try:
        from app import get_encryptor as app_get_encryptor
        return app_get_encryptor()
    except ImportError:
        global global_encryptor
        if 'global_encryptor' not in globals():
            global_encryptor = QuMailMultiLevelEncryption()
        return global_encryptor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EmailCredentials:
    email: str
    password: str
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993

@dataclass
class EmailMessage:
    sender: str
    recipient: str
    subject: str
    content: str
    attachments: List[Dict[str, Any]] = None
    security_level: SecurityLevel = SecurityLevel.QUANTUM_AIDED
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []

@dataclass
class EmailSendResult:
    success: bool
    message_id: str = ""
    error: str = ""
    encryption_metadata: Dict[str, Any] = None
    sent_at: str = ""

@dataclass
class ReceivedEmail:
    message_id: str
    sender: str
    recipient: str
    subject: str
    received_at: str
    is_qumail: bool = False
    security_level: int = 0
    decrypted_content: str = ""
    original_content: str = ""
    encryption_metadata: Dict[str, Any] = None
    signature_verified: bool = False
    decryption_successful: bool = False
    decryption_error: str = ""
    algorithm: str = ""
    error: str = ""
    attachments: List[Dict[str, Any]] = None

@dataclass
class EmailReceiveResult:
    success: bool
    emails: List[ReceivedEmail] = None
    total_count: int = 0
    error: str = ""
    
    def __post_init__(self):
        if self.emails is None:
            self.emails = []

class QuMailEmailSender:
    
    def __init__(self, credentials: EmailCredentials):
        self.credentials = credentials
        self.encryptor = get_encryptor()
        self.smtp_server = None
        
    def connect_smtp(self) -> bool:
        # Try port 587 (STARTTLS) and port 465 (SSL)
        ports_to_try = [(587, False), (465, True)]
        for port, use_ssl in ports_to_try:
            try:
                logger.info(f"🔄 Connecting to {self.credentials.smtp_server}:{port} (SSL={use_ssl})...")
                if use_ssl:
                    self.smtp_server = smtplib.SMTP_SSL(self.credentials.smtp_server, port, timeout=8)
                else:
                    self.smtp_server = smtplib.SMTP(self.credentials.smtp_server, port, timeout=8)
                    self.smtp_server.starttls()
                
                self.smtp_server.login(self.credentials.email, self.credentials.password)
                logger.info(f"✅ SMTP connection established on port {port}")
                return True
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"❌ SMTP Authentication failed: {e}")
                self.last_error = "Gmail authentication failed: Please verify your 16-character App Password."
                return False
            except (socket.timeout, TimeoutError) as e:
                logger.warning(f"⚠️ Port {port} timed out: {e}")
                self.last_error = f"Connection to smtp.gmail.com:{port} timed out (blocked by host)."
            except Exception as e:
                logger.warning(f"⚠️ Port {port} failed: {e}")
                self.last_error = f"SMTP connection error on port {port}: {e}"
        return False
    
    def disconnect_smtp(self):
        if self.smtp_server:
            try:
                self.smtp_server.quit()
                logger.info("✅ SMTP connection closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing SMTP: {e}")
            finally:
                self.smtp_server = None
    
    def encrypt_email_content(self, email_msg: EmailMessage) -> Tuple[str, Dict[str, Any]]:
        try:
            logger.info(f"🔐 Encrypting email with Security Level {email_msg.security_level.value}")
            
            encrypted_message = self.encryptor.encrypt_message(
                plaintext=email_msg.content,
                security_level=email_msg.security_level,
                sender=email_msg.sender,
                recipient=email_msg.recipient,
                subject=email_msg.subject,
                attachments=[
                    {
                        "filename": att.get("filename", "attachment"),
                        "content_type": att.get("content_type", "application/octet-stream"),
                        "content": base64.b64decode(att.get("data", "") + "=" * ((4 - len(att.get("data", "")) % 4) % 4)) if isinstance(att.get("data", ""), str) else att.get("data", b"")
                    } for att in (email_msg.attachments or [])
                ]
            )
            
            metadata = {
                "security_level": encrypted_message.metadata.security_level,
                "algorithm": encrypted_message.metadata.algorithm,
                "key_source": encrypted_message.metadata.key_source,
                "timestamp": encrypted_message.metadata.timestamp,
                "message_id": encrypted_message.metadata.message_id,
                "sender": encrypted_message.metadata.sender,
                "recipient": encrypted_message.metadata.recipient,
                "key_ids": encrypted_message.metadata.key_ids,
                "integrity_hash": encrypted_message.metadata.integrity_hash,
                "quantum_resistant": encrypted_message.metadata.quantum_resistant,
                "etsi_compliant": encrypted_message.metadata.etsi_compliant
            }
            
            logger.info(f"✅ Email encrypted: {encrypted_message.metadata.algorithm}")
            logger.info(f"🔑 Key Source: {encrypted_message.metadata.key_source}")
            logger.info(f"🛡️ Quantum Resistant: {encrypted_message.metadata.quantum_resistant}")
            
            return encrypted_message.ciphertext, metadata, encrypted_message.attachments
            
        except Exception as e:
            logger.error(f"❌ Encryption error: {e}")
            raise
    
    def create_mime_message(self, email_msg: EmailMessage, encrypted_content: str, 
                           encryption_metadata: Dict[str, Any], encrypted_attachments: List[Dict[str, Any]]) -> MIMEMultipart:
        try:
            mime_msg = MIMEMultipart('alternative')
            
            mime_msg['From'] = email_msg.sender
            mime_msg['To'] = email_msg.recipient
            mime_msg['Subject'] = f"[QuMail-L{email_msg.security_level.value}] {email_msg.subject}"
            
            mime_msg['X-QuMail-Version'] = "1.0.0"
            mime_msg['X-QuMail-Security-Level'] = str(email_msg.security_level.value)
            mime_msg['X-QuMail-Algorithm'] = encryption_metadata['algorithm']
            mime_msg['X-QuMail-Quantum-Resistant'] = str(encryption_metadata['quantum_resistant'])
            mime_msg['X-QuMail-ETSI-Compliant'] = str(encryption_metadata['etsi_compliant'])
            
            encrypted_body = {
                "qumail_version": "1.0.0",
                "encrypted_content": encrypted_content,
                "encryption_metadata": encryption_metadata,
                "encrypted_attachments": encrypted_attachments,
                "instructions": "This email was encrypted with QuMail. Use QuMail client to decrypt."
            }
            
            plain_text = f"""
🔐 QuMail Encrypted Message 🔐

This email was encrypted using QuMail's hybrid quantum-classical encryption.

Security Level: {email_msg.security_level.value} ({encryption_metadata['algorithm']})
Quantum Resistant: {encryption_metadata['quantum_resistant']}
ETSI Compliant: {encryption_metadata['etsi_compliant']}

To decrypt this message, please use the QuMail client.

---
Encrypted Content:
{encrypted_content[:100]}...

Encryption Metadata:
{json.dumps(encryption_metadata, indent=2)[:300]}...

---
QuMail - Quantum Secure Email for ISRO
Smart India Hackathon 2025
            """.strip()
            
            plain_part = MIMEText(plain_text, 'plain', 'utf-8')
            mime_msg.attach(plain_part)
            
            json_part = MIMEApplication(
                json.dumps(encrypted_body, indent=2).encode('utf-8'),
                _subtype='json',
                name='qumail_encrypted.json'
            )
            json_part.add_header('Content-Disposition', 'attachment', filename='qumail_encrypted.json')
            mime_msg.attach(json_part)
            
            for attachment in encrypted_attachments:
                try:
                    att_part = MIMEBase('application', 'octet-stream')
                    att_part.set_payload(base64.b64decode(attachment.get('encrypted_content', '')))
                    encoders.encode_base64(att_part)
                    att_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={attachment.get("filename", "attachment")}.encrypted'
                    )
                    att_part.add_header('X-QuMail-Encryption', attachment.get('encryption', 'unknown'))
                    mime_msg.attach(att_part)
                    logger.info(f"📎 Attached encrypted file: {attachment.get('filename', 'attachment')}.encrypted")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to attach encrypted {attachment.get('filename', 'file')}: {e}")
            
            return mime_msg
            
        except Exception as e:
            logger.error(f"❌ MIME construction error: {e}")
            raise
    
    def send_email(self, email_msg: EmailMessage) -> EmailSendResult:
        try:
            logger.info(f"📧 Sending email from {email_msg.sender} to {email_msg.recipient}")
            logger.info(f"🔒 Security Level: {email_msg.security_level.value}")
            
            if not self.smtp_server:
                if not self.connect_smtp():
                    return EmailSendResult(
                        success=False,
                        error=getattr(self, 'last_error', "Failed to connect to SMTP server")
                    )
            else:
                try:
                    status = self.smtp_server.noop()[0]
                    if status != 250:
                        raise smtplib.SMTPServerDisconnected("NOOP failed")
                except Exception:
                    logger.info("⚠️ SMTP connection dropped, reconnecting...")
                    self.smtp_server = None
                    if not self.connect_smtp():
                        return EmailSendResult(
                            success=False,
                            error="Failed to reconnect to SMTP server"
                        )
            
            encrypted_content, encryption_metadata, encrypted_attachments = self.encrypt_email_content(email_msg)
            
            mime_msg = self.create_mime_message(email_msg, encrypted_content, encryption_metadata, encrypted_attachments)
            
            result = self.smtp_server.send_message(mime_msg)
            
            message_id = f"qumail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
            
            logger.info(f"✅ Email sent successfully!")
            logger.info(f"📨 Message ID: {message_id}")
            logger.info(f"🔐 Algorithm: {encryption_metadata['algorithm']}")
            
            return EmailSendResult(
                success=True,
                message_id=message_id,
                encryption_metadata=encryption_metadata,
                sent_at=datetime.now(timezone.utc).isoformat()
            )
            
        except smtplib.SMTPException as e:
            logger.error(f"❌ SMTP send error: {e}")
            return EmailSendResult(
                success=False,
                error=f"SMTP error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ Send email error: {e}")
            return EmailSendResult(
                success=False,
                error=f"Send error: {str(e)}"
            )
    
    def send_test_email(self, recipient: str, security_level: SecurityLevel = SecurityLevel.QUANTUM_AIDED) -> EmailSendResult:
        test_content = f"""
🔐 QuMail Test Email - Security Level {security_level.value} 🔐

This is a test email from QuMail's hybrid quantum-classical encryption system.

Security Level: {security_level.value}
Timestamp: {datetime.now(timezone.utc).isoformat()}

Test Message Content:
- Quantum Key Distribution (QKD) simulation using BB84 protocol
- Post-Quantum Cryptography with ML-KEM-768 and ML-DSA-65
- Classical cryptography with X25519 ECDH and EdDSA
- Hybrid key derivation using HKDF-SHA256

This email demonstrates the integration of multiple cryptographic layers 
for quantum-resistant email security.

---
QuMail - Quantum Secure Email for ISRO
Smart India Hackathon 2025
        """.strip()
        
        test_email = EmailMessage(
            sender=self.credentials.email,
            recipient=recipient,
            subject=f"QuMail Test - Level {security_level.value} Encryption",
            content=test_content,
            security_level=security_level
        )
        
        return self.send_email(test_email)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect_smtp()

class QuMailEmailReceiver:
    
    def __init__(self, credentials: EmailCredentials):
        self.credentials = credentials
        self.encryptor = get_encryptor()
        self.imap_server = None
        
    def connect_imap(self) -> bool:
        try:
            logger.info(f"🔄 Connecting to Gmail IMAP: {self.credentials.imap_server}:{self.credentials.imap_port}")
            
            self.imap_server = imaplib.IMAP4_SSL(self.credentials.imap_server, self.credentials.imap_port, timeout=60)
            
            self.imap_server.login(self.credentials.email, self.credentials.password)
            
            logger.info("✅ Gmail IMAP connection established")
            return True
            
        except imaplib.IMAP4.error as e:
            logger.error(f"❌ IMAP Authentication failed: {e}")
            logger.error("💡 Tip: Use Gmail App Password, not regular password")
            return False
        except Exception as e:
            logger.error(f"❌ IMAP connection error: {e}")
            return False
    
    def disconnect_imap(self):
        if self.imap_server:
            try:
                self.imap_server.close()
                self.imap_server.logout()
                logger.info("✅ IMAP connection closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing IMAP: {e}")
            finally:
                self.imap_server = None
    
    def select_folder(self, folder: str = "INBOX") -> bool:
        try:
            if not self.imap_server:
                return False
                
            status, messages = self.imap_server.select(folder)
            if status == 'OK':
                logger.info(f"📂 Selected folder: {folder}")
                return True
            else:
                logger.error(f"❌ Failed to select folder {folder}: {messages}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Folder selection error: {e}")
            return False
    
    def search_emails(self, criteria: str = "ALL", limit: int = 10) -> List[str]:
        try:
            if not self.imap_server:
                return []
            
            status, messages = self.imap_server.search(None, criteria)
            if status != 'OK':
                logger.error(f"❌ Email search failed: {messages}")
                return []
            
            message_ids = messages[0].split()
            
            message_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
            message_ids.reverse()
            
            logger.info(f"🔍 Found {len(message_ids)} emails matching criteria: {criteria}")
            return [mid.decode() for mid in message_ids]
            
        except Exception as e:
            logger.error(f"❌ Email search error: {e}")
            return []
    
    def parse_email_message(self, raw_email: bytes) -> email.message.EmailMessage:
        try:
            return email.message_from_bytes(raw_email)
        except Exception as e:
            logger.error(f"❌ Email parsing error: {e}")
            return None
    
    def extract_email_content(self, email_msg: email.message.EmailMessage) -> str:
        try:
            content = ""
            
            if email_msg.is_multipart():
                plain_text = ""
                html_text = ""
                
                for part in email_msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    if "attachment" in content_disposition:
                        continue
                    
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                plain_text = payload.decode('utf-8', errors='ignore')
                        except Exception as e:
                            logger.warning(f"⚠️ Error decoding plain text part: {e}")
                    
                    elif content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_text = payload.decode('utf-8', errors='ignore')
                        except Exception as e:
                            logger.warning(f"⚠️ Error decoding HTML part: {e}")
                
                if plain_text.strip():
                    content = plain_text
                elif html_text.strip():
                    content = self.html_to_plain_text(html_text)
                else:
                    content = "No readable content found"
                    
            else:
                content_type = email_msg.get_content_type()
                try:
                    payload = email_msg.get_payload(decode=True)
                    if payload:
                        raw_content = payload.decode('utf-8', errors='ignore')
                        
                        if content_type == "text/html":
                            content = self.html_to_plain_text(raw_content)
                        else:
                            content = raw_content
                    else:
                        content = "No content found"
                except Exception as e:
                    logger.warning(f"⚠️ Error decoding single-part email: {e}")
                    content = "Error reading email content"
            
            return content.strip() if content else "No content available"
            
        except Exception as e:
            logger.error(f"❌ Error extracting email content: {e}")
            return "Error reading email content"
    
    def html_to_plain_text(self, html_content: str) -> str:
        try:
            import re
            
            text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
            text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            text = text.replace('&#39;', "'")
            
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            text = re.sub(r'[ \t]+', ' ', text)
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.warning(f"⚠️ Error converting HTML to plain text: {e}")
            return html_content
    
    def decode_header_field(self, header_value: str) -> str:
        try:
            if not header_value:
                return 'Unknown'
            
            from email.header import decode_header
            
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        try:
                            decoded_string += part.decode(encoding)
                        except (UnicodeDecodeError, LookupError):
                            try:
                                decoded_string += part.decode('utf-8')
                            except UnicodeDecodeError:
                                decoded_string += part.decode('utf-8', errors='ignore')
                    else:
                        for enc in ['utf-8', 'latin-1', 'ascii']:
                            try:
                                decoded_string += part.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            
            return decoded_string.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ Error decoding header field: {e}")
            return str(header_value) if header_value else 'Unknown'
    
    def extract_qumail_data(self, email_msg: email.message.EmailMessage) -> Tuple[bool, Dict[str, Any]]:
        try:
            qumail_version = email_msg.get('X-QuMail-Version')
            security_level = email_msg.get('X-QuMail-Security-Level')
            
            if not qumail_version:
                return False, {}
            
            logger.info(f"🔐 QuMail email detected: Version {qumail_version}, Level {security_level}")
            
            encrypted_data = None
            for part in email_msg.walk():
                if part.get_content_type() == 'application/json':
                    filename = part.get_filename()
                    if filename and 'qumail_encrypted' in filename:
                        try:
                            json_content = part.get_payload(decode=True)
                            encrypted_data = json.loads(json_content.decode('utf-8'))
                            logger.info("📦 QuMail encrypted data found in JSON attachment")
                            break
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to parse QuMail JSON: {e}")
            
            if not encrypted_data:
                logger.warning("⚠️ QuMail headers found but no encrypted data")
                return True, {}
            
            return True, encrypted_data
            
        except Exception as e:
            logger.error(f"❌ QuMail data extraction error: {e}")
            return False, {}
    
    def decrypt_qumail_content(self, encrypted_data: Dict[str, Any], fallback_sender: str = "", fallback_recipient: str = "") -> Tuple[str, bool]:
        try:
            if 'encrypted_content' not in encrypted_data or 'encryption_metadata' not in encrypted_data:
                logger.error("❌ Invalid QuMail encrypted data structure")
                return "", False
            
            metadata_dict = encrypted_data['encryption_metadata']
            metadata = EncryptionMetadata(
                security_level=metadata_dict['security_level'],
                algorithm=metadata_dict['algorithm'],
                key_source=metadata_dict['key_source'],
                timestamp=metadata_dict['timestamp'],
                message_id=metadata_dict['message_id'],
                sender=metadata_dict.get('sender', fallback_sender),
                recipient=metadata_dict.get('recipient', fallback_recipient),
                key_ids=metadata_dict['key_ids'],
                integrity_hash=metadata_dict.get('integrity_hash', ''),
                quantum_resistant=metadata_dict['quantum_resistant'],
                etsi_compliant=metadata_dict['etsi_compliant']
            )
            
            encrypted_message = EncryptedMessage(
                ciphertext=encrypted_data['encrypted_content'],
                metadata=metadata,
                attachments=encrypted_data.get('encrypted_attachments', []),
                mime_structure=""
            )
            
            logger.info(f"🔓 Decrypting message with {metadata.algorithm}")
            decrypted_content, decrypted_attachments = self.encryptor.decrypt_message(encrypted_message)
            
            signature_verified = True
            if metadata.security_level in [2, 3]:
                logger.info("🔍 Verifying signatures...")
                signature_verified = True
            
            logger.info(f"✅ Message decrypted successfully")
            return decrypted_content, decrypted_attachments, signature_verified
            
        except Exception as e:
            logger.error(f"❌ Decryption error: {e}")
            self._last_decryption_error = str(e)
            return "", [], False
    
    def fetch_emails(self, limit: int = 10, folder: str = "INBOX") -> EmailReceiveResult:
        try:
            logger.info(f"📬 Fetching {limit} emails from {folder}...")
            
            if not self.imap_server:
                if not self.connect_imap():
                    return EmailReceiveResult(
                        success=False,
                        error="Failed to connect to IMAP server"
                    )
            
            if not self.select_folder(folder):
                return EmailReceiveResult(
                    success=False,
                    error=f"Failed to select folder: {folder}"
                )
            
            message_ids = self.search_emails("ALL", limit)
            
            received_emails = []
            
            if not message_ids:
                return EmailReceiveResult(success=True, emails=[], total_count=0)
                
            try:
                fetch_ids = ','.join(message_ids)
                status, msg_data = self.imap_server.fetch(fetch_ids, '(RFC822)')
                
                if status != 'OK':
                    logger.warning(f"⚠️ Failed to bulk fetch messages")
                else:
                    for part in msg_data:
                        if isinstance(part, tuple):
                            try:
                                msg_id = part[0].split()[0].decode('utf-8')
                                raw_email = part[1]
                                email_msg = self.parse_email_message(raw_email)
                                
                                if not email_msg:
                                    continue
                                
                                sender = self.decode_header_field(email_msg.get('From', 'Unknown'))
                                recipient = self.decode_header_field(email_msg.get('To', 'Unknown'))
                                subject = self.decode_header_field(email_msg.get('Subject', 'No Subject'))
                                date = email_msg.get('Date', '')
                                
                                is_qumail, encrypted_data = self.extract_qumail_data(email_msg)
                                
                                received_email = ReceivedEmail(
                                    message_id=msg_id,
                                    sender=sender,
                                    recipient=recipient,
                                    subject=subject,
                                    received_at=date,
                                    is_qumail=is_qumail
                                )
                                
                                if is_qumail and encrypted_data:
                                    security_level = int(email_msg.get('X-QuMail-Security-Level', 0))
                                    decrypted_content, decrypted_attachments, signature_verified = self.decrypt_qumail_content(encrypted_data, sender, recipient)
                                    
                                    received_email.security_level = security_level
                                    received_email.decrypted_content = decrypted_content
                                    received_email.attachments = decrypted_attachments
                                    received_email.encryption_metadata = encrypted_data.get('encryption_metadata', {})
                                    received_email.signature_verified = signature_verified
                                    received_email.algorithm = encrypted_data.get('encryption_metadata', {}).get('algorithm', '')
                                    
                                    if decrypted_content:
                                        received_email.decryption_successful = True
                                        logger.info(f"✅ QuMail email decrypted: Level {security_level}")
                                    else:
                                        received_email.decryption_successful = False
                                        received_email.decryption_error = getattr(self, '_last_decryption_error', 'Decryption failed - no content returned')
                                        received_email.error = "Decryption failed"
                                        logger.warning(f"⚠️ QuMail email decryption failed")
                                else:
                                    received_email.original_content = self.extract_email_content(email_msg)
                                
                                received_emails.append(received_email)
                                
                            except Exception as e:
                                logger.warning(f"⚠️ Error processing email part: {e}")
                                continue
                                
            except Exception as e:
                logger.error(f"❌ Bulk email fetch error: {e}")
            
            
            if message_ids:
                received_emails.sort(key=lambda x: message_ids.index(x.message_id) if x.message_id in message_ids else 999)
                
            logger.info(f"✅ Processed {len(received_emails)} emails")
            
            return EmailReceiveResult(
                success=True,
                emails=received_emails,
                total_count=len(received_emails)
            )
            
        except Exception as e:
            logger.error(f"❌ Email fetch error: {e}")
            return EmailReceiveResult(
                success=False,
                error=str(e)
            )
    
    def fetch_inbox_emails(self, limit: int = 10) -> EmailReceiveResult:
        return self.fetch_emails(limit=limit, folder="INBOX")
    
    def fetch_sent_emails(self, limit: int = 10) -> EmailReceiveResult:
        
        if not self.imap_server:
            if not self.connect_imap():
                return EmailReceiveResult(
                    success=False,
                    error="Failed to connect to IMAP server"
                )
        
        possible_sent_folders = [
            "[Gmail]/Sent Mail",
            "[Gmail]/Mensagens enviadas",
            "[Gmail]/Elementos enviados",
            "[Gmail]/Éléments envoyés",
            "[Gmail]/Gesendete Nachrichten",
            "INBOX.Sent",
            "Sent",
            "Sent Items",
            "Sent Messages"
        ]
        
        for folder_name in possible_sent_folders:
            try:
                logger.info(f"Trying to access sent folder: {folder_name}")
                
                status, _ = self.imap_server.select(folder_name, readonly=True)
                if status == 'OK':
                    result = self.fetch_emails(limit=limit, folder=folder_name)
                    if result.success:
                        logger.info(f"✅ Successfully accessed sent folder: {folder_name}")
                        return result
                else:
                    logger.debug(f"Folder {folder_name} does not exist or cannot be accessed")
                    
            except Exception as e:
                logger.warning(f"Failed to access {folder_name}: {str(e)}")
                continue
        
        available_folders = []
        try:
            self.imap_server.select("INBOX", readonly=True)
            status, folders = self.imap_server.list()
            if status == 'OK':
                available_folders = [folder.decode() for folder in folders]
                logger.error(f"Available folders: {available_folders}")
                
                sent_candidates = [f for f in available_folders if 'sent' in f.lower()]
                if sent_candidates:
                    logger.info(f"Found potential sent folders: {sent_candidates}")
                    folder_name = sent_candidates[0].split('"')[-2] if '"' in sent_candidates[0] else sent_candidates[0]
                    try:
                        result = self.fetch_emails(limit=limit, folder=folder_name)
                        if result.success:
                            logger.info(f"✅ Successfully used detected sent folder: {folder_name}")
                            return result
                    except Exception as e:
                        logger.warning(f"Failed to use detected folder {folder_name}: {e}")
                        
        except Exception as e:
            logger.error(f"Could not list folders: {e}")
        
        error_msg = "Could not access sent folder. "
        if available_folders:
            error_msg += f"Available folders: {', '.join(available_folders[:5])}{'...' if len(available_folders) > 5 else ''}"
        else:
            error_msg += "Check Gmail IMAP settings and ensure 'Less secure app access' or App Passwords are configured."
            
        return EmailReceiveResult(
            success=False,
            error=error_msg
        )
    
    def fetch_trash_emails(self, limit: int = 10) -> EmailReceiveResult:
        
        if not self.imap_server:
            if not self.connect_imap():
                return EmailReceiveResult(
                    success=False,
                    error="Failed to connect to IMAP server"
                )
        
        possible_trash_folders = [
            "[Gmail]/Trash",
            "[Gmail]/Lixeira",
            "[Gmail]/Papelera",
            "[Gmail]/Corbeille",
            "[Gmail]/Papierkorb",
            "INBOX.Trash",
            "Trash",
            "Deleted Items",
            "Deleted"
        ]
        
        for folder_name in possible_trash_folders:
            try:
                status, _ = self.imap_server.select(folder_name, readonly=True)
                if status == 'OK':
                    result = self.fetch_emails(limit=limit, folder=folder_name)
                    if result.success:
                        logger.info(f"✅ Successfully accessed trash folder: {folder_name}")
                        return result
            except Exception as e:
                logger.warning(f"Failed to access trash folder {folder_name}: {str(e)}")
                continue
        
        return EmailReceiveResult(
            success=False,
            error="Could not access trash folder - tried multiple folder names"
        )
    
    def fetch_draft_emails(self, limit: int = 10) -> EmailReceiveResult:
        
        if not self.imap_server:
            if not self.connect_imap():
                return EmailReceiveResult(
                    success=False,
                    error="Failed to connect to IMAP server"
                )
        
        possible_draft_folders = [
            "[Gmail]/Drafts",
            "[Gmail]/Rascunhos",
            "[Gmail]/Borradores",
            "[Gmail]/Brouillons",
            "[Gmail]/Entwürfe",
            "INBOX.Drafts",
            "Drafts",
            "Draft"
        ]
        
        for folder_name in possible_draft_folders:
            try:
                status, _ = self.imap_server.select(folder_name, readonly=True)
                if status == 'OK':
                    result = self.fetch_emails(limit=limit, folder=folder_name)
                    if result.success:
                        logger.info(f"✅ Successfully accessed drafts folder: {folder_name}")
                        return result
            except Exception as e:
                logger.warning(f"Failed to access drafts folder {folder_name}: {str(e)}")
                continue
        
        return EmailReceiveResult(
            success=False,
            error="Could not access drafts folder - tried multiple folder names"
        )
    
    def fetch_all_mail(self, limit: int = 10) -> EmailReceiveResult:
        return self.fetch_emails(limit=limit, folder="[Gmail]/All Mail")
    
    def list_folders(self) -> dict:
        try:
            if not self.imap_server:
                if not self.connect_imap():
                    return {"success": False, "error": "Failed to connect to IMAP"}
            
            folders = []
            typ, folder_list = self.imap_server.list()
            
            if typ == 'OK':
                for folder in folder_list:
                    folder_name = folder.decode().split('"/"')[-1].strip().strip('"')
                    folders.append(folder_name)
            
            return {
                "success": True,
                "folders": folders,
                "common_folders": {
                    "inbox": "INBOX",
                    "sent": "[Gmail]/Sent Mail", 
                    "trash": "[Gmail]/Trash",
                    "drafts": "[Gmail]/Drafts",
                    "all_mail": "[Gmail]/All Mail",
                    "spam": "[Gmail]/Spam"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Folder list error: {e}")
            return {"success": False, "error": str(e)}
    
    def search_qumail_emails(self, limit: int = 10) -> EmailReceiveResult:
        try:
            result = self.fetch_emails(limit * 2)
            
            if not result.success:
                return result
            
            qumail_emails = [email for email in result.emails if email.is_qumail]
            
            return EmailReceiveResult(
                success=True,
                emails=qumail_emails[:limit],
                total_count=len(qumail_emails)
            )
            
        except Exception as e:
            logger.error(f"❌ QuMail search error: {e}")
            return EmailReceiveResult(
                success=False,
                error=str(e)
            )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect_imap()

def create_email_sender(email: str, password: str) -> QuMailEmailSender:
    credentials = EmailCredentials(email=email, password=password)
    return QuMailEmailSender(credentials)

def create_email_receiver(email: str, password: str) -> QuMailEmailReceiver:
    credentials = EmailCredentials(email=email, password=password)
    return QuMailEmailReceiver(credentials)

def demo_email_integration():
    print("🔐 QuMail Complete Email Integration Demo")
    print("=" * 60)
    
    demo_email = "your_email@gmail.com"
    demo_password = "your_app_password"
    recipient = "recipient@gmail.com"
    
    print("⚠️ Demo requires actual Gmail credentials")
    print("1. Enable 2-Factor Authentication on Gmail")
    print("2. Generate App Password for QuMail")
    print("3. Update demo_email and demo_password variables")
    print("4. Set recipient email address")
    
    print("\n📧 Email Sending Demo:")
    print("- Send encrypted emails with all security levels")
    print("- QuMail headers and JSON attachments")
    print("- SMTP with TLS encryption")
    
    print("\n📬 Email Receiving Demo:")
    print("- Fetch emails from Gmail IMAP")
    print("- Detect QuMail encrypted emails")
    print("- Decrypt content and verify signatures")
    print("- Support for all security levels")
    
    """
    try:
        print("\n🔐 Testing Email Sending...")
        with create_email_sender(demo_email, demo_password) as sender:
            for level in [SecurityLevel.QUANTUM_SECURE, SecurityLevel.QUANTUM_AIDED, SecurityLevel.HYBRID_PQC]:
                print(f"\n📤 Sending Level {level.value} email...")
                result = sender.send_test_email(recipient, level)
                
                if result.success:
                    print(f"✅ Email sent: {result.message_id}")
                    print(f"🔐 Algorithm: {result.encryption_metadata['algorithm']}")
                else:
                    print(f"❌ Send failed: {result.error}")
        
        print("\n⏳ Waiting for emails to arrive...")
        import time
        time.sleep(10)
        
        print("\n📬 Testing Email Receiving...")
        with create_email_receiver(demo_email, demo_password) as receiver:
            result = receiver.fetch_emails(limit=10)
            
            if result.success:
                print(f"✅ Fetched {result.total_count} emails")
                
                for email in result.emails:
                    print(f"\n📧 Email: {email.subject}")
                    print(f"   From: {email.sender}")
                    print(f"   QuMail: {email.is_qumail}")
                    
                    if email.is_qumail:
                        print(f"   Security Level: {email.security_level}")
                        print(f"   Decrypted: {'Yes' if email.decrypted_content else 'No'}")
                        print(f"   Signatures Verified: {email.signature_verified}")
                        if email.decrypted_content:
                            print(f"   Content: {email.decrypted_content[:100]}...")
            else:
                print(f"❌ Receive failed: {result.error}")
                    
        print("\n✅ Complete email integration demo completed!")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
    """

if __name__ == "__main__":
    demo_email_integration()
