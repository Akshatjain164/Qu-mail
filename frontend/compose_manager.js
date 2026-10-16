

class QuMailComposeManager {
    constructor() {
        this.sendBtn = null;
        this.recipientInput = null;
        this.subjectInput = null;
        this.messageTextarea = null;
        this.encryptionLevelSelect = null;
        this.isSending = false;
        this.attachments = [];
        
        console.log('✉️ QuMail Compose Manager initialized');
    }

    
    initialize() {
        console.log('🔄 Initializing Compose Manager...');
        

        this.getUIElements();
        

        this.setupEventListeners();
        
        console.log('✅ Compose Manager ready');
    }

    
    getUIElements() {
        this.sendBtn = document.getElementById('send-secure-btn');
        this.recipientInput = document.getElementById('recipient');
        this.subjectInput = document.getElementById('subject');
        this.messageTextarea = document.getElementById('message');
        this.encryptionLevelSelect = document.getElementById('encryption-level');
        this.attachmentBtn = document.getElementById('attachment-btn');
        this.attachmentInput = document.getElementById('attachment-input');
        this.attachmentsContainer = document.getElementById('attachments-container');
        this.attachmentBadge = document.getElementById('attachment-badge');
    }

    
    setupEventListeners() {

        if (this.sendBtn) {

            const newSendBtn = this.sendBtn.cloneNode(true);
            this.sendBtn.parentNode.replaceChild(newSendBtn, this.sendBtn);
            this.sendBtn = newSendBtn;
            
            this.sendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleSendEmail();
            });
            
