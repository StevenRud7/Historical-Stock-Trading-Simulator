// app.js — Main application controller

// ── Global state ─────────────────────────────────────────────────
window.AppState = {
  gameId:          null,
  currentDate:     null,
  status:          'idle',
  initialBalance:  10000,
  daysRemaining:   0,
  lastConfig:      null,
};

// Prevent duplicate listener attachment (persists across game sessions on same page load)
let _gameListenersOnce = false;
// Prevent initSetupScreen from re-running setup-only init
let _setupInitOnce = false;
// Prevent handleGameEnd from firing twice simultaneously
let _gameEndInProgress = false;

// ── Toast ─────────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 3000) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast visible ${type}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('visible'), duration);
}

// ── Ticker suggestions ────────────────────────────────────────────
async function showTickerSuggestions(q, containerId, onSelect) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!q) { container.classList.remove('visible'); return; }
  try {
    const data = await API.searchTickers(q);
    if (!data.results.length) { container.classList.remove('visible'); return; }
    container.innerHTML = data.results.map(r => `
      <div class="suggestion-item" data-sym="${r.symbol}">
        <span class="sug-symbol">${r.symbol}</span>
        <span class="sug-name">${r.name}</span>
      </div>`).join('');
    container.querySelectorAll('.suggestion-item').forEach(item => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault(); onSelect(item.dataset.sym);
        container.classList.remove('visible');
      });
    });
    container.classList.add('visible');
  } catch (_) { container.classList.remove('visible'); }
  document.addEventListener('click', (e) => {
    if (!container.contains(e.target)) container.classList.remove('visible');
  }, { once: true });
}

// ── Screen management ─────────────────────────────────────────────
function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(`screen-${name}`).classList.add('active');
}

// ── Refresh game state ────────────────────────────────────────────
AppState.refresh = async function () {
  if (!this.gameId) return;
  try {
    const [gameState, portfolio, history] = await Promise.all([
      API.getGame(this.gameId),
      API.getPortfolio(this.gameId),
      API.getTradeHistory(this.gameId),
    ]);
    this.currentDate   = gameState.current_date;
    this.status        = gameState.status;
    this.daysRemaining = gameState.days_remaining;
    gameState.total_realized_pnl = portfolio.total_realized_pnl;

    Portfolio.render(gameState);
    Portfolio.renderTradeHistory(history);
    Trading.updateDate(gameState.current_date);
    Trading.updateCash(gameState.cash_balance);
    Trading.updatePositions(gameState.positions);
    updateTopBar(gameState);
    await Chart.refreshAllWatchlist();
    // Note: do NOT call handleGameEnd from refresh — advanceDay handles that explicitly
  } catch (err) { console.error('Refresh error:', err); }
};

AppState.triggerGameOver = function () { handleGameEnd('game_over'); };

// ── Top bar update ────────────────────────────────────────────────
function updateTopBar(state) {
  const dateEl  = document.getElementById('currentDateDisplay');
  const newDate = fmt.date(state.current_date);
  if (dateEl.textContent !== newDate) {
    dateEl.textContent = newDate;
    dateEl.classList.remove('date-animate');
    void dateEl.offsetWidth;
    dateEl.classList.add('date-animate');
  }
  document.getElementById('dayCounterText').textContent =
    `Day ${state.current_day_index + 1} of ${state.total_trading_days}`;
  const pct = (state.current_day_index + 1) / state.total_trading_days * 100;
  document.getElementById('dayProgressFill').style.width = `${Math.min(100, pct).toFixed(1)}%`;

  const nextBtn = document.getElementById('btnNextDay');
  if (state.days_remaining <= 0 || state.status !== 'active') {
    nextBtn.disabled = true;
    nextBtn.textContent = state.status === 'completed' ? '✓ Complete' : '✗ Game Over';
  } else {
    nextBtn.disabled = false;
    nextBtn.textContent = `Next Day → (${state.days_remaining} left)`;
  }
}

