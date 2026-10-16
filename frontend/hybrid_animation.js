


class HybridKeyAnimator {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.particles = {
            qkd: [],
            mlkem: [],
            ecdh: []
        };
        this.superKey = null;
        this.animationId = null;
        this.isAnimating = false;
        this.animationPhase = 0;
        
        this.init();
    }

    init() {
        console.log('🎭 Initializing Hybrid Key Animation System...');
        this.setupScene();
        this.setupEventListeners();
    }

    setupScene() {
        const canvas = document.getElementById('hybrid-animation-canvas');
        if (!canvas) {
            console.error('❌ Animation canvas not found');
            return;
        }


        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);


        this.camera = new THREE.PerspectiveCamera(75, canvas.offsetWidth / canvas.offsetHeight, 0.1, 1000);
        this.camera.position.z = 15;


        this.renderer = new THREE.WebGLRenderer({ 
            canvas: canvas, 
            antialias: true, 
            alpha: true 
        });
        this.renderer.setSize(canvas.offsetWidth, canvas.offsetHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);


        window.addEventListener('resize', () => this.onWindowResize());
    }

    setupEventListeners() {

        document.addEventListener('animationComplete', () => {
            setTimeout(() => {
                this.hideModal();
            }, 2000);
        });


        const closeBtn = document.getElementById('close-hybrid-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideModal();
            });
        }


        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const modal = document.getElementById('hybrid-key-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    this.hideModal();
                }
            }
        });
    }

    onWindowResize() {
        const canvas = document.getElementById('hybrid-animation-canvas');
        if (!canvas) return;

        this.camera.aspect = canvas.offsetWidth / canvas.offsetHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(canvas.offsetWidth, canvas.offsetHeight);
    }


    async startAnimation(keyTypes = ['qkd', 'mlkem', 'ecdh']) {
        if (this.isAnimating) return;
        
        console.log('🚀 Starting Hybrid Key Animation...');
        this.isAnimating = true;
        this.animationPhase = 0;
        
        this.showModal();
        this.clearScene();
        

        await this.phase1_InitializeParticles(keyTypes);
        await this.phase2_StreamParticles();
        await this.phase3_MergeToSuperKey();
        await this.phase4_CompleteSuperKey();
        
        this.isAnimating = false;
        document.dispatchEvent(new CustomEvent('animationComplete'));
    }

    showModal() {
        const modal = document.getElementById('hybrid-key-modal');
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
    }

    hideModal() {
        const modal = document.getElementById('hybrid-key-modal');
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
            this.stopAnimation();
        }
    }

    clearScene() {

        Object.values(this.particles).forEach(particleArray => {
            particleArray.forEach(particle => {
                this.scene.remove(particle);
            });
        });
        

        this.particles = { qkd: [], mlkem: [], ecdh: [] };
        

        if (this.superKey) {
            this.scene.remove(this.superKey);
            this.superKey = null;
        }
    }

    async phase1_InitializeParticles(keyTypes) {
        this.updateStatus('Initializing quantum channels...');
        this.updateProgress(10);
        
        const particleCount = 200;
        
        for (const keyType of keyTypes) {
            await this.createParticleSystem(keyType, particleCount);
            await this.delay(300);
        }
        
        this.updateProgress(30);
    }

    createParticleSystem(keyType, count) {
        return new Promise((resolve) => {
            const colors = {
                qkd: 0x00ff88,
                mlkem: 0x8b5cf6,
                ecdh: 0x3b82f6
            };

            const positions = {
                qkd: { x: -8, y: 4 },
                mlkem: { x: -8, y: 0 },
                ecdh: { x: -8, y: -4 }
            };

            const geometry = new THREE.SphereGeometry(0.05, 8, 6);
            const material = new THREE.MeshBasicMaterial({ 
                color: colors[keyType],
                transparent: true,
                opacity: 0.8
            });

            for (let i = 0; i < count; i++) {
                const particle = new THREE.Mesh(geometry, material);
                

                const startPos = positions[keyType];
                particle.position.set(
                    startPos.x + (Math.random() - 0.5) * 2,
                    startPos.y + (Math.random() - 0.5) * 1,
                    (Math.random() - 0.5) * 2
                );
                

                particle.userData = {
                    type: keyType,
                    speed: 0.02 + Math.random() * 0.02,
                    targetX: 0,
                    targetY: 0,
                    targetZ: 0,
                    phase: 'streaming'
                };
                
                this.scene.add(particle);
                this.particles[keyType].push(particle);
            }
            
            this.updateStatus(`Generated ${keyType.toUpperCase()} particles...`);
            resolve();
        });
    }

    async phase2_StreamParticles() {
        this.updateStatus('Streaming cryptographic keys...');
        this.animationPhase = 1;
        
        return new Promise((resolve) => {
            const startTime = Date.now();
            const duration = 2000;
            
            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                

                this.updateProgress(30 + progress * 40);
                

                Object.values(this.particles).forEach(particleArray => {
                    particleArray.forEach(particle => {
                        if (particle.userData.phase === 'streaming') {

                            particle.position.x += (particle.userData.targetX - particle.position.x) * particle.userData.speed;
                            particle.position.y += (particle.userData.targetY - particle.position.y) * particle.userData.speed;
                            particle.position.z += (particle.userData.targetZ - particle.position.z) * particle.userData.speed;
                            

                            particle.rotation.x += 0.02;
                            particle.rotation.y += 0.01;
                        }
                    });
                });
                
                this.renderer.render(this.scene, this.camera);
                
                if (progress < 1) {
                    this.animationId = requestAnimationFrame(animate);
                } else {
                    resolve();
                }
            };
            
            animate();
        });
    }

    async phase3_MergeToSuperKey() {
        this.updateStatus('Merging quantum keys...');
        this.animationPhase = 2;
        this.updateProgress(70);
        
        return new Promise((resolve) => {
            const startTime = Date.now();
            const duration = 1500;
            
            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                

                Object.values(this.particles).forEach(particleArray => {
                    particleArray.forEach(particle => {

                        particle.position.lerp(new THREE.Vector3(0, 0, 0), 0.1);
                        

                        const scale = 1 - progress * 0.8;
                        particle.scale.setScalar(scale);
                        

                        particle.material.opacity = 0.8 * (1 - progress);
                    });
                });
                
                this.renderer.render(this.scene, this.camera);
                
                if (progress < 1) {
                    this.animationId = requestAnimationFrame(animate);
                } else {
                    resolve();
                }
            };
            
            animate();
        });
    }

    async phase4_CompleteSuperKey() {
        this.updateStatus('Quantum super-key generated!');
        this.animationPhase = 3;
        

        this.clearScene();
        

        const superKeyGeometry = new THREE.SphereGeometry(1, 32, 24);
        const superKeyMaterial = new THREE.MeshBasicMaterial({
            color: 0x8b5cf6,
            transparent: true,
            opacity: 0
        });
        
        this.superKey = new THREE.Mesh(superKeyGeometry, superKeyMaterial);
        this.scene.add(this.superKey);
        

        return new Promise((resolve) => {
            const startTime = Date.now();
            const duration = 1000;
            
            const animate = () => {
                const elapsed = Date.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                

                this.superKey.material.opacity = progress * 0.9;
                this.superKey.scale.setScalar(progress);
                

                const pulse = 1 + Math.sin(elapsed * 0.005) * 0.1;
                this.superKey.scale.setScalar(progress * pulse);
                

                this.superKey.rotation.y += 0.02;
                this.superKey.rotation.x += 0.01;
                

                this.updateProgress(90 + progress * 10);
                
                this.renderer.render(this.scene, this.camera);
                
                if (progress < 1) {
                    this.animationId = requestAnimationFrame(animate);
                } else {
                    this.updateStatus('Hybrid encryption ready!');
                    this.updateSuperKeyStatus('256-bit Super-Key');
                    resolve();
                }
            };
            
            animate();
        });
    }

    updateStatus(message) {
        const statusElement = document.getElementById('animation-status');
        if (statusElement) {
            statusElement.textContent = message;
        }
        console.log(`🎭 ${message}`);
    }

    updateProgress(percentage) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-percentage');
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${Math.round(percentage)}%`;
        }
    }

    updateSuperKeyStatus(status) {
        const statusElement = document.querySelector('#super-key-status span');
        if (statusElement) {
            statusElement.textContent = status;
        }
    }

    stopAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        this.isAnimating = false;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}


document.addEventListener('DOMContentLoaded', () => {

    setTimeout(() => {
        if (typeof THREE !== 'undefined') {
            window.hybridAnimator = new HybridKeyAnimator();
            console.log('✅ Hybrid Key Animator initialized');
        } else {
            console.error('❌ Three.js not loaded');
        }
    }, 100);
});


window.HybridKeyAnimator = HybridKeyAnimator;
window.hybridAnimator = null;


window.showHybridKeyAnimation = (keyTypes = ['qkd', 'mlkem', 'ecdh']) => {
    if (window.hybridAnimator) {
        window.hybridAnimator.startAnimation(keyTypes);
    } else {
        console.error('❌ Hybrid animator not initialized');
        console.log('💡 Attempting to initialize now...');
        

        if (typeof THREE !== 'undefined') {
            window.hybridAnimator = new HybridKeyAnimator();
            console.log('✅ Hybrid Key Animator initialized on-demand');

            setTimeout(() => {
                if (window.hybridAnimator) {
                    window.hybridAnimator.startAnimation(keyTypes);
                }
            }, 100);
        }
    }
};
