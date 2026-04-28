// components/fastforward.js — Fast-forward modal

const FastForward = (() => {

  let _bound = false;

  function init() {
    // Only bind DOM listeners once — prevents listener stacking on Play Again
    if (_bound) return;
    _bound = true;

    document.getElementById('btnFastForward').addEventListener('click', openModal);
    document.getElementById('ffModalClose').addEventListener('click', closeModal);
    document.getElementById('ffModal').addEventListener('click', (e) => {
      if (e.target === document.getElementById('ffModal')) closeModal();
    });

    document.querySelectorAll('.ff-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.ff-preset').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('ffDays').value = btn.dataset.days;
      });
    });

    document.getElementById('ffDays').addEventListener('input', () => {
      document.querySelectorAll('.ff-preset').forEach(b => b.classList.remove('active'));
      clampDays();
    });

    document.getElementById('btnFFExecute').addEventListener('click', execute);
  }

  function getMaxDays() {
    return Math.max(1, window.AppState?.daysRemaining ?? 365);
  }

  function openModal() {
    document.getElementById('ffModal').classList.add('visible');
    document.getElementById('ffReport').classList.add('hidden');
    setLoading(false);
    document.getElementById('ffBtnText').textContent = 'Simulate →';

    // Update max label and clamp presets
    const max = getMaxDays();
    const maxLabel = document.getElementById('ffMaxLabel');
    if (maxLabel) maxLabel.textContent = `(max ${max} days remaining)`;

    const input = document.getElementById('ffDays');
    input.max = max;
    input.value = Math.min(parseInt(input.value) || 5, max);

    // Disable presets that exceed remaining days
    document.querySelectorAll('.ff-preset').forEach(btn => {
      const d = parseInt(btn.dataset.days);
      btn.disabled = d > max;
      btn.style.opacity = d > max ? '0.35' : '';
    });
  }

  function clampDays() {
    const max = getMaxDays();
    const input = document.getElementById('ffDays');
    const val = parseInt(input.value) || 1;
    if (val > max) input.value = max;
    if (val < 1)   input.value = 1;
  }

  function closeModal() {
    document.getElementById('ffModal').classList.remove('visible');
  }

  function setLoading(on) {
    const btnText = document.getElementById('ffBtnText');
    const loading = document.getElementById('ffLoading');
    const btn     = document.getElementById('btnFFExecute');
    btnText.style.display = on ? 'none' : '';
    loading.classList.toggle('hidden', !on);
    btn.disabled = on;
  }

  async function execute() {
    const gameId = window.AppState?.gameId;
    if (!gameId) return;

    clampDays();
    const days = parseInt(document.getElementById('ffDays').value);
    const max  = getMaxDays();

    if (!days || days < 1) { showToast('Enter at least 1 day.', 'error'); return; }
    if (days > max) { showToast(`Only ${max} market days remaining.`, 'error'); return; }

    setLoading(true);
    document.getElementById('ffReport').classList.add('hidden');

    try {
      const report = await API.fastForward(gameId, days);
      renderReport(report);
      if (window.AppState?.refresh) await window.AppState.refresh();

      if (report.game_over) {
        closeModal();
        setTimeout(() => window.AppState?.triggerGameOver(), 600);
      } else {
        if (report.message) showToast(report.message, 'success', 3500);
        // Check if simulation naturally ended (reached last day)
        const gameNowDone = window.AppState?.daysRemaining === 0 || window.AppState?.status === 'completed';
        if (gameNowDone) {
          closeModal();
          setTimeout(() => {
            if (typeof handleGameEnd === 'function') handleGameEnd('completed');
          }, 800);
        }
        if (report.end_value !== undefined) {
          // Update max for next time
          const maxLabel = document.getElementById('ffMaxLabel');
          const newMax = window.AppState?.daysRemaining ?? 0;
          if (maxLabel) maxLabel.textContent = newMax > 0 ? `(${newMax} days remaining)` : '(simulation ended)';
        }
      }
    } catch (err) {
      showToast('Fast-forward failed: ' + err.message, 'error');
    } finally {
      setLoading(false);
      document.getElementById('ffBtnText').textContent = 'Simulate Again →';
    }
  }

  function renderReport(r) {
    const reportEl = document.getElementById('ffReport');
    reportEl.classList.remove('hidden');

    const netCls  = fmt.colorClass(r.net_pnl);
    const netSign = r.net_pnl >= 0 ? '+' : '';

    let posHTML = '';
    if (r.position_changes && r.position_changes.length > 0) {
      posHTML = `
        <div class="ff-position-changes">
          <div class="ff-pos-title">Position Performance</div>
          ${r.position_changes.map(p => {
            const cls  = fmt.colorClass(p.value_change);
            const sign = p.price_change >= 0 ? '+' : '';
            return `<div class="ff-pos-row">
              <span><span class="ff-pos-ticker">${p.ticker}</span> <span class="ff-pos-type">${p.position_type}</span></span>
              <span style="color:var(--text-muted);font-size:9px">${fmt.currency(p.start_price)} → ${fmt.currency(p.end_price)}</span>
              <span class="ff-pos-change ${cls}">${sign}${p.price_change_pct.toFixed(1)}% (${sign}${fmt.currency(p.value_change)})</span>
            </div>`;
          }).join('')}
        </div>`;
    }

    reportEl.innerHTML = `
      <div class="ff-report-title">
        📊 ${r.days_simulated} market day${r.days_simulated !== 1 ? 's' : ''} simulated
        <span style="color:var(--text-muted);font-size:10px;font-weight:400">${fmt.dateShort(r.start_date)} → ${fmt.dateShort(r.end_date)}</span>
      </div>
      <div class="ff-metric-grid">
        <div class="ff-metric"><span class="ff-metric-label">Start Value</span><span class="ff-metric-val">${fmt.currency(r.start_value)}</span></div>
        <div class="ff-metric"><span class="ff-metric-label">End Value</span><span class="ff-metric-val">${fmt.currency(r.end_value)}</span></div>
        <div class="ff-metric"><span class="ff-metric-label">Net P&L</span><span class="ff-metric-val ${netCls}">${netSign}${fmt.currency(r.net_pnl)}</span></div>
        <div class="ff-metric"><span class="ff-metric-label">Period Return</span><span class="ff-metric-val ${netCls}">${netSign}${r.net_pnl_pct.toFixed(2)}%</span></div>
        ${r.best_day ? `<div class="ff-metric"><span class="ff-metric-label">🟢 Best Day</span><span class="ff-metric-val positive">+${fmt.currency(r.best_day.daily_pnl)}</span><span class="ff-metric-sub">${fmt.dateShort(r.best_day.date)}</span></div>` : ''}
        ${r.worst_day ? `<div class="ff-metric"><span class="ff-metric-label">🔴 Worst Day</span><span class="ff-metric-val negative">${fmt.currency(r.worst_day.daily_pnl)}</span><span class="ff-metric-sub">${fmt.dateShort(r.worst_day.date)}</span></div>` : ''}
      </div>
      ${posHTML}
      ${r.message ? `<div class="ff-message">${r.message}</div>` : ''}`;
  }

  return { init, openModal, closeModal };
})();