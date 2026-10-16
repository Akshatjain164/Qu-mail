// QuMail Centralized API Configuration
(function() {
    // Deployed Render backend URL
    const LIVE_BACKEND_URL = 'https://qu-mail-a4jk.onrender.com';

    // Check if running on local dev server and explicitly targeting local port 5000
    const isLocalDev = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        && localStorage.getItem('qumail_use_local') === 'true';

    const baseUrl = isLocalDev ? 'http://localhost:5000' : (localStorage.getItem('qumail_backend_url') || LIVE_BACKEND_URL);

    window.QUMAIL_CONFIG = {
        API_BASE_URL: baseUrl.replace(/\/+$/, ''),
        get API_API() { return `${this.API_BASE_URL}/api`; },
        get API_QKD() { return `${this.API_BASE_URL}/api/qkd`; }
    };

    console.log(`📡 QuMail API endpoint: ${window.QUMAIL_CONFIG.API_BASE_URL}`);
})();
