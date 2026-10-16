import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, jsonify, request, abort
from flask_cors import CORS
import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone


import json
import os
from threading import Lock

from config import Config

QKD_CONFIG = Config.QKD_CONFIG
FLASK_CONFIG = Config.FLASK_CONFIG

try:
    from email_integration import (
        create_email_sender, 
        create_email_receiver, 
        EmailMessage, 
        EmailCredentials,
        SecurityLevel,
        QuMailEmailSender
    )
    print("✅ Email integration modules imported successfully")
except ImportError as e:
    print(f"⚠️ Email integration import warning: {e}")
    create_email_sender = None
    create_email_receiver = None

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'simulator'))
try:
    from qkd import create_bb84_simulator
    bb84_simulator = create_bb84_simulator()
    print("✅ BB84 QKD Simulator loaded successfully")
except ImportError as e:
    print(f"⚠️ BB84 Simulator not available: {e}")
    bb84_simulator = None
except Exception as e:
    print(f"⚠️ BB84 Simulator initialization error: {e}")
    bb84_simulator = None

try:
    from crypto import create_ecdh_manager, create_hybrid_manager
    ecdh_manager = create_ecdh_manager()
    hybrid_manager = create_hybrid_manager()
    print("✅ ECDH/X25519 Crypto Module loaded successfully")
except ImportError as e:
    print(f"⚠️ ECDH Crypto Module not available: {e}")
    ecdh_manager = None
    hybrid_manager = None
except Exception as e:
    print(f"⚠️ ECDH Crypto Module initialization error: {e}")
    ecdh_manager = None
    hybrid_manager = None

mlkem_manager = None

try:
    from hybrid import create_hybrid_derivator
    from real_pqc import create_real_pqc_manager
    hybrid_derivator = create_hybrid_derivator()
    real_pqc_manager = create_real_pqc_manager()
    print("✅ Hybrid Key Derivation Module loaded successfully")
    print("✅ Real Post-Quantum Cryptography Module loaded successfully")
except ImportError as e:
    print(f"⚠️ Hybrid Derivation Module not available: {e}")
    hybrid_derivator = None
    real_pqc_manager = None
except Exception as e:
    print(f"⚠️ Hybrid Derivation Module initialization error: {e}")
    hybrid_derivator = None

app = Flask(__name__)

cors_origins = [
    "http://localhost:*",
    "https://mail.google.com",
    "chrome-extension://*",
]

if os.environ.get('ENVIRONMENT') == 'production':
    cors_origins.extend([
        "https://qumail-backend.onrender.com",
    ])

CORS(app, origins=cors_origins, supports_credentials=True)

key_lock = Lock()

from supabase_client import supabase_storage
firebase_ref = supabase_storage

class QuantumKeyManager:
    
    def __init__(self):
        self.max_keys = 10
        self.key_size_bits = QKD_CONFIG['key_length']
        
        if not firebase_ref:
            print("❌ ERROR: Firebase required for key persistence!")
            pass
        
        print("✅ QuantumKeyManager using Firebase as PRIMARY storage")
    
    def get_active_key_count(self, user_email=None):
        try:
            if user_email:
                user_keys = supabase_storage.get_all_user_keys(user_email)
                return len(user_keys)
            else:
                all_keys = {}
                return len(all_keys)
        except Exception as e:
            print(f"❌ Firebase key count error: {e}")
            return 0
    
    def get_total_generated_count(self):
        try:
            active_keys = {}
            active_count = len(active_keys)
            
            history_keys = {}
            history_count = len(history_keys)
            
            return active_count + history_count
        except Exception as e:
            print(f"❌ Firebase total count error: {e}")
            return 0
    
    def store_key_for_users(self, key_data, sender_email, recipient_email, security_level):
        try:
            key_id = key_data["key_id"]
            
            enhanced_key_data = {
                **key_data,
                "sender": sender_email,
                "recipient": recipient_email,
                "security_level": security_level,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "key_type": "qkd"
            }
            
            supabase_storage.set_user_key(sender_email, key_id, enhanced_key_data)
            
            supabase_storage.set_user_key(recipient_email, key_id, enhanced_key_data)
            
            print(f"🔑 Key {key_id} stored for both {sender_email} and {recipient_email}")
            return True
            
        except Exception as e:
            print(f"❌ Firebase key storage error: {e}")
            return False
    
    def get_key_for_user(self, key_id, user_email):
        try:
            key_data = supabase_storage.get_user_key(user_email, key_id)
            if key_data:
                print(f"✅ Retrieved key {key_id} for {user_email}")
                return key_data
            else:
                print(f"⚠️ Key {key_id} not found for {user_email}")
                return None
        except Exception as e:
            print(f"❌ Firebase key retrieval error: {e}")
            return None
    
    def list_keys_for_user(self, user_email, limit=None):
        try:
            keys = supabase_storage.get_all_user_keys(user_email)
            if limit:
                sorted_keys = sorted(keys.items(), key=lambda x: x[1].get('created_at', ''), reverse=True)
                return dict(sorted_keys[:limit])
            return keys
        except Exception as e:
            print(f"❌ Firebase key listing error: {e}")
            return {}
    
    def generate_quantum_key(self, sender_email=None, recipient_email=None, security_level=1):
        with key_lock:
            if bb84_simulator:
                try:
                    print("🔬 Generating quantum key using BB84 simulation...")
                    key_data = bb84_simulator.generate_qkd_key(target_length=self.key_size_bits)
                    
                    validation = bb84_simulator.validate_key_security(key_data)
                    if not validation["is_secure"]:
                        print(f"⚠️ Key security validation failed: {validation['recommendations']}")
                        key_data = bb84_simulator.generate_qkd_key(target_length=self.key_size_bits)
                    
                    if sender_email and recipient_email:
                        success = self.store_key_for_users(key_data, sender_email, recipient_email, security_level)
                        if not success:
                            print("❌ Failed to store key in Firebase - key generation failed")
                            return None
                    else:
                        firebase_ref.child('qkd_keys').child(key_data["key_id"]).set(key_data)
                        print(f"🔑 BB84 Key {key_data['key_id']} stored in Firebase (no user association)")
                    
                    metadata = key_data["metadata"]
                    print(f"✅ Generated BB84 QKD key: {key_data['key_id']} "
                          f"(Level {security_level}, "
                          f"{metadata['error_rate']*100:.1f}% error, "
                          f"{metadata['fidelity']:.3f} fidelity)")
                    
                    return key_data
                    
                except Exception as e:
                    print(f"❌ BB84 simulation error: {e}")
            
            print("⚠️ Falling back to mock key generation...")
            
            key_material = secrets.token_hex(32)
            
            timestamp = int(time.time() * 1000)
            random_suffix = secrets.randbelow(1000)
            key_id = f"qkd_mock_{timestamp}_{random_suffix}"
            
            error_rate = round(secrets.randbelow(20) / 100.0, 3)
            fidelity = round(0.85 + (secrets.randbelow(150) / 1000.0), 3)
            distance_km = secrets.randbelow(100) + 10
            
            if fidelity <= 0 or fidelity > 1:
                fidelity = 0.95
            
            if error_rate < 0.05 and fidelity > 0.95:
                security_level = 1
            elif error_rate < 0.1 and fidelity > 0.9:
                security_level = 2
            elif error_rate < 0.15 and fidelity > 0.85:
                security_level = 3
            else:
                security_level = 4
            
            key_data = {
                "key_id": key_id,
                "key": key_material,
                "metadata": {
                    "length": self.key_size_bits,
                    "error_rate": error_rate,
                    "protocol": "BB84-Mock",
                    "security_level": security_level,
                    "fidelity": fidelity,
                    "distance_km": distance_km,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'),
                    "status": "available"
                }
            }
            
            try:
                firebase_ref.child('qkd_keys').child(key_id).set(key_data)
                print(f"🔑 Mock Key {key_id} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error: {e}")
            
            print(f"🔑 Generated Mock QKD key: {key_id} (Level {security_level}, {error_rate*100:.1f}% error)")
            return key_data
    
    def get_available_keys(self, user_email=None):
        if user_email:
            return self.list_keys_for_user(user_email, limit=self.max_keys)
        else:
            try:
                all_keys = {}
                return list(all_keys.values())
            except Exception as e:
                print(f"❌ Firebase get all keys error: {e}")
                return []
    
    def consume_key(self, key_id, user_email):
        with key_lock:
            try:
                key_data = self.get_key_for_user(key_id, user_email)
                if not key_data:
                    print(f"⚠️ Key {key_id} not found for user {user_email}")
                    return False
                
                key_data['status'] = 'consumed'
                key_data['consumed_at'] = datetime.now(timezone.utc).isoformat()
                
                firebase_ref.child('key_history').child(key_id).set(key_data)
                
                sender = key_data.get('sender')
                recipient = key_data.get('recipient')
                
                if sender:
                    supabase_storage.delete_user_key(sender, key_id)
                if recipient and recipient != sender:
                    supabase_storage.delete_user_key(recipient, key_id)
                
                print(f"✅ Key {key_id} consumed for {user_email} and moved to history")
                return True
                
            except Exception as e:
                print(f"❌ Firebase key consumption error: {e}")
            return False
    
    def cleanup_expired_keys(self, user_email=None):
        try:
            current_time = datetime.now(timezone.utc)
            
            if user_email:
                user_keys = self.list_keys_for_user(user_email)
                for key_id, key_data in user_keys.items():
                    if self._is_key_expired(key_data, current_time):
                        print(f"⏰ Expiring key: {key_id} for user {user_email}")
                        self.consume_key(key_id, user_email)
            else:
                try:
                    all_users = firebase_ref.child('keys').child('users').get() or {}
                    for email, user_keys in all_users.items():
                        for key_id, key_data in user_keys.items():
                            if self._is_key_expired(key_data, current_time):
                                print(f"⏰ Expiring key: {key_id} for user {email}")
                                self.consume_key(key_id, email)
                except Exception as e:
                    print(f"❌ Global cleanup error: {e}")
                    
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
    
    def _is_key_expired(self, key_data, current_time):
        try:
            if 'metadata' in key_data and 'expires_at' in key_data['metadata']:
                expires_at = datetime.fromisoformat(key_data['metadata']['expires_at'].replace('Z', '+00:00'))
                return current_time > expires_at
            if 'created_at' in key_data:
                created_at = datetime.fromisoformat(key_data['created_at'].replace('Z', '+00:00'))
                return (current_time - created_at).days >= 1
        except Exception:
            pass
        return False