// ── Summary modal ─────────────────────────────────────────────────
function initSummaryModal() {
  const modal = document.getElementById('summaryModal');
  document.getElementById('summaryModalClose').addEventListener('click', () => modal.classList.remove('visible'));
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('visible'); });
  document.getElementById('btnViewSummary').addEventListener('click', async () => {
    if (!AppState.gameId) return;
    try {
      const [game, portfolio] = await Promise.all([API.getGame(AppState.gameId), API.getPortfolio(AppState.gameId)]);
      const pnl = game.total_portfolio_value - game.initial_balance;
      document.getElementById('summaryModalContent').innerHTML = `
        <div class="sm-grid">
          <div class="sm-card"><div class="sm-label">Portfolio Value</div><div class="sm-value">${fmt.currency(game.total_portfolio_value)}</div></div>
          <div class="sm-card"><div class="sm-label">Cash Available</div><div class="sm-value">${fmt.currency(portfolio.cash_balance)}</div></div>
          <div class="sm-card"><div class="sm-label">Total P&L</div><div class="sm-value ${fmt.colorClass(pnl)}">${fmt.pnl(pnl).text}</div></div>
          <div class="sm-card"><div class="sm-label">Total Return</div><div class="sm-value ${fmt.colorClass(game.total_return_pct)}">${fmt.pct(game.total_return_pct)}</div></div>
          <div class="sm-card"><div class="sm-label">Unrealized P&L</div><div class="sm-value ${fmt.colorClass(portfolio.total_unrealized_pnl)}">${fmt.pnl(portfolio.total_unrealized_pnl).text}</div></div>
          <div class="sm-card"><div class="sm-label">Realized P&L</div><div class="sm-value ${fmt.colorClass(portfolio.total_realized_pnl)}">${fmt.pnl(portfolio.total_realized_pnl).text}</div></div>
        </div>
        <div class="sm-info">
          <span>📅 Current date: <strong>${fmt.date(game.current_date)}</strong></span>
          <span>⏳ Days remaining: <strong>${game.days_remaining}</strong></span>
          <span>📦 Open positions: <strong>${game.positions.length}</strong></span>
        </div>`;
      modal.classList.add('visible');
    } catch (err) { showToast('Could not load summary: ' + err.message, 'error'); }
  });
}

// ── Quit modal ────────────────────────────────────────────────────
function initQuitModal() {
  const modal = document.getElementById('quitModal');
  document.getElementById('btnQuitGame').addEventListener('click', () => modal.classList.add('visible'));
  document.getElementById('quitModalClose').addEventListener('click', () => modal.classList.remove('visible'));
  document.getElementById('btnQuitCancel').addEventListener('click', () => modal.classList.remove('visible'));
  document.getElementById('btnQuitConfirm').addEventListener('click', handleQuitGame);
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('visible'); });
}

async function handleQuitGame() {
  document.getElementById('quitModal').classList.remove('visible');
  const btn = document.getElementById('btnNextDay');
  if (btn) btn.disabled = true;
  try {
    const summary = await API.quitGame(AppState.gameId);
    AppState.status = 'quit_early';
    renderSummaryScreen(summary, 'quit_early');
  } catch (err) { showToast('Could not quit: ' + err.message, 'error'); if (btn) btn.disabled = false; }
}

// ── Game end — single entry point, guards against double-fire ────
let _handleGameEndCalled = false;

async function handleGameEnd(status) {
  if (status === 'active') return;
  if (_handleGameEndCalled) return;  // already handling
  _handleGameEndCalled = true;

  const btn = document.getElementById('btnNextDay');
  if (btn) btn.disabled = true;
  try {
    const summary = await API.getGameSummary(AppState.gameId);
    renderSummaryScreen(summary, status);
  } catch (err) {
    console.error('Failed to load end summary:', err);
    _handleGameEndCalled = false; // allow retry
  }
}

function resetGameEndFlag() {
  _handleGameEndCalled = false;
}

