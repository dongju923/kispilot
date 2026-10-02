/* 시장·업종 */
window.renderPage = function () {
  const { esc, fmt, cls, signed, pct, arrow, unit, fill, load, $ } = UI;
  const { n, list, first, md, hm } = KIS;

  const INDEX = {
    '0001': { name: 'KOSPI', market: 'KSP', cat: ['0001', 'K'] },
    '1001': { name: 'KOSDAQ', market: 'KSQ', cat: ['1001', 'Q'] },
    '2001': { name: 'KOSPI 200', market: 'KSP', cat: ['2001', 'K2'] },
  };

  function showIndex(iscd) {
    const cfg = INDEX[iscd];

    load('#idxDetail', () => API.get('sector/inquire_index_price', { iscd }), (el, d) => {
      const o = d.output || {};
      const diff = n(o.bstp_nmix_prdy_vrss);
      $('#idxHead').innerHTML = `
        <span class="price-big">${fmt(n(o.bstp_nmix_prpr), 2)}</span>
        <span class="mono ${cls(diff)}" style="font-size:15px;padding-bottom:6px">${arrow(diff, 2)}&nbsp; ${pct(n(o.bstp_nmix_prdy_ctrt))}</span>`;
      const rise = n(o.ascn_issu_cnt) || 0;
      const flat = n(o.stnr_issu_cnt) || 0;
      const fall = n(o.down_issu_cnt) || 0;
      const total = Math.max(1, rise + flat + fall);
      const w = (x) => ((x / total) * 100).toFixed(1) + '%';
      el.innerHTML = `
        <dl class="kv-list">
          <div class="kv"><dt>시가</dt><dd class="mono">${fmt(n(o.bstp_nmix_oprc), 2)}</dd></div>
          <div class="kv"><dt>고가</dt><dd class="mono up">${fmt(n(o.bstp_nmix_hgpr), 2)}</dd></div>
          <div class="kv"><dt>저가</dt><dd class="mono dn">${fmt(n(o.bstp_nmix_lwpr), 2)}</dd></div>
          <div class="kv"><dt>거래량</dt><dd class="mono">${fmt(n(o.acml_vol))}천주</dd></div>
          <div class="kv"><dt>거래대금</dt><dd class="mono">${unit(n(o.acml_tr_pbmn) * 1e6)}</dd></div>
        </dl>
        <div class="col" style="padding:0 18px 16px">
          <div class="stack" role="img" aria-label="상승 ${rise}, 보합 ${flat}, 하락 ${fall}">
            <div style="width:${w(rise)};background:var(--up)"></div><div style="width:${w(flat)};background:var(--neutral-bar)"></div><div style="width:${w(fall)};background:var(--dn)"></div>
          </div>
          <div class="between" style="font-size:12px"><span class="up">상승 ${fmt(rise)}</span><span class="flat">보합 ${fmt(flat)}</span><span class="dn">하락 ${fmt(fall)}</span></div>
        </div>`;
    });

    $('#sectorMarket').textContent = `· ${cfg.name}`;
    load('#sectorRows', () => API.get('sector/inquire_index_category_price', { iscd: cfg.cat[0], mrkt_cls_code: cfg.cat[1], blng_cls_code: '0' }), (el, d) => {
      const rows = list(d.output2)
        .filter((r) => r.bstp_cls_code !== iscd)
        .map((r) => ({ name: r.hts_kor_isnm, value: n(r.bstp_nmix_prpr), pct: n(r.bstp_nmix_prdy_ctrt), amount: n(r.acml_tr_pbmn) * 1e6 }))
        .sort((a, b) => (b.pct ?? -999) - (a.pct ?? -999));
      const maxPct = Math.max(0.01, ...rows.map((s) => Math.abs(s.pct || 0)));
      fill(el, rows, (s) => `
        <div class="tr">
          <span style="font-weight:500">${esc(s.name)}</span>
          <span class="mono r">${fmt(s.value, 2)}</span>
          <span class="mono r ${cls(s.pct)}">${pct(s.pct)}</span>
          <span class="mono r muted">${unit(s.amount)}</span>
          <span style="display:flex;justify-content:flex-end"><span style="height:6px;border-radius:3px;background:${(s.pct || 0) >= 0 ? 'var(--up)' : 'var(--dn)'};width:${Math.max(4, Math.round(Math.abs(s.pct || 0) / maxPct * 100))}%"></span></span>
        </div>`);
    });

    load('#flowRows', () => API.get('price_anal/inquire_investor_daily_by_market', { market: cfg.market, sector_code: cfg.market === 'KSP' ? '0001' : '1001', date: KIS.ymd(), days: 6 }), (el, d) => {
      const eok = (v) => (n(v) == null ? null : Math.round(n(v) / 100)); // 백만원 → 억원
      fill(el, list(d.output), (f) => {
        const [a, b, c] = [eok(f.prsn_ntby_tr_pbmn), eok(f.frgn_ntby_tr_pbmn), eok(f.orgn_ntby_tr_pbmn)];
        return `
          <div class="tr">
            <span class="mono">${md(f.stck_bsop_date)}</span>
            <span class="mono r ${cls(a)}">${signed(a)}</span>
            <span class="mono r ${cls(b)}">${signed(b)}</span>
            <span class="mono r ${cls(c)}">${signed(c)}</span>
          </div>`;
      });
    });
  }

  // ── 지수 차트 (지수 분봉은 KIS 분봉 API 가 없어 yfinance 만 사용 → 약 15분 지연) ──
  let iscd = '0001';
  let tf = 'D';
  const chart = PriceChart.create($('#chart'), { panes: $('#chartPanes') });
  ChartTools.mount({ toolbar: $('#chartTools'), legend: $('#chartLegend'), panes: $('#chartPanes'), chart });
  $('#chart').addEventListener('chart:loaded', (e) => {
    const intradayNote = e.detail.intraday ? ' · 지수 분봉은 yfinance 기준(약 15분 지연, 15:00 이후 없음)' : '';
    $('#chartSrc').textContent = `데이터: ${e.detail.sources.join(' · ')}${intradayNote}`;
  });
  const loadChart = () => chart.load({ code: iscd, tf, kind: 'index' });
  $('#chartSeg').addEventListener('seg:change', (e) => { tf = e.detail; loadChart(); });

  showIndex('0001');
  loadChart();
  $('#indexSeg').addEventListener('seg:change', (e) => { iscd = e.detail; showIndex(iscd); loadChart(); });

  // 예상 체결 지수: 08:00~09:00 는 장전 예상, 그 외에는 (직전) 장마감 예상
  const hhmm = new Date().getHours() * 100 + new Date().getMinutes();
  const before = hhmm >= 800 && hhmm < 900;
  $('#expLabel').textContent = before ? '장전 예상' : '장마감 예상';
  // 객체 키 '1001','2001' 은 숫자로 취급돼 순서가 바뀌므로 배열로 순서를 고정
  load('#expIndex', () => Promise.all(['0001', '1001', '2001'].map((iscd) => [iscd, INDEX[iscd]]).map(([iscd, cfg]) =>
    API.get('sector/exp_total_index', { iscd, mkop_cls_code: before ? '1' : '2' })
      .then((d) => ({ name: cfg.name, o: d.output1 || {} })))), (el, rows) => {
    el.innerHTML = rows.map(({ name, o }) => {
      const p = n(o.prdy_ctrt);
      const value = n(o.bstp_nmix_prpr);
      return `<div class="kv"><dt style="color:var(--ink)">${esc(name)}</dt><dd class="mono ${cls(p)}">${value ? `${fmt(value, 2)} · ${pct(p)}` : '—'}</dd></div>`;
    }).join('');
  });

  load('#fundTiles', () => API.get('price_anal/mktfunds'), (el, d) => {
    const o = first(d.output);
    $('#fundDate').textContent = `${md(o.bsop_date)} 기준`;
    const eok = (v) => n(v) * 1e8;
    el.innerHTML = [['고객예탁금', o.cust_dpmn_amt], ['신용융자잔고', o.crdt_loan_rmnd], ['미수금', o.uncl_amt]].map(([k, v]) => `
      <div class="col" style="gap:2px"><span class="cap">${k}</span><span class="mono" style="font-size:15px">${unit(eok(v))}</span></div>`).join('');
  });

  // 주식 관련 기사만 (utils/news.py). KIS 는 기사 주소를 주지 않아 제목 검색 링크로 연다.
  load('#newsList', () => API.get('news', { count: 30 }), (el, d) => {
    fill(el, list(d), (x) => `
      <a class="row news-item" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" style="gap:12px;padding:10px 18px;border-bottom:1px solid var(--line-soft);font-size:13px">
        <span class="mono cap" style="flex-shrink:0">${md(x.date)} ${hm(x.time)}</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(x.title)}">${esc(x.title)}</span>
        <span class="cap" style="flex-shrink:0">${esc(x.source)}</span>
      </a>`);
  });
};