qkd_manager = QuantumKeyManager()

print("✅ QKD Manager initialized with Firebase primary storage")
print("🔑 Keys will be generated on-demand for Chrome extension users")

if hybrid_derivator:
    hybrid_derivator.set_managers(
        qkd_manager=qkd_manager,
        ecdh_manager=ecdh_manager,
        mlkem_manager=mlkem_manager,
        real_pqc_manager=real_pqc_manager
    )
    print("🔗 Hybrid derivator connected to all crypto managers")

@app.route('/')
def home():
    return jsonify({
        "service": "QuMail Hybrid Quantum-Classical Key Manager",
        "version": "1.0.0",
        "standards": ["ETSI GS QKD 014", "RFC 7748 (X25519)", "NIST FIPS 203 (ML-KEM-768)"],
        "description": "Byte_Bandits Byte_Bandits 2026 - Quantum Secure Email",
        "components": {
            "qkd_available": bb84_simulator is not None,
            "ecdh_available": ecdh_manager is not None,
            "mlkem_available": mlkem_manager is not None,
            "real_pqc_available": real_pqc_manager is not None,
            "hybrid_available": hybrid_manager is not None,
            "hybrid_derivation_available": hybrid_derivator is not None
        },
        "endpoints": {
            "qkd": {
                "get_key": "/api/qkd/key",
                "get_keys": "/api/qkd/keys", 
                "consume_key": "/api/qkd/consume/<key_id>",
                "generate_key": "/api/qkd/generate",
                "status": "/api/qkd/status",
                "test_bb84": "/api/qkd/bb84/test"
            },
            "encryption_endpoints": {
                "encrypt_message": "/api/encrypt",
                "decrypt_message": "/api/decrypt", 
                "get_encryption_levels": "/api/encrypt/levels"
            },
            "email_endpoints": {
                "send_email": "/api/email/send",
                "send_test_email": "/api/email/test",
                "receive_emails": "/api/email/receive",
                "receive_qumail_emails": "/api/email/receive/qumail",
                "email_status": "/api/email/status"
            },
            "ecdh": {
                "generate_keypair": "/api/ecdh/keypair",
                "get_public_key": "/api/ecdh/public/<key_id>",
                "compute_shared_secret": "/api/ecdh/exchange",
                "status": "/api/ecdh/status",
                "test": "/api/ecdh/test"
            },
            "mlkem": {
                "generate_keypair": "/api/mlkem/keypair",
                "get_public_key": "/api/mlkem/public/<key_id>",
                "encapsulate_secret": "/api/mlkem/encapsulate",
                "decapsulate_secret": "/api/mlkem/decapsulate",
                "status": "/api/mlkem/status",
                "test": "/api/mlkem/test"
            },
            "hybrid": {
                "generate_keypair": "/api/hybrid/keypair",
                "status": "/api/hybrid/status"
            },
            "hybrid_derivation": {
                "derive_key": "/api/hybrid/derive",
                "get_key": "/api/hybrid/key/<key_id>",
                "list_keys": "/api/hybrid/keys",
                "security_analysis": "/api/hybrid/security",
                "test_derivation": "/api/hybrid/test"
            }
        }
    })

