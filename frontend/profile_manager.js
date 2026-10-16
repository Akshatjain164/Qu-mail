

class QuMailProfileManager {
    constructor() {
        this.profileBtn = null;
        this.profileDropdown = null;
        this.profileEmail = null;
        this.signoutBtn = null;
        this.centerModal = null;
        
        console.log('👤 QuMail Profile Manager initialized');
    }

    
    initialize() {
        console.log('🔄 Initializing Profile Manager...');
        

        this.getUIElements();
        

        this.createProfileDropdown();
        

        this.setupEventListeners();
        

        this.createCenterModal();
        

        this.updateProfileState();
        
        console.log('✅ Profile Manager ready');
    }

    
    getUIElements() {
        this.profileBtn = document.getElementById('profile-btn');

    }

    
    setupEventListeners() {

        if (this.profileBtn) {
            this.profileBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleProfile();
            });
        }


        document.addEventListener('click', () => {
            this.closeDropdown();
        });
    }

    
    setupDropdownEventListeners() {

        if (this.signoutBtn) {
            this.signoutBtn.addEventListener('click', () => {
                this.signOut();
            });
        }


        if (this.profileDropdown) {
            this.profileDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
    }

    
    createProfileDropdown() {

        this.profileDropdown = document.createElement('div');
        this.profileDropdown.id = 'profile-dropdown';
        this.profileDropdown.className = 'fixed w-64 glass-dark border border-violet-500/30 rounded-lg p-4 shadow-xl hidden';
        this.profileDropdown.style.zIndex = '99999';
        
        this.profileDropdown.innerHTML = `
            <div id="profile-info" class="space-y-3">
                <div class="text-sm text-violet-300">Signed in as:</div>
                <div id="profile-email" class="text-white font-medium text-sm break-all"></div>
                <hr class="border-violet-500/30">
                <button id="signout-btn" class="w-full text-left text-red-300 hover:text-red-200 text-sm py-2 px-3 rounded hover:bg-red-500/10 transition-colors">
                    Sign out
                </button>
            </div>
        `;
        
        document.body.appendChild(this.profileDropdown);
        

        this.profileEmail = document.getElementById('profile-email');
        this.signoutBtn = document.getElementById('signout-btn');
        

        this.setupDropdownEventListeners();
    }

    
    createCenterModal() {

        this.centerModal = document.createElement('div');
        this.centerModal.id = 'profile-center-modal';
        this.centerModal.className = 'fixed inset-0 bg-black/70 backdrop-blur-lg z-50 hidden flex items-center justify-center';
        
        this.centerModal.innerHTML = `
            <div class="glass-dark border border-violet-500/30 rounded-2xl p-8 mx-4 w-full max-w-md">
                <div class="text-center mb-6">
                    <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 flex items-center justify-center">
                        <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                        </svg>
                    </div>
                    <h2 class="text-2xl font-bold text-white mb-2">Sign in to QuMail</h2>
                    <p class="text-violet-300">Configure your Gmail account for quantum-secure email</p>
                </div>

                <form id="profile-login-form" class="space-y-4">
                    <div>
                        <label class="block text-violet-300 text-sm font-medium mb-2">Gmail Address</label>
                        <input 
                            type="email" 
                            id="profile-email-input"
                            class="w-full bg-white/10 border border-violet-500/30 rounded-lg px-4 py-3 text-white placeholder-violet-300/50 focus:outline-none focus:border-violet-400 focus:ring-1 focus:ring-violet-400"
                            placeholder="your.email@gmail.com"
                            required
                        >
                    </div>
                    
                    <div>
                        <label class="block text-violet-300 text-sm font-medium mb-2">App Password</label>
                        <input 
                            type="password" 
                            id="profile-password-input"
                            class="w-full bg-white/10 border border-violet-500/30 rounded-lg px-4 py-3 text-white placeholder-violet-300/50 focus:outline-none focus:border-violet-400 focus:ring-1 focus:ring-violet-400"
                            placeholder="16-character app password"
                            required
                        >
                    </div>

                    <!-- App Password Help -->
                    <div class="bg-violet-500/10 border border-violet-500/20 rounded-lg p-4">
                        <p class="text-violet-300 text-sm mb-2">
                            <strong>📱 Need an App Password?</strong>
                        </p>
                        <ol class="text-violet-300/80 text-xs space-y-1 ml-4 list-decimal">
                            <li>Go to <strong>myaccount.google.com</strong></li>
                            <li>Security → 2-Step Verification</li>
                            <li>App passwords → Generate new</li>
                            <li>Select "Mail" and copy the 16-character code</li>
                        </ol>
                    </div>

                    <div class="flex space-x-3 mt-6">
                        <button 
                            type="button" 
                            id="profile-cancel-btn"
                            class="flex-1 bg-gray-600 hover:bg-gray-700 text-white py-3 px-4 rounded-lg font-medium transition-colors"
                        >
                            Cancel
                        </button>
                        <button 
                            type="submit" 
                            id="profile-signin-btn"
                            class="flex-1 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white py-3 px-4 rounded-lg font-medium transition-all duration-200"
                        >
                            Sign In
                        </button>
                    </div>
                </form>

                <div id="profile-status" class="hidden mt-4 p-3 rounded-lg text-center text-sm">
                    <span id="profile-status-text"></span>
                </div>
            </div>
        `;

        document.body.appendChild(this.centerModal);


        this.setupModalEventListeners();
    }

    
    setupModalEventListeners() {
        const form = document.getElementById('profile-login-form');
        const cancelBtn = document.getElementById('profile-cancel-btn');
        const emailInput = document.getElementById('profile-email-input');
        const passwordInput = document.getElementById('profile-password-input');


        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSignIn(emailInput.value, passwordInput.value);
            });
        }


        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.closeCenterModal();
            });
        }


        this.centerModal.addEventListener('click', (e) => {
            if (e.target === this.centerModal) {
                this.closeCenterModal();
            }
        });
    }

    
    toggleProfile() {
        if (this.isLoggedIn()) {

            this.toggleDropdown();
        } else {

            this.showCenterModal();
        }
    }

    
    isLoggedIn() {
        return window.emailIntegration && window.emailIntegration.credentials;
    }

    
    toggleDropdown() {
        if (this.profileDropdown) {
            const isHidden = this.profileDropdown.classList.contains('hidden');
            if (isHidden) {

                this.positionDropdown();
                this.profileDropdown.classList.remove('hidden');
                this.updateProfileInfo();
            } else {
                this.profileDropdown.classList.add('hidden');
            }
        }
    }

    
    positionDropdown() {
        if (this.profileBtn && this.profileDropdown) {
            const rect = this.profileBtn.getBoundingClientRect();
            this.profileDropdown.style.position = 'fixed';
            this.profileDropdown.style.top = (rect.bottom + 8) + 'px';
            this.profileDropdown.style.right = (window.innerWidth - rect.right) + 'px';
            this.profileDropdown.style.zIndex = '99999';
        }
    }

    
    closeDropdown() {
        if (this.profileDropdown) {
            this.profileDropdown.classList.add('hidden');
        }
    }

    
    showCenterModal() {
        if (this.centerModal) {
            this.centerModal.classList.remove('hidden');

            const emailInput = document.getElementById('profile-email-input');
            if (emailInput) {
                setTimeout(() => emailInput.focus(), 100);
            }
        }
    }

    
    closeCenterModal() {
        if (this.centerModal) {
            this.centerModal.classList.add('hidden');

            const form = document.getElementById('profile-login-form');
            if (form) {
                form.reset();
            }
            this.hideStatus();
        }
    }

    
    async handleSignIn(email, password) {
        try {
            this.showStatus('Connecting to Gmail...', 'info');
            

            if (window.emailIntegration) {
                window.emailIntegration.setCredentials(email, password);
                

                await window.emailIntegration.initializeConnection();
                
                if (window.emailIntegration.isReady()) {
                    this.showStatus('Successfully signed in!', 'success');
                    

                    setTimeout(() => {
                        this.closeCenterModal();
                        this.updateProfileState();
                    }, 1500);
                } else {
                    throw new Error('Failed to connect to Gmail. Please check your credentials.');
                }
            } else {
                throw new Error('Email integration not available');
            }
            
        } catch (error) {
            console.error('❌ Sign in failed:', error);
            this.showStatus(`Sign in failed: ${error.message}`, 'error');
        }
    }

    
    signOut() {
        try {

            if (window.emailIntegration) {
                window.emailIntegration.credentials = null;
                window.emailIntegration.isConnected = false;
            }
            

            this.closeDropdown();
            

            this.updateProfileState();
            
            console.log('✅ Signed out successfully');
            
        } catch (error) {
            console.error('❌ Sign out failed:', error);
        }
    }

    
    updateProfileState() {

        if (window.quMailEmailManager) {

            setTimeout(() => {
                window.quMailEmailManager.loadFolder('inbox').catch(console.error);
            }, 100);
        }
    }

    
    updateProfileInfo() {
        if (this.profileEmail && window.emailIntegration && window.emailIntegration.credentials) {
            this.profileEmail.textContent = window.emailIntegration.credentials.email;
        }
    }

    
    showStatus(message, type = 'info') {
        const statusDiv = document.getElementById('profile-status');
        const statusText = document.getElementById('profile-status-text');
        
        if (statusDiv && statusText) {
            statusText.textContent = message;
            statusDiv.className = `mt-4 p-3 rounded-lg text-center text-sm ${
                type === 'success' ? 'bg-green-500/20 text-green-300 border border-green-500/30' :
                type === 'error' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                'bg-violet-500/20 text-violet-300 border border-violet-500/30'
            }`;
            statusDiv.classList.remove('hidden');
        }
    }

    
    hideStatus() {
        const statusDiv = document.getElementById('profile-status');
        if (statusDiv) {
            statusDiv.classList.add('hidden');
        }
    }
}


let quMailProfileManager = null;

document.addEventListener('DOMContentLoaded', () => {
    quMailProfileManager = new QuMailProfileManager();
    quMailProfileManager.initialize();
    

    window.quMailProfileManager = quMailProfileManager;
});
