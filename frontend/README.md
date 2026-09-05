# NIVARAN Frontend — Web User Interface

Revenue recovery, resolved intelligently.

This is the official user-facing React + TypeScript + Vite web interface for **NIVARAN**.

## Local Development & Setup

### 1. Prerequisites
- Node.js v18+ (Node.js v24+ recommended)
- Python 3.10+ (for backend)

### 2. Start Backend API Server
In the project root directory:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Backend API will run at `http://localhost:8000`.

### 3. Start Frontend Development Server
In the `frontend` directory:
```bash
npm install
npm run dev
```
Frontend application will open at `http://localhost:5173`.

## Environment Variables

Copy `.env.example` to `.env` (optional):
```env
VITE_API_BASE_URL=http://localhost:8000
```
*Note: Never put backend API keys or secrets in frontend configuration.*
