# Local Development & Environment Setup Guide

## 1. System Requirements

- **Operating System:** Windows 10/11, macOS, or Ubuntu 22.04+
- **Python:** Version 3.12 or higher
- **Node.js:** Version 20+ LTS with `pnpm`
- **Docker:** Docker Desktop with Compose support
- **Git:** Version 2.40+

---

## 2. Repository Configuration

Clone the repository and set up environment definitions:

```bash
git clone https://github.com/Sujal-Shreshya/Antygravity-AI-trading.git
cd Antygravity-AI-trading

# Create local environment from example
cp .env.example .env
```

Ensure `LIVE_TRADING=false` is set in your `.env`.

---

## 3. Infrastructure Initialization

Spin up PostgreSQL 16 and Redis 7 containers:

```bash
docker compose up -d postgres redis
```

Verify services are healthy:

```bash
docker compose ps
```

---

## 4. Backend Environment

Create a virtual environment and install core packages:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
```

---

## 5. Security & Secret Hygiene

- **Never** add secrets, production database URLs, or broker API tokens to `.env.example` or any committed code.
- Ensure `.env` is ignored by Git (`git status` should never show `.env`).
- Live trading is restricted to Phase 14 and requires manual operational sign-off.
