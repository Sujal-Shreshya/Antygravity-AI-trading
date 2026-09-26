export type MarketType = "INDIAN_EQUITY" | "CRYPTO_SPOT" | "FOREX_SPOT";

export interface Instrument {
  symbol: string;
  name: string;
  market: MarketType;
  exchange: string;
  tick_size: number;
  lot_size: number;
  is_active: boolean;
}

export interface Quote {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  timestamp: string;
  provider: string;
}

export interface Candle {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type OrderSide = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT" | "STOP";
export type OrderStatus = "PENDING" | "SUBMITTED" | "FILLED" | "PARTIALLY_FILLED" | "CANCELLED" | "REJECTED";

export interface Order {
  order_id: string;
  client_order_id: string;
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price?: number;
  filled_quantity: number;
  average_price?: number;
  status: OrderStatus;
  is_paper: boolean;
  created_at: string;
  updated_at: string;
  broker_message?: string;
}

export interface Position {
  id: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  stop_loss?: number;
  take_profit?: number;
  is_paper: boolean;
  updated_at: string;
}

export interface PortfolioBalance {
  currency: string;
  cash: number;
  equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  available_margin: number;
  is_paper: boolean;
  timestamp: string;
}

export interface KillSwitchStatus {
  is_active: boolean;
  engaged_at: string | null;
  reason: string | null;
  operator_id: string | null;
}

export interface RiskStatus {
  kill_switch: KillSwitchStatus;
  live_trading_enabled: boolean;
  parameters: {
    max_risk_per_trade_pct: number;
    max_daily_loss_pct: number;
    max_portfolio_drawdown_pct: number;
    max_open_positions: number;
    max_single_position_pct: number;
    min_risk_reward_ratio: number;
  };
}

export interface RiskEvent {
  id: string;
  rule_name: string;
  action: string;
  reason: string;
  details: Record<string, any>;
  created_at: string;
}

export interface StrategySignal {
  symbol: string;
  direction: "BUY" | "SELL" | "HOLD";
  entry: number;
  stop_loss: number;
  take_profit: number;
  confidence: number;
  strategy: string;
  reasons: string[];
  timestamp: string;
  market_regime?: string;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_equity: number;
  total_net_pnl: number;
  total_return_pct: number;
  cagr_pct: number;
  annualized_volatility_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  max_drawdown_duration_bars: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  average_trade_pnl: number;
  average_win_pnl: number;
  average_loss_pnl: number;
  win_loss_ratio: number;
  expectancy: number;
  total_commission_paid: number;
  total_slippage_paid: number;
}

export interface BacktestResult {
  backtest_id: string;
  config: {
    strategy_name: string;
    symbol: string;
    timeframe: string;
    initial_capital: number;
  };
  metrics: BacktestMetrics;
  trades: Array<{
    trade_id: string;
    symbol: string;
    direction: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    net_pnl: number;
    return_pct: number;
    exit_reason: string;
  }>;
  equity_curve: Array<{
    timestamp: string;
    equity: number;
    cash: number;
    drawdown_pct: number;
  }>;
}
