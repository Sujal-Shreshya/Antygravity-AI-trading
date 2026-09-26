# AI Trading Engine

A production-oriented, multi-market algorithmic trading and analysis platform designed for Indian Equities & Derivatives (NSE/BSE), Global Cryptocurrencies (Binance-compatible), and Forex pairs. Built with a strict **fail-closed, safety-first architecture**, paper-trading default, and modular event-driven pipeline.

---

## ⚠️ Important Trading Risk Disclaimer & Safety Baseline

> **CRITICAL OPERATING RULE:**  
> **`LIVE_TRADING=false` is enforced by default in all configurations, environments, and tests.**  
> When `LIVE_TRADING=false`, the platform is technically incapable of routing real orders to any external broker or exchange. All executions route exclusively through the paper trading engine or event-driven backtester.
>
> 1. Algorithmic trading involves substantial risk of financial loss. Past performance, backtest metrics, and AI/ML model outputs do **not** guarantee future profits.
> 2. No market data, broker response, order fill, or execution price is ever fabricated. Missing data is flagged with explicit provenance and quality degradation warnings.
> 3. Enabling live execution requires explicit multi-step verification, capital allocation limits, risk-boundary validation, and confirmation of active emergency kill-switch controls.

---

## 🏛️ High-Level System Architecture

```
                       ┌─────────────────────────────────────────┐
                       │          React Dark Terminal UI         │
                       │ (Vite + TypeScript + LightweightCharts) │
                       └────────────────────┬────────────────────┘
                                            │ HTTP / WebSocket
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Gateway & Core Router                          │
│                   (JWT Auth, RBAC, Rate-Limiting, Idempotency)                  │
└───────┬───────────────────────────────────┬─────────────────────────────┬───────┘
        │                                   │                             │
        ▼                                   ▼                             ▼
┌──────────────────────┐         ┌──────────────────────┐      ┌──────────────────┐
│ Market Data Engine   │         │ Strategy & AI Engine │      │ Backtesting      │
│ ├─ WebSocket Feeds   │         │ ├─ Technical Plugin  │      │ ├─ Event Driver  │
│ ├─ Historical OHLCV  │         │ ├─ Indicators (TA)   │      │ ├─ Slippage/Fees │
│ ├─ Multi-Timeframe   │         │ ├─ ML Regimes/Filter │      │ └─ Metrics Engine│
│ └─ Normalization     │         │ └─ Signal Generator  │      └──────────────────┘
└──────────┬───────────┘         └──────────┬───────────┘
           │                                │ Signals
           ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Risk Management Engine                             │
│ ├─ Max Risk / Trade (1%)   ├─ Max Daily Loss (3%)   ├─ Portfolio Drawdown (10%) │
│ ├─ Max Open Positions      ├─ Position Sizing (ATR) ├─ Global Kill Switch       │
│ └──────────────────────────┴─ Pre-Trade Validation ─┴───────────────────────────┘
                                            │ Approved Orders
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │          Execution Coordinator          │
                       └────┬───────────────────────────────┬────┘
                            │ LIVE_TRADING=false            │ LIVE_TRADING=true (Phase 14)
                            ▼                               ▼
               ┌─────────────────────────┐     ┌─────────────────────────┐
               │   Paper Trading Engine  │     │   Broker Adapters       │
               │ ├─ Simulated Fills      │     │ ├─ Kite Connect (NSE)   │
               │ ├─ Slippage & Fees      │     │ ├─ Binance (Crypto)     │
               │ └─ Virtual Portfolio    │     │ └─ OANDA (Forex)        │
               └────────────┬────────────┘     └────────────┬────────────┘
                            │                               │
                            ▼                               ▼
               ┌─────────────────────────────────────────────────────────┐
               │               PostgreSQL & Redis State                  │
               │ ├─ Postgres: Persistent Orders, Trades, Signals, Audit  │
               │ └─ Redis: Live Ticks, Quotes, Ephemeral Cache, Pub/Sub  │
               └─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Python 3.12+, FastAPI, Uvicorn, asyncio |
| **Data Validation & Settings** | Pydantic v2, Pydantic-Settings |
| **Persistence & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (AsyncIO), Alembic |
| **In-Memory Cache & PubSub** | Redis 7, redis-py |
| **Quant & Data Analysis** | Pandas, NumPy, pandas-ta / TA-Lib |
| **Machine Learning** | LightGBM, XGBoost, Scikit-learn (signal ranking & regime classification) |
| **Frontend Dashboard** | React 18, TypeScript, Tailwind CSS, TradingView Lightweight Charts |
| **DevOps & Infrastructure** | Docker, Docker Compose, Nginx, GitHub Actions |

---

## 📁 Repository Directory Structure

```
Antygravity-AI-trading/
├── .github/
│   └── workflows/
│       └── ci.yml               # Automated CI pipeline (lint, test, build, docker)
├── backend/
│   ├── api/                     # FastAPI routes, schemas, and dependencies
│   ├── core/                    # Core configuration, security, logger, kill switch
│   ├── data/                    # Market data consumers, normalizers, WebSocket clients
│   ├── brokers/                 # Unified broker abstraction & adapter implementations
│   ├── strategies/              # Strategy interface & 10 baseline algorithmic strategies
│   ├── indicators/              # Modular technical indicators (RSI, MACD, EMA, etc.)
│   ├── signals/                 # Signal models, aggregation, ranking, and calibration
│   ├── risk/                    # Pre-trade risk validation, position sizing, circuit breakers
│   ├── portfolio/               # Portfolio accounting, real-time P&L, position tracking
│   ├── execution/               # Execution coordinator (routes to paper or broker)
│   ├── backtesting/             # Event-driven backtesting engine with realistic friction
│   ├── paper_trading/           # In-memory realistic execution simulation & paper persistence
│   ├── database/                # SQLAlchemy async models, migrations, and session factory
│   ├── monitoring/              # System health, telemetry, latency metrics, and audit logs
│   ├── notifications/           # Multi-channel alerts (Telegram, SMTP, Webhooks)
│   └── tests/                   # Backend test suites (unit, integration, safety gates)
├── frontend/
│   ├── components/              # Modular UI components (tables, order pads, modal alerts)
│   ├── pages/                   # Terminal pages (Overview, Markets, Watchlist, Charts, etc.)
│   ├── charts/                  # TradingView Lightweight Charts wrappers & candle renders
│   ├── services/                # API client services & WebSocket connection managers
│   ├── hooks/                   # Custom React hooks (useMarketData, useOrders, useAuth)
│   └── types/                   # TypeScript interfaces and API schemas
├── infrastructure/
│   ├── docker/                  # Dockerfiles for backend and frontend
│   └── nginx/                   # Reverse proxy configuration
├── scripts/                     # Operational automation scripts (bootstrap, migrations, seed)
├── docs/
│   ├── architecture/            # Architectural decisions, data models, and safety docs
│   └── setup.md                 # Step-by-step local development setup guide
├── tests/                       # End-to-end and cross-layer integration tests
├── .env.example                 # Safe environment configuration template
├── .gitignore                   # Multi-language git ignore specification
├── docker-compose.yml           # Local multi-container orchestration
├── LICENSE                      # MIT Open Source License
└── README.md                    # Project documentation entry point
```

---

## ⚡ Quick Start & Local Setup

### Prerequisites
- Python 3.12+
- Node.js 20+ LTS & pnpm
- Docker & Docker Compose
- Git

### 1. Clone & Configure Environment
```bash
git clone https://github.com/Sujal-Shreshya/Antygravity-AI-trading.git
cd Antygravity-AI-trading