            console.log('✅ Real email send handler attached');
        }


        if (this.messageTextarea) {
            this.messageTextarea.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    this.handleSendEmail();
                }
            });
        }

        if (this.attachmentBtn && this.attachmentInput) {
            this.attachmentBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.attachmentInput.click();
            });

            this.attachmentInput.addEventListener('change', (e) => {
                this.handleFilesSelected(e.target.files);
            });
        }
    }

    async handleFilesSelected(files) {
        if (!files || files.length === 0) return;
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const reader = new FileReader();
            
            reader.onload = (e) => {
                const base64Data = e.target.result.split(',')[1]; 
                this.attachments.push({
                    filename: file.name,
                    content_type: file.type || 'application/octet-stream',
                    data: base64Data
                });
                this.updateAttachmentsUI();
            };
            reader.readAsDataURL(file);
        }
        
        this.attachmentInput.value = '';
    }

    updateAttachmentsUI() {
        if (this.attachments.length > 0) {
            this.attachmentBadge.textContent = this.attachments.length;
            this.attachmentBadge.classList.remove('hidden');
            this.attachmentsContainer.classList.remove('hidden');
            
            this.attachmentsContainer.innerHTML = '';
            this.attachments.forEach((att, index) => {
                const badge = document.createElement('div');
                badge.className = 'bg-violet-900/50 border border-violet-500/30 text-violet-200 text-xs px-2 py-1 rounded-md flex items-center gap-2';
                badge.innerHTML = `
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.586-6.586a2 2 0 00-2.828-2.828z"></path></svg>
                    <span class="truncate max-w-[150px]">${att.filename}</span>
                    <button class="hover:text-white transition-colors" data-index="${index}">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                `;
                
                badge.querySelector('button').addEventListener('click', (e) => {
                    e.preventDefault();
                    this.attachments.splice(index, 1);
                    this.updateAttachmentsUI();
                });
                
                this.attachmentsContainer.appendChild(badge);
            });
        } else {
            this.attachmentBadge.classList.add('hidden');
            this.attachmentsContainer.classList.add('hidden');
            this.attachmentsContainer.innerHTML = '';
        }
    }

    
    async handleSendEmail() {
        if (this.isSending) return;

        try {

            const formData = this.validateAndGetFormData();
            if (!formData) return;


            if (!window.emailIntegration || !window.emailIntegration.isReady()) {
                this.showError('Please sign in to send emails');
                if (window.quMailProfileManager) {
                    window.quMailProfileManager.showCenterModal();
                }
                return;
            }


            this.setSendingState(true);


            this.showHybridKeyAnimation(formData.securityLevel);


            await new Promise(resolve => setTimeout(resolve, 50));


            console.log('📧 Sending real encrypted email...');
            const result = await window.emailIntegration.sendEncryptedEmail(formData);

            if (result && result.success) {
                this.showSuccess(`Email sent successfully! Message ID: ${result.message_id}`);
                this.clearForm();
            } else {
                throw new Error(result?.error || 'Failed to send email');
            }

        } catch (error) {
            console.error('❌ Email send failed:', error);
            this.showError(`Failed to send email: ${error.message}`);
        } finally {
            this.setSendingState(false);
        }
    }

    
    validateAndGetFormData() {
        const recipient = this.recipientInput?.value?.trim();
        const subject = this.subjectInput?.value?.trim();
        const message = this.messageTextarea?.value?.trim();
        const securityLevel = parseInt(this.encryptionLevelSelect?.value || 2);


        if (!recipient) {
            this.showError('Please enter a recipient email address');
            this.recipientInput?.focus();
            return null;
        }

        if (!this.isValidEmail(recipient)) {
            this.showError('Please enter a valid email address');
            this.recipientInput?.focus();
            return null;
        }

        if (!subject) {
            this.showError('Please enter a subject');
            this.subjectInput?.focus();
            return null;
        }

        if (!message) {
            this.showError('Please enter a message');
            this.messageTextarea?.focus();
            return null;
        }

        return {
            to: recipient,
            recipient: recipient,
            subject: subject,
            message: message,
            securityLevel: securityLevel,
            attachments: this.attachments
        };
    }

    
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    
    showHybridKeyAnimation(securityLevel) {
        if (!window.showHybridKeyAnimation) {
            console.log('⚠️ Hybrid key animation not available');
            return;
        }


        let keyTypes = [];
        
        switch(parseInt(securityLevel)) {
            case 1:
                keyTypes = ['qkd'];
                break;
            case 2:
                keyTypes = ['qkd', 'ecdh'];
                break;
            case 3:
                keyTypes = ['mlkem', 'ecdh'];
                break;
            case 4:
                keyTypes = ['ecdh'];
                break;
            default:
                keyTypes = ['qkd', 'mlkem', 'ecdh'];
        }

        console.log(`🎭 Triggering hybrid key animation for Level ${securityLevel} with keys:`, keyTypes);
        window.showHybridKeyAnimation(keyTypes);


        const handleAnimationComplete = () => {
            console.log('✅ Hybrid animation completed');
            document.removeEventListener('animationComplete', handleAnimationComplete);
        };
        
        document.addEventListener('animationComplete', handleAnimationComplete);
    }

    
    setSendingState(sending) {
        this.isSending = sending;
        
        if (this.sendBtn) {
            if (sending) {
                this.sendBtn.disabled = true;
                this.sendBtn.innerHTML = `
                    <div class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span>Sending...</span>
                `;
                this.sendBtn.classList.add('opacity-75');
            } else {
                this.sendBtn.disabled = false;
                this.sendBtn.innerHTML = `
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                    </svg>
                    <span>Send Secure</span>
                `;
                this.sendBtn.classList.remove('opacity-75');
            }
        }
    }

    
    clearForm() {
        if (this.recipientInput) this.recipientInput.value = '';
        if (this.subjectInput) this.subjectInput.value = '';
        if (this.messageTextarea) this.messageTextarea.value = '';
        

        if (this.encryptionLevelSelect) {
            this.encryptionLevelSelect.value = '2';
        }
        
        this.attachments = [];
        this.updateAttachmentsUI();
    }

    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    
    showError(message) {
        this.showNotification(message, 'error');
    }

    
    showNotification(message, type = 'info') {

        const notification = document.createElement('div');
        notification.className = `fixed top-6 right-6 z-[99999] max-w-md p-4 rounded-lg shadow-xl transition-all duration-300 transform translate-x-full ${
            type === 'success' ? 'bg-green-500/90 text-white border border-green-400' :
            type === 'error' ? 'bg-red-500/90 text-white border border-red-400' :
            'bg-violet-500/90 text-white border border-violet-400'
        }`;
        
        notification.innerHTML = `
            <div class="flex items-center space-x-3">
                <div class="flex-shrink-0">
                    ${type === 'success' ? 
                        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>' :
                        type === 'error' ?
                        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>' :
                        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
                    }
                </div>
                <div class="flex-1">
                    <p class="text-sm font-medium">${message}</p>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" class="flex-shrink-0 opacity-70 hover:opacity-100">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        

        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        

        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }, 5000);
    }
}


let quMailComposeManager = null;

document.addEventListener('DOMContentLoaded', () => {

    setTimeout(() => {
        quMailComposeManager = new QuMailComposeManager();
        quMailComposeManager.initialize();
        

        window.quMailComposeManager = quMailComposeManager;
        
        console.log('🚀 Compose Manager fully initialized');
    }, 1000);
});