// ── Summary screen ────────────────────────────────────────────────
function renderSummaryScreen(s, status) {
  const isGameOver = status === 'game_over';
  const isQuit     = status === 'quit_early';
  document.getElementById('gameoverHeader').querySelector('.gameover-icon').textContent =
    isGameOver ? '💀' : isQuit ? '🚪' : '🏆';
  document.getElementById('gameoverTitle').textContent =
    isGameOver ? 'Game Over' : isQuit ? 'Ended Early' : 'Simulation Complete!';
  document.getElementById('gameoverSubtitle').textContent = isGameOver
    ? "Your portfolio was wiped out. Here's the post-mortem."
    : isQuit ? `You quit on ${fmt.date(AppState.currentDate)}.`
    : `You traded from ${fmt.date(s.start_date)} to ${fmt.date(s.end_date)}`;

  const returnCls = fmt.colorClass(s.total_return);

  // ── Stats grid ─────────────────────────────────────────────────
  document.getElementById('summaryGrid').innerHTML = `
    <div class="sg-card grade-card">
      <div class="sg-label">Performance Grade</div>
      <div class="sg-value grade-${s.performance_grade}">${s.performance_grade}</div>
      <div class="sg-sub">${gradeLabel(s.performance_grade)}</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Final Portfolio Value</div>
      <div class="sg-value">${fmt.currency(s.final_value)}</div>
      <div class="sg-sub">Started with ${fmt.currency(s.initial_balance)}</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Total Return</div>
      <div class="sg-value ${returnCls}">${fmt.pct(s.total_return_pct)}</div>
      <div class="sg-sub ${returnCls}">${fmt.pnl(s.total_return).text}</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Cash at End</div>
      <div class="sg-value">${fmt.currency(s.cash_balance)}</div>
      <div class="sg-sub">liquid</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Positions Value</div>
      <div class="sg-value">${fmt.currency(s.open_positions_value)}</div>
      <div class="sg-sub">at market close price</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Unrealized P&L</div>
      <div class="sg-value ${fmt.colorClass(s.total_unrealized_pnl)}">${fmt.pnl(s.total_unrealized_pnl).text}</div>
      <div class="sg-sub">from open positions</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Realized P&L</div>
      <div class="sg-value ${fmt.colorClass(s.total_realized_pnl)}">${fmt.pnl(s.total_realized_pnl).text}</div>
      <div class="sg-sub">from closed trades</div>
    </div>
    <div class="sg-card">
      <div class="sg-label">Win Rate</div>
      <div class="sg-value">${s.win_rate.toFixed(0)}%</div>
      <div class="sg-sub">${s.winning_trades}W · ${s.losing_trades}L</div>
    </div>
    ${s.best_trade ? `
    <div class="sg-card">
      <div class="sg-label">🏅 Best Trade</div>
      <div class="sg-value positive">${fmt.currency(s.best_trade.pnl)}</div>
      <div class="sg-sub">${s.best_trade.ticker} · ${fmt.dateShort(s.best_trade.date)}</div>
    </div>` : ''}
    ${s.worst_trade ? `
    <div class="sg-card">
      <div class="sg-label">💔 Worst Trade</div>
      <div class="sg-value negative">${fmt.currency(s.worst_trade.pnl)}</div>
      <div class="sg-sub">${s.worst_trade.ticker} · ${fmt.dateShort(s.worst_trade.date)}</div>
    </div>` : ''}
    ${s.most_traded_ticker ? `
    <div class="sg-card">
      <div class="sg-label">🔁 Most Traded</div>
      <div class="sg-value" style="color:var(--primary)">${s.most_traded_ticker}</div>
      <div class="sg-sub">favorite ticker</div>
    </div>` : ''}`;

  // ── Open positions at end ────────────────────────────────────────
  const openPosEl = document.getElementById('summaryOpenPositions');
  if (s.open_positions && s.open_positions.length > 0) {
    openPosEl.innerHTML = `
      <h3>Open Positions at End <span class="summary-note">(included in final value at market close price)</span></h3>
      <div class="summary-table-wrap">
        <table class="summary-table">
          <thead><tr><th>Ticker</th><th>Type</th><th>Shares</th><th>Avg Cost</th><th>Final Price</th><th>Market Value</th><th>Unrealized P&L</th></tr></thead>
          <tbody>${s.open_positions.map(p => {
            const { text: pnlText, cls: pnlCls } = fmt.pnl(p.unrealized_pnl);
            return `<tr>
              <td style="color:var(--primary);font-weight:700">${p.ticker}</td>
              <td><span class="ti-action ${p.position_type === 'LONG' ? 'BUY' : 'SHORT'}">${p.position_type}</span></td>
              <td>${fmt.shares(p.quantity)}</td>
              <td>${fmt.currency(p.avg_cost, 2)}</td>
              <td>${fmt.currency(p.current_price, 2)}</td>
              <td>${fmt.currency(p.current_value)}</td>
              <td class="${pnlCls}">${pnlText} (${fmt.pct(p.unrealized_pnl_pct)})</td>
            </tr>`;
          }).join('')}</tbody>
        </table>
      </div>`;
  } else { openPosEl.innerHTML = ''; }

  // ── Highlight trades ─────────────────────────────────────────────
  const htEl = document.getElementById('highlightTrades');
  if (s.best_trade || s.worst_trade) {
    htEl.innerHTML = `<div class="highlight-trades-inner">
      ${s.best_trade ? `<div class="ht-card positive-card">
        <div class="ht-label">🏅 Best Trade</div>
        <div class="ht-ticker">${s.best_trade.ticker}</div>
        <div class="ht-pnl positive">+${fmt.currency(s.best_trade.pnl)}</div>
        <div class="ht-detail">${s.best_trade.action} ${fmt.shares(s.best_trade.quantity)} shares on ${fmt.dateShort(s.best_trade.date)}</div>
      </div>` : ''}
      ${s.worst_trade ? `<div class="ht-card negative-card">
        <div class="ht-label">💔 Worst Trade</div>
        <div class="ht-ticker">${s.worst_trade.ticker}</div>
        <div class="ht-pnl negative">${fmt.currency(s.worst_trade.pnl)}</div>
        <div class="ht-detail">${s.worst_trade.action} ${fmt.shares(s.worst_trade.quantity)} shares on ${fmt.dateShort(s.worst_trade.date)}</div>
      </div>` : ''}
    </div>`;
  } else { htEl.innerHTML = ''; }

  // ── Trade history ────────────────────────────────────────────────
  const tbody = document.getElementById('summaryTableBody');
  if (!s.trade_history.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">No trades placed.</td></tr>';
  } else {
    tbody.innerHTML = s.trade_history.map(t => {
      const showPnl = (t.action === 'SELL' || t.action === 'COVER') && t.realized_pnl !== 0;
      const { text: pnlText, cls: pnlCls } = showPnl ? fmt.pnl(t.realized_pnl) : { text: '—', cls: 'neutral' };
      return `<tr>
        <td>${fmt.dateShort(t.trade_date)}</td>
        <td style="color:var(--primary);font-weight:700">${t.ticker}</td>
        <td><span class="ti-action ${t.action}">${t.action}</span></td>
        <td>${fmt.shares(t.quantity)}</td>
        <td>${fmt.currency(t.price, 2)}</td>
        <td>${fmt.currency(t.total_value)}</td>
        <td class="${pnlCls}">${pnlText}</td>
      </tr>`;
    }).join('');
  }

  // Reset play-again button state before showing screen
  const playBtn = document.getElementById('btnPlayAgain');
  playBtn.disabled = false;
  playBtn.textContent = '↩ Play Again';

  showScreen('gameover');

  // Scroll to top of gameover screen
  document.getElementById('screen-gameover').scrollTop = 0;

  // Load summary charts asynchronously (don't block screen render)
  if (AppState.gameId) {
    SummaryChart.destroy();
    SummaryChart.load(AppState.gameId);
  }
}