# Create local environment file from safe template
cp .env.example .env
```

Ensure `LIVE_TRADING=false` remains configured in your local `.env`.

### 2. Run with Docker Compose
```bash
docker compose up -d postgres redis
```

### 3. Backend Setup
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
pnpm install
pnpm dev
```

---

## 🛡️ Risk Management & Safety Controls

The risk engine operates as an autonomous gate between signal generation and order execution. An order cannot be dispatched without passing all pre-trade validations:

1. **Maximum Risk Per Trade:** Caps capital loss per trade to 1% of account equity. Position sizing is calculated as:
   $$\text{Position Size} = \frac{\text{Account Equity} \times \text{Risk Fraction}}{\vert \text{Entry Price} - \text{Stop Loss Price} \vert}$$
2. **Maximum Daily Loss Limit:** If aggregate daily realized + unrealized drawdown exceeds 3%, trading halts for the day.
3. **Maximum Portfolio Drawdown:** Breaching 10% overall drawdown trips global risk circuit breaker.
4. **Maximum Open Positions:** Restricts concurrent position count (default: 10).
5. **Global Emergency Kill Switch:** Instant operator abort trigger that freezes signal execution and cancels all open working orders.

---

## 📈 Development Roadmap & Phases

- **Phase 0:** Workspace inspection, Git foundation, security setup, repository initialization (Current)
- **Phase 1:** Architectural specifications & project foundation
- **Phase 2:** Backend services & PostgreSQL/SQLAlchemy schemas
- **Phase 3:** Market data subsystem (WebSockets, REST, normalization)
- **Phase 4:** Technical indicators & plugin-based strategy framework
- **Phase 5:** Signal aggregation & regime evaluation
- **Phase 6:** Pre-trade risk management & circuit breakers
- **Phase 7:** Event-driven backtesting engine
- **Phase 8:** Paper trading engine with realistic fill simulation
- **Phase 9:** React dark-mode trading dashboard
- **Phase 10:** Broker abstraction & market adapters (NSE, Binance, OANDA)
- **Phase 11:** Multi-channel alerting & system observability
- **Phase 12:** End-to-end testing, safety validation & security audit
- **Phase 13:** Containerization, Docker Compose & production deployment
- **Phase 14:** Live trading integration (fail-closed, requires explicit operator authorization)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
