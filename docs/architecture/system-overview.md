# Architecture: System Overview

## 1. High-Level Principles

The **AI Trading Engine** is designed as a modular, event-driven trading platform with clear separation of concerns, strict boundary interfaces, and defense-in-depth safety controls.

```
Market Data -> Strategies -> Signals -> Risk Engine -> Execution Coordinator -> Broker/Paper
      │                                       │
      ▼                                       ▼
Postgres / Redis (Normalized State)      Audit Logs & Telemetry
```

### Core Tenets
1. **Paper-First Execution:** Live trading is technically impossible by default (`LIVE_TRADING=false`).
2. **Provider Agnostic:** Strategies and Risk engines have zero knowledge of underlying broker implementations.
3. **Data Integrity:** No synthetic or hallucinated prices. Missing data yields explicit gaps or errors.
4. **Synchronous Pre-Trade Risk Gate:** Every order intent must pass atomic risk evaluation before execution.

---

## 2. Core Subsystems

### 2.1 Market Data Engine (`backend/data/`)
- Ingests real-time ticks/bars via WebSockets and REST pollers.
- Normalizes disparate broker schemas into a unified internal OHLCV candle model.
- Dispatches data events to strategy workers and updates Redis caching layer.

### 2.2 Strategy Engine (`backend/strategies/` & `backend/indicators/`)
- Implements a uniform `BaseStrategy` abstract interface.
- Calculates technical indicators (EMA, SMA, RSI, MACD, Bollinger Bands, ATR, VWAP).
- Emits structured, immutable `StrategySignal` objects.

### 2.3 Signal Engine (`backend/signals/`)
- Aggregates multi-strategy outputs across symbols and timeframes.
- Applies optional ML-based regime classification and signal confidence ranking.
- Distinguishes raw signals from executable trade proposals.

### 2.4 Risk Management Engine (`backend/risk/`)
- Acts as a mandatory firewall before the execution coordinator.
- Evaluates per-trade risk (1%), daily drawdown limits (3%), total drawdown limits (10%), and max positions.
- Computes volatility-adjusted position sizing using ATR.
- Enforces an emergency kill switch.

### 2.5 Execution Coordinator (`backend/execution/`)
- Determines execution target based on runtime flags.
- When `LIVE_TRADING=false`, forwards orders to `backend/paper_trading/`.
- When `LIVE_TRADING=true` (Phase 14), routes through authenticated broker adapters with idempotency keys.

### 2.6 Persistence Layer (`backend/database/`)
- PostgreSQL is the permanent system of record for accounts, orders, fills, positions, and audits.
- Redis manages fast sub-millisecond cache state, rate limiting, and pub/sub streams.

---

## 3. Supported Markets

- **Indian Equities & Derivatives (NSE / BSE):** Cash equities, NIFTY 50, BANK NIFTY, stock futures and options.
- **Cryptocurrency:** Major spot and perpetual futures pairs (BTC/USDT, ETH/USDT) via Binance-compatible APIs.
- **Forex:** Major currency pairs (EUR/USD, GBP/USD, USD/JPY, USD/CAD, AUD/USD, USD/CHF).
