# 🛡️ QuMail: Quantum Secure Email Client

<div align="center">

![QuMail Logo](https://img.shields.io/badge/QuMail-Quantum%20Secure-blueviolet?style=for-the-badge&logo=shield&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend%20API-lightgrey?style=for-the-badge&logo=flask&logoColor=white)
![Electron](https://img.shields.io/badge/Electron-Desktop%20GUI-47848F?style=for-the-badge&logo=electron&logoColor=white)

**Next-Generation Quantum-Safe Hybrid Encrypted Email Client**

*Combining Quantum Key Distribution (QKD), Post-Quantum Cryptography (ML-KEM/Kyber), and Classical Encryption*

</div>

---

## 🌟 Overview

**QuMail** is a quantum-resilient email communication client designed to safeguard electronic correspondence against present and future quantum computing threats ("Harvest Now, Decrypt Later"). It pairs modern user-friendly email interfaces with a 3-layer cryptographic defense framework.

### 🚀 Hybrid Cryptographic Architecture

QuMail employs a multi-tiered cryptographic system:

- 🔮 **Quantum Layer**: Simulated BB84 Quantum Key Distribution via ETSI GS QKD 014-compliant REST APIs.
- 🛡️ **Post-Quantum Cryptography (PQC)**: NIST-standardized ML-KEM-768 (Kyber) for quantum-safe key encapsulation and ML-DSA for quantum-proof digital signatures.
- 🔐 **Classical Layer**: ECDH / X25519 key exchange + AES-256-GCM authenticated encryption.

---

## 🎨 Key Features

- **🔐 4-Tier Configurable Security Levels**:
  - **Level 1 (Quantum OTP)**: Information-theoretic security via QKD one-time pad.
  - **Level 2 (Quantum-Aided AES)**: AES-256 with quantum-seeded dynamic keys.
  - **Level 3 (Hybrid PQC)**: Post-quantum ML-KEM-768 combined with classical ECDH.
  - **Level 4 (Standard)**: Standard encryption for non-sensitive communications.
- **✨ Glassmorphic User Interface**: Sleek, futuristic violet/purple theme with responsive animations, real-time particle feedback, and Three.js key visualization.
- **☁️ Cloud & Local Key Sync**: Centralized public key registry backed by Supabase with local encrypted caching.
- **📬 Email Provider Compatibility**: Works seamlessly with Gmail and Yahoo Mail over secure TLS/SMTP/IMAP.

---

## 📁 Repository Structure

```
Qu-mail/
├── ⚙️ backend/             # Flask REST API, Cryptographic Engines & QKD APIs
│   ├── app.py             # Main Flask server
│   ├── crypto.py          # ECDH & hybrid key derivation
│   ├── email_integration.py # SMTP / IMAP integration
│   ├── encryption.py      # Core encryption routines
│   ├── real_pqc.py        # ML-KEM & Post-Quantum cryptographic operations
│   └── supabase_client.py # Cloud key store integration
├── 🎨 frontend/            # Glassmorphism UI (HTML, CSS, JS, Electron)
│   ├── index.html         # Main client dashboard
│   ├── login.html         # User authentication & provider setup
│   ├── renderer.js        # UI controller and API client
│   └── hybrid_animation.js # Three.js visual key-exchange animation
├── 🔬 simulator/           # BB84 Quantum Key Distribution Simulator
│   └── qkd.py             # Qiskit-based photon polarization simulation
├── 📋 requirements.txt     # Python backend dependencies
├── 📦 package.json         # Electron & frontend dependencies
└── 🚫 .gitignore           # Git ignore configurations
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.10+** (Recommended: 3.11 or 3.12)
- **Node.js 18+** & npm
- Standard operating system (Windows 10/11, macOS, Linux)

### 1. Clone the Repository
```bash
git clone https://github.com/Akshatjain164/Qu-mail.git
cd Qu-mail
```

### 2. Set Up the Backend
```bash
# Navigate to backend and create virtual environment
cd backend
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the Flask API
python app.py
```
The backend API will start on `http://localhost:5000`.

### 3. Set Up & Launch the Frontend
In a new terminal:
```bash
# Return to project root
npm install

# Start the Electron application
npm start
```

---

## 📜 License

This project is licensed under the MIT License.
