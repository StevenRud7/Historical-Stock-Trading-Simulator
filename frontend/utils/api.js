// utils/api.js — All backend fetch calls

const API_BASE = (window.location.protocol === 'file:')
  ? 'http://localhost:8000'
  : window.location.origin;

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(API_BASE + path, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error('Cannot connect to server. Make sure the backend is running on port 8000.');
    }
    throw err;
  }
}

const API = {
  async newGame(config)           { return apiFetch('/api/game/new', { method: 'POST', body: JSON.stringify(config) }); },
  async getGame(gameId)           { return apiFetch(`/api/game/${gameId}`); },
  async advanceDay(gameId)        { return apiFetch(`/api/game/${gameId}/advance`, { method: 'POST' }); },
  async quitGame(gameId)          { return apiFetch(`/api/game/${gameId}/quit`,    { method: 'POST' }); },
  async getGameSummary(gameId)    { return apiFetch(`/api/game/${gameId}/summary`); },

  async getChart(gameId, ticker)  { return apiFetch(`/api/market/chart?game_id=${gameId}&ticker=${encodeURIComponent(ticker)}`); },
  async getPrice(gameId, ticker)  { return apiFetch(`/api/market/price?game_id=${gameId}&ticker=${encodeURIComponent(ticker)}`); },
  async searchTickers(q)          { return apiFetch(`/api/market/search?q=${encodeURIComponent(q)}`); },
  async prefetchTicker(gameId, ticker) {
    return apiFetch(`/api/market/prefetch?game_id=${gameId}&ticker=${encodeURIComponent(ticker)}`, { method: 'POST' });
  },
  async validateTicker(ticker)    { return apiFetch(`/api/market/validate?ticker=${encodeURIComponent(ticker)}`); },

  async executeTrade(gameId, ticker, action, quantity) {
    return apiFetch('/api/portfolio/trade', {
      method: 'POST',
      body: JSON.stringify({ game_id: gameId, ticker, action, quantity }),
    });
  },
  async getPortfolio(gameId)      { return apiFetch(`/api/portfolio/${gameId}`); },
  async getTradeHistory(gameId)   { return apiFetch(`/api/portfolio/${gameId}/history`); },

  async fastForward(gameId, days) {
    return apiFetch('/api/simulation/fastforward', {
      method: 'POST', body: JSON.stringify({ game_id: gameId, days }),
    });
  },
  async getSummaryCharts(gameId)         { return apiFetch(`/api/market/summary-charts?game_id=${gameId}`); },
};