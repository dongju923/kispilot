/* 종목 분석 — 시세·호가 탭
 * 실시간(ccnl 체결 · book 호가)이 켜져 있으면 헤더·체결·호가·차트를 실시간으로 갱신하고,
 * 끊기거나 일시정지되면 '5초 자동 갱신'(REST) 으로 대신한다.
 */
window.renderPage = async function () {
  const { fmt, cls, pct, arrow, fill, load, $, $$ } = UI;
  const { n, list, md, hms } = KIS;
  const code = await API.currentCode('005930');
  let stock = null;
  let ticks = [];

  const loadHead = (opt) => load('#stockHead', () => API.loadStock(code), (el, s) => {
    stock = s;
    document.title = `${s.name} · 시세·호가 · KISPilot`;
    UI.stockHeader(el, s);
  }, opt);

  const renderBook = (book) => UI.ladder($('#ladder'), book, { current: stock && stock.price });
  const loadBook = (opt) => load('#ladder', () => API.get('price/inquire_asking_price', { code }), (el, d) => {
    renderBook(KIS.orderbook(d.output1 || {}, 5));
  }, opt);

  // 체결 목록: side 1 매수체결(빨강) / 5 매도체결(파랑). REST 는 직전 체결가와 비교해 정한다.
  function renderTicks() {
    fill('#tickRows', ticks, (t) => `
      <div class="tr${t.fresh ? ` flash-${t.side === '5' ? 'dn' : 'up'}` : ''}">
        <span class="mono muted">${hms(t.time)}</span>
        <span class="mono r">${fmt(t.price)}</span>
        <span class="mono r ${cls(t.pct)}">${pct(t.pct)}</span>
        <span class="mono r ${t.side === '5' ? 'dn' : t.side === '1' ? 'up' : 'flat'}">${fmt(t.qty)}</span>
      </div>`, '체결 내역이 없습니다.');
    ticks.forEach((t) => { t.fresh = false; });
  }
  const setStrength = (s) => {
    $('#strength').textContent = s == null ? '—' : `${fmt(s, 2)}%`;
    $('#strength').className = `mono ${s >= 100 ? 'up' : 'dn'}`;
  };
  const loadTicks = (opt) => load('#tickRows', () => API.get('price/inquire_ccnl', { code }), (el, d) => {
    const rows = list(d.output);
    setStrength(n(rows[0] && rows[0].tday_rltv));
    ticks = rows.map((t, i) => {
      const prev = rows[i + 1] ? n(rows[i + 1].stck_prpr) : n(t.stck_prpr);
      const dir = n(t.stck_prpr) - prev;
      return { time: t.stck_cntg_hour, price: n(t.stck_prpr), pct: n(t.prdy_ctrt), qty: n(t.cntg_vol), side: dir > 0 ? '1' : dir < 0 ? '5' : '' };
    });
    renderTicks();
  }, opt);

  const loadDaily = (period) => load('#dailyRows', () => API.get('price/inquire_daily_price', { code, period_div: period }), (el, d) => {
    fill(el, list(d.output), (r) => {
      const diff = n(r.prdy_vrss);
      const frgn = n(r.frgn_ntby_qty);
      return `
        <div class="tr">
          <span class="mono">${period === 'M' ? r.stck_bsop_date.slice(0, 4) + '.' + r.stck_bsop_date.slice(4, 6) : md(r.stck_bsop_date)}</span>
          <span class="mono r">${fmt(n(r.stck_clpr))}</span>
          <span class="mono r ${cls(diff)}">${arrow(diff)}</span>
          <span class="mono r ${cls(diff)}">${pct(n(r.prdy_ctrt))}</span>
          <span class="mono r muted">${fmt(n(r.stck_hgpr))} / ${fmt(n(r.stck_lwpr))}</span>
          <span class="mono r muted">${fmt(n(r.acml_vol))}</span>
          <span class="mono r ${cls(frgn)}">${UI.signed(frgn)}</span>
        </div>`;
    });
  });

  // ── 차트 ──
  const TF_KEY = 'pykis.chartTf';
  let tf = API.store.get(TF_KEY) || 'D';
  const chart = PriceChart.create($('#chart'), { panes: $('#chartPanes') });
  ChartTools.mount({ toolbar: $('#chartTools'), legend: $('#chartLegend'), panes: $('#chartPanes'), chart });
  $$('#chartSeg button').forEach((b) => b.classList.toggle('on', b.dataset.value === tf));
  $('#chart').addEventListener('chart:loaded', (e) => { $('#chartSrc').textContent = `데이터: ${e.detail.sources.join(' · ')}`; });
  const loadChart = (opt) => chart.load({ code, tf }, opt);
  $('#chartSeg').addEventListener('seg:change', (e) => { tf = e.detail; API.store.set(TF_KEY, tf); loadChart(); });

  await loadHead();
  loadChart();
  loadBook();
  loadTicks();
  loadDaily('D');
  $('#dailySeg').addEventListener('seg:change', (e) => loadDaily(e.detail));

  // ── 5초 자동 갱신 (실시간이 없을 때) ──
  let timer;
  const startPolling = (on) => {
    clearInterval(timer);
    if (!on) return;
    timer = setInterval(async () => {
      if (document.hidden) return;
      const quiet = { quiet: true };
      await loadHead(quiet);
      loadBook(quiet);
      loadTicks(quiet);
      loadChart(quiet);
    }, 5000);
  };
  $('#autoRefresh').addEventListener('change', (e) => startPolling(e.target.checked));

  // ── 실시간 ──
  let headQueued = false;
  const repaintHead = () => {
    if (headQueued) return;
    headQueued = true;
    requestAnimationFrame(() => { headQueued = false; UI.stockHeader($('#stockHead'), stock); });
  };
  const signedOf = (v, sign) => { const x = n(v); return x != null && (sign === '4' || sign === '5') && x > 0 ? -x : x; };

  Live.connect({ ccnl: [code], book: [code] }, {
    ccnl(t) {
      const price = n(t.stck_prpr);
      if (!price) return;
      if (stock) {
        Object.assign(stock, {
          price, diff: signedOf(t.prdy_vrss, t.prdy_vrss_sign), pct: signedOf(t.prdy_ctrt, t.prdy_vrss_sign),
          open: n(t.stck_oprc) || stock.open, high: n(t.stck_hgpr) || stock.high, low: n(t.stck_lwpr) || stock.low, volume: n(t.acml_vol) || stock.volume,
        });
        repaintHead();
      }
      setStrength(n(t.cttr));
      ticks.unshift({ time: t.stck_cntg_hour, price, pct: signedOf(t.prdy_ctrt, t.prdy_vrss_sign), qty: n(t.cntg_vol), side: t.cntg_cls_code, fresh: true });
      ticks = ticks.slice(0, 40);
      renderTicks();
      chart.tick({
        date: t.bsop_date, time: t.stck_cntg_hour, price, qty: n(t.cntg_vol), acmlVol: n(t.acml_vol),
        open: n(t.stck_oprc), high: n(t.stck_hgpr), low: n(t.stck_lwpr),
      });
    },
    book(b) {
      renderBook(KIS.orderbook(b, 5));
    },
    state(on) {
      // 실시간 수신 중에는 5초 갱신을 끄고 체크박스를 숨긴다
      $('#autoRefreshWrap').hidden = on;
      if (on) { $('#autoRefresh').checked = false; startPolling(false); }
    },
    resync() {
      // 일시정지·탭 숨김 동안 놓친 체결·분봉을 채운다
      const quiet = { quiet: true };
      loadHead(quiet);
      loadBook(quiet);
      loadTicks(quiet);
      loadChart(quiet);
    },
  });
};
