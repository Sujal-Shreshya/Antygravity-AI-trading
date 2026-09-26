import {
  BacktestResult,
  Candle,
  Instrument,
  Order,
  PortfolioBalance,
  Position,
  Quote,
  RiskEvent,
  RiskStatus,
} from "../types";

const API_BASE = "/api/v1";

class ApiService {
  private token: string | null = localStorage.getItem("jwt_token");

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem("jwt_token", token);
    } else {
      localStorage.removeItem("jwt_token");
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed with status ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string):Promise<{ access_token: string }> {
    const data = await this.request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(email: string, password: string): Promise<any> {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  // Portfolio
  async getPortfolioBalance(): Promise<PortfolioBalance> {
    return this.request<PortfolioBalance>("/portfolio/balance");
  }

  // Instruments
  async getInstruments(market?: string): Promise<Instrument[]> {
    const query = market ? `?market=${market}` : "";
    return this.request<Instrument[]>(`/instruments${query}`);
  }

  // Market Data
  async getQuote(symbol: string): Promise<Quote> {
    return this.request<Quote>(`/market-data/quote/${encodeURIComponent(symbol)}`);
  }

  async getCandles(symbol: string, timeframe: string = "15m", limit: number = 100): Promise<Candle[]> {
    return this.request<Candle[]>(
      `/market-data/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`
    );
  }

  // Orders
  async submitOrder(order: any): Promise<Order> {
    return this.request<Order>("/orders", {
      method: "POST",
      body: JSON.stringify(order),
    });
  }

  async getOrders(symbol?: string): Promise<Order[]> {
    const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
    return this.request<Order[]>(`/orders${query}`);
  }

  async cancelOrder(orderId: string): Promise<Order> {
    return this.request<Order>(`/orders/${orderId}`, {
      method: "DELETE",
    });
  }

  // Positions
  async getPositions(): Promise<Position[]> {
    return this.request<Position[]>("/positions");
  }

  // Risk & Kill Switch
  async getRiskStatus(): Promise<RiskStatus> {
    return this.request<RiskStatus>("/risk/status");
  }

  async activateKillSwitch(reason: string): Promise<any> {
    return this.request("/risk/kill-switch/activate", {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  }

  async deactivateKillSwitch(): Promise<any> {
    return this.request("/risk/kill-switch/deactivate", {
      method: "POST",
    });
  }

  async getRiskEvents(): Promise<RiskEvent[]> {
    return this.request<RiskEvent[]>("/risk/events");
  }

  async evaluateOrderRisk(order: any): Promise<any> {
    return this.request("/risk/evaluate", {
      method: "POST",
      body: JSON.stringify(order),
    });
  }

  // Strategies & Signals
  async getStrategies(): Promise<any[]> {
    return this.request<any[]>("/strategies");
  }

  async getConsensusSignal(symbol: string, timeframe: string): Promise<any> {
    return this.request(`/signals/consensus?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`);
  }

  async getMarketRegime(symbol: string, timeframe: string): Promise<any> {
    return this.request(`/signals/regime?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`);
  }

  // Backtesting
  async runBacktest(payload: any): Promise<BacktestResult> {
    return this.request<BacktestResult>("/backtest/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getBacktestResults(): Promise<any[]> {
    return this.request<any[]>("/backtest/results");
  }

  // Paper Trading
  async executePaperOrder(orderId: string, currentPrice: number): Promise<Order> {
    return this.request<Order>(`/paper/execute/${orderId}`, {
      method: "POST",
      body: JSON.stringify({ current_price: currentPrice }),
    });
  }

  async getPaperPortfolio(): Promise<any> {
    return this.request("/paper/portfolio");
  }

  async resetPaperAccount(): Promise<any> {
    return this.request("/paper/reset", {
      method: "POST",
    });
  }
}

export const api = new ApiService();
