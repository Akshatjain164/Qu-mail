const { app, BrowserWindow, Menu, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');


class QuMailApp {
    constructor() {
        this.mainWindow = null;
        this.loginWindow = null;
        this.isDevelopment = process.env.NODE_ENV === 'development';
        this.userCredentials = null;
        this.backendProcess = null;
    }

    createMainWindow() {

        this.mainWindow = new BrowserWindow({
            width: 1400,
            height: 900,
            minWidth: 1200,
            minHeight: 800,
            show: false,
            icon: path.join(__dirname, 'assets', 'icon.png'),
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
                enableRemoteModule: true,
                webSecurity: false
            },
            titleBarStyle: 'default',
            frame: true,
            backgroundColor: '#1a1b2e',
            vibrancy: 'under-window'
        });


        this.mainWindow.loadFile(path.join(__dirname, 'index.html'));


        this.mainWindow.webContents.once('dom-ready', () => {
            if (this.userCredentials) {
                this.mainWindow.webContents.send('user-credentials', this.userCredentials);
            }
        });


        this.mainWindow.once('ready-to-show', () => {
            this.mainWindow.show();


            if (this.isDevelopment) {
                this.mainWindow.webContents.openDevTools();
            }
        });


        this.mainWindow.on('closed', () => {
            this.mainWindow = null;
        });


        this.mainWindow.on('maximize', () => {
            this.mainWindow.webContents.send('window-maximized');
        });

        this.mainWindow.on('unmaximize', () => {
            this.mainWindow.webContents.send('window-unmaximized');
        });
    }

    createLoginWindow() {

        this.loginWindow = new BrowserWindow({
            width: 500,
            height: 700,
            resizable: false,
            show: false,
            center: true,
            icon: path.join(__dirname, 'assets', 'icon.png'),
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
                enableRemoteModule: true,
                webSecurity: false
            },
            titleBarStyle: 'default',
            frame: true,
            backgroundColor: '#667eea',
            alwaysOnTop: false
        });


        this.loginWindow.loadFile(path.join(__dirname, 'login.html'));


        this.loginWindow.once('ready-to-show', () => {
            this.loginWindow.show();

            if (this.isDevelopment) {
                this.loginWindow.webContents.openDevTools();
            }
        });


        this.loginWindow.on('closed', () => {
            this.loginWindow = null;

            if (!this.mainWindow) {
                app.quit();
            }
        });
    }

    createMenu() {
        const template = [
            {
                label: 'QuMail',
                submenu: [
                    {
                        label: 'About QuMail',
                        click: () => {
                            this.showAboutDialog();
                        }
                    },
                    { type: 'separator' },
                    {
                        label: 'Preferences...',
                        accelerator: 'CmdOrCtrl+,',
                        click: () => {
                            this.mainWindow.webContents.send('open-preferences');
                        }
                    },
                    { type: 'separator' },
                    {
                        label: 'Quit QuMail',
                        accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
                        click: () => {
                            app.quit();
                        }
                    }
                ]
            },
            {
                label: 'Email',
                submenu: [
                    {
                        label: 'New Email',
                        accelerator: 'CmdOrCtrl+N',
                        click: () => {
                            this.mainWindow.webContents.send('new-email');
                        }
                    },
                    {
                        label: 'Send Email',
                        accelerator: 'CmdOrCtrl+Enter',
                        click: () => {
                            this.mainWindow.webContents.send('send-email');
                        }
                    },
                    { type: 'separator' },
                    {
                        label: 'Refresh Inbox',
                        accelerator: 'CmdOrCtrl+R',
                        click: () => {
                            this.mainWindow.webContents.send('refresh-inbox');
                        }
                    }
                ]
            },
            {
                label: 'View',
                submenu: [
                    { role: 'reload' },
                    { role: 'forcereload' },
                    { role: 'toggledevtools' },
                    { type: 'separator' },
                    { role: 'resetzoom' },
                    { role: 'zoomin' },
                    { role: 'zoomout' },
                    { type: 'separator' },
                    { role: 'togglefullscreen' }
                ]
            },
            {
                label: 'Window',
                submenu: [
                    { role: 'minimize' },
                    { role: 'close' }
                ]
            }
        ];

        const menu = Menu.buildFromTemplate(template);
        Menu.setApplicationMenu(menu);
    }

    showAboutDialog() {
        const { dialog } = require('electron');
        dialog.showMessageBox(this.mainWindow, {
            type: 'info',
            title: 'About QuMail',
            message: 'QuMail: Quantum Secure Email Client',
            detail: `Version: 1.0.0
Developed by Byte_Bandits
Problem Statement ID: 25179

Features:
• Quantum Key Distribution (QKD) Integration
• Post-Quantum Cryptography (ML-KEM-768, ML-DSA-6x5)
• Hybrid Encryption Framework (192-bit security)
• Gmail/Yahoo Compatibility
• Violet/Purple Glassmorphism UI

Team: Byte_Bandits`,
            buttons: ['OK']
        });
    }

    setupIPC() {

        ipcMain.on('login-success', (event, credentials) => {
            console.log('✅ Login successful for:', credentials.email);
            this.userCredentials = credentials;


            if (this.loginWindow) {
                this.loginWindow.close();
                this.loginWindow = null;
            }


            this.createMainWindow();
        });


        ipcMain.on('open-external-url', (event, url) => {
            shell.openExternal(url);
        });


        ipcMain.handle('get-app-version', () => {
            return app.getVersion();
        });

        ipcMain.handle('show-save-dialog', async () => {
            const { dialog } = require('electron');
            const result = await dialog.showSaveDialog(this.mainWindow, {
                filters: [
                    { name: 'Email Files', extensions: ['eml'] },
                    { name: 'All Files', extensions: ['*'] }
                ]
            });
            return result;
        });

        ipcMain.handle('show-open-dialog', async () => {
            const { dialog } = require('electron');
            const result = await dialog.showOpenDialog(this.mainWindow, {
                properties: ['openFile', 'multiSelections'],
                filters: [
                    { name: 'All Files', extensions: ['*'] },
                    { name: 'Images', extensions: ['jpg', 'png', 'gif'] },
                    { name: 'Documents', extensions: ['pdf', 'doc', 'docx'] }
                ]
            });
            return result;
        });
    }

    startBackend() {
        const pythonPath = path.join(__dirname, '..', 'backend', '.venv', 'Scripts', 'python.exe');
        const scriptPath = path.join(__dirname, '..', 'backend', 'app.py');
        
        console.log(`🚀 Starting backend process (hidden): ${pythonPath} ${scriptPath}`);
        
        this.backendProcess = spawn(pythonPath, [scriptPath], {
            cwd: path.join(__dirname, '..', 'backend'),
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
            windowsHide: true
        });
        
        this.backendProcess.stdout.on('data', (data) => {
            console.log(`[Backend]: ${data}`);
        });
        
        this.backendProcess.stderr.on('data', (data) => {
            console.error(`[Backend Error]: ${data}`);
        });
        
        this.backendProcess.on('close', (code) => {
            console.log(`Backend process exited with code ${code}`);
        });
    }

    stopBackend() {
        if (this.backendProcess) {
            console.log('Stopping backend process tree...');
            try {
                if (process.platform === 'win32') {
                    const { execSync } = require('child_process');
                    execSync(`taskkill /pid ${this.backendProcess.pid} /T /F`);
                } else {
                    this.backendProcess.kill('SIGKILL');
                }
            } catch (e) {
                console.error('Failed to kill backend process forcefully:', e);
                try {
                    this.backendProcess.kill();
                } catch (err) {}
            }
            this.backendProcess = null;
        }
    }

    initialize() {

        app.whenReady().then(() => {

            this.startBackend();


            this.createLoginWindow();
            this.createMenu();
            this.setupIPC();


            app.on('activate', () => {
                if (BrowserWindow.getAllWindows().length === 0) {
                    this.createMainWindow();
                }
            });
        });


        app.on('window-all-closed', () => {
            this.stopBackend();
            if (process.platform !== 'darwin') {
                app.quit();
            }
        });


        app.on('before-quit', () => {
            this.stopBackend();
        });

        app.on('will-quit', () => {
            this.stopBackend();
        });


        app.on('web-contents-created', (event, contents) => {
            contents.on('new-window', (event, navigationUrl) => {
                event.preventDefault();
                console.log('Blocked new window to:', navigationUrl);
            });
        });
    }
}


const quMailApp = new QuMailApp();
quMailApp.initialize();
