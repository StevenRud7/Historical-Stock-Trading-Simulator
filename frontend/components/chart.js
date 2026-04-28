// components/chart.js — Lightweight Charts candlestick component

const Chart = (() => {
  let chart = null;
  let candleSeries = null;
  let volumeSeries = null;
  let currentTicker = null;
  let gameId = null;
  let watchlist = [];
  let isLoading = false;

  function init(gId, ticker) {
    gameId = gId;
    currentTicker = ticker;

    const container = document.getElementById('chartContainer');
    container.innerHTML = '';

    chart = LightweightCharts.createChart(container, {
      layout: {
        background: { color: '#090b10' },
        textColor: '#8892a4',
        fontFamily: "'DM Mono', monospace",
      },
      grid: {
        vertLines: { color: '#1d2840' },
        horzLines: { color: '#1d2840' },
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: '#1d2840', labelBackgroundColor: '#5ba4cf' },
        horzLine: { color: '#1d2840', labelBackgroundColor: '#5ba4cf' },
      },
      rightPriceScale: { borderColor: '#1d2840' },
      timeScale: {
        borderColor: '#1d2840',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        lockVisibleTimeRangeOnResize: true,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (chart && container.clientWidth > 0) {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      }
    });
    ro.observe(container);
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });

    // Candlestick series
    candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444',
      borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });

    // Volume series
    volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    // Crosshair tooltip — update price display while hovering
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData) return;
      const bar = param.seriesData.get(candleSeries);
      if (bar) {
        document.getElementById('chartPrice').textContent = fmt.currency(bar.close);
      }
    });

    bindTickerUI();
    bindWatchlistUI();
    loadTicker(ticker);
  }

  function bindTickerUI() {
    const tickerLabel = document.getElementById('chartTickerLabel');
    const tickerInput = document.getElementById('chartTickerInput');

    // Click the ticker label to switch
    tickerLabel.addEventListener('click', () => {
      tickerInput.style.display = 'block';
      tickerInput.value = '';
      tickerInput.focus();
      tickerLabel.style.opacity = '0.3';
    });

    tickerInput.addEventListener('blur', () => {
      setTimeout(() => {
        tickerInput.style.display = 'none';
        tickerLabel.style.opacity = '1';
      }, 200);
    });

    tickerInput.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        const sym = tickerInput.value.trim().toUpperCase();
        tickerInput.style.display = 'none';
        tickerLabel.style.opacity = '1';
        if (sym) { await loadTicker(sym); addToWatchlist(sym); }
      }
      if (e.key === 'Escape') {
        tickerInput.style.display = 'none';
        tickerLabel.style.opacity = '1';
      }
    });

    tickerInput.addEventListener('input', async () => {
      const q = tickerInput.value.trim();
      await showTickerSuggestions(q, 'chartTickerSuggestions', async (sym) => {
        tickerInput.style.display = 'none';
        tickerLabel.style.opacity = '1';
        await loadTicker(sym);
        addToWatchlist(sym);
      });
    });
  }

  function bindWatchlistUI() {
    document.getElementById('watchlistBar').addEventListener('click', (e) => {
      if (e.target.classList.contains('add-watchlist-btn')) {
        const sym = prompt('Enter ticker symbol to watch:');
        if (sym) { addToWatchlist(sym.toUpperCase().trim()); }
        return;
      }
      if (e.target.classList.contains('wc-remove')) {
        e.stopPropagation();
        const chip = e.target.closest('.watchlist-chip');
        if (chip?.dataset.ticker) removeFromWatchlist(chip.dataset.ticker);
        return;
      }
      const chip = e.target.closest('.watchlist-chip');
      if (chip?.dataset.ticker) loadTicker(chip.dataset.ticker);
    });

    document.getElementById('btnWatchlist').addEventListener('click', () => {
      const sym = prompt('Add ticker to watchlist:');
      if (sym) addToWatchlist(sym.toUpperCase().trim());
    });
  }

  async function loadTicker(ticker) {
    if (!ticker || !gameId || isLoading) return;
    ticker = ticker.toUpperCase().trim();
    isLoading = true;

    document.getElementById('chartTickerLabel').textContent = ticker;
    document.getElementById('chartPrice').textContent = 'Loading…';
    document.getElementById('chartChange').textContent = '';
    currentTicker = ticker;

    // Sync with trade panel
    if (typeof Trading !== 'undefined') Trading.setTickerFromPosition(ticker);

    try {
      const data = await API.getChart(gameId, ticker);
      renderChart(data);
      updateWatchlistChip(ticker, data.current_price, data.price_change, data.price_change_pct);
      document.querySelectorAll('.watchlist-chip').forEach(c => {
        c.classList.toggle('active', c.dataset.ticker === ticker);
      });
    } catch (err) {
      document.getElementById('chartPrice').textContent = 'Error';
      document.getElementById('chartChange').textContent = err.message;
      showToast(`Could not load ${ticker}: ${err.message}`, 'error');
    } finally {
      isLoading = false;
    }
  }

  function renderChart(data) {
    if (!data.bars || data.bars.length === 0) return;

    const candles = data.bars.map(b => ({
      time: b.date,
      open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    const volumes = data.bars.map(b => ({
      time: b.date,
      value: b.volume,
      color: b.close >= b.open ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)',
    }));

    candleSeries.setData(candles);
    volumeSeries.setData(volumes);
    chart.timeScale().fitContent();

    const price     = data.current_price;
    const change    = data.price_change;
    const changePct = data.price_change_pct;

    document.getElementById('chartPrice').textContent = fmt.currency(price);
    const changeEl = document.getElementById('chartChange');
    const sign = change >= 0 ? '+' : '';
    changeEl.textContent = `${sign}${fmt.currency(change)} (${sign}${changePct.toFixed(2)}%)`;
    changeEl.className = `chart-change ${fmt.colorClass(change)}`;
  }

  function addToWatchlist(ticker) {
    ticker = ticker.toUpperCase().trim();
    if (!ticker || watchlist.includes(ticker)) return;
    watchlist.push(ticker);
    renderWatchlistBar();

    // Fetch price asynchronously
    API.getChart(gameId, ticker).then(data => {
      updateWatchlistChip(ticker, data.current_price, data.price_change, data.price_change_pct);
    }).catch(() => {
      API.prefetchTicker(gameId, ticker).then(data => {
        updateWatchlistChip(ticker, data.current_price, 0, 0);
      }).catch(() => {});
    });
  }

  function removeFromWatchlist(ticker) {
    watchlist = watchlist.filter(t => t !== ticker);
    renderWatchlistBar();
    // If we removed the current ticker, stay on it but unmark in watchlist
  }

  function renderWatchlistBar() {
    const bar = document.getElementById('watchlistBar');
    bar.innerHTML = '';

    watchlist.forEach(ticker => {
      const chip = document.createElement('div');
      chip.className = 'watchlist-chip' + (ticker === currentTicker ? ' active' : '');
      chip.dataset.ticker = ticker;
      chip.innerHTML = `
        <span class="wc-symbol">${ticker}</span>
        <span class="wc-price" id="wcp-${ticker}">—</span>
        <span class="wc-change" id="wcc-${ticker}">—</span>
        <span class="wc-remove" title="Remove">✕</span>
      `;
      bar.appendChild(chip);
    });

    const addBtn = document.createElement('button');
    addBtn.className = 'add-watchlist-btn';
    addBtn.title = 'Add ticker to watchlist';
    addBtn.textContent = '+';
    bar.appendChild(addBtn);
  }

  function updateWatchlistChip(ticker, price, change, changePct) {
    const priceEl  = document.getElementById(`wcp-${ticker}`);
    const changeEl = document.getElementById(`wcc-${ticker}`);
    if (priceEl)  priceEl.textContent  = fmt.currency(price);
    if (changeEl) {
      const sign = change >= 0 ? '+' : '';
      changeEl.textContent = `${sign}${changePct.toFixed(1)}%`;
      changeEl.className   = `wc-change ${fmt.colorClass(change)}`;
    }
  }

  async function refreshAllWatchlist() {
    for (const ticker of watchlist) {
      try {
        const data = await API.getChart(gameId, ticker);
        updateWatchlistChip(ticker, data.current_price, data.price_change, data.price_change_pct);
        if (ticker === currentTicker) renderChart(data);
      } catch (_) {}
    }
  }

  function getCurrentTicker() { return currentTicker; }
  function getWatchlist()     { return [...watchlist]; }

  return { init, loadTicker, addToWatchlist, removeFromWatchlist, renderWatchlistBar, refreshAllWatchlist, getCurrentTicker, getWatchlist };
})();