// components/trading.js — Trade form logic

const Trading = (() => {
  let gameId = null;
  let currentAction = 'BUY';
  let currentPrice = 0;
  let cashBalance = 0;
  let positions = [];
  let priceDebounceTimer = null;
  let pendingTrade = null;

  // ── CRITICAL: only bind DOM listeners once per page load ──────
  let _bound = false;

  const ACTION_HINTS = {
    BUY:   '📈 Buy shares — profit when price rises above your cost.',
    SELL:  '💵 Sell your long shares — profit is realized immediately.',
    SHORT: '📉 Bet the stock falls — requires collateral equal to position value.',
    COVER: '🔒 Close your short — profit if price fell, loss if it rose.',
  };

  const ACTION_BUTTON_CLASSES = {
    BUY: '', SELL: 'sell-mode', SHORT: 'short-mode', COVER: 'cover-mode',
  };

  const ACTION_LABELS = {
    BUY: 'Buy', SELL: 'Sell', SHORT: 'Short', COVER: 'Cover',
  };

  function init(gId) {
    // Always update the game ID (changes each new game)
    gameId = gId;
    // Only wire DOM listeners once — prevents stacking on Play Again
    if (!_bound) {
      bindEvents();
      _bound = true;
    }
  }

  function bindEvents() {
    // Action tabs
    document.querySelectorAll('.action-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.action-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentAction = tab.dataset.action;
        document.getElementById('actionHint').textContent = ACTION_HINTS[currentAction];
        const btn = document.getElementById('btnExecuteTrade');
        btn.className = `btn-execute-trade ${ACTION_BUTTON_CLASSES[currentAction]}`;
        btn.textContent = `${ACTION_LABELS[currentAction]} Shares`;
        updateCostPreview();
        updateMaxButton();
      });
    });

    // Qty +/- stepper buttons
    document.querySelectorAll('.qty-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const delta  = parseInt(btn.dataset.delta);
        const input  = document.getElementById('tradeQty');
        const newVal = Math.max(0.01, (parseFloat(input.value) || 1) + delta);
        input.value  = parseFloat(newVal.toFixed(2));
        updateCostPreview();
      });
    });

    // Qty input change
    document.getElementById('tradeQty').addEventListener('input', updateCostPreview);

    // Max / All button
    document.getElementById('btnMaxShares').addEventListener('click', setMaxShares);

    // Ticker input with debounce + suggestions
    const tradeTickerInput = document.getElementById('tradeTicker');
    tradeTickerInput.addEventListener('input', async () => {
      clearTimeout(priceDebounceTimer);
      const q = tradeTickerInput.value.trim().toUpperCase();
      currentPrice = 0;
      document.getElementById('tradePrice').textContent = '—';
      updateCostPreview();
      if (q.length >= 1) {
        await showTickerSuggestions(q, 'tradeTickerSuggestions', (sym) => {
          tradeTickerInput.value = sym;
          fetchCurrentPrice(sym);
        });
        priceDebounceTimer = setTimeout(() => fetchCurrentPrice(q), 500);
      }
    });

    tradeTickerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(priceDebounceTimer);
        fetchCurrentPrice(tradeTickerInput.value.trim().toUpperCase());
      }
    });

    // Execute button — show confirm for large trades
    document.getElementById('btnExecuteTrade').addEventListener('click', () => {
      const ticker = document.getElementById('tradeTicker').value.trim().toUpperCase();
      const qty    = parseFloat(document.getElementById('tradeQty').value);
      if (!ticker)           { setFeedback('Enter a ticker symbol.', 'error'); return; }
      if (!qty || qty <= 0)  { setFeedback('Enter a valid quantity.', 'error'); return; }
      if (!currentPrice)     { setFeedback('Price not loaded yet. Try again.', 'error'); return; }

      const totalCost = qty * currentPrice;
      if (totalCost > 10000 || (cashBalance > 0 && totalCost / cashBalance > 0.30)) {
        showConfirmDialog(ticker, currentAction, qty, currentPrice, totalCost);
      } else {
        executeTrade(ticker, currentAction, qty);
      }
    });

    // Confirm modal buttons
    document.getElementById('btnConfirmTrade').addEventListener('click', () => {
      closeConfirmDialog();
      if (pendingTrade) {
        const { ticker, action, qty } = pendingTrade;
        pendingTrade = null;
        executeTrade(ticker, action, qty);
      }
    });

    document.getElementById('btnCancelTrade').addEventListener('click', () => {
      closeConfirmDialog();
      pendingTrade = null;
    });

    document.getElementById('confirmModal').addEventListener('click', (e) => {
      if (e.target === document.getElementById('confirmModal')) {
        closeConfirmDialog();
        pendingTrade = null;
      }
    });
  }

  async function fetchCurrentPrice(ticker) {
    if (!ticker || !gameId) return;
    ticker = ticker.toUpperCase().trim();
    try {
      const data = await API.getPrice(gameId, ticker);
      currentPrice = data.price;
      document.getElementById('tradePrice').textContent = fmt.currency(data.price, 2);
      updateCostPreview();
      updateMaxButton();
    } catch (_) {
      document.getElementById('tradePrice').textContent = '—';
      currentPrice = 0;
      updateCostPreview();
    }
  }

  function updateCostPreview() {
    const qty  = parseFloat(document.getElementById('tradeQty').value) || 0;
    const cost = qty * currentPrice;
    document.getElementById('tradeCost').textContent = currentPrice ? fmt.currency(cost) : '—';

    const cashAfterEl = document.getElementById('tradeCashAfter');
    if (currentAction === 'BUY' || currentAction === 'SHORT') {
      const after = cashBalance - cost;
      cashAfterEl.textContent = currentPrice ? fmt.currency(after) : '—';
      cashAfterEl.className   = after < 0 ? 'negative' : '';
    } else {
      const after = cashBalance + cost;
      cashAfterEl.textContent = currentPrice ? fmt.currency(after) : '—';
      cashAfterEl.className   = 'positive';
    }
  }

  function setMaxShares() {
    if (!currentPrice || currentPrice <= 0) {
      setFeedback('Load a ticker price first.', 'error');
      return;
    }
    const ticker = document.getElementById('tradeTicker').value.trim().toUpperCase();
    let maxQty = 0;

    if (currentAction === 'BUY' || currentAction === 'SHORT') {
      const raw = cashBalance / currentPrice;
      maxQty = Math.floor(raw * 100) / 100;
    } else if (currentAction === 'SELL') {
      const pos = positions.find(p => p.ticker === ticker && p.position_type === 'LONG');
      maxQty = pos ? (Math.floor(pos.quantity * 100) / 100) : 0;
    } else if (currentAction === 'COVER') {
      const pos = positions.find(p => p.ticker === ticker && p.position_type === 'SHORT');
      maxQty = pos ? (Math.floor(pos.quantity * 100) / 100) : 0;
    }

    if (maxQty > 0) {
      document.getElementById('tradeQty').value = maxQty;
      updateCostPreview();
    } else {
      setFeedback(
        currentAction === 'SELL'  ? 'No long position in this ticker.' :
        currentAction === 'COVER' ? 'No short position in this ticker.' :
        'Insufficient cash for even 0.01 shares.', 'error'
      );
    }
  }

  function updateMaxButton() {
    const btn = document.getElementById('btnMaxShares');
    if (!btn) return;
    if (currentAction === 'SELL' || currentAction === 'COVER') {
      btn.textContent = 'All';
      btn.title = 'Set quantity to close full position';
    } else {
      btn.textContent = 'Max';
      btn.title = 'Set maximum affordable quantity';
    }
  }

  async function executeTrade(ticker, action, qty) {
    const btn = document.getElementById('btnExecuteTrade');
    btn.disabled = true;
    btn.textContent = 'Executing…';
    setFeedback('', '');

    try {
      const result = await API.executeTrade(gameId, ticker, action, qty);
      cashBalance = result.new_cash_balance;

      let msg = `${action} ${fmt.shares(qty)} ${ticker} @ ${fmt.currency(result.price)}`;
      if (result.realized_pnl && result.realized_pnl !== 0) {
        const sign = result.realized_pnl >= 0 ? '+' : '';
        msg += ` · P&L: ${sign}${fmt.currency(result.realized_pnl)}`;
      }
      setFeedback(msg, 'success');
      showToast(msg, result.realized_pnl >= 0 ? 'success' : 'error', 3500);

      if (window.AppState?.refresh) await window.AppState.refresh();
      Chart.addToWatchlist(ticker);

      document.getElementById('tradeQty').value = 1;
      updateCostPreview();

    } catch (err) {
      setFeedback(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = `${ACTION_LABELS[action]} Shares`;
    }
  }

  function showConfirmDialog(ticker, action, qty, price, total) {
    pendingTrade = { ticker, action, qty };
    document.getElementById('confirmTradeDetails').innerHTML = `
      <div class="confirm-row">
        <span>Action</span>
        <span class="ti-action ${action}">${action}</span>
      </div>
      <div class="confirm-row">
        <span>Ticker</span>
        <span style="color:var(--primary);font-weight:700;font-family:var(--font-mono)">${ticker}</span>
      </div>
      <div class="confirm-row">
        <span>Shares</span>
        <span style="font-family:var(--font-mono)">${fmt.shares(qty)}</span>
      </div>
      <div class="confirm-row">
        <span>Price</span>
        <span style="font-family:var(--font-mono)">${fmt.currency(price, 2)}</span>
      </div>
      <div class="confirm-row confirm-total">
        <span>Total</span>
        <span style="font-family:var(--font-mono);font-size:16px;font-weight:700">${fmt.currency(total)}</span>
      </div>`;
    document.getElementById('confirmModal').classList.add('visible');
  }

  function closeConfirmDialog() {
    document.getElementById('confirmModal').classList.remove('visible');
  }

  function setFeedback(msg, type) {
    const el = document.getElementById('tradeFeedback');
    el.textContent = msg;
    el.className = `trade-feedback ${type}`;
    if (type === 'success') setTimeout(() => { if (el.textContent === msg) el.textContent = ''; }, 5000);
  }

  // ── Public API ─────────────────────────────────────────────────
  function updateDate(dateStr) {
    const el = document.getElementById('tradeDateBadge');
    if (el) el.textContent = fmt.date(dateStr);
  }

  function updateCash(cash) {
    cashBalance = cash;
    updateCostPreview();
  }

  function updatePositions(pos) {
    positions = pos || [];
  }

  function setTickerFromPosition(ticker) {
    document.getElementById('tradeTicker').value = ticker;
    fetchCurrentPrice(ticker);
  }

  return { init, updateDate, updateCash, updatePositions, setTickerFromPosition, fetchCurrentPrice };
})();