@app.route('/api/qkd/key', methods=['GET'])
def get_quantum_key():
    try:
        qkd_manager.cleanup_expired_keys()
        
        available_keys = qkd_manager.get_available_keys()
        
        if not available_keys:
            key_data = qkd_manager.generate_quantum_key()
        else:
            key_data = available_keys[0]
        
        response = {
            "key_id": key_data["key_id"],
            "key": key_data["key"],
            "metadata": key_data["metadata"]
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Error getting key: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to get quantum key"
        }), 500

@app.route('/api/qkd/keys', methods=['GET'])
def get_all_keys():
    try:
        qkd_manager.cleanup_expired_keys()
        keys = qkd_manager.get_available_keys()
        
        return jsonify({
            "total_keys": len(keys),
            "keys": keys
        }), 200
        
    except Exception as e:
        print(f"❌ Error fetching keys: {e}")
        return jsonify({"error": "Failed to fetch keys"}), 500

@app.route('/api/qkd/consume/<key_id>', methods=['POST', 'DELETE'])
def consume_quantum_key(key_id):
    try:
        success = qkd_manager.consume_key(key_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Key {key_id} consumed successfully",
                "key_id": key_id
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Key not found",
                "key_id": key_id
            }), 404
            
    except Exception as e:
        print(f"❌ Error consuming key: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to consume key"
        }), 500

@app.route('/api/qkd/generate', methods=['POST'])
def generate_new_key():
    try:
        current_key_count = qkd_manager.get_active_key_count()
        if current_key_count >= qkd_manager.max_keys:
            return jsonify({
                "error": "Maximum key capacity reached",
                "max_keys": qkd_manager.max_keys,
                "current_keys": current_key_count
            }), 429
        
        key_data = qkd_manager.generate_quantum_key()
        
        return jsonify({
            "success": True,
            "message": "New quantum key generated",
            "key_data": key_data
        }), 201
        
    except Exception as e:
        print(f"❌ Error generating new key: {e}")
        return jsonify({"error": "Failed to generate key"}), 500

