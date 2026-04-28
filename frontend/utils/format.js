// utils/format.js — Number and date formatting helpers

const fmt = {
  currency(val, decimals = 2) {
    if (val === null || val === undefined || isNaN(val)) return '—';
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000)     return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
    return `${sign}$${abs.toFixed(decimals)}`;
  },

  pct(val, decimals = 2) {
    if (val === null || val === undefined || isNaN(val)) return '—';
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(decimals)}%`;
  },

  pnl(val) {
    if (val === null || val === undefined || isNaN(val)) return { text: '—', cls: 'neutral' };
    const text = (val >= 0 ? '+' : '') + fmt.currency(val);
    const cls = val > 0 ? 'positive' : val < 0 ? 'negative' : 'neutral';
    return { text, cls };
  },

  pnlPct(val) {
    if (val === null || val === undefined || isNaN(val)) return { text: '—', cls: 'neutral' };
    const sign = val >= 0 ? '+' : '';
    const text = `${sign}${val.toFixed(2)}%`;
    const cls = val > 0 ? 'positive' : val < 0 ? 'negative' : 'neutral';
    return { text, cls };
  },

  date(str) {
    if (!str) return '—';
    const [y, m, d] = str.split('-');
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(m) - 1]} ${parseInt(d)}, ${y}`;
  },

  dateShort(str) {
    if (!str) return '—';
    const [y, m, d] = str.split('-');
    return `${m}/${d}/${y.slice(2)}`;
  },

  shares(val) {
    if (val === null || val === undefined) return '—';
    if (Number.isInteger(val) || Math.abs(val - Math.round(val)) < 0.0001) {
      return Math.round(val).toLocaleString();
    }
    return val.toFixed(4);
  },

  colorClass(val) {
    if (val > 0) return 'positive';
    if (val < 0) return 'negative';
    return 'neutral';
  },
};