function gradeLabel(g) {
  return { S: 'Legendary', A: 'Excellent', B: 'Good', C: 'Average', D: 'Poor', F: 'Disastrous' }[g] || '';
}

// ═════════════════════════════════════════════════════════════════
// SETUP SCREEN
// ═════════════════════════════════════════════════════════════════
function initSetupScreen() {
  // Ticker tape — build only once
  if (!_setupInitOnce) {
    const tape = ['AAPL +2.3%','TSLA -1.8%','NVDA +4.1%','MSFT +0.7%','AMZN +1.2%',
      'META +3.4%','GOOGL -0.5%','SPY +1.0%','QQQ +1.5%','NFLX +2.7%',
      'AMD +5.2%','PLTR -3.1%','COIN +8.4%','BA -1.2%','JPM +0.9%'].join('   ·   ');
    const inner = document.createElement('div');
    inner.className = 'ticker-tape-inner';
    inner.textContent = tape + '   ·   ' + tape;
    const el = document.getElementById('tickerTape');
    if (el && !el.querySelector('.ticker-tape-inner')) el.appendChild(inner);

    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('startDate').value = btn.dataset.start;
        document.getElementById('endDate').value   = btn.dataset.end;
        document.getElementById('setupError').textContent = '';
      });
    });

    document.querySelectorAll('.balance-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.balance-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('initialBalance').value = btn.dataset.amount;
      });
    });

    document.getElementById('initialBalance').addEventListener('input', () => {
      document.querySelectorAll('.balance-btn').forEach(b => b.classList.remove('active'));
    });

    document.querySelectorAll('.pop-ticker').forEach(btn => {
      btn.addEventListener('click', () => { document.getElementById('startTicker').value = btn.dataset.t; });
    });

    document.getElementById('startTicker').addEventListener('input', async () => {
      await showTickerSuggestions(document.getElementById('startTicker').value.trim(), 'setupTickerSuggestions',
        (sym) => { document.getElementById('startTicker').value = sym; });
    });

    document.getElementById('endDate').addEventListener('change', validateDates);
    document.getElementById('startDate').addEventListener('change', validateDates);
    document.getElementById('btnStart').addEventListener('click', startGame);

    _setupInitOnce = true;
  }

  resetStartButton();
}