@app.route('/api/qkd/status', methods=['GET'])
def qkd_status():
    try:
        qkd_manager.cleanup_expired_keys()
        
        status = {
            "system": "QuMail QKD Manager",
            "status": "operational",
            "active_keys": qkd_manager.get_active_key_count(),
            "max_keys": qkd_manager.max_keys,
            "total_generated": qkd_manager.get_total_generated_count(),
            "firebase_connected": firebase_ref is not None,
            "qkd_available": True,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        return jsonify({"error": "Failed to get status"}), 500

@app.route('/api/qkd/bb84/test', methods=['GET'])
def test_bb84_simulator():
    try:
        if not bb84_simulator:
            return jsonify({
                "error": "BB84 simulator not available",
                "message": "Qiskit BB84 simulator is not loaded"
            }), 503
        
        test_key = bb84_simulator.generate_qkd_key(target_length=64)
        validation = bb84_simulator.validate_key_security(test_key)
        
        return jsonify({
            "simulator_status": "operational",
            "test_key_generated": True,
            "key_preview": {
                "key_id": test_key["key_id"],
                "protocol": test_key["metadata"]["protocol"],
                "error_rate": test_key["metadata"]["error_rate"],
                "fidelity": test_key["metadata"]["fidelity"],
                "security_level": test_key["metadata"]["security_level"],
                "quantum_parameters": test_key["metadata"].get("quantum_parameters", {})
            },
            "security_validation": validation,
            "message": "BB84 QKD simulator is working correctly"
        }), 200
        
    except Exception as e:
        print(f"❌ Error testing BB84 simulator: {e}")
        return jsonify({
            "error": "BB84 simulator test failed",
            "message": str(e)
        }), 500


@app.route('/api/ecdh/keypair', methods=['POST'])
def generate_ecdh_keypair():
    try:
        if not ecdh_manager:
            return jsonify({
                "error": "ECDH module not available",
                "message": "Cryptography module is not loaded"
            }), 503
        
        data = request.get_json() if request.is_json else {}
        key_id = data.get('key_id')
        
        keypair = ecdh_manager.generate_keypair(key_id)
        
        if firebase_ref:
            try:
                firebase_ref.child('ecdh_keys').child(keypair['key_id']).set(keypair)
                print(f"🔑 ECDH key pair {keypair['key_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for ECDH key: {e}")
        
        response = {
            "success": True,
            "key_id": keypair["key_id"],
            "algorithm": keypair["algorithm"],
            "public_key": keypair["public_key"],
            "public_key_hex": keypair["public_key_hex"],
            "metadata": keypair["metadata"]
        }
        
        return jsonify(response), 201
        
    except Exception as e:
        print(f"❌ Error generating ECDH key pair: {e}")
        return jsonify({
            "error": "Failed to generate ECDH key pair",
            "message": str(e)
        }), 500

@app.route('/api/ecdh/public/<key_id>', methods=['GET'])
def get_ecdh_public_key(key_id):
    try:
        if not ecdh_manager:
            return jsonify({
                "error": "ECDH module not available"
            }), 503
        
        public_key = ecdh_manager.get_public_key(key_id)
        
        if not public_key:
            return jsonify({
                "error": "Key not found",
                "key_id": key_id
            }), 404
        
        keypairs = ecdh_manager.list_active_keypairs()
        if key_id in keypairs:
            return jsonify({
                "success": True,
                "key_id": key_id,
                "public_key": public_key,
                "algorithm": keypairs[key_id]["algorithm"],
                "metadata": keypairs[key_id]["metadata"]
            }), 200
        else:
            return jsonify({
                "error": "Key not found in active keypairs"
            }), 404
            
    except Exception as e:
        print(f"❌ Error getting ECDH public key: {e}")
        return jsonify({
            "error": "Failed to get public key",
            "message": str(e)
        }), 500

@app.route('/api/ecdh/exchange', methods=['POST'])
def compute_ecdh_shared_secret():
    try:
        if not ecdh_manager:
            return jsonify({
                "error": "ECDH module not available"
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Missing JSON data"
            }), 400
        
        local_key_id = data.get('local_key_id')
        remote_public_key = data.get('remote_public_key')
        shared_secret_id = data.get('shared_secret_id')
        
        if not local_key_id or not remote_public_key:
            return jsonify({
                "error": "Missing required parameters",
                "required": ["local_key_id", "remote_public_key"]
            }), 400
        
        shared_secret = ecdh_manager.compute_shared_secret(
            local_key_id, 
            remote_public_key, 
            shared_secret_id
        )
        
        if firebase_ref:
            try:
                firebase_data = shared_secret.copy()
                firebase_data.pop('shared_secret', None)
                firebase_data.pop('shared_secret_b64', None)
                firebase_ref.child('ecdh_shared_secrets').child(shared_secret['shared_secret_id']).set(firebase_data)
                print(f"🤝 ECDH shared secret metadata {shared_secret['shared_secret_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for shared secret: {e}")
        
        response = {
            "success": True,
            "shared_secret_id": shared_secret["shared_secret_id"],
            "local_key_id": shared_secret["local_key_id"],
            "algorithm": shared_secret["algorithm"],
            "key_derivation": shared_secret["key_derivation"],
            "metadata": shared_secret["metadata"],
            "shared_secret_preview": shared_secret["shared_secret"][:16] + "...",
            "message": "Shared secret computed successfully"
        }
        
        return jsonify(response), 201
        
    except ValueError as e:
        return jsonify({
            "error": "Invalid parameters",
            "message": str(e)
        }), 400
    except Exception as e:
        print(f"❌ Error computing ECDH shared secret: {e}")
        return jsonify({
            "error": "Failed to compute shared secret",
            "message": str(e)
        }), 500

@app.route('/api/ecdh/test', methods=['GET'])
def test_ecdh_exchange():
    try:
        if not ecdh_manager:
            return jsonify({
                "error": "ECDH module not available"
            }), 503
        
        demo_result = ecdh_manager.simulate_key_exchange()
        
        return jsonify({
            "ecdh_status": "operational",
            "test_successful": demo_result["demo_successful"],
            "key_exchange_verified": demo_result["key_exchange_verified"],
            "alice_key_id": demo_result["alice_key_id"],
            "shared_secret_id": demo_result["shared_secret_id"],
            "shared_secret_preview": demo_result["shared_secret_preview"],
            "message": "ECDH/X25519 key exchange is working correctly"
        }), 200
        
    except Exception as e:
        print(f"❌ Error testing ECDH exchange: {e}")
        return jsonify({
            "error": "ECDH test failed",
            "message": str(e)
        }), 500

@app.route('/api/ecdh/status', methods=['GET'])
def ecdh_status():
    try:
        if not ecdh_manager:
            return jsonify({
                "error": "ECDH module not available"
            }), 503
        
        ecdh_manager.cleanup_expired_keys()
        
        active_keypairs = ecdh_manager.list_active_keypairs()
        shared_secrets = ecdh_manager.list_shared_secrets()
        
        status = {
            "system": "QuMail ECDH/X25519 Manager",
            "status": "operational",
            "algorithm": "X25519",
            "curve": "Curve25519",
            "active_keypairs": len(active_keypairs),
            "shared_secrets": len(shared_secrets),
            "security_level": "256-bit equivalent",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        print(f"❌ Error getting ECDH status: {e}")
        return jsonify({
            "error": "Failed to get ECDH status",
            "message": str(e)
        }), 500


@app.route('/api/hybrid/keypair', methods=['POST'])
def generate_hybrid_keypair():
    try:
        if not hybrid_manager:
            return jsonify({
                "error": "Hybrid crypto module not available"
            }), 503
        
        data = request.get_json() if request.is_json else {}
        hybrid_id = data.get('hybrid_id')
        
        hybrid_key = hybrid_manager.generate_hybrid_keypair(hybrid_id)
        
        if firebase_ref:
            try:
                firebase_ref.child('hybrid_keys').child(hybrid_key['hybrid_id']).set(hybrid_key)
                print(f"🔐 Hybrid key {hybrid_key['hybrid_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for hybrid key: {e}")
        
        return jsonify({
            "success": True,
            "hybrid_id": hybrid_key["hybrid_id"],
            "algorithms": hybrid_key["algorithms"],
            "ecdh_key_id": hybrid_key["ecdh_key_id"],
            "ecdh_public_key": hybrid_key["ecdh_public_key"],
            "metadata": hybrid_key["metadata"],
            "message": "Hybrid key pair generated successfully"
        }), 201
        
    except Exception as e:
        print(f"❌ Error generating hybrid key pair: {e}")
        return jsonify({
            "error": "Failed to generate hybrid key pair",
            "message": str(e)
        }), 500

@app.route('/api/hybrid/status', methods=['GET'])
def hybrid_status():
    try:
        if not hybrid_manager:
            return jsonify({
                "error": "Hybrid crypto module not available"
            }), 503
        
        status = {
            "system": "QuMail Hybrid Crypto Manager",
            "status": "operational",
            "supported_algorithms": ["X25519", "ML-KEM-768"] if mlkem_manager else ["X25519"],
            "security_level": "192-bit hybrid",
            "active_hybrid_keys": len(hybrid_manager.hybrid_keys),
            "components": {
                "qkd_available": bb84_simulator is not None,
                "ecdh_available": ecdh_manager is not None,
                "ml_kem_available": mlkem_manager is not None
            },
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        print(f"❌ Error getting hybrid status: {e}")
        return jsonify({
            "error": "Failed to get hybrid status",
            "message": str(e)
        }), 500


@app.route('/api/mlkem/keypair', methods=['POST'])
def generate_mlkem_keypair():
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available",
                "message": "Post-quantum cryptography module is not loaded"
            }), 503
        
        data = request.get_json() if request.is_json else {}
        key_id = data.get('key_id')
        
        keypair = mlkem_manager.generate_keypair(key_id)
        
        if firebase_ref:
            try:
                firebase_data = keypair.copy()
                firebase_data.pop('private_key', None)
                firebase_ref.child('mlkem_keys').child(keypair['key_id']).set(firebase_data)
                print(f"🔬 ML-KEM key pair {keypair['key_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for ML-KEM key: {e}")
        
        response = {
            "success": True,
            "key_id": keypair["key_id"],
            "algorithm": keypair["algorithm"],
            "variant": keypair["variant"],
            "public_key": keypair["public_key"],
            "public_key_hex": keypair["public_key_hex"],
            "metadata": keypair["metadata"]
        }
        
        return jsonify(response), 201
        
    except Exception as e:
        print(f"❌ Error generating ML-KEM key pair: {e}")
        return jsonify({
            "error": "Failed to generate ML-KEM key pair",
            "message": str(e)
        }), 500

@app.route('/api/mlkem/public/<key_id>', methods=['GET'])
def get_mlkem_public_key(key_id):
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available"
            }), 503
        
        public_key = mlkem_manager.get_public_key(key_id)
        
        if not public_key:
            return jsonify({
                "error": "Key not found",
                "key_id": key_id
            }), 404
        
        keypairs = mlkem_manager.list_active_keypairs()
        if key_id in keypairs:
            return jsonify({
                "success": True,
                "key_id": key_id,
                "public_key": public_key,
                "algorithm": keypairs[key_id]["algorithm"],
                "variant": keypairs[key_id]["variant"],
                "metadata": keypairs[key_id]["metadata"]
            }), 200
        else:
            return jsonify({
                "error": "Key not found in active keypairs"
            }), 404
            
    except Exception as e:
        print(f"❌ Error getting ML-KEM public key: {e}")
        return jsonify({
            "error": "Failed to get public key",
            "message": str(e)
        }), 500

