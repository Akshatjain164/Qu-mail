

class QuMailEmailManager {
    constructor() {
        this.currentFolder = 'inbox';
        this.currentEmail = null;
        this.emailIntegration = null;
        this.isLoading = false;
        

        this.loadingIndicator = null;
        this.emailListContainer = null;
        this.emailReaderContainer = null;
        this.emailComposerContainer = null;
        this.folderTitle = null;
        this.emailListCount = null;
        this.emailList = null;
        
        console.log('📧 QuMail Email Manager initialized');
    }

    
    async initialize() {
        console.log('🔄 Initializing QuMail Email Manager...');
        

        await this.waitForEmailIntegration();
        

        this.getUIElements();
        

        this.setupEventListeners();
        

        await this.loadFolder('inbox');
        
        console.log('✅ QuMail Email Manager ready');
    }

    
    async waitForEmailIntegration() {
        let attempts = 0;
        const maxAttempts = 50;
        
        while (attempts < maxAttempts) {
            if (window.emailIntegration) {

                if (window.emailIntegration.isConnected) {
                    this.emailIntegration = window.emailIntegration;
                    console.log('✅ Email integration connected to backend');
                    

                    if (window.emailIntegration.credentials) {
                        console.log('✅ Email credentials configured');
                        return;
                    } else {
                        console.log('⚠️ Email integration connected but credentials not set');
                        console.log('💡 Please configure Gmail App Password in the settings');

                        return;
                    }
                } else {
                    console.log(`⏳ Waiting for backend connection... (${attempts + 1}/${maxAttempts})`);
                }
            } else {
                console.log(`⏳ Waiting for email integration module... (${attempts + 1}/${maxAttempts})`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        console.warn('⚠️ Email integration wait timeout - Backend may not be running');
    }

    
    getUIElements() {
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.emailListContainer = document.getElementById('email-list-container');
        this.emailReaderContainer = document.getElementById('email-reader-container');
        this.emailComposerContainer = document.getElementById('email-composer-container');
        this.folderTitle = document.getElementById('folder-title');
        this.emailListCount = document.getElementById('email-list-count');
        this.emailList = document.getElementById('email-list');
        
        console.log('📋 UI elements initialized');
    }

    
    setupEventListeners() {

        document.querySelectorAll('.nav-folder').forEach(folder => {
            folder.addEventListener('click', (e) => {
                e.preventDefault();
                const folderName = folder.dataset.folder;
                this.loadFolder(folderName);
            });
        });


        const topComposeBtn = document.getElementById('top-compose-btn');
        if (topComposeBtn) {
            topComposeBtn.addEventListener('click', () => {
                this.showComposer();
            });
        }


        const sidebarComposeBtn = document.getElementById('sidebar-compose-btn');
        if (sidebarComposeBtn) {
            sidebarComposeBtn.addEventListener('click', () => {
                this.showComposer();
            });
        }


        const closeEmailReader = document.getElementById('close-email-reader');
        if (closeEmailReader) {
            closeEmailReader.addEventListener('click', () => {
                this.closeEmailReader();
            });
        }

        console.log('🎧 Event listeners setup complete');
    }


    
    showLoading() {
        this.loadingIndicator.classList.remove('hidden');
        this.emailListContainer.classList.add('hidden');
        this.isLoading = true;
    }

    
    showEmailList() {
        this.loadingIndicator.classList.add('hidden');
        this.emailListContainer.classList.remove('hidden');
        this.isLoading = false;
    }

    
    showEmailReader() {
        const overlay = document.getElementById('email-reader-overlay');
        const composeContainer = document.getElementById('email-composer-container');
        
        if (overlay) {
            overlay.classList.remove('hidden');
        }
        

        if (composeContainer) {
            composeContainer.classList.add('blur-sm', 'opacity-75');
        }
        
        this.isLoading = false;
    }

    
    showComposer() {
        this.closeEmailReader();
        console.log('✍️ Composer focused');
    }

    
    closeEmailReader() {
        const overlay = document.getElementById('email-reader-overlay');
        const composeContainer = document.getElementById('email-composer-container');
        
        if (overlay) {
            overlay.classList.add('hidden');
        }
        

        if (composeContainer) {
            composeContainer.classList.remove('blur-sm', 'opacity-75');
        }
        
        this.currentEmail = null;
        console.log('📪 Email reader closed, compose area restored');
    }

    
    async loadFolder(folderName) {
        console.log(`📁 Loading folder: ${folderName}`);
        

        this.updateActiveFolder(folderName);
        this.currentFolder = folderName;
        

        this.showLoading();
        
        try {

            if (!this.emailIntegration || !this.emailIntegration.isReady()) {
                if (!this.emailIntegration) {
                    throw new Error('Email integration not available');
                } else if (!this.emailIntegration.isConnected) {
                    throw new Error('Backend not connected. Please start the backend server.');
                } else if (!this.emailIntegration.credentials) {
                    this.showCredentialsRequired();
                    return;
                }
            }
            

            let result;
            const limit = 10;
            
            switch (folderName) {
                case 'inbox':
                    result = await this.emailIntegration.getInboxEmails(limit);
                    break;
                case 'sent':
                    try {
                        result = await this.emailIntegration.getSentEmails(limit);
                    } catch (sentError) {
                        console.warn(`⚠️ Sent folder access failed:`, sentError.message);
                        result = { 
                            emails: [], 
                            message: `Sent folder not accessible: ${sentError.message}. This is common with some Gmail configurations. Try accessing the folder directly in Gmail to enable it.` 
                        };
                    }
                    break;
                case 'drafts':
                    try {
                        result = await this.emailIntegration.getDraftEmails(limit);
                    } catch (draftError) {
                        console.warn(`⚠️ Drafts folder access failed:`, draftError.message);
                        result = { 
                            emails: [], 
                            message: `Drafts folder not accessible: ${draftError.message}. This folder may not be enabled for IMAP access.` 
                        };
                    }
                    break;
                case 'trash':
                    try {
                        result = await this.emailIntegration.getTrashEmails(limit);
                    } catch (trashError) {
                        console.warn(`⚠️ Trash folder access failed:`, trashError.message);
                        result = { 
                            emails: [], 
                            message: `Trash folder not accessible: ${trashError.message}. This folder may not be enabled for IMAP access.` 
                        };
                    }
                    break;
                default:
                    result = await this.emailIntegration.getInboxEmails(limit);
            }

            console.log(`📬 Received ${result.emails?.length || 0} emails from ${folderName}`);
            

            this.displayEmails(result.emails || [], folderName, result.message);
            
        } catch (error) {
            console.error(`❌ Error loading ${folderName}:`, error);
            this.showEmailList();
            this.displayError(`Failed to load ${folderName}: ${error.message}`);
        }
    }

    
    updateActiveFolder(folderName) {

        document.querySelectorAll('.nav-folder').forEach(folder => {
            folder.classList.remove('bg-violet-500/20');
        });
        

        const activeFolder = document.querySelector(`[data-folder="${folderName}"]`);
        if (activeFolder) {
            activeFolder.classList.add('bg-violet-500/20');
        }
        

        const folderTitleMap = {
            inbox: 'Inbox',
            sent: 'Sent',
            drafts: 'Drafts',
            trash: 'Trash'
        };
        
        if (this.folderTitle) {
            this.folderTitle.textContent = folderTitleMap[folderName] || 'Unknown';
        }
    }

    
    displayEmails(emails, folderName, message = null) {
        if (!this.emailList || !this.emailListCount) return;
        

        this.emailListCount.textContent = `${emails.length} emails`;
        this.updateFolderCount(folderName, emails.length);
        

        this.emailList.innerHTML = '';
        
        if (emails.length === 0) {
            const messageText = message || 'This folder is empty';
            this.emailList.innerHTML = `
                <div class="text-center py-8 text-violet-300">
                    <svg class="w-12 h-12 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                    </svg>
                    <p class="text-sm font-medium">No emails found</p>
                    <p class="text-xs opacity-75">${this.escapeHtml(messageText)}</p>
                </div>
            `;
        } else {

            emails.forEach((email, index) => {
                const emailItem = this.createEmailItem(email, index);
                this.emailList.appendChild(emailItem);
            });
        }
        

        this.showEmailList();
        
        console.log(`📋 Displayed ${emails.length} emails for ${folderName}`);
    }

    
    createEmailItem(email, index) {
        const emailDiv = document.createElement('div');
        emailDiv.className = 'email-thumbnail p-3 rounded-lg hover:bg-violet-500/10 cursor-pointer transition-all duration-200 border-b border-violet-500/10';
        emailDiv.dataset.emailIndex = index;
        

        const from = email.sender || email.from || 'Unknown Sender';
        const subject = this.decodeUtf8String(email.subject || 'No Subject');
        const snippet = this.getEmailSnippet(email);
        const date = email.received_at ? new Date(email.received_at) : (email.date ? new Date(email.date) : null);
        const isQuMail = email.is_qumail || false;
        

        const initials = this.getInitials(from);
        

        let levelBadge = '';
        if (isQuMail) {
            const securityLevel = this.getQuMailLevel(email);
            levelBadge = `<span class="text-xs px-2 py-1 rounded-full bg-violet-500/20 text-violet-300">${securityLevel}</span>`;
        } else {
            levelBadge = '<span class="text-xs px-2 py-1 rounded-full bg-gray-500/20 text-gray-400">Regular</span>';
        }
        

        const timeAgo = date ? this.formatTimeAgo(date) : '';
        

        const isRecent = date && (new Date() - date) < 30 * 60 * 1000;
        const onlineIndicator = isRecent ? '<div class="w-2 h-2 rounded-full bg-green-400 absolute top-1 right-1"></div>' : '';
        
        emailDiv.innerHTML = `
            <div class="flex items-center space-x-3">
                <!-- Avatar with initials -->
                <div class="relative flex-shrink-0">
                    <div class="w-10 h-10 rounded-full bg-gradient-to-r ${this.getAvatarColor(from)} flex items-center justify-center text-white font-medium text-sm">
                        ${initials}
                    </div>
                    ${onlineIndicator}
                </div>
                
                <!-- Email Content -->
                <div class="flex-1 min-w-0">
                    <!-- Sender name and time -->
                    <div class="flex items-center justify-between mb-1">
                        <h3 class="text-white font-medium text-sm truncate">${this.escapeHtml(this.getDisplayName(from))}</h3>
                        <span class="text-gray-400 text-xs">${timeAgo}</span>
                    </div>
                    
                    <!-- Subject -->
                    <h4 class="text-violet-300 text-sm font-medium truncate mb-1">${this.escapeHtml(subject)}</h4>
                    
                    <!-- Snippet -->
                    <p class="text-gray-400 text-xs truncate mb-2">${this.escapeHtml(snippet)}...</p>
                    
                    <!-- Level badge and edit icon -->
                    <div class="flex items-center justify-between">
                        ${levelBadge}
                        <svg class="w-4 h-4 text-violet-400 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                        </svg>
                    </div>
                </div>
            </div>
        `;
        

        emailDiv.addEventListener('click', () => {
            this.openEmail(email, index);
        });
        
        return emailDiv;
    }

    
    getEmailSnippet(email) {

        const content = email.decrypted_content || 
                       email.original_content || 
                       email.body || 
                       email.content || 
                       email.text || 
                       email.snippet || 
                       '';
        
        if (!content) return 'No content';
        

        const cleanContent = this.decodeUtf8String(content)
            .replace(/<[^>]*>/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        
        return cleanContent.length > 60 ? cleanContent.substring(0, 60) + '...' : cleanContent;
    }

    
    formatEmailContent(content) {
        if (!content) return 'No content';
        

        let formattedContent = this.decodeUtf8String(content);
        

        if (formattedContent.includes('<') && formattedContent.includes('>')) {

            formattedContent = formattedContent
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<\/p>/gi, '\n\n')
                .replace(/<[^>]*>/g, '')
                .replace(/&nbsp;/g, ' ')
                .replace(/&amp;/g, '&')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&quot;/g, '"')
                .replace(/&#39;/g, "'");
        }
        

        formattedContent = formattedContent
            .replace(/\r\n/g, '\n')
            .replace(/\r/g, '\n')
            .replace(/\n{3,}/g, '\n\n')
            .replace(/[ \t]+/g, ' ')
            .trim();
        
        return this.escapeHtml(formattedContent);
    }

    
    getInitials(name) {
        if (!name) return '?';
        const parts = name.split(/[<@\s]+/);
        const firstPart = parts[0] || '?';
        return firstPart.charAt(0).toUpperCase();
    }

    
    getQuMailLevel(email) {
        if (email.security_level) {
            return `Level ${email.security_level}`;
        }
        

        const algorithm = email.algorithm || '';
        if (algorithm.includes('OTP') || algorithm.includes('Quantum Secure')) {
            return 'Level 1: Quantum Secure';
        } else if (algorithm.includes('Quantum-aided AES')) {
            return 'Level 2: Quantum-aided AES';
        } else if (algorithm.includes('Hybrid PQC') || algorithm.includes('ML-KEM')) {
            return 'Level 3: Hybrid PQC';
        } else if (algorithm.includes('Classical') || algorithm.includes('No Quantum')) {
            return 'Level 4: Classical';
        }
        
        return 'QuMail Encrypted';
    }

    
    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffMinutes < 60) {
            return `${diffMinutes}m`;
        } else if (diffHours < 24) {
            return `${diffHours}h`;
        } else {
            return `${diffDays}d`;
        }
    }

    
    getAvatarColor(name) {
        const colors = [
            'from-violet-500 to-purple-600',
            'from-blue-500 to-indigo-600', 
            'from-green-500 to-emerald-600',
            'from-red-500 to-pink-600',
            'from-yellow-500 to-orange-600',
            'from-cyan-500 to-teal-600'
        ];
        

        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }

    
    getDisplayName(from) {
        if (!from) return 'Unknown Sender';
        

        let cleanFrom = this.decodeUtf8String(from).trim();
        

        const quotedNameMatch = cleanFrom.match(/^"([^"]+)"\s*<.*>$/);
        if (quotedNameMatch) {
            return quotedNameMatch[1].trim();
        }
        

        const nameMatch = cleanFrom.match(/^([^<]+)<.*>$/);
        if (nameMatch) {
            const name = nameMatch[1].trim();

            return name.replace(/^["']|["']$/g, '').trim();
        }
        

        const emailMatch = cleanFrom.match(/^([^@]+)@/);
        if (emailMatch) {
            const username = emailMatch[1];

            return username.replace(/[._-]/g, ' ')
                          .replace(/\b\w/g, l => l.toUpperCase())
                          .trim();
        }
        

        if (cleanFrom.includes(' ') && !cleanFrom.includes('@')) {
            return cleanFrom;
        }
        
        return cleanFrom;
    }

    
    async openEmail(email, index) {
        console.log(`📖 Opening email: ${email.subject}`);
        console.log('📧 Full email data:', email);
        
        this.currentEmail = email;
        

        this.updateEmailReader(email);
        

        this.showEmailReader();
    }

    
    updateEmailReader(email) {
        const subjectElement = document.getElementById('email-reader-subject');
        const contentElement = document.getElementById('email-reader-content');
        
        if (!subjectElement || !contentElement) return;
        

        subjectElement.textContent = this.decodeUtf8String(email.subject || 'No Subject');
        

        let emailHtml = this.buildEmailHtml(email);
        

        contentElement.innerHTML = emailHtml;
    }

    
    buildEmailHtml(email) {

        const from = email.sender || email.from || 'Unknown Sender';
        const to = email.recipient || email.to || email.recipients || 'Unknown Recipient';
        const date = email.received_at || email.date || email.timestamp;
        const formattedDate = date ? new Date(date).toLocaleString() : 'Unknown Date';
        const isQuMail = email.is_qumail || false;
        
        let content = '';
        

        content += `
            <div class="bg-violet-500/10 p-4 rounded-lg mb-6 border border-violet-500/20">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-violet-300 font-medium">From:</span>
                        <span class="text-white ml-2">${this.escapeHtml(from)}</span>
                    </div>
                    <div>
                        <span class="text-violet-300 font-medium">To:</span>
                        <span class="text-white ml-2">${this.escapeHtml(to)}</span>
                    </div>
                    <div>
                        <span class="text-violet-300 font-medium">Date:</span>
                        <span class="text-white ml-2">${formattedDate}</span>
                    </div>
                    <div>
                        <span class="text-violet-300 font-medium">Type:</span>
                        <span class="text-white ml-2">${isQuMail ? '🔐 QuMail Encrypted' : '📧 Regular Email'}</span>
                    </div>
                </div>
            </div>
        `;
        

        content += '<div class="prose prose-invert max-w-none">';
        
        if (isQuMail) {

            if (email.decryption_successful === true) {
                content += `
                    <div class="bg-green-500/10 border border-green-500/30 p-4 rounded-lg mb-4">
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="text-green-400">✅</span>
                            <span class="text-green-300 font-medium">Decryption Successful</span>
                        </div>
                        <div class="text-sm text-green-200">
                            Algorithm: ${email.algorithm || 'Unknown'}
                        </div>
                    </div>
                    <div class="text-white whitespace-pre-wrap">${this.formatEmailContent(email.decrypted_content || email.original_content || email.body || email.content || email.text || 'No content')}</div>
                `;
            } else if (email.decryption_successful === false) {
                content += `
                    <div class="bg-red-500/10 border border-red-500/30 p-4 rounded-lg mb-4">
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="text-red-400">❌</span>
                            <span class="text-red-300 font-medium">Decryption Failed</span>
                        </div>
                        <div class="text-sm text-red-200">
                            ${email.decryption_error || 'Unknown error'}
                        </div>
                    </div>
                    <div class="bg-gray-800/50 p-4 rounded-lg">
                        <h4 class="text-violet-300 font-medium mb-2">Encrypted Content:</h4>
                        <pre class="text-gray-300 text-xs whitespace-pre-wrap font-mono">${this.escapeHtml(email.original_content || email.body || email.content || email.text || 'No content available')}</pre>
                    </div>
                `;
            } else {

                content += `
                    <div class="bg-violet-500/10 border border-violet-500/30 p-4 rounded-lg mb-4">
                        <div class="flex items-center space-x-2 mb-2">
                            <span class="text-violet-400">🔐</span>
                            <span class="text-violet-300 font-medium">QuMail Encrypted</span>
                        </div>
                    </div>
                    <div class="bg-gray-800/50 p-4 rounded-lg">
                        <h4 class="text-violet-300 font-medium mb-2">Encrypted Content:</h4>
                        <pre class="text-gray-300 text-xs whitespace-pre-wrap font-mono">${this.escapeHtml(email.original_content || email.body || email.content || email.text || 'No content available')}</pre>
                    </div>
                `;
            }
        } else {

            const emailBody = email.original_content || email.body || email.content || email.text || email.snippet || 'No content available';
            content += `<div class="text-white whitespace-pre-wrap">${this.formatEmailContent(emailBody)}</div>`;
        }
        
        content += '</div>';
        
        if (email.attachments && email.attachments.length > 0) {
            content += `
                <div class="mt-6 border-t border-violet-500/20 pt-4">
                    <h4 class="text-violet-300 text-sm font-medium mb-3 flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.586-6.586a2 2 0 00-2.828-2.828z"></path></svg>
                        Attachments (${email.attachments.length})
                    </h4>
                    <div class="flex flex-wrap gap-3">
            `;
            
            email.attachments.forEach(att => {
                const downloadUrl = `data:${att.content_type || 'application/octet-stream'};base64,${att.data}`;
                content += `
                    <a href="${downloadUrl}" download="${this.escapeHtml(att.filename || 'attachment')}"
                        class="flex items-center gap-2 bg-violet-900/30 hover:bg-violet-800/50 border border-violet-500/30 text-violet-200 text-sm px-3 py-2 rounded-lg transition-colors group">
                        <svg class="w-4 h-4 text-violet-400 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                        <span class="truncate max-w-[200px]">${this.escapeHtml(att.filename || 'attachment')}</span>
                    </a>
                `;
            });
            
            content += `
                    </div>
                </div>
            `;
        }
        
        return content;
    }

    
    updateFolderCount(folderName, count) {
        const countElement = document.getElementById(`${folderName}-count`);
        if (countElement) {
            countElement.textContent = count.toString();
            countElement.style.display = count > 0 ? 'block' : 'none';
        }
    }

    
    showCredentialsRequired() {
        if (!this.emailList) return;
        
        this.emailList.innerHTML = `
            <div class="text-center py-8 text-violet-300">
                <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                </svg>
                <p class="text-lg font-medium">Gmail Configuration Required</p>
                <p class="text-sm opacity-75 mb-4">Please configure your Gmail App Password to access emails</p>
                <button onclick="window.quMailProfileManager?.showCenterModal()" class="bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-lg transition-colors">
                    Configure Gmail
                </button>
            </div>
        `;
        this.showEmailList();
    }

    
    displayError(message) {
        if (!this.emailList) return;
        
        this.emailList.innerHTML = `
            <div class="text-center py-8 text-red-300">
                <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="text-lg font-medium">Error Loading Emails</p>
                <p class="text-sm opacity-75">${this.escapeHtml(message)}</p>
            </div>
        `;
    }

    
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    
    decodeUtf8String(str) {
        if (!str) return '';
        

        if (str.includes('=?UTF-8?Q?') || str.includes('=?utf-8?q?')) {
            try {

                let decoded = str.replace(/=\?UTF-8\?Q\?/gi, '').replace(/\?=$/g, '');

                decoded = decoded.replace(/=([0-9A-F]{2})/gi, (match, hex) => {
                    return String.fromCharCode(parseInt(hex, 16));
                });

                decoded = decoded.replace(/_/g, ' ');
                return decoded;
            } catch (e) {
                console.warn('Failed to decode UTF-8 string:', str, e);
                return str;
            }
        }
        
        return str;
    }

    
    async refresh() {
        if (this.isLoading) return;
        await this.loadFolder(this.currentFolder);
    }
}


let quMailEmailManager = null;

async function initializeEmailManager() {
    try {
        quMailEmailManager = new QuMailEmailManager();
        await quMailEmailManager.initialize();
        

        window.quMailEmailManager = quMailEmailManager;
        
        console.log('🚀 QuMail Email Manager fully initialized');
    } catch (error) {
        console.error('❌ Failed to initialize Email Manager:', error);
        

        setTimeout(initializeEmailManager, 2000);
    }
}


if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeEmailManager);
} else {
    initializeEmailManager();
}

console.log('📧 QuMail Email Manager script loaded');
