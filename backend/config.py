import os
from typing import Dict, Any
class Config:
    SUPABASE_CONFIG = {
        'url': os.environ.get('SUPABASE_URL', 'https://xbhcyzwatxhpadwtycnp.supabase.co'),
        'key': os.environ.get('SUPABASE_KEY', 'sb_publishable_WqofHS4kvrRllvPOCYLUjg_LHto2JJ4'),
    }
    QKD_CONFIG = {
        'key_length': 256,
        'error_rate_threshold': 0.15,
        'bb84_basis_count': 1024,
        'etsi_compliance': True
    }
    ENCRYPTION_CONFIG = {
        'aes_key_size': 256,
        'ml_kem_variant': 768,
        'ml_dsa_variant': '6x5',
        'kdf_algorithm': 'sha256',
        'ecdh_curve': 'X25519'
    }
    EMAIL_CONFIG = {
        'smtp_timeout': 30,
        'imap_timeout': 30,
        'max_attachment_size': 25 * 1024 * 1024,
        'supported_providers': ['gmail', 'yahoo']
    }
    FLASK_CONFIG = {
        'host': '0.0.0.0',
        'port': int(os.environ.get('PORT', 5000)),
        'debug': os.environ.get('ENVIRONMENT', 'development') != 'production',
        'ssl_context': None
    }
class SupabaseSetup:
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        required_fields = ['url', 'key']
        for field in required_fields:
            value = config.get(field, '')
            if not value or value.startswith('YOUR_'):
                print(f"Missing Supabase configuration: {field}")
                return False
        return True
    @staticmethod
    def initialize_supabase(config: Dict[str, Any]):
        try:
            from supabase import create_client
            client = create_client(config['url'], config['key'])
            return client
        except Exception as e:
            print(f"Supabase initialization error: {e}")
            return None
def load_config():
    env = os.getenv('QUMAIL_ENV', 'development')
    if env == 'production':
        Config.FLASK_CONFIG['debug'] = False
        Config.FLASK_CONFIG['ssl_context'] = 'adhoc'
    return Config
config = load_config()