@app.route('/api/mlkem/encapsulate', methods=['POST'])
def encapsulate_mlkem_secret():
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available"
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Missing JSON data"
            }), 400
        
        remote_public_key = data.get('remote_public_key')
        secret_id = data.get('secret_id')
        
        if not remote_public_key:
            return jsonify({
                "error": "Missing required parameter: remote_public_key"
            }), 400
        
        encapsulated_data = mlkem_manager.encapsulate_secret(
            remote_public_key, 
            secret_id
        )
        
        if firebase_ref:
            try:
                firebase_data = encapsulated_data.copy()
                firebase_data.pop('shared_secret', None)
                firebase_data.pop('shared_secret_b64', None)
                firebase_ref.child('mlkem_encapsulated_secrets').child(encapsulated_data['secret_id']).set(firebase_data)
                print(f"🔒 ML-KEM encapsulated secret metadata {encapsulated_data['secret_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for encapsulated secret: {e}")
        
        response = {
            "success": True,
            "secret_id": encapsulated_data["secret_id"],
            "algorithm": encapsulated_data["algorithm"],
            "ciphertext": encapsulated_data["ciphertext"],
            "key_derivation": encapsulated_data["key_derivation"],
            "metadata": encapsulated_data["metadata"],
            "shared_secret_preview": encapsulated_data["shared_secret"][:16] + "...",
            "message": "Shared secret encapsulated successfully"
        }
        
        return jsonify(response), 201
        
    except Exception as e:
        print(f"❌ Error encapsulating ML-KEM secret: {e}")
        return jsonify({
            "error": "Failed to encapsulate secret",
            "message": str(e)
        }), 500

@app.route('/api/mlkem/decapsulate', methods=['POST'])
def decapsulate_mlkem_secret():
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available"
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Missing JSON data"
            }), 400
        
        local_key_id = data.get('local_key_id')
        ciphertext = data.get('ciphertext')
        
        if not local_key_id or not ciphertext:
            return jsonify({
                "error": "Missing required parameters",
                "required": ["local_key_id", "ciphertext"]
            }), 400
        
        decapsulated_data = mlkem_manager.decapsulate_secret(local_key_id, ciphertext)
        
        response = {
            "success": True,
            "algorithm": decapsulated_data["algorithm"],
            "local_key_id": decapsulated_data["local_key_id"],
            "metadata": decapsulated_data["metadata"],
            "shared_secret_preview": decapsulated_data["shared_secret"][:16] + "...",
            "message": "Shared secret decapsulated successfully"
        }
        
        return jsonify(response), 200
        
    except ValueError as e:
        return jsonify({
            "error": "Invalid parameters",
            "message": str(e)
        }), 400
    except Exception as e:
        print(f"❌ Error decapsulating ML-KEM secret: {e}")
        return jsonify({
            "error": "Failed to decapsulate secret",
            "message": str(e)
        }), 500

@app.route('/api/mlkem/test', methods=['GET'])
def test_mlkem_kem():
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available"
            }), 503
        
        demo_result = mlkem_manager.simulate_full_kem_exchange()
        
        return jsonify({
            "mlkem_status": "operational",
            "test_successful": demo_result["demo_successful"],
            "key_encapsulation_verified": demo_result["key_encapsulation_verified"],
            "algorithm": demo_result["algorithm"],
            "quantum_resistant": demo_result["quantum_resistant"],
            "alice_key_id": demo_result["alice_key_id"],
            "secret_id": demo_result["secret_id"],
            "shared_secret_preview": demo_result["shared_secret_preview"],
            "message": "ML-KEM-768 key encapsulation is working correctly"
        }), 200
        
    except Exception as e:
        print(f"❌ Error testing ML-KEM: {e}")
        return jsonify({
            "error": "ML-KEM test failed",
            "message": str(e)
        }), 500

