/* ETF */
window.renderPage = async function () {
  const { esc, fmt, cls, signed, pct, unit, fill, load, $ } = UI;
  const { n, list, md, hm } = KIS;
  const code = await API.currentCode('069500', 'pykis.lastEtf');

  // ── 헤더 ──
  load('#etfHead', () => Promise.all([API.stockMeta(code), API.get('price/inquire_etf_price', { code })]), (el, [meta, d]) => {
    const o = d.output || {};
    document.title = `${meta.name} · ETF · KISPilot`;
    const s = {
      code, name: meta.name, price: n(o.stck_prpr), diff: n(o.prdy_vrss), pct: n(o.prdy_ctrt),
      tags: ['ETF', o.etf_rprs_bstp_kor_isnm && `기초 ${o.etf_rprs_bstp_kor_isnm}`, o.mbcr_name].filter(Boolean),
    };
    UI.stockHeader(el, s, {
      api: 'inquire_etf_price',
      stats: [
        ['NAV', fmt(n(o.nav), 2)],
        ['괴리율', pct(n(o.dprt)), cls(n(o.dprt))],
        ['추적오차율', n(o.trc_errt) == null ? '—' : `${fmt(n(o.trc_errt), 2)}%`],
        ['순자산총액', unit(n(o.etf_ntas_ttam) * 1e8)],
        ['거래량', fmt(n(o.acml_vol))],
        ['구성 종목 수', `${fmt(n(o.etf_cnfg_issu_cnt))}개`],
      ],
    });
  });

  // ── 차트 ──
  let tf = 'D';
  const chart = PriceChart.create($('#chart'), { panes: $('#chartPanes') });
  ChartTools.mount({ toolbar: $('#chartTools'), legend: $('#chartLegend'), panes: $('#chartPanes'), chart });
  $('#chart').addEventListener('chart:loaded', (e) => { $('#chartSrc').textContent = `데이터: ${e.detail.sources.join(' · ')}`; });
  chart.load({ code, tf });
  $('#chartSeg').addEventListener('seg:change', (e) => { tf = e.detail; chart.load({ code, tf }); });

  // ── NAV 요약 ──
  load('#navSummary', () => API.get('price/nav_comparison_trend', { code }), (el, d) => {
    const a = d.output1 || {};
    const b = d.output2 || {};
    const tile = (k, v, c = '') => `<div class="ratio"><span class="cap">${k}</span><span class="mono ${c}">${v}</span></div>`;
    el.innerHTML = tile('시장가', fmt(n(a.stck_prpr)), cls(n(a.prdy_vrss)))
      + tile('NAV', fmt(n(b.nav), 2), cls(n(b.nav_prdy_vrss)))
      + tile('시장가 등락률', pct(n(a.prdy_ctrt)), cls(n(a.prdy_ctrt)))
      + tile('NAV 등락률', pct(n(b.nav_prdy_ctrt)), cls(n(b.nav_prdy_ctrt)));
  });

  // ── NAV 비교 추이 ──
  const renderNav = (kind) => {
    const daily = kind === 'daily';
    $('#navApi').textContent = daily ? 'nav_comparison_daily_trend' : 'nav_comparison_time_trend';
    $('#navCol').textContent = daily ? '일자' : '시간';
    const task = daily
      ? () => API.get('price/nav_comparison_daily_trend', { code, start_date: KIS.daysAgo(60), end_date: KIS.ymd() })
      : () => API.get('price/nav_comparison_time_trend', { code });
    load('#navRows', task, (el, d) => {
      fill(el, list(d.output), (r) => {
        const gap = n(r.nav_vrss_prpr);
        return `
          <div class="tr">
            <span class="mono">${daily ? md(r.stck_bsop_date) : hm(r.bsop_hour)}</span>
            <span class="mono r">${fmt(n(daily ? r.stck_clpr : r.stck_prpr))}</span>
            <span class="mono r muted">${fmt(n(r.nav), 2)}</span>
            <span class="mono r ${cls(gap)}">${signed(gap, 2)}</span>
            <span class="mono r ${cls(n(r.dprt))}">${pct(n(r.dprt))}</span>
          </div>`;
      });
    });
  };
  renderNav('time');
  $('#navSeg').addEventListener('seg:change', (e) => renderNav(e.detail));

  // ── 구성 종목 (+ 상위 30개 시세) ──
  load('#compRows', async () => {
    const d = await API.get('price/inquire_etf_component_stock_price', { code });
    const rows = list(d.output2);
    const codes = rows.map((r) => r.stck_shrn_iscd).filter((c) => /^[0-9A-Z]{6}$/.test(c)).slice(0, 30);
    const quotes = codes.length
      ? await API.get('price_anal/intstock_multprice', { codes }).then((q) => list(q.output)).catch(() => [])
      : [];
    return { rows, total: n((d.output1 || {}).etf_cnfg_issu_cnt), quotes: new Map(quotes.map((q) => [q.inter_shrn_iscd, q])) };
  }, (el, { rows, total, quotes }) => {
    $('#compCount').textContent = total ? `${fmt(total)}종목 중 ${rows.length}` : `${rows.length}종목`;
    const maxW = Math.max(0.01, ...rows.map((r) => n(r.etf_cnfg_issu_rlim) || 0));
    fill(el, rows, (r) => {
      const q = quotes.get(r.stck_shrn_iscd);
      const w = n(r.etf_cnfg_issu_rlim);
      const p = q ? n(q.prdy_ctrt) : null;
      return `
        <a class="tr" href="stock.html?code=${esc(r.stck_shrn_iscd)}">
          <span style="font-weight:500">${esc(r.hts_kor_isnm)}</span>
          <span class="row" style="justify-content:flex-end;gap:6px"><span class="meter gold" style="width:36px"><span style="width:${Math.max(4, Math.round((w || 0) / maxW * 100))}%"></span></span><span class="mono">${fmt(w, 2)}%</span></span>
          <span class="mono r">${q ? fmt(n(q.inter2_prpr)) : '—'}</span>
          <span class="mono r ${cls(p)}">${pct(p)}</span>
          <span class="mono r muted">${unit(n(r.etf_vltn_amt))}</span>
        </a>`;
    });
  });
};
