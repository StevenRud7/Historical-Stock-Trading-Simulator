// components/portfolio.js — Portfolio dashboard rendering

const Portfolio = (() => {

  function render(state) {
    const { cash_balance, total_portfolio_value, total_return_pct, positions, initial_balance } = state;
    const pnl = total_portfolio_value - initial_balance;

    // ── Top bar ────────────────────────────────────────────────
    setText('topPortfolioValue', fmt.currency(total_portfolio_value));
    setText('topCashBalance', fmt.currency(cash_balance));

    const pnlEl = document.getElementById('topPnL');
    const { text: pnlText, cls: pnlCls } = fmt.pnl(pnl);
    pnlEl.textContent = pnlText;
    pnlEl.className   = `ps-value ${pnlCls}`;

    const retEl = document.getElementById('topReturn');
    const retSign = total_return_pct >= 0 ? '+' : '';
    retEl.textContent = `${retSign}${total_return_pct.toFixed(2)}%`;
    retEl.className   = `ps-value ${fmt.colorClass(total_return_pct)}`;

    // ── Left panel stats ───────────────────────────────────────
    const positionsValue = total_portfolio_value - cash_balance;
    setText('portCash',          fmt.currency(cash_balance));
    setText('portPositionsVal',  fmt.currency(Math.max(0, positionsValue)));
    setText('portTotal',         fmt.currency(total_portfolio_value));

    // Unrealized P&L from positions
    const unrealized = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
    const unrealEl = document.getElementById('portUnrealized');
    const { text: uText, cls: uCls } = fmt.pnl(unrealized);
    unrealEl.textContent = uText;
    unrealEl.className   = `stat-val ${uCls}`;

    // Realized P&L
    if (state.total_realized_pnl !== undefined) {
      const realEl = document.getElementById('portRealized');
      const { text: rText, cls: rCls } = fmt.pnl(state.total_realized_pnl);
      realEl.textContent = rText;
      realEl.className   = `stat-val ${rCls}`;
    }

    const retEl2 = document.getElementById('portReturn');
    retEl2.textContent = `${retSign}${total_return_pct.toFixed(2)}%`;
    retEl2.className   = `stat-val ${fmt.colorClass(total_return_pct)}`;

    // ── Positions ──────────────────────────────────────────────
    renderPositions(positions);
    document.getElementById('positionCount').textContent =
      `${positions.length} position${positions.length !== 1 ? 's' : ''}`;

    // Pass positions to Trading for max-shares calculation
    if (typeof Trading !== 'undefined') Trading.updatePositions(positions);
  }

  function renderPositions(positions) {
    const container = document.getElementById('positionsList');
    if (!positions || positions.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          No open positions.<br/>
          Use the trade panel to buy or short a stock.
        </div>`;
      return;
    }

    container.innerHTML = positions.map(p => {
      const { text: pnlText, cls: pnlCls } = fmt.pnl(p.unrealized_pnl);
      const pctSign = p.unrealized_pnl_pct >= 0 ? '+' : '';
      const pctText = `${pctSign}${p.unrealized_pnl_pct.toFixed(2)}%`;
      const typeClass = p.position_type.toLowerCase();

      return `
        <div class="position-card" data-ticker="${p.ticker}" tabindex="0"
             title="Click to load chart and fill trade form">
          <div class="pc-header">
            <span class="pc-ticker">${p.ticker}</span>
            <span class="pc-type ${typeClass}">${p.position_type}</span>
          </div>
          <div class="pc-details">
            <span class="pc-detail">Shares <span>${fmt.shares(p.quantity)}</span></span>
            <span class="pc-detail">Avg Cost <span>${fmt.currency(p.avg_cost, 2)}</span></span>
            <span class="pc-detail">Cur Price <span>${fmt.currency(p.current_price, 2)}</span></span>
            <span class="pc-detail">Value <span>${fmt.currency(p.current_value)}</span></span>
          </div>
          <div class="pc-pnl ${pnlCls}">
            ${pnlText} <span class="pc-pnl-pct">(${pctText})</span>
          </div>
        </div>`;
    }).join('');

    // Clicking a position loads its chart and fills trade form
    container.querySelectorAll('.position-card').forEach(card => {
      const onClick = () => {
        const ticker = card.dataset.ticker;
        Chart.loadTicker(ticker);
        if (typeof Trading !== 'undefined') Trading.setTickerFromPosition(ticker);
      };
      card.addEventListener('click', onClick);
      card.addEventListener('keydown', (e) => { if (e.key === 'Enter') onClick(); });
    });
  }

  function renderTradeHistory(trades) {
    const container = document.getElementById('tradeHistory');
    const countEl   = document.getElementById('tradeCount');
    countEl.textContent = `${trades.length} trade${trades.length !== 1 ? 's' : ''}`;

    if (!trades || trades.length === 0) {
      container.innerHTML = '<div class="empty-state">No trades yet.</div>';
      return;
    }

    container.innerHTML = trades.map(t => {
      const showPnl   = (t.action === 'SELL' || t.action === 'COVER') && t.realized_pnl !== 0;
      const { text: pnlText, cls: pnlCls } = showPnl ? fmt.pnl(t.realized_pnl) : { text: '', cls: '' };

      return `
        <div class="trade-item">
          <span class="ti-action ${t.action}">${t.action}</span>
          <div class="ti-info">
            <div class="ti-ticker">${t.ticker}</div>
            <div class="ti-details">${fmt.shares(t.quantity)} sh @ ${fmt.currency(t.price)} · ${fmt.dateShort(t.trade_date)}</div>
          </div>
          <div class="ti-pnl">
            <div class="ti-amount">${fmt.currency(t.total_value)}</div>
            ${showPnl ? `<div class="ti-pnl-val ${pnlCls}">${pnlText}</div>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  function flashPortfolio(direction) {
    const el = document.getElementById('topPortfolioValue');
    if (!el) return;
    el.classList.remove('flash-green', 'flash-red');
    void el.offsetWidth; // reflow
    el.classList.add(direction >= 0 ? 'flash-green' : 'flash-red');
    setTimeout(() => el.classList.remove('flash-green', 'flash-red'), 600);
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  return { render, renderPositions, renderTradeHistory, flashPortfolio };
})();