function resetStartButton() {
  const btn = document.getElementById('btnStart');
  btn.classList.remove('loading');
  btn.disabled = false;
  document.getElementById('setupError').textContent = '';
}

function validateDates() {
  const start = new Date(document.getElementById('startDate').value);
  const end   = new Date(document.getElementById('endDate').value);
  if ((end - start) / 86400000 < 7) {
    document.getElementById('setupError').textContent = '⚠ End date must be at least 1 week after start.';
    return false;
  }
  if (end > new Date()) {
    document.getElementById('setupError').textContent = '⚠ End date cannot be in the future.';
    return false;
  }
  document.getElementById('setupError').textContent = '';
  return true;
}

async function startGame() {
  if (!validateDates()) return;
  const startDate = document.getElementById('startDate').value;
  const endDate   = document.getElementById('endDate').value;
  const balance   = parseFloat(document.getElementById('initialBalance').value);
  const ticker    = (document.getElementById('startTicker').value || 'AAPL').trim().toUpperCase();
  if (!startDate || !endDate) { document.getElementById('setupError').textContent = 'Select a date range.'; return; }
  if (isNaN(balance) || balance < 1000) { document.getElementById('setupError').textContent = 'Min $1,000.'; return; }

  const btn = document.getElementById('btnStart');
  btn.classList.add('loading'); btn.disabled = true;
  document.getElementById('setupError').textContent = '';

  try {
    const game = await API.newGame({ start_date: startDate, end_date: endDate, initial_balance: balance, starting_tickers: [ticker] });
    AppState.lastConfig    = { startDate, endDate, balance, ticker };
    AppState.gameId        = game.game_id;
    AppState.currentDate   = game.current_date;
    AppState.daysRemaining = game.days_remaining;
    AppState.initialBalance = balance;
    AppState.status        = 'active';
    resetGameEndFlag();
    showScreen('game');
    await initGameScreen(game, ticker);
  } catch (err) {
    document.getElementById('setupError').textContent = '✗ ' + err.message;
    btn.classList.remove('loading'); btn.disabled = false;
  }
}

