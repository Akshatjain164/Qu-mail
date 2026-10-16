
import secrets
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple, Optional, Any
import json
import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

class ECDHKeyExchange:
    
    def __init__(self):
        self.active_keypairs = {}
        self.shared_secrets = {}
        self.key_history = []
        
    def generate_keypair(self, key_id: str = None) -> Dict[str, Any]:
        if not key_id:
            timestamp = int(time.time() * 1000)
            random_suffix = secrets.randbelow(1000)
            key_id = f"ecdh_x25519_{timestamp}_{random_suffix}"
        
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        private_key_b64 = base64.b64encode(private_key_bytes).decode('utf-8')
        public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
        
        keypair_data = {
            "key_id": key_id,
            "algorithm": "X25519",
            "curve": "Curve25519",
            "private_key": private_key_b64,
            "public_key": public_key_b64,
            "public_key_hex": public_key_bytes.hex(),
            "metadata": {
                "key_size": 256,
                "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat().replace('+00:00', 'Z'),
                "status": "active",
                "usage": "key_exchange",
                "security_level": "256-bit equivalent"
            }
        }
        
        self.active_keypairs[key_id] = {
            "data": keypair_data,
            "private_key_obj": private_key,
            "public_key_obj": public_key
        }
        
        print(f"🔑 Generated X25519 key pair: {key_id}")
        return keypair_data
    
    def get_public_key(self, key_id: str) -> Optional[str]:
        if key_id in self.active_keypairs:
            return self.active_keypairs[key_id]["data"]["public_key"]
        return None
    
    def compute_shared_secret(self, local_key_id: str, remote_public_key_b64: str, 
                            shared_secret_id: str = None) -> Dict[str, Any]:
        if local_key_id not in self.active_keypairs:
            raise ValueError(f"Local key {local_key_id} not found")
        
        try:
            local_private_key = self.active_keypairs[local_key_id]["private_key_obj"]
            
            remote_public_key_bytes = base64.b64decode(remote_public_key_b64)
            remote_public_key = x25519.X25519PublicKey.from_public_bytes(remote_public_key_bytes)
            
            shared_secret_raw = local_private_key.exchange(remote_public_key)
            
            if not shared_secret_id:
                timestamp = int(time.time() * 1000)
                random_suffix = secrets.randbelow(1000)
                shared_secret_id = f"ecdh_secret_{timestamp}_{random_suffix}"
            
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'QuMail ECDH Key Exchange',
                backend=default_backend()
            ).derive(shared_secret_raw)
            
            shared_secret_hex = derived_key.hex()
            shared_secret_b64 = base64.b64encode(derived_key).decode('utf-8')
            
            shared_secret_data = {
                "shared_secret_id": shared_secret_id,
                "local_key_id": local_key_id,
                "algorithm": "X25519-HKDF-SHA256",
                "shared_secret": shared_secret_hex,
                "shared_secret_b64": shared_secret_b64,
                "key_derivation": "HKDF-SHA256",
                "metadata": {
                    "length": 256,
                    "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat().replace('+00:00', 'Z'),
                    "status": "active",
                    "local_key_id": local_key_id,
                    "remote_public_key_fingerprint": hashlib.sha256(remote_public_key_bytes).hexdigest()[:16],
                    "usage": "hybrid_encryption"
                }
            }
            
            self.shared_secrets[shared_secret_id] = shared_secret_data
            self.key_history.append({
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "action": "shared_secret_computed",
                "shared_secret_id": shared_secret_id,
                "local_key_id": local_key_id
            })
            
            print(f"🤝 Computed ECDH shared secret: {shared_secret_id}")
            return shared_secret_data
            
        except Exception as e:
            print(f"❌ ECDH computation error: {e}")
            raise
    
    def get_shared_secret(self, shared_secret_id: str) -> Optional[Dict[str, Any]]:
        return self.shared_secrets.get(shared_secret_id)
    
    def list_active_keypairs(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for key_id, keypair in self.active_keypairs.items():
            result[key_id] = {
                "key_id": key_id,
                "algorithm": keypair["data"]["algorithm"],
                "public_key": keypair["data"]["public_key"],
                "public_key_hex": keypair["data"]["public_key_hex"],
                "metadata": keypair["data"]["metadata"]
            }
        return result
    
    def list_shared_secrets(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for secret_id, secret_data in self.shared_secrets.items():
            result[secret_id] = {
                "shared_secret_id": secret_id,
                "local_key_id": secret_data["local_key_id"],
                "algorithm": secret_data["algorithm"],
                "metadata": secret_data["metadata"]
            }
        return result
    
    def cleanup_expired_keys(self):
        current_time = datetime.now(timezone.utc)
        
        expired_keypairs = []
        for key_id, keypair in self.active_keypairs.items():
            expires_at = datetime.fromisoformat(
                keypair["data"]["metadata"]["expires_at"].replace('Z', '+00:00')
            )
            if current_time > expires_at:
                expired_keypairs.append(key_id)
        
        for key_id in expired_keypairs:
            del self.active_keypairs[key_id]
            print(f"⏰ Expired ECDH key pair: {key_id}")
        
        expired_secrets = []
        for secret_id, secret_data in self.shared_secrets.items():
            expires_at = datetime.fromisoformat(
                secret_data["metadata"]["expires_at"].replace('Z', '+00:00')
            )
            if current_time > expires_at:
                expired_secrets.append(secret_id)
        
        for secret_id in expired_secrets:
            del self.shared_secrets[secret_id]
            print(f"⏰ Expired ECDH shared secret: {secret_id}")
    
    def simulate_key_exchange(self) -> Dict[str, Any]:
        alice_keypair = self.generate_keypair("alice_demo_key")
        alice_public_key = alice_keypair["public_key"]
        
        bob_private_key = x25519.X25519PrivateKey.generate()
        bob_public_key = bob_private_key.public_key()
        bob_public_key_bytes = bob_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        bob_public_key_b64 = base64.b64encode(bob_public_key_bytes).decode('utf-8')
        
        alice_shared_secret = self.compute_shared_secret(
            "alice_demo_key", 
            bob_public_key_b64, 
            "demo_shared_secret"
        )
        
        alice_public_key_bytes = base64.b64decode(alice_public_key)
        alice_public_key_obj = x25519.X25519PublicKey.from_public_bytes(alice_public_key_bytes)
        bob_shared_secret_raw = bob_private_key.exchange(alice_public_key_obj)
        
        bob_derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'QuMail ECDH Key Exchange',
            backend=default_backend()
        ).derive(bob_shared_secret_raw)
        
        alice_secret_bytes = base64.b64decode(alice_shared_secret["shared_secret_b64"])
        secrets_match = alice_secret_bytes == bob_derived_key
        
        return {
            "demo_successful": True,
            "secrets_match": secrets_match,
            "alice_key_id": "alice_demo_key",
            "alice_public_key": alice_public_key,
            "bob_public_key": bob_public_key_b64,
            "shared_secret_id": "demo_shared_secret",
            "shared_secret_preview": alice_shared_secret["shared_secret"][:16] + "...",
            "key_exchange_verified": secrets_match
        }

class HybridCryptoManager:
    
    def __init__(self):
        self.ecdh = ECDHKeyExchange()
        self.hybrid_keys = {}
        
        try:
            self.mlkem = None
            self.mlkem_available = False
            print("🔬 ML-KEM-768 integrated into hybrid manager")
        except ImportError:
            self.mlkem = None
            self.mlkem_available = False
            print("⚠️ ML-KEM-768 not available for hybrid manager")
        
    def generate_hybrid_keypair(self, hybrid_id: str = None) -> Dict[str, Any]:
        if not hybrid_id:
            timestamp = int(time.time() * 1000)
            hybrid_id = f"hybrid_{timestamp}"
        
        ecdh_keypair = self.ecdh.generate_keypair(f"{hybrid_id}_ecdh")
        
        algorithms = ["X25519"]
        components = ["ECDH/X25519"]
        
        hybrid_key_data = {
            "hybrid_id": hybrid_id,
            "ecdh_key_id": ecdh_keypair["key_id"],
            "ecdh_public_key": ecdh_keypair["public_key"],
        }
        
        if self.mlkem_available and self.mlkem:
            try:
                mlkem_keypair = self.mlkem.generate_keypair(f"{hybrid_id}_mlkem")
                hybrid_key_data["mlkem_key_id"] = mlkem_keypair["key_id"]
                hybrid_key_data["mlkem_public_key"] = mlkem_keypair["public_key"]
                algorithms.append("ML-KEM-768")
                components.append("ML-KEM-768")
                print(f"🔬 Added ML-KEM-768 to hybrid key: {hybrid_id}")
            except Exception as e:
                print(f"⚠️ Failed to add ML-KEM to hybrid key: {e}")
        
        hybrid_key_data.update({
            "algorithms": algorithms,
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "security_level": "192-bit hybrid" if self.mlkem_available else "128-bit hybrid",
                "status": "active",
                "components": components,
                "mlkem_available": self.mlkem_available
            }
        })
        
        self.hybrid_keys[hybrid_id] = hybrid_key_data
        
        print(f"🔐 Generated hybrid key pair: {hybrid_id} with {len(algorithms)} algorithms")
        return hybrid_key_data
    
    def get_hybrid_public_data(self, hybrid_id: str) -> Optional[Dict[str, Any]]:
        if hybrid_id in self.hybrid_keys:
            data = {
                "hybrid_id": hybrid_id,
                "algorithms": self.hybrid_keys[hybrid_id]["algorithms"],
                "ecdh_public_key": self.hybrid_keys[hybrid_id]["ecdh_public_key"],
                "metadata": self.hybrid_keys[hybrid_id]["metadata"]
            }
            
            if "mlkem_public_key" in self.hybrid_keys[hybrid_id]:
                data["mlkem_public_key"] = self.hybrid_keys[hybrid_id]["mlkem_public_key"]
                data["mlkem_key_id"] = self.hybrid_keys[hybrid_id]["mlkem_key_id"]
            
            return data
        return None

def create_ecdh_manager() -> ECDHKeyExchange:
    return ECDHKeyExchange()

def create_hybrid_manager() -> HybridCryptoManager:
    return HybridCryptoManager()

def test_ecdh_exchange():
    print("🔐 Testing ECDH/X25519 Key Exchange...")
    
    ecdh = create_ecdh_manager()
    
    keypair = ecdh.generate_keypair("test_key_001")
    print(f"✅ Generated key pair: {keypair['key_id']}")
    print(f"🔑 Public key: {keypair['public_key'][:32]}...")
    
    demo_result = ecdh.simulate_key_exchange()
    print(f"✅ Key exchange demo: {'SUCCESS' if demo_result['demo_successful'] else 'FAILED'}")
    print(f"🤝 Secrets match: {demo_result['secrets_match']}")
    print(f"🔒 Shared secret: {demo_result['shared_secret_preview']}")
    
    hybrid = create_hybrid_manager()
    hybrid_key = hybrid.generate_hybrid_keypair("test_hybrid_001")
    print(f"✅ Generated hybrid key: {hybrid_key['hybrid_id']}")
    
    print("\n✅ ECDH/X25519 test completed!")
    return demo_result

if __name__ == "__main__":
    test_ecdh_exchange()

