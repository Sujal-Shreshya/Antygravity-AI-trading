# Architecture: Safety, Risk Controls & Emergency Protocol

## 1. Safety Invariants

The platform maintains the following immutable safety invariants:

1. **Default Fail-Closed State:**
   - `LIVE_TRADING=false` is enforced at configuration load, dependency injection, and order execution layers.
   - Any failure in configuration loading causes the system to halt immediately.
   - Presence of broker API keys does **not** activate live execution.

2. **Zero Naked Orders:**
   - Every entry order requires a corresponding Stop Loss price calculation before execution submission.
   - Risk/reward ratio must satisfy minimum thresholds (default: >= 1.5).

3. **Idempotent Order Handling:**
   - Every order submission requires a unique client order ID (`client_order_id`).
   - Duplicate submissions within a rolling 60-second window are rejected to prevent double fills.

---

## 2. Risk Evaluation Pipeline

```
[Signal Created]
       │
       ▼
[Pre-Trade Risk Checks]
   ├── Check 1: Kill switch state -> If active, REJECT
   ├── Check 2: Market status / trading hours -> If closed, REJECT
   ├── Check 3: Daily loss threshold (< 3%) -> If breached, REJECT
   ├── Check 4: Portfolio drawdown limit (< 10%) -> If breached, REJECT
   ├── Check 5: Max concurrent open positions (< 10) -> If exceeded, REJECT
   ├── Check 6: Single position exposure (< 15% equity) -> If exceeded, REJECT
   ├── Check 7: Position size calculation -> Derived from 1% risk & SL distance
   └── Check 8: Broker account margin verification -> If insufficient, REJECT
       │
       ▼
[Decision: APPROVED or REJECTED with Audit Log]
```

---

## 3. Emergency Kill Switch Architecture

The Emergency Kill Switch provides an instantaneous operator override:

- **State Persistence:** Kill switch state is recorded in both Redis (for sub-millisecond check latency) and PostgreSQL (for audit durability).
- **Execution Effect:**
  1. Immediately halts acceptance of all new incoming orders.
  2. Dispatches cancellation commands for all open, unfilled limit/stop orders.
  3. Emits high-priority alerts across all configured channels (Telegram, SMTP, Web UI).
  4. Requires explicit authenticated admin credentials to disengage.