// ── Play Again with same settings ────────────────────────────────
async function playAgainSameConfig() {
  const cfg = AppState.lastConfig;
  if (!cfg) { location.reload(); return; }

  const btn = document.getElementById('btnPlayAgain');
  btn.disabled = true;
  btn.textContent = 'Starting…';

  try {
    const game = await API.newGame({ start_date: cfg.startDate, end_date: cfg.endDate, initial_balance: cfg.balance, starting_tickers: [cfg.ticker] });
    AppState.gameId        = game.game_id;
    AppState.currentDate   = game.current_date;
    AppState.daysRemaining = game.days_remaining;
    AppState.initialBalance = cfg.balance;
    AppState.status        = 'active';
    resetGameEndFlag();
    // Reset listeners flag so game screen re-inits cleanly
    _gameListenersOnce = false;
    showScreen('game');
    await initGameScreen(game, cfg.ticker);
  } catch (err) {
    showToast('Could not restart: ' + err.message, 'error');
    btn.disabled = false;
    btn.textContent = '↩ Play Again';
  }
}

// ── Game screen init ──────────────────────────────────────────────
async function initGameScreen(gameState, ticker) {
  Trading.init(AppState.gameId);
  FastForward.init();

  if (!_gameListenersOnce) {
    initSummaryModal();
    initQuitModal();

    document.getElementById('btnNextDay').addEventListener('click', advanceDay);

    document.getElementById('btnPlayAgain').addEventListener('click', playAgainSameConfig);

    document.getElementById('btnBackToSetup').addEventListener('click', () => {
      AppState.gameId = null;
      AppState.status = 'idle';
      showScreen('setup');
      resetStartButton();
    });

    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (document.querySelector('.modal-overlay.visible')) return;
      if (e.code === 'Space') { e.preventDefault(); advanceDay(); }
      if (e.key === 'f' || e.key === 'F') FastForward.openModal();
      if (e.key === '?') HowToPlay.open();
    });

    _gameListenersOnce = true;
  }

  Portfolio.render(gameState);
  Trading.updateDate(gameState.current_date);
  Trading.updateCash(gameState.cash_balance);
  Trading.updatePositions(gameState.positions);
  updateTopBar(gameState);
  Chart.init(AppState.gameId, ticker);
  Chart.addToWatchlist(ticker);
  Chart.renderWatchlistBar();
}

// ── Advance one day ───────────────────────────────────────────────
async function advanceDay() {
  if (!AppState.gameId) return;
  const btn = document.getElementById('btnNextDay');
  if (btn.disabled) return;
  btn.disabled = true;
  const prevText = btn.textContent;
  btn.textContent = 'Loading…';

  try {
    const result = await API.advanceDay(AppState.gameId);
    AppState.currentDate   = result.current_date;
    AppState.status        = result.status;
    AppState.daysRemaining = result.days_remaining ?? 0;

    if (result.portfolio_value_change !== undefined)
      Portfolio.flashPortfolio(result.portfolio_value_change);

    if (result.portfolio_value_change !== undefined && Math.abs(result.portfolio_value_change) > 0.01) {
      const sign = result.portfolio_value_change >= 0 ? '+' : '';
      const pct  = result.portfolio_value_change_pct?.toFixed(2) ?? '0.00';
      showToast(
        `${fmt.date(result.current_date)}: ${sign}${fmt.currency(result.portfolio_value_change)} (${sign}${pct}%)`,
        result.portfolio_value_change >= 0 ? 'success' : 'error', 2500
      );
    }

    // Refresh display (does NOT call handleGameEnd)
    await AppState.refresh();

    // Then handle end — this is the ONLY place advanceDay triggers end screen
    if (result.status !== 'active') {
      if (result.message) showToast(result.message, result.status === 'completed' ? 'success' : 'error', 3500);
      // Small delay so toast/portfolio flash completes before transition
      setTimeout(() => handleGameEnd(result.status), 600);
    }
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.textContent = prevText;
  }
}

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initSetupScreen();
  HowToPlay.init();
  try { await apiFetch('/api/health'); }
  catch (_) {
    document.getElementById('setupError').textContent =
      '⚠ Cannot reach server. Run: cd backend && uvicorn main:app --reload --port 8000';
  }
});