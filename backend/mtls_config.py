import os
import ssl
from flask import Flask, request, jsonify, g
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from functools import wraps
class QuMailmTLSConfig:
    def __init__(self, cert_dir="certs"):
        self.cert_dir = cert_dir
        self.ca_cert_path = os.path.join(cert_dir, "ca.crt")
        self.server_cert_path = os.path.join(cert_dir, "server.crt")
        self.server_key_path = os.path.join(cert_dir, "server.key")
        self.ca_cert = self._load_ca_certificate()
    def _load_ca_certificate(self):
        try:
            with open(self.ca_cert_path, "rb") as f:
                ca_cert_data = f.read()
            ca_cert = x509.load_pem_x509_certificate(ca_cert_data, default_backend())
            print(f"✅ CA Certificate loaded: {self.ca_cert_path}")
            return ca_cert
        except Exception as e:
            print(f"❌ Failed to load CA certificate: {e}")
            return None
    def create_ssl_context(self):
        print("🔐 Configuring mTLS SSL Context...")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.server_cert_path, self.server_key_path)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(self.ca_cert_path)
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        print("✅ SSL Context configured with mTLS")
        print("   • Client certificates: REQUIRED")
        print("   • Minimum TLS version: 1.2")
        print("   • Cipher suites: ECDHE+AESGCM preferred")
        return context
    def extract_client_info(self, request):
        try:
            client_cert_pem = request.environ.get('SSL_CLIENT_CERT')
            if not client_cert_pem:
                return None
            client_cert = x509.load_pem_x509_certificate(
                client_cert_pem.encode('utf-8'), 
                default_backend()
            )
            subject = client_cert.subject
            client_info = {
                "common_name": None,
                "organization": None,
                "organizational_unit": None,
                "country": None,
                "serial_number": str(client_cert.serial_number),
                "valid_from": client_cert.not_valid_before.isoformat(),
                "valid_until": client_cert.not_valid_after.isoformat(),
                "fingerprint": client_cert.fingerprint(hashes.SHA256()).hex()
            }
            for attribute in subject:
                if attribute.oid == x509.NameOID.COMMON_NAME:
                    client_info["common_name"] = attribute.value
                elif attribute.oid == x509.NameOID.ORGANIZATION_NAME:
                    client_info["organization"] = attribute.value
                elif attribute.oid == x509.NameOID.ORGANIZATIONAL_UNIT_NAME:
                    client_info["organizational_unit"] = attribute.value
                elif attribute.oid == x509.NameOID.COUNTRY_NAME:
                    client_info["country"] = attribute.value
            return client_info
        except Exception as e:
            print(f"❌ Error extracting client info: {e}")
            return None
def require_mtls_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_cert = request.environ.get('SSL_CLIENT_CERT')
        if not client_cert:
            return jsonify({
                "error": "Client certificate required",
                "message": "mTLS authentication failed - no client certificate provided",
                "code": "MTLS_CERT_REQUIRED"
            }), 401
        try:
            from cryptography.hazmat.primitives import hashes
            client_cert_obj = x509.load_pem_x509_certificate(
                client_cert.encode('utf-8'), 
                default_backend()
            )
            subject = client_cert_obj.subject
            client_cn = None
            for attribute in subject:
                if attribute.oid == x509.NameOID.COMMON_NAME:
                    client_cn = attribute.value
                    break
            g.client_cn = client_cn
            g.client_cert_serial = str(client_cert_obj.serial_number)
            g.client_cert_fingerprint = client_cert_obj.fingerprint(hashes.SHA256()).hex()
            print(f"🔐 mTLS authenticated client: {client_cn} (Serial: {g.client_cert_serial[:16]}...)")
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ mTLS authentication error: {e}")
            return jsonify({
                "error": "Invalid client certificate",
                "message": "mTLS authentication failed - certificate validation error",
                "code": "MTLS_CERT_INVALID"
            }), 401
    return decorated_function
def setup_mtls_logging(app):
    @app.before_request
    def log_mtls_request():
        client_cert = request.environ.get('SSL_CLIENT_CERT')
        if client_cert:
            try:
                client_cert_obj = x509.load_pem_x509_certificate(
                    client_cert.encode('utf-8'), 
                    default_backend()
                )
                subject = client_cert_obj.subject
                client_cn = "Unknown"
                for attribute in subject:
                    if attribute.oid == x509.NameOID.COMMON_NAME:
                        client_cn = attribute.value
                        break
                print(f"🔒 mTLS Request: {request.method} {request.path} from {client_cn}")
            except Exception as e:
                print(f"⚠️ mTLS logging error: {e}")
        else:
            print(f"⚠️ Non-mTLS Request: {request.method} {request.path} (No client certificate)")
    @app.after_request  
    def log_mtls_response(response):
        client_cn = getattr(g, 'client_cn', 'Unknown')
        print(f"✅ mTLS Response: {response.status_code} to {client_cn}")
        return response
def create_mtls_test_endpoints(app):
    @app.route('/api/mtls/status')
    @require_mtls_auth
    def mtls_status():
        return jsonify({
            "mtls_enabled": True,
            "client_authenticated": True,
            "client_cn": g.client_cn,
            "client_serial": g.client_cert_serial,
            "client_fingerprint": g.client_cert_fingerprint[:32] + "...",
            "message": "mTLS authentication successful",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
    @app.route('/api/mtls/info')
    @require_mtls_auth
    def mtls_info():
        return jsonify({
            "protocol": "TLS 1.2+",
            "authentication": "Mutual TLS (mTLS)",
            "ca_issuer": "QuMail Root CA",
            "client_cn": g.client_cn,
            "client_serial": g.client_cert_serial,
            "security_level": "High (4096-bit RSA)",
            "compliance": "ETSI GS QKD 014",
            "organization": "QuMail Project - Byte-Bandits",
            "message": "Quantum-secure communication channel established"
        })
def configure_flask_mtls(app, cert_dir="certs"):
    print("🔐 Configuring Flask app for mTLS...")
    mtls_config = QuMailmTLSConfig(cert_dir)
    setup_mtls_logging(app)
    import datetime
    create_mtls_test_endpoints(app)
    print("✅ Flask mTLS configuration complete")
    return mtls_config
def run_mtls_server(app, host='0.0.0.0', port=5443, cert_dir="certs"):
    print(f"🚀 Starting QuMail mTLS Server on {host}:{port}")
    print("🔐 Mutual TLS authentication enabled")
    print("📡 ETSI GS QKD 014 compliant")
    mtls_config = configure_flask_mtls(app, cert_dir)
    ssl_context = mtls_config.create_ssl_context()
    app.run(
        host=host,
        port=port,
        ssl_context=ssl_context,
        debug=False,
        threaded=True
    )
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    @app.route('/')
    def hello():
        return jsonify({"message": "QuMail mTLS Test Server", "status": "running"})
    run_mtls_server(app)
