from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .io_utils import write_text


def render_dashboard(
    *,
    setups: list[dict],
    leaderboard: list[dict],
    watchlist: list[dict],
    signals: list[dict],
    backtest: list[dict] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    backtest = backtest or []
    payload = {
        "generatedAt": generated_at.isoformat(),
        "setups": setups,
        "leaderboard": leaderboard,
        "watchlist": watchlist,
        "signals": signals,
        "backtest": backtest,
    }
    data_json = json.dumps(payload, sort_keys=True).replace("</", "<\\/")
    summary = _summary(setups, leaderboard, watchlist, signals)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stock Chatter Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #67727e;
      --line: #d8dde4;
      --panel: #ffffff;
      --panel-2: #eef3f8;
      --fresh: #157f67;
      --momentum: #1f65d6;
      --risk: #b45f06;
      --avoid: #b3261e;
      --noise: #626a73;
      --accent: #6f5cc2;
      --shadow: 0 1px 2px rgba(20, 26, 33, .08), 0 8px 28px rgba(20, 26, 33, .07);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.42 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 18px 22px 14px;
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 22px;
      font-weight: 720;
      letter-spacing: 0;
    }}
    .subhead {{
      color: var(--muted);
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(220px, 1.3fr) repeat(3, minmax(130px, .5fr));
      gap: 10px;
      align-items: end;
    }}
    label {{ display: grid; gap: 4px; color: var(--muted); font-size: 12px; font-weight: 650; }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--ink);
      font: inherit;
      min-height: 36px;
      padding: 7px 9px;
    }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      padding: 16px;
      max-width: 1800px;
      margin: 0 auto;
    }}
    .metric-row {{
      display: grid;
      grid-template-columns: repeat(7, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      box-shadow: var(--shadow);
    }}
    .metric b {{ display: block; font-size: 22px; line-height: 1; margin-bottom: 5px; }}
    .metric span {{ color: var(--muted); font-size: 12px; font-weight: 650; }}
    .workflow {{
      display: grid;
      grid-template-columns: repeat(4, minmax(180px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .workflow-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px;
      box-shadow: var(--shadow);
      min-height: 120px;
    }}
    .workflow-panel h2 {{
      margin: 0 0 8px;
      font-size: 13px;
      letter-spacing: 0;
    }}
    .mini-item {{
      border-top: 1px solid #eef1f5;
      padding: 7px 0;
      font-size: 12px;
    }}
    .mini-item strong {{ font-size: 13px; }}
    .mini-meta {{ color: var(--muted); margin-top: 2px; }}
    .warning-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
    }}
    .board {{
      display: grid;
      grid-template-columns: repeat(5, minmax(220px, 1fr));
      gap: 12px;
      align-items: start;
    }}
    .lane {{
      min-width: 0;
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }}
    .lane h2 {{
      margin: 0 0 8px;
      font-size: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      letter-spacing: 0;
    }}
    .count {{ color: var(--muted); font-weight: 650; }}
    .ticker-card {{
      border: 1px solid var(--line);
      border-left: 4px solid var(--noise);
      background: var(--panel);
      border-radius: 8px;
      padding: 10px;
      margin: 8px 0;
      cursor: pointer;
      box-shadow: 0 1px 2px rgba(20, 26, 33, .06);
    }}
    .ticker-card:hover {{ outline: 2px solid rgba(31, 101, 214, .18); }}
    .ticker-card[data-label="fresh_watch"], .ticker-card[data-label="building"] {{ border-left-color: var(--fresh); }}
    .ticker-card[data-label="momentum_confirmed"] {{ border-left-color: var(--momentum); }}
    .ticker-card[data-label="extended"], .ticker-card[data-label="late_chase"] {{ border-left-color: var(--risk); }}
    .ticker-card[data-label="avoid_wait"] {{ border-left-color: var(--avoid); }}
    .ticker-title {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 7px;
    }}
    .ticker-title strong {{ font-size: 18px; letter-spacing: 0; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 750;
      white-space: nowrap;
      background: #e6e9ef;
      color: #36404a;
    }}
    .badge.fresh {{ background: #dff3ec; color: #0b644f; }}
    .badge.momentum {{ background: #e1ecff; color: #174eab; }}
    .badge.risk {{ background: #fff0da; color: #874600; }}
    .badge.avoid {{ background: #fde8e7; color: #8f1d17; }}
    .badge.warn {{ background: #fff4d9; color: #7a4b00; }}
    .badge.low {{ background: #eef0f2; color: #525b65; }}
    .card-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 5px 8px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 7px;
    }}
    .reason {{ font-size: 12px; color: #35404a; }}
    .tabs {{
      display: flex;
      gap: 8px;
      margin: 16px 0 8px;
      border-bottom: 1px solid var(--line);
    }}
    .tab {{
      border: 0;
      background: transparent;
      padding: 9px 10px;
      font: inherit;
      font-weight: 700;
      color: var(--muted);
      cursor: pointer;
      border-bottom: 3px solid transparent;
    }}
    .tab.active {{ color: var(--ink); border-bottom-color: var(--accent); }}
    .table-wrap {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
      box-shadow: var(--shadow);
      max-height: 520px;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 900px; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 2;
      font-size: 12px;
      color: var(--muted);
    }}
    td.wrap {{ white-space: normal; min-width: 260px; }}
    aside {{
      position: sticky;
      top: 114px;
      align-self: start;
      display: grid;
      gap: 12px;
    }}
    .detail, .themes {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
      box-shadow: var(--shadow);
    }}
    .detail h2, .themes h2 {{ font-size: 16px; margin: 0 0 10px; }}
    .detail-row {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      border-bottom: 1px solid #eef1f5;
      padding: 6px 0;
    }}
    .detail-row span:first-child {{ color: var(--muted); }}
    .feed-panel {{
      margin-top: 12px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}
    .feed-panel h3 {{
      margin: 0 0 8px;
      font-size: 13px;
      letter-spacing: 0;
    }}
    .feed-item {{
      border: 1px solid #e5e9ef;
      border-radius: 8px;
      padding: 9px;
      margin: 8px 0;
      background: #fbfcfd;
    }}
    .feed-meta {{
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      font-size: 11px;
      font-weight: 650;
      margin-bottom: 5px;
    }}
    .feed-text {{
      color: #27323d;
      font-size: 12px;
      white-space: normal;
      overflow-wrap: anywhere;
    }}
    .feed-link {{ color: var(--momentum); font-weight: 700; text-decoration: none; }}
    .bar {{
      display: grid;
      grid-template-columns: 92px 1fr 32px;
      align-items: center;
      gap: 8px;
      margin: 8px 0;
      font-size: 12px;
    }}
    .bar-track {{ height: 9px; background: #edf0f4; border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: var(--accent); }}
    .empty {{ color: var(--muted); padding: 12px 4px; }}
    @media (max-width: 1200px) {{
      main {{ grid-template-columns: 1fr; }}
      aside {{ position: static; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .board, .workflow {{ grid-template-columns: repeat(2, minmax(240px, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      header {{ position: static; }}
      .toolbar, .metric-row, aside, .board, .workflow {{ grid-template-columns: 1fr; }}
      main {{ padding: 10px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Stock Chatter Dashboard</h1>
    <div class="subhead">
      <span>Generated {escape(summary["generated"])}</span>
      <span>{summary["setups"]} ticker setups</span>
      <span>{summary["priced"]} with price context</span>
      <span>{summary["accounts"]} accounts</span>
      <span>{summary["feed"]} feed items</span>
    </div>
    <div class="toolbar">
      <label>Search<input id="search" type="search" placeholder="Ticker, account, catalyst, reason"></label>
      <label>Setup<select id="labelFilter"><option value="">All setups</option></select></label>
      <label>Price<select id="priceFilter"><option value="">All</option><option value="priced">Priced only</option><option value="unpriced">Unpriced only</option></select></label>
      <label>Sort<select id="sortMode"><option value="actionability">Actionability</option><option value="quality">Quality score</option><option value="mentions">Mentions</option><option value="ret5">5D return</option><option value="rv">Relative volume</option></select></label>
    </div>
  </header>
  <main>
    <section>
      <div class="metric-row" id="metrics"></div>
      <div class="workflow" id="workflow"></div>
      <div class="board" id="board"></div>
      <div class="tabs">
        <button class="tab active" data-tab="setups">All Setups</button>
        <button class="tab" data-tab="leaderboard">Account Leaderboard</button>
        <button class="tab" data-tab="backtest">Trust Backtest</button>
        <button class="tab" data-tab="watchlist">Watchlist Memory</button>
        <button class="tab" data-tab="feed">Follow Feed</button>
      </div>
      <div class="table-wrap"><table id="dataTable"></table></div>
    </section>
    <aside>
      <div class="detail" id="detail"></div>
      <div class="themes" id="themes"></div>
    </aside>
  </main>
  <script id="dashboard-data" type="application/json">{data_json}</script>
  <script>
    const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
    const lanes = [
      ['Fresh Watch', ['fresh_watch', 'building']],
      ['Momentum Confirmed', ['momentum_confirmed']],
      ['Already Ran / Chase Risk', ['extended', 'late_chase']],
      ['Avoid / Wait', ['avoid_wait']],
      ['Speculative / Noise', ['noise']]
    ];
    const labelClass = label => label === 'momentum_confirmed' ? 'momentum' :
      (label === 'fresh_watch' || label === 'building') ? 'fresh' :
      (label === 'extended' || label === 'late_chase') ? 'risk' :
      label === 'avoid_wait' ? 'avoid' : '';
    const pct = value => value === '' || value == null || Number.isNaN(Number(value)) ? 'n/a' : `${{(Number(value) * 100).toFixed(1)}}%`;
    const num = value => Number(value || 0);
    const text = value => String(value || '');
    const tokens = value => text(value).split(';').filter(Boolean);
    let activeTab = 'setups';
    let selectedTicker = DATA.setups[0]?.ticker || '';

    const labelFilter = document.getElementById('labelFilter');
    [...new Set(DATA.setups.map(row => row.setup_label).filter(Boolean))].sort().forEach(label => {{
      const option = document.createElement('option');
      option.value = label;
      option.textContent = label;
      labelFilter.appendChild(option);
    }});
    ['search', 'labelFilter', 'priceFilter', 'sortMode'].forEach(id => document.getElementById(id).addEventListener('input', render));
    document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {{
      activeTab = button.dataset.tab;
      document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab === button));
      renderTable();
    }}));

    function filteredSetups() {{
      const query = document.getElementById('search').value.trim().toLowerCase();
      const label = labelFilter.value;
      const price = document.getElementById('priceFilter').value;
      let rows = DATA.setups.filter(row => {{
        const haystack = [row.ticker, row.asset_type, row.setup_label, row.reason, row.catalysts, row.news_confirmation, row.top_accounts, row.warnings, row.confidence_label].join(' ').toLowerCase();
        if (query && !haystack.includes(query)) return false;
        if (label && row.setup_label !== label) return false;
        if (price === 'priced' && row.price_data_available !== 'true') return false;
        if (price === 'unpriced' && row.price_data_available === 'true') return false;
        return true;
      }});
      const sort = document.getElementById('sortMode').value;
      rows.sort((a, b) => {{
        if (sort === 'mentions') return num(b.mention_count) - num(a.mention_count);
        if (sort === 'ret5') return num(b.prior_ret_5d) - num(a.prior_ret_5d);
        if (sort === 'rv') return num(b.relative_volume) - num(a.relative_volume);
        if (sort === 'actionability') return num(b.actionability_rank) - num(a.actionability_rank);
        return num(b.quality_score) - num(a.quality_score);
      }});
      return rows;
    }}

    function filterGeneric(rows) {{
      const query = document.getElementById('search').value.trim().toLowerCase();
      if (!query) return rows;
      return rows.filter(row => Object.values(row).join(' ').toLowerCase().includes(query));
    }}

    function render() {{
      const rows = filteredSetups();
      renderMetrics(rows);
      renderWorkflow(rows);
      renderBoard(rows);
      renderDetail(rows.find(row => row.ticker === selectedTicker) || rows[0]);
      renderThemes(rows);
      renderTable();
    }}

    function renderMetrics(rows) {{
      const counts = Object.fromEntries(lanes.map(([name, labels]) => [name, rows.filter(row => labels.includes(row.setup_label)).length]));
      const priced = rows.filter(row => row.price_data_available === 'true').length;
      const blocked = rows.filter(row => tokens(row.warnings).some(w => ['unpriced','asset_ambiguous','single_source'].includes(w))).length;
      const metrics = [
        ['Fresh/Building', counts['Fresh Watch']],
        ['Momentum', counts['Momentum Confirmed']],
        ['Chase Risk', counts['Already Ran / Chase Risk']],
        ['Avoid/Noise', counts['Avoid / Wait'] + counts['Speculative / Noise']],
        ['Priced', priced],
        ['Blocked', blocked],
        ['Feed Items', DATA.signals.length]
      ];
      document.getElementById('metrics').innerHTML = metrics.map(([label, value]) => `<div class="metric"><b>${{value}}</b><span>${{label}}</span></div>`).join('');
    }}

    function renderWorkflow(rows) {{
      const action = rows
        .filter(row => ['fresh_watch','building','momentum_confirmed'].includes(row.setup_label) && row.price_data_available === 'true' && !tokens(row.warnings).includes('chase_risk'))
        .sort((a, b) => num(b.actionability_rank) - num(a.actionability_rank))
        .slice(0, 5);
      const changed = filterGeneric(DATA.watchlist).filter(row => row.label_changed === 'true').slice(0, 5);
      const blocked = rows.filter(row => tokens(row.warnings).some(w => ['unpriced','asset_ambiguous','single_source'].includes(w))).slice(0, 5);
      const chase = rows.filter(row => ['extended','late_chase'].includes(row.setup_label)).slice(0, 5);
      const panels = [
        ['Action Queue', action, row => `${{esc(row.ticker)}} · ${{esc(row.setup_label)}} · rank ${{esc(row.actionability_rank)}}`, row => esc(row.reason || '')],
        ['Changed', changed, row => `${{esc(row.ticker)}} · ${{esc(row.previous_setup_label || 'new')}} -> ${{esc(row.latest_setup_label)}}`, row => esc(row.status || '')],
        ['Needs Confirmation', blocked, row => `${{esc(row.ticker)}} · ${{esc(row.setup_label)}}`, row => esc(row.warnings || '')],
        ['Do Not Chase', chase, row => `${{esc(row.ticker)}} · ${{esc(row.setup_label)}}`, row => `5D ${{pct(row.prior_ret_5d)}} · ${{esc(row.reason || '')}}`]
      ];
      document.getElementById('workflow').innerHTML = panels.map(([title, items, primary, secondary]) => `<section class="workflow-panel"><h2>${{title}}</h2>${{items.length ? items.map(row => `<div class="mini-item"><strong>${{primary(row)}}</strong><div class="mini-meta">${{secondary(row)}}</div></div>`).join('') : '<div class="empty">None.</div>'}}</section>`).join('');
    }}

    function renderBoard(rows) {{
      document.getElementById('board').innerHTML = lanes.map(([name, labels]) => {{
        const allLaneRows = rows.filter(row => labels.includes(row.setup_label));
        const laneRows = allLaneRows.slice(0, 12);
        return `<section class="lane"><h2>${{name}} <span class="count">${{laneRows.length}} shown / ${{allLaneRows.length}}</span></h2>${{laneRows.length ? laneRows.map(card).join('') : '<div class="empty">No matching tickers.</div>'}}</section>`;
      }}).join('');
      document.querySelectorAll('.ticker-card').forEach(card => card.addEventListener('click', () => {{
        selectedTicker = card.dataset.ticker;
        renderDetail(DATA.setups.find(row => row.ticker === selectedTicker));
      }}));
    }}

    function card(row) {{
      const warn = tokens(row.warnings).slice(0, 3).map(w => `<span class="badge warn">${{esc(w)}}</span>`).join('');
      return `<article class="ticker-card" data-ticker="${{esc(row.ticker)}}" data-label="${{esc(row.setup_label)}}">
        <div class="ticker-title"><strong>${{esc(row.ticker)}}</strong><span class="badge ${{labelClass(row.setup_label)}}">${{esc(row.setup_label)}}</span></div>
        <div class="card-grid">
          <span>Rank ${{esc(row.actionability_rank || '0')}}</span><span>${{esc(row.confidence_label || 'n/a')}} conf</span>
          <span>Score ${{num(row.quality_score).toFixed(1)}}</span><span>${{esc(row.mention_count)}} mentions</span>
          <span>1D ${{pct(row.prior_ret_1d)}}</span><span>5D ${{pct(row.prior_ret_5d)}}</span>
          <span>RV ${{row.relative_volume ? num(row.relative_volume).toFixed(1) + 'x' : 'n/a'}}</span><span>${{esc(row.asset_type || 'asset?')}}</span>
        </div>
        <div class="warning-list">${{warn}}</div>
        <div class="reason">${{esc(row.reason)}}</div>
      </article>`;
    }}

    function renderDetail(row) {{
      if (!row) {{
        document.getElementById('detail').innerHTML = '<h2>Ticker Detail</h2><div class="empty">No ticker selected.</div>';
        return;
      }}
      selectedTicker = row.ticker;
      const fields = [
        ['Setup', row.setup_label],
        ['Actionability', row.actionability],
        ['Actionability rank', row.actionability_rank || 'n/a'],
        ['Confidence', row.confidence_label || 'n/a'],
        ['Warnings', row.warnings || 'none'],
        ['Asset type', row.asset_type || 'n/a'],
        ['Quality score', num(row.quality_score).toFixed(1)],
        ['Mentions', `${{row.mention_count}} across ${{row.distinct_account_count}} accounts`],
        ['Entry/watch/exit/short', `${{row.entry_count || 0}} / ${{row.watch_count || 0}} / ${{row.exit_count || 0}} / ${{row.short_count || 0}}`],
        ['Source score', num(row.source_score).toFixed(1)],
        ['Price date', row.price_date || 'n/a'],
        ['1D / 5D / 20D', `${{pct(row.prior_ret_1d)}} / ${{pct(row.prior_ret_5d)}} / ${{pct(row.prior_ret_20d)}}`],
        ['Gap / RV', `${{pct(row.current_gap)}} / ${{row.relative_volume ? num(row.relative_volume).toFixed(1) + 'x' : 'n/a'}}`],
        ['20D high distance', pct(row.distance_from_20d_high)],
        ['Catalysts', row.catalysts || 'social_only'],
        ['Catalyst type', row.news_confirmation || 'social_only'],
        ['First seen', row.first_seen_at || 'n/a'],
        ['Latest mention', row.latest_mention_at || 'n/a'],
        ['First account', row.first_account || 'n/a'],
        ['Top accounts', row.top_accounts || 'n/a'],
        ['Reason', row.reason || 'n/a']
      ];
      const tickerSignals = DATA.signals
        .filter(signal => text(signal.ticker).toUpperCase() === text(row.ticker).toUpperCase())
        .sort((a, b) => text(b.tweet_created_at).localeCompare(text(a.tweet_created_at)))
        .slice(0, 8);
      const feedHtml = `<div class="feed-panel"><h3>Follow Feed Mentions</h3>${{tickerSignals.length ? tickerSignals.map(feedItem).join('') : '<div class="empty">No saved feed posts for this ticker.</div>'}}</div>`;
      document.getElementById('detail').innerHTML = `<h2>${{esc(row.ticker)}} Detail</h2>` + fields.map(([k, v]) => `<div class="detail-row"><span>${{esc(k)}}</span><strong>${{esc(v)}}</strong></div>`).join('') + feedHtml;
    }}

    function renderThemes(rows) {{
      const counts = new Map();
      rows.forEach(row => text(row.catalysts || 'social_only').split(';').filter(Boolean).forEach(tag => counts.set(tag, (counts.get(tag) || 0) + 1)));
      const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
      const max = Math.max(1, ...sorted.map(([, count]) => count));
      document.getElementById('themes').innerHTML = '<h2>Theme Map</h2>' + (sorted.length ? sorted.map(([tag, count]) => `<div class="bar"><span>${{esc(tag.replaceAll('_', ' '))}}</span><div class="bar-track"><div class="bar-fill" style="width:${{count / max * 100}}%"></div></div><strong>${{count}}</strong></div>`).join('') : '<div class="empty">No themes.</div>');
    }}

    function filteredFeed() {{
      const query = document.getElementById('search').value.trim().toLowerCase();
      return DATA.signals
        .filter(row => {{
          const haystack = [row.ticker, row.account, row.account_tier, row.action, row.catalysts, row.text].join(' ').toLowerCase();
          return !query || haystack.includes(query);
        }})
        .sort((a, b) => text(b.tweet_created_at).localeCompare(text(a.tweet_created_at)));
    }}

    function feedItem(row) {{
      const link = row.url ? `<a class="feed-link" href="${{esc(row.url)}}" target="_blank" rel="noopener">open</a>` : '';
      return `<article class="feed-item">
        <div class="feed-meta"><span>${{esc(row.account)}}</span><span>${{esc(row.tweet_created_at)}}</span><span>${{esc(row.ticker)}}</span><span>${{esc(row.action)}}</span>${{link}}</div>
        <div class="feed-text">${{esc(row.text)}}</div>
      </article>`;
    }}

    function renderTable() {{
      if (activeTab === 'leaderboard') {{
        table(filterGeneric(DATA.leaderboard), ['account', 'account_tier', 'leaderboard_score', 'mention_count', 'distinct_ticker_count', 'entry_count', 'first_mention_count', 'top_tickers']);
      }} else if (activeTab === 'backtest') {{
        table(filterGeneric(DATA.backtest), ['account', 'account_tier', 'trust_label', 'evidence_status', 'trust_score', 'signal_count', 'actionable_count', 'entry_count', 'short_count', 'exit_count', 'watch_count', 'mention_count', 'complete_1d_count', 'complete_5d_count', 'complete_20d_count', 'avg_ret_1d', 'avg_excess_ret_1d', 'hit_rate_1d', 'avg_ret_5d', 'avg_excess_ret_5d', 'hit_rate_5d', 'avg_ret_20d', 'avg_excess_ret_20d', 'hit_rate_20d', 'top_tickers']);
      }} else if (activeTab === 'watchlist') {{
        table(filterGeneric(DATA.watchlist), ['ticker', 'status', 'label_changed', 'previous_setup_label', 'still_fresh', 'first_setup_label', 'latest_setup_label', 'latest_quality_score', 'age_days', 'first_seen_at', 'latest_seen_at', 'first_account', 'catalysts', 'mention_count']);
      }} else if (activeTab === 'feed') {{
        table(filteredFeed(), ['tweet_created_at', 'account', 'account_tier', 'ticker', 'action', 'catalysts', 'hype_score', 'url', 'text']);
      }} else {{
        table(filteredSetups(), ['ticker', 'asset_type', 'setup_label', 'actionability_rank', 'confidence_label', 'warnings', 'quality_score', 'mention_count', 'distinct_account_count', 'entry_count', 'watch_count', 'exit_count', 'short_count', 'price_date', 'prior_ret_1d', 'prior_ret_5d', 'prior_ret_20d', 'relative_volume', 'distance_from_20d_high', 'catalysts', 'top_accounts', 'reason']);
      }}
    }}

    function table(rows, cols) {{
      const head = `<thead><tr>${{cols.map(col => `<th>${{esc(col)}}</th>`).join('')}}</tr></thead>`;
      const body = `<tbody>${{rows.map(row => `<tr>${{cols.map(col => `<td class="${{['text','reason','warnings','top_tickers','catalysts'].includes(col) ? 'wrap' : ''}}">${{formatCell(col, row[col])}}</td>`).join('')}}</tr>`).join('')}}</tbody>`;
      document.getElementById('dataTable').innerHTML = head + body;
    }}

    function formatCell(col, value) {{
      if (['prior_ret_1d','prior_ret_5d','prior_ret_20d','distance_from_20d_high','avg_ret_1d','avg_ret_5d','avg_ret_20d','avg_excess_ret_1d','avg_excess_ret_5d','avg_excess_ret_20d','hit_rate_1d','hit_rate_5d','hit_rate_20d','avg_max_drawdown_20d'].includes(col)) return pct(value);
      if (col === 'relative_volume') return value ? `${{num(value).toFixed(1)}}x` : 'n/a';
      if (col === 'url') return value ? `<a class="feed-link" href="${{esc(value)}}" target="_blank" rel="noopener">open</a>` : '';
      if (col.includes('score')) return value ? num(value).toFixed(1) : 'n/a';
      return esc(value || '');
    }}

    function esc(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    }}

    render();
  </script>
</body>
</html>
"""


def write_dashboard(
    path: str | Path,
    *,
    setups: list[dict],
    leaderboard: list[dict],
    watchlist: list[dict],
    signals: list[dict],
    backtest: list[dict] | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, render_dashboard(setups=setups, leaderboard=leaderboard, watchlist=watchlist, signals=signals, backtest=backtest))


def _summary(setups: list[dict], leaderboard: list[dict], watchlist: list[dict], signals: list[dict]) -> dict[str, str]:
    priced = sum(1 for row in setups if row.get("price_data_available") == "true")
    return {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "setups": str(len(setups)),
        "priced": str(priced),
        "accounts": str(len(leaderboard)),
        "watchlist": str(len(watchlist)),
        "feed": str(len(signals)),
    }
