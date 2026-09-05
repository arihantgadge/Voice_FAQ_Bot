# 🚀 Production Deployment Guide: AI Voice FAQ Builder

This guide provides end-to-end instructions for deploying the **AI Voice FAQ Assistant** to **Render**, **Railway**, and **Vercel**, matching the specifications in `specs.md`.

---

## 📋 Table of Contents
1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Deploying to Render (Recommended)](#2-deploying-to-render-recommended)
3. [Deploying to Railway](#3-deploying-to-railway)
4. [Deploying to Vercel (Serverless)](#4-deploying-to-vercel-serverless)
5. [Critical Production Architecture & Audio Notes](#5-critical-production-architecture--audio-notes)
6. [Troubleshooting & Verification](#6-troubleshooting--verification)

---

## 1. Pre-Deployment Checklist

Before deploying, ensure your code is committed to a GitHub/GitLab repository:

```bash
git init
git add .
git commit -m "feat: complete AI Voice FAQ builder with multi-engine STT and edge-tts"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-voice-faq-builder.git
git push -u origin main
```

### Essential Configuration Files Included in Repository
- `requirements.txt`: Python runtime dependencies (`flask`, `gunicorn`, `SpeechRecognition`, `edge-tts`, etc.)
- `Procfile`: WSGI server process runner (`web: gunicorn app:app ...`)
- `runtime.txt`: Pinned Python version (`python-3.11.9`)
- `render.yaml`: Infrastructure blueprint for Render
- `railway.json`: Nixpacks deployment configuration for Railway
- `vercel.json`: WSGI routing & serverless build specification for Vercel

---

## 2. Deploying to Render (Recommended)

Render provides an exceptional free tier and native support for Python web services with persistent WebSockets and streaming audio.

### Option A: 1-Click Blueprint Deployment (Fastest)
1. Log in to [Render](https://dashboard.render.com/).
2. Click **Blueprints** in the top navigation.
3. Click **New Blueprint Instance**.
4. Connect your GitHub repository: `YOUR_USERNAME/ai-voice-faq-builder`.
5. Render will automatically detect the [render.yaml](file:///c:/Users/Arihant/OneDrive/문서/Ai%20voice%20FAQ%20builder/render.yaml) file in your repository.
6. Under **Environment Variables**, enter your optional `OPENAI_API_KEY` (or leave blank to use the built-in natural engines).
7. Click **Apply**. Render will build and deploy your app with SSL enabled automatically.

---

### Option B: Manual Web Service Setup
1. Log in to [Render](https://dashboard.render.com/).
2. Click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository**.
4. Choose your `ai-voice-faq-builder` repository.
5. Fill in the deployment details:
   - **Name**: `ai-voice-faq-bot`
   - **Region**: Select the region closest to your users (e.g., `Singapore`, `Frankfurt`, `Oregon`).
   - **Branch**: `main`
   - **Root Directory**: Leave blank (root).
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
     ```
   - **Instance Type**: `Free`
6. Expand **Advanced** -> **Environment Variables**:
   | Key | Value | Description |
   |---|---|---|
   | `PYTHON_VERSION` | `3.11.9` | Ensures modern Python runtime compatibility |
   | `OPENAI_API_KEY` | *(optional)* | For GPT-4o / Cloud Whisper fallback |
7. Click **Create Web Service**.
8. Wait 2-3 minutes for the build to finish. Your app will be live at:
   `https://ai-voice-faq-bot.onrender.com`

---

## 3. Deploying to Railway

Railway auto-detects Python projects and binds `$PORT` automatically with Nixpacks.

### Step-by-Step Instructions
1. Log in to [Railway](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your `ai-voice-faq-builder` repository.
4. Railway will inspect your repository, find `railway.json` and `Procfile`, and initiate the build.
5. While deploying, navigate to the **Variables** tab and add any desired environment variables:
   - `OPENAI_API_KEY`: *(Optional)* Your OpenAI key.
   - `PYTHON_VERSION`: `3.11.9`
6. Go to the **Settings** tab:
   - Under **Networking**, click **Generate Domain** (e.g., `ai-voice-faq-bot.up.railway.app`).
   - Notice that Railway provides an automatic **HTTPS** SSL certificate.
7. Click **Deployments** to inspect the live build logs. Once complete, your voice bot is immediately accessible.

---

## 4. Deploying to Vercel (Serverless)

Vercel deploys Python applications as Serverless WSGI functions.

### Step-by-Step Instructions via Vercel Dashboard
1. Log in to [Vercel](https://vercel.com/).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository: `ai-voice-faq-builder`.
4. In the configuration screen:
   - **Framework Preset**: `Other`
   - **Root Directory**: `./` (leave default)
5. Under **Environment Variables**, add:
   - `OPENAI_API_KEY`: *(Optional)*
6. Click **Deploy**.
7. Vercel reads [vercel.json](file:///c:/Users/Arihant/OneDrive/문서/Ai%20voice%20FAQ%20builder/vercel.json), routes all `/static/*` requests to the static assets, and pipes `/api/*` and root HTML requests into `app.py`.

### Deploying via Vercel CLI (Alternative)
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Login to Vercel
vercel login

# 3. Deploy preview
vercel

# 4. Deploy to production
vercel --prod
```

> [!NOTE]
> Serverless platforms like Vercel have an execution timeout (10s on Hobby plan, 60s on Pro plan). For long multi-sentence studio voice synthesis or heavy custom models, Render or Railway provides longer timeouts (120s+) via Gunicorn workers.

---

## 5. Critical Production Architecture & Audio Notes

### 🔒 1. HTTPS is Mandatory for Microphone Access
Modern browsers (Chrome, Safari, Edge, Firefox) **strictly disallow** `navigator.mediaDevices.getUserMedia` on insecure HTTP connections.
- When running locally: `http://localhost:5000` is treated as a secure origin by default.
- When deployed in production: The website **must be accessed via HTTPS**.
- **Good news**: Render, Railway, and Vercel all automatically issue free, auto-renewing SSL/TLS certificates for your domains!

### 🎙️ 2. Dual-Engine Resilient Speech Architecture
In production environments, some user browsers may have adblockers or network restrictions that block Google's speech recognition websocket endpoints (`webkitSpeechRecognition`).
- The application implements a **Dual-Engine Speech Recorder**:
  1. Captures raw audio via Web Audio API (`AudioContext` + `ScriptProcessorNode`).
  2. Encodes uncompressed 16-bit 16kHz mono WAV buffers natively in browser memory.
  3. If browser speech recognition drops or errors with `network`, the app seamlessly sends the WAV buffer to `/api/transcribe` on your backend.
  4. The backend uses Python `SpeechRecognition` or Whisper to accurately transcribe speech without dropping a word.

### 🔊 3. High-Fidelity Edge-TTS Voice Synthesis
- The application delivers human-grade female (`JennyNeural`) and male (`GuyNeural`) speech via `edge-tts`.
- Audio is returned as base64 audio chunks directly to the browser and played via HTML5 `Audio`.
- If client-side speech synthesis is preferred, the app has an automatic fallback to browser native SpeechSynthesis voices.

---

## 6. Troubleshooting & Verification

### Smoke Test Endpoints
Once your application is deployed, run the following verification commands in your terminal:

```bash
# 1. Check health & analytics
curl -X GET https://YOUR_APP_URL/api/analytics

# 2. Test FAQ semantic retrieval
curl -X POST https://YOUR_APP_URL/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the cutoff for JEE Mains?", "language": "en", "answer_mode": "detailed"}'

# 3. Test Speech Transcription endpoint
curl -X POST https://YOUR_APP_URL/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio": "", "language": "en"}'
```

### Common Issues & Fixes
| Issue | Cause | Resolution |
|---|---|---|
| **Microphone blocked / not permitted** | Accessing via HTTP instead of HTTPS | Ensure you are visiting `https://your-domain.com`. Verify browser permissions in the URL bar icon. |
| **Gunicorn worker timeout (CRITICAL [worker timeout])** | Heavy query latency exceeding default 30s | The `Procfile` sets `--timeout 120`. Ensure this flag is present in your start command. |
| **502 Bad Gateway on Render/Railway** | Flask app listening on hardcoded port | `app.py` reads `PORT` from environment variables (`int(os.environ.get("PORT", 5000))`). Gunicorn binds to `0.0.0.0:$PORT`. |
| **ModuleNotFoundError on deploy** | Missing package in `requirements.txt` | Ensure all dependencies from `requirements.txt` (`gunicorn`, `SpeechRecognition`, `edge-tts`, `flask`) are committed. |

---

🎉 **Your AI Voice FAQ Assistant is now fully production-ready and live!**