@app.route('/api/mlkem/status', methods=['GET'])
def mlkem_status():
    try:
        if not mlkem_manager:
            return jsonify({
                "error": "ML-KEM-768 module not available"
            }), 503
        
        mlkem_manager.cleanup_expired_keys()
        
        active_keypairs = mlkem_manager.list_active_keypairs()
        encapsulated_secrets = mlkem_manager.list_encapsulated_secrets()
        
        status = {
            "system": "QuMail ML-KEM-768 Manager",
            "status": "operational",
            "algorithm": "ML-KEM-768",
            "variant": "Kyber768" if hasattr(mlkem_manager, 'use_real_mlkem') and mlkem_manager.use_real_mlkem else "Simulated",
            "security_level": "192-bit post-quantum",
            "nist_standard": "FIPS 203",
            "active_keypairs": len(active_keypairs),
            "encapsulated_secrets": len(encapsulated_secrets),
            "quantum_resistant": True,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        return jsonify(status), 200
        
    except Exception as e:
        print(f"❌ Error getting ML-KEM status: {e}")
        return jsonify({
            "error": "Failed to get ML-KEM status",
            "message": str(e)
        }), 500


@app.route('/api/hybrid/derive', methods=['POST'])
def derive_hybrid_key():
    try:
        if not hybrid_derivator:
            return jsonify({
                "error": "Hybrid derivation module not available"
            }), 503
        
        data = request.get_json() if request.is_json else {}
        qkd_key_id = data.get('qkd_key_id')
        ecdh_shared_secret_id = data.get('ecdh_shared_secret_id')
        mlkem_shared_secret_id = data.get('mlkem_shared_secret_id')
        hybrid_key_id = data.get('hybrid_key_id')
        include_components = data.get('include_components', ['QKD', 'ECDH', 'MLKEM'])
        
        hybrid_key = hybrid_derivator.derive_hybrid_key(
            qkd_key_id=qkd_key_id,
            ecdh_shared_secret_id=ecdh_shared_secret_id,
            mlkem_shared_secret_id=mlkem_shared_secret_id,
            hybrid_key_id=hybrid_key_id,
            include_components=include_components
        )
        
        if firebase_ref:
            try:
                firebase_data = hybrid_key.copy()
                firebase_data.pop('derived_key', None)
                firebase_ref.child('hybrid_derived_keys').child(hybrid_key['hybrid_key_id']).set(firebase_data)
                print(f"🔐 Hybrid key metadata {hybrid_key['hybrid_key_id']} stored in Firebase")
            except Exception as e:
                print(f"⚠️ Firebase storage error for hybrid key: {e}")
        
        response = {
            "success": True,
            "hybrid_key_id": hybrid_key["hybrid_key_id"],
            "algorithm": hybrid_key["algorithm"],
            "security_level": hybrid_key["security_level"],
            "security_description": hybrid_key["security_description"],
            "components": hybrid_key["components"],
            "security_contributions": hybrid_key["security_contributions"],
            "key_length": hybrid_key["key_length"],
            "component_info": hybrid_key["component_info"],
            "metadata": hybrid_key["metadata"],
            "derived_key_preview": hybrid_key["derived_key"][:16] + "...",
            "message": "Hybrid key derived successfully"
        }
        
        return jsonify(response), 201
        
    except ValueError as e:
        return jsonify({
            "error": "Invalid parameters or insufficient components",
            "message": str(e)
        }), 400
    except Exception as e:
        print(f"❌ Error deriving hybrid key: {e}")
        return jsonify({
            "error": "Failed to derive hybrid key",
            "message": str(e)
        }), 500


global_encryptor = None

def get_encryptor():
    global global_encryptor
    if global_encryptor is None:
        from encryption import QuMailMultiLevelEncryption
        global_encryptor = QuMailMultiLevelEncryption()
    return global_encryptor

@app.route('/api/encrypt', methods=['POST'])
def encrypt_message():
    try:
        data = request.get_json()
        
        required_fields = ['plaintext', 'security_level', 'sender', 'recipient']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        from encryption import SecurityLevel
        encryptor = get_encryptor()
        
        security_level_map = {
            1: SecurityLevel.QUANTUM_SECURE,
            2: SecurityLevel.QUANTUM_AIDED, 
            3: SecurityLevel.HYBRID_PQC,
            4: SecurityLevel.NO_QUANTUM
        }
        
        security_level = security_level_map.get(data['security_level'])
        if not security_level:
            return jsonify({"error": "Invalid security level. Must be 1-4"}), 400
        
        encrypted_message = encryptor.encrypt_message(
            plaintext=data['plaintext'],
            security_level=security_level,
            sender=data['sender'],
            recipient=data['recipient'],
            subject=data.get('subject', ''),
            attachments=data.get('attachments', [])
        )
        
        response_data = {
            "success": True,
            "encrypted_data": {
                "ciphertext": encrypted_message.ciphertext,
                "metadata": {
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
                },
                "attachments": encrypted_message.attachments,
                "mime_structure": encrypted_message.mime_structure
            }
        }
        
        print(f"✅ Message encrypted with Level {data['security_level']}: {encrypted_message.metadata.algorithm}")
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ Encryption error: {e}")
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/decrypt', methods=['POST'])
def decrypt_message():
    try:
        data = request.get_json()
        
        if 'encrypted_data' not in data:
            return jsonify({"error": "Missing encrypted_data"}), 400
        
        from encryption import EncryptedMessage, EncryptionMetadata
        encryptor = get_encryptor()
        
        encrypted_data = data['encrypted_data']
        metadata = EncryptionMetadata(
            security_level=encrypted_data['metadata']['security_level'],
            algorithm=encrypted_data['metadata']['algorithm'],
            key_source=encrypted_data['metadata']['key_source'],
            timestamp=encrypted_data['metadata']['timestamp'],
            message_id=encrypted_data['metadata']['message_id'],
            sender=encrypted_data['metadata']['sender'],
            recipient=encrypted_data['metadata']['recipient'],
            key_ids=encrypted_data['metadata']['key_ids'],
            integrity_hash=encrypted_data['metadata']['integrity_hash'],
            quantum_resistant=encrypted_data['metadata']['quantum_resistant'],
            etsi_compliant=encrypted_data['metadata']['etsi_compliant']
        )
        
        encrypted_message = EncryptedMessage(
            ciphertext=encrypted_data['ciphertext'],
            metadata=metadata,
            attachments=encrypted_data.get('attachments', []),
            mime_structure=encrypted_data.get('mime_structure', '')
        )
        
        plaintext, decrypted_attachments = encryptor.decrypt_message(encrypted_message)
        
        response_data = {
            "success": True,
            "plaintext": plaintext,
            "attachments": decrypted_attachments,
            "metadata": {
                "security_level": metadata.security_level,
                "algorithm": metadata.algorithm,
                "decryption_timestamp": datetime.now().isoformat()
            }
        }
        
        print(f"✅ Message decrypted from Level {metadata.security_level}: {metadata.algorithm}")
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ Decryption error: {e}")
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/encrypt/levels', methods=['GET'])
def get_encryption_levels():
    try:
        encryptor = get_encryptor()
        
        analysis = encryptor.get_security_analysis()
        
        response_data = {
            "success": True,
            "encryption_levels": analysis["encryption_levels"],
            "system_capabilities": analysis["system_capabilities"],
            "real_pqc_available": encryptor.real_pqc is not None,
            "api_connected": True
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ Encryption levels error: {e}")
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/hybrid/key/<key_id>', methods=['GET'])
def get_hybrid_key(key_id):
    try:
        if not hybrid_derivator:
            return jsonify({
                "error": "Hybrid derivation module not available"
            }), 503
        
        hybrid_key = hybrid_derivator.get_hybrid_key(key_id)
        
        if not hybrid_key:
            return jsonify({
                "error": "Hybrid key not found",
                "key_id": key_id
            }), 404
        
        return jsonify({
            "success": True,
            **hybrid_key
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting hybrid key: {e}")
        return jsonify({
            "error": "Failed to get hybrid key",
            "message": str(e)
        }), 500

@app.route('/api/hybrid/keys', methods=['GET'])
def list_hybrid_keys():
    try:
        if not hybrid_derivator:
            return jsonify({
                "error": "Hybrid derivation module not available"
            }), 503
        
        hybrid_derivator.cleanup_expired_keys()
        
        hybrid_keys = hybrid_derivator.list_hybrid_keys()
        
        return jsonify({
            "success": True,
            "hybrid_keys": hybrid_keys,
            "count": len(hybrid_keys),
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }), 200
        
    except Exception as e:
        print(f"❌ Error listing hybrid keys: {e}")
        return jsonify({
            "error": "Failed to list hybrid keys",
            "message": str(e)
        }), 500

@app.route('/api/hybrid/security', methods=['GET'])
def hybrid_security_analysis():
    try:
        if not hybrid_derivator:
            return jsonify({
                "error": "Hybrid derivation module not available"
            }), 503
        
        analysis = hybrid_derivator.get_security_analysis()
        
        return jsonify({
            "success": True,
            **analysis,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting security analysis: {e}")
        return jsonify({
            "error": "Failed to get security analysis",
            "message": str(e)
        }), 500

@app.route('/api/hybrid/test', methods=['GET'])
def test_hybrid_derivation():
    try:
        if not hybrid_derivator:
            return jsonify({
                "error": "Hybrid derivation module not available"
            }), 503
        
        demo_result = hybrid_derivator.generate_full_hybrid_demo()
        
        return jsonify({
            "hybrid_derivation_status": "operational",
            **demo_result,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }), 200
        
    except Exception as e:
        print(f"❌ Error testing hybrid derivation: {e}")
        return jsonify({
            "error": "Hybrid derivation test failed",
            "message": str(e)
        }), 500


@app.route('/api/email/send', methods=['POST'])
def send_encrypted_email():
    try:
        data = request.get_json()
        
        required_fields = ['sender_email', 'sender_password', 'recipient', 'subject', 'content', 'security_level']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        if not create_email_sender:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
        
        security_level_map = {
            1: SecurityLevel.QUANTUM_SECURE,
            2: SecurityLevel.QUANTUM_AIDED,
            3: SecurityLevel.HYBRID_PQC,
            4: SecurityLevel.NO_QUANTUM
        }
        
        security_level = security_level_map.get(data['security_level'])
        if not security_level:
            return jsonify({"error": "Invalid security level. Must be 1-4"}), 400
        
        email_msg = EmailMessage(
            sender=data['sender_email'],
            recipient=data['recipient'],
            subject=data['subject'],
            content=data['content'],
            attachments=data.get('attachments', []),
            security_level=security_level
        )
        
        with create_email_sender(data['sender_email'], data['sender_password']) as sender:
            result = sender.send_email(email_msg)
        
        if result.success:
            response_data = {
                "success": True,
                "message_id": result.message_id,
                "sent_at": result.sent_at,
                "encryption_metadata": result.encryption_metadata,
                "message": f"Email sent successfully with Level {data['security_level']} encryption"
            }
            print(f"✅ Email sent: {result.message_id}")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "success": False,
                "error": result.error
            }), 500
            
    except Exception as e:
        print(f"❌ Email send error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/email/test', methods=['POST'])
def send_test_email():
    try:
        data = request.get_json()
        
        required_fields = ['sender_email', 'sender_password', 'recipient']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        
        security_level_map = {
            1: SecurityLevel.QUANTUM_SECURE,
            2: SecurityLevel.QUANTUM_AIDED,
            3: SecurityLevel.HYBRID_PQC,
            4: SecurityLevel.NO_QUANTUM
        }
        
        security_level = security_level_map.get(data.get('security_level', 2), SecurityLevel.QUANTUM_AIDED)
        
        with create_email_sender(data['sender_email'], data['sender_password']) as sender:
            result = sender.send_test_email(data['recipient'], security_level)
        
        if result.success:
            response_data = {
                "success": True,
                "message_id": result.message_id,
                "sent_at": result.sent_at,
                "encryption_metadata": result.encryption_metadata,
                "message": f"Test email sent successfully with Level {security_level.value} encryption"
            }
            print(f"✅ Test email sent: {result.message_id}")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "success": False,
                "error": result.error
            }), 500
            
    except Exception as e:
        print(f"❌ Test email error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/email/status', methods=['GET', 'POST'])
def email_status():
    try:
        if request.method == 'GET':
            
            status = {
                "service": "QuMail Email Integration",
                "status": "operational",
                "supported_providers": ["Gmail"],
                "supported_security_levels": {
                    "1": "Quantum Secure (OTP)",
                    "2": "Quantum-aided AES", 
                    "3": "Hybrid PQC",
                    "4": "No Quantum Security"
                },
                "features": [
                    "SMTP sending with TLS",
                    "Multi-level encryption",
                    "MIME multipart messages",
                    "Attachment support",
                    "App Password authentication"
                ],
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            
            return jsonify(status), 200
        
        elif request.method == 'POST':
            data = request.get_json()
            
            if not data or 'email' not in data or 'password' not in data:
                return jsonify({
                    "success": False,
                    "error": "Missing email or password"
                }), 400
            
            email = data['email']
            password = data['password']
            
            if not email.endswith('@gmail.com'):
                return jsonify({
                    "success": False,
                    "error": "Only Gmail addresses are supported"
                }), 400
            
            if len(password.replace(' ', '')) != 16:
                return jsonify({
                    "success": False,
                    "error": "Gmail App Password must be 16 characters"
                }), 400
            
            try:
                
                clean_password = password.replace(' ', '')
                credentials = EmailCredentials(email=email, password=clean_password)
                
                with create_email_sender(credentials.email, credentials.password) as sender:
                    if sender.connect_smtp():
                        return jsonify({
                            "success": True,
                            "message": "Gmail credentials validated successfully",
                            "email": email
                        }), 200
                    else:
                        return jsonify({
                            "success": False,
                            "error": "Failed to connect to Gmail SMTP server"
                        }), 401
                        
            except Exception as smtp_error:
                return jsonify({
                    "success": False,
                    "error": f"Gmail authentication failed: {str(smtp_error)}"
                }), 401
        
    except Exception as e:
        print(f"❌ Email status error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/email/receive', methods=['POST'])
def receive_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        
        limit = data.get('limit', 10)
        folder = data.get('folder', 'INBOX')
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.fetch_emails(limit=limit, folder=folder)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "is_qumail": email.is_qumail,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "original_content": email.original_content,
                    "encryption_metadata": email.encryption_metadata,
                    "attachments": email.attachments,
                    "signature_verified": email.signature_verified,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            response_data = {
                "success": True,
                "emails": emails_data,
                "total_count": result.total_count,
                "folder": folder,
                "message": f"Successfully received {result.total_count} emails"
            }
            
            print(f"✅ Received {result.total_count} emails from {folder}")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "success": False,
                "error": result.error
            }), 500
            
    except Exception as e:
        print(f"❌ Email receive error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/email/receive/qumail', methods=['POST'])
def receive_qumail_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        
        limit = data.get('limit', 10)
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.search_qumail_emails(limit=limit)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "encryption_metadata": email.encryption_metadata,
                    "attachments": email.attachments,
                    "signature_verified": email.signature_verified,
                    "decryption_successful": email.decryption_successful,
                    "decryption_error": email.decryption_error,
                    "algorithm": email.algorithm,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            response_data = {
                "success": True,
                "qumail_emails": emails_data,
                "total_count": result.total_count,
                "message": f"Successfully received {result.total_count} QuMail encrypted emails"
            }
            
            print(f"✅ Received {result.total_count} QuMail emails")
            return jsonify(response_data), 200
        else:
            return jsonify({
                "success": False,
                "error": result.error
            }), 500
            
    except Exception as e:
        print(f"❌ QuMail receive error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.route('/api/email/folders', methods=['POST'])
def list_email_folders():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        if not create_email_receiver:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
            
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.list_folders()
            
            if result.get("success") and "folders" in result:
                folders = result["folders"]
                
                detected_folders = {
                    "inbox": "INBOX",
                    "sent": None,
                    "drafts": None,
                    "trash": None,
                    "spam": None
                }
                
                for folder in folders:
                    folder_lower = folder.lower()
                    if not detected_folders["sent"] and "sent" in folder_lower:
                        detected_folders["sent"] = folder
                    elif not detected_folders["drafts"] and ("draft" in folder_lower or "rascunho" in folder_lower):
                        detected_folders["drafts"] = folder
                    elif not detected_folders["trash"] and ("trash" in folder_lower or "lixeira" in folder_lower or "papelera" in folder_lower):
                        detected_folders["trash"] = folder
                    elif not detected_folders["spam"] and "spam" in folder_lower:
                        detected_folders["spam"] = folder
                
                result["detected_folders"] = detected_folders
                result["troubleshooting"] = {
                    "missing_sent": detected_folders["sent"] is None,
                    "missing_drafts": detected_folders["drafts"] is None,
                    "missing_trash": detected_folders["trash"] is None,
                    "tip": "If folders are missing, try accessing them in Gmail web interface first to enable IMAP access"
                }
        
        return jsonify(result), 200 if result.get("success") else 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/email/inbox', methods=['POST'])
def get_inbox_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        limit = data.get('limit', 10)
        
        if not create_email_receiver:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.fetch_inbox_emails(limit=limit)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "original_content": email.original_content,
                    "is_qumail": email.is_qumail,
                    "signature_verified": email.signature_verified,
                    "decryption_successful": email.decryption_successful,
                    "decryption_error": email.decryption_error,
                    "algorithm": email.algorithm,
                    "attachments": email.attachments,
                    "encryption_metadata": email.encryption_metadata,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            return jsonify({
                "success": True,
                "emails": emails_data,
                "total_count": result.total_count,
                "folder": "INBOX"
            }), 200
        else:
            return jsonify({"success": False, "error": result.error}), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/email/sent', methods=['POST'])
def get_sent_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        limit = data.get('limit', 10)
        
        if not create_email_receiver:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.fetch_sent_emails(limit=limit)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "original_content": email.original_content,
                    "is_qumail": email.is_qumail,
                    "signature_verified": email.signature_verified,
                    "decryption_successful": email.decryption_successful,
                    "decryption_error": email.decryption_error,
                    "algorithm": email.algorithm,
                    "attachments": email.attachments,
                    "encryption_metadata": email.encryption_metadata,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            return jsonify({
                "success": True,
                "emails": emails_data,
                "total_count": result.total_count,
                "folder": "[Gmail]/Sent Mail"
            }), 200
        else:
            return jsonify({"success": False, "error": result.error}), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/email/trash', methods=['POST'])
def get_trash_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        limit = data.get('limit', 10)
        
        if not create_email_receiver:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.fetch_trash_emails(limit=limit)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "original_content": email.original_content,
                    "is_qumail": email.is_qumail,
                    "signature_verified": email.signature_verified,
                    "decryption_successful": email.decryption_successful,
                    "decryption_error": email.decryption_error,
                    "algorithm": email.algorithm,
                    "attachments": email.attachments,
                    "encryption_metadata": email.encryption_metadata,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            return jsonify({
                "success": True,
                "emails": emails_data,
                "total_count": result.total_count,
                "folder": "[Gmail]/Trash"
            }), 200
        else:
            return jsonify({"success": False, "error": result.error}), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/email/drafts', methods=['POST'])
def get_draft_emails():
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        limit = data.get('limit', 10)
        
        if not create_email_receiver:
            return jsonify({"success": False, "error": "Email integration not available"}), 500
        
        with create_email_receiver(data['email'], data['password']) as receiver:
            result = receiver.fetch_draft_emails(limit=limit)
        
        if result.success:
            emails_data = []
            for email in result.emails:
                email_data = {
                    "message_id": email.message_id,
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "received_at": email.received_at,
                    "security_level": email.security_level,
                    "decrypted_content": email.decrypted_content,
                    "original_content": email.original_content,
                    "is_qumail": email.is_qumail,
                    "signature_verified": email.signature_verified,
                    "decryption_successful": email.decryption_successful,
                    "decryption_error": email.decryption_error,
                    "algorithm": email.algorithm,
                    "attachments": email.attachments,
                    "encryption_metadata": email.encryption_metadata,
                    "error": email.error
                }
                emails_data.append(email_data)
            
            return jsonify({
                "success": True,
                "emails": emails_data,
                "total_count": result.total_count,
                "folder": "[Gmail]/Drafts"
            }), 200
        else:
            return jsonify({"success": False, "error": result.error}), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='QuMail QKD Manager')
    parser.add_argument('--mtls', action='store_true', help='Enable mTLS authentication')
    parser.add_argument('--mtls-port', type=int, default=5443, help='mTLS port (default: 5443)')
    args = parser.parse_args()
    
    if args.mtls:
        print("🔐 Starting QuMail QKD Manager with mTLS...")
        print("📡 ETSI GS QKD 014 Compliant API (mTLS Secured)")
        print(f"🔑 Key size: {QKD_CONFIG['key_length']} bits")
        print(f"📊 Max keys: 10")
        print(f"🌐 Server: https://localhost:{args.mtls_port} (mTLS)")
        
        from mtls_config import run_mtls_server
        run_mtls_server(app, host=FLASK_CONFIG['host'], port=args.mtls_port)
    else:
        print("🚀 Starting QuMail Backend Server...")
        print(f"📡 ETSI GS QKD 014 Compliant API")
        print(f"🔑 Key size: {QKD_CONFIG['key_length']} bits")
        print(f"📊 Max keys: 10")
        
        if os.environ.get('ENVIRONMENT') == 'production':
            print(f"🌐 Production Server: https://qumail-backend.onrender.com")
            print("🔥 Running in production mode - use gunicorn")
        else:
            print(f"🌐 Development Server: http://localhost:{FLASK_CONFIG['port']}")
        app.run(
            host=FLASK_CONFIG['host'],
            port=FLASK_CONFIG['port'],
            debug=FLASK_CONFIG['debug']
        )

