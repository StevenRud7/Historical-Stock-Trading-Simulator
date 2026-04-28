// components/summarychart.js — End-of-game charts with trade markers

const SummaryChart = (() => {
  let chart = null;
  let candleSeries = null;
  let markerSeries = null;
  let currentTicker = null;
  let chartData = {};   // { ticker: { bars, trades } }
  let allTickers = [];

  const ACTION_COLORS = {
    BUY:   '#3ecf8e',
    SELL:  '#e85d7a',
    SHORT: '#e8a43a',
    COVER: '#a78bfa',
  };

  const ACTION_SHAPES = {
    BUY:   'arrowUp',
    SELL:  'arrowDown',
    SHORT: 'arrowDown',
    COVER: 'arrowUp',
  };

  const ACTION_POSITIONS = {
    BUY:   'belowBar',
    SELL:  'aboveBar',
    SHORT: 'aboveBar',
    COVER: 'belowBar',
  };

  async function load(gameId) {
    const section    = document.getElementById('summaryChartsSection');
    const loading    = document.getElementById('summaryChartLoading');
    const container  = document.getElementById('summaryChartContainer');
    const tabsEl     = document.getElementById('summaryChartTabs');

    if (!section) return;
    section.style.display = 'block';
    loading.style.display = 'block';
    loading.textContent   = 'Loading charts…';

    try {
      // Use apiFetch directly to avoid any API object caching issues
      const data = await apiFetch(`/api/market/summary-charts?game_id=${gameId}`);
      allTickers = data.tickers || [];
      chartData  = data.charts || {};
      const fav  = data.favourite_ticker;

      if (!allTickers.length) {
        loading.textContent = 'No trades placed — no charts to show.';
        return;
      }

      loading.style.display = 'none';

      // Build tabs
      tabsEl.innerHTML = allTickers.map(t => `
        <button class="sc-tab${t === (fav || allTickers[0]) ? ' active' : ''}"
                data-ticker="${t}">
          ${t}${t === fav ? ' ★' : ''}
        </button>`).join('');

      tabsEl.querySelectorAll('.sc-tab').forEach(btn => {
        btn.addEventListener('click', () => {
          tabsEl.querySelectorAll('.sc-tab').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          renderTicker(btn.dataset.ticker);
        });
      });

      // Create chart
      buildChart(container);
      renderTicker(fav || allTickers[0]);

    } catch (err) {
      loading.textContent = 'Could not load charts: ' + err.message;
    }
  }

  function buildChart(container) {
    // Clear previous chart
    container.innerHTML = '';
    const chartDiv = document.createElement('div');
    chartDiv.style.cssText = 'width:100%;height:320px;';
    container.appendChild(chartDiv);

    chart = LightweightCharts.createChart(chartDiv, {
      layout: {
        background: { color: '#0e1118' },
        textColor: '#a0b0cc',
        fontFamily: "'DM Mono', monospace",
      },
      grid: {
        vertLines: { color: '#1d2840' },
        horzLines: { color: '#1d2840' },
      },
      crosshair: {
        vertLine: { color: '#1d2840', labelBackgroundColor: '#5ba4cf' },
        horzLine: { color: '#1d2840', labelBackgroundColor: '#5ba4cf' },
      },
      rightPriceScale: { borderColor: '#1d2840' },
      timeScale: {
        borderColor: '#1d2840',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (chart && chartDiv.clientWidth > 0) {
        chart.applyOptions({ width: chartDiv.clientWidth, height: 320 });
      }
    });
    ro.observe(chartDiv);
    chart.applyOptions({ width: chartDiv.clientWidth, height: 320 });

    candleSeries = chart.addCandlestickSeries({
      upColor: '#3ecf8e', downColor: '#e85d7a',
      borderUpColor: '#3ecf8e', borderDownColor: '#e85d7a',
      wickUpColor: '#3ecf8e', wickDownColor: '#e85d7a',
    });

    // Volume
    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chart._volSeries = volSeries;
  }

  function renderTicker(ticker) {
    if (!chart || !chartData[ticker]) return;
    currentTicker = ticker;

    const { bars, trades } = chartData[ticker];
    if (!bars || !bars.length) return;

    const candles = bars.map(b => ({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close }));
    const volumes = bars.map(b => ({
      time: b.date, value: b.volume,
      color: b.close >= b.open ? 'rgba(62,207,142,.22)' : 'rgba(232,93,122,.22)',
    }));

    candleSeries.setData(candles);
    if (chart._volSeries) chart._volSeries.setData(volumes);

    // Build markers from trade annotations
    const markers = buildMarkers(trades, bars);
    candleSeries.setMarkers(markers);
    chart.timeScale().fitContent();

    // Update ticker label
    const label = document.getElementById('scCurrentTicker');
    if (label) {
      const lastBar  = bars[bars.length - 1];
      const firstBar = bars[0];
      const totalReturn = ((lastBar.close - firstBar.close) / firstBar.close * 100).toFixed(1);
      const sign = totalReturn >= 0 ? '+' : '';
      label.innerHTML = `<span style="color:var(--primary-bright);font-weight:700">${ticker}</span> <span style="font-size:10px;color:var(--text-muted)">full period: <span style="color:${totalReturn>=0?'var(--gain-text)':'var(--loss-text)'}">${sign}${totalReturn}%</span></span>`;
    }
  }

  function buildMarkers(trades, bars) {
    if (!trades || !trades.length) return [];

    // Get set of valid bar dates for snapping
    const barDates = new Set(bars.map(b => b.date));

    // Group trades by date (can have multiple on same day)
    const byDate = {};
    trades.forEach(t => {
      const d = t.date;
      if (!byDate[d]) byDate[d] = [];
      byDate[d].push(t);
    });

    const markers = [];

    Object.entries(byDate).forEach(([date, dayTrades]) => {
      // Snap to nearest available bar date
      let snapDate = date;
      if (!barDates.has(date)) {
        // Find nearest bar
        const sorted = bars.map(b => b.date).sort();
        snapDate = sorted.reduce((prev, curr) =>
          Math.abs(new Date(curr) - new Date(date)) < Math.abs(new Date(prev) - new Date(date)) ? curr : prev
        );
      }

      // Merge multiple trades on same day into one marker per action type
      const actionGroups = {};
      dayTrades.forEach(t => {
        if (!actionGroups[t.action]) actionGroups[t.action] = { qty: 0, total: 0, pnl: 0 };
        actionGroups[t.action].qty   += t.quantity;
        actionGroups[t.action].total += t.total_value;
        actionGroups[t.action].pnl  += t.realized_pnl || 0;
      });

      Object.entries(actionGroups).forEach(([action, agg]) => {
        const pnlStr = (action === 'SELL' || action === 'COVER') && agg.pnl !== 0
          ? ` P&L: ${agg.pnl >= 0 ? '+' : ''}$${Math.abs(agg.pnl).toFixed(0)}`
          : '';

        markers.push({
          time:     snapDate,
          position: ACTION_POSITIONS[action] || 'aboveBar',
          color:    ACTION_COLORS[action] || '#5ba4cf',
          shape:    ACTION_SHAPES[action] || 'circle',
          text:     `${action} ${agg.qty.toFixed(2)}${pnlStr}`,
          size:     1.2,
        });
      });
    });

    // Sort markers by time (required by Lightweight Charts)
    markers.sort((a, b) => a.time < b.time ? -1 : a.time > b.time ? 1 : 0);
    return markers;
  }

  function destroy() {
    if (chart) { chart.remove(); chart = null; }
    candleSeries = null;
    chartData = {};
    allTickers = [];
  }

  return { load, destroy };
})();