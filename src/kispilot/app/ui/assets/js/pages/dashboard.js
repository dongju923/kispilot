/* 대시보드 */
window.renderPage = function () {
  const { esc, fmt, cls, signed, pct, arrow, unit, fill, load, $ } = UI;
  const { n, list, first, md, hm } = KIS;

  // ── 지수 3개 + 고객예탁금 ──
  const INDICES = [['KOSPI', '0001'], ['KOSDAQ', '1001'], ['KOSPI 200', '2001']];
  const tiles = $('#indexTiles');
  tiles.innerHTML = [...INDICES.map(([name]) => name), '고객예탁금']
    .map((name, i) => `<a class="tile" href="market.html" id="idx${i}"><span style="font-size:13px;font-weight:600">${esc(name)}</span>${UI.loadingHtml('')}</a>`).join('');

  INDICES.forEach(([name, iscd], i) => {
    load(`#idx${i}`, () => API.get('sector/inquire_index_price', { iscd }), (el, d) => {
      const o = d.output || {};
      const diff = n(o.bstp_nmix_prdy_vrss);
      el.innerHTML = `
        <div class="between"><span style="font-size:13px;font-weight:600">${esc(name)}</span><span class="api">inquire_index_price</span></div>
        <span class="tile__value lg">${fmt(n(o.bstp_nmix_prpr), 2)}</span>
        <span class="mono ${cls(diff)}" style="font-size:13px">${arrow(diff, 2)}&nbsp; ${pct(n(o.bstp_nmix_prdy_ctrt))}</span>`;
    });
  });
  load('#idx3', () => API.get('price_anal/mktfunds'), (el, d) => {
    const o = first(d.output);
    const dep = n(o.cust_dpmn_amt) * 1e8; // 억원 → 원
    const chg = n(o.cust_dpmn_amt_prdy_vrss) * 1e8;
    el.innerHTML = `
      <div class="between"><span style="font-size:13px;font-weight:600">고객예탁금</span><span class="api">mktfunds</span></div>
      <span class="tile__value lg">${unit(dep)}</span>
      <span class="mono ${cls(chg)}" style="font-size:13px">${chg >= 0 ? '▲' : '▼'} ${unit(Math.abs(chg))}&nbsp; ${md(o.bsop_date)} 기준</span>`;
  });

  // ── 계좌 요약 ──
  load('#accBox', () => API.acct('order/inquire_balance'), (el, d) => {
    const s = first(d.output2);
    const holds = list(d.output1).filter((h) => n(h.hldg_qty) > 0)
      .sort((a, b) => n(b.evlu_amt) - n(a.evlu_amt));
    const pl = n(s.evlu_pfls_smtl_amt);
    const buy = n(s.pchs_amt_smtl_amt);
    const plPct = buy ? (pl / buy) * 100 : null;
    el.innerHTML = `
      <div class="card-b">
        <div class="between" style="align-items:flex-end">
          <div class="col">
            <span class="cap">총 평가금액</span>
            <span class="mono" style="font-size:28px;font-weight:500">${fmt(n(s.tot_evlu_amt))}<span class="cap" style="font-size:16px"> 원</span></span>
          </div>
          <div class="mono r ${cls(pl)}" style="font-size:14px">${signed(pl)}<br>${pct(plPct)}</div>
        </div>
        <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px;border-radius:8px;background:var(--surface-2)">
          <div class="col" style="gap:2px"><span class="cap">예수금(D+2)</span><span class="mono">${fmt(n(s.prvs_rcdl_excc_amt))}</span></div>
          <div class="col" style="gap:2px"><span class="cap">주식 평가금액</span><span class="mono">${fmt(n(s.scts_evlu_amt))}</span></div>
          <div class="col" style="gap:2px"><span class="cap">매입금액</span><span class="mono">${fmt(buy)}</span></div>
        </div>
        <div id="accHoldings"></div>
      </div>`;
    fill('#accHoldings', holds.slice(0, 4), (h) => `
      <a href="stock.html?code=${esc(h.pdno)}" class="between" style="height:34px;font-size:13px;border-bottom:1px solid var(--line-soft)">
        <span style="flex:1">${esc(h.prdt_name)}</span>
        <span class="mono muted r" style="width:80px">${fmt(n(h.hldg_qty))}주</span>
        <span class="mono r ${cls(n(h.evlu_pfls_rt))}" style="width:80px">${pct(n(h.evlu_pfls_rt))}</span>
      </a>`, '보유 종목이 없습니다.');
  });

  // ── 관심종목 ──
  const codes = Watch.list();
  if (!codes.length) {
    $('#watchRows').innerHTML = UI.stateHtml('empty', '관심종목이 없습니다. 종목 화면에서 ☆ 를 눌러 추가하세요.');
  } else {
    const loadWatch = (opt) => load('#watchRows', () => API.get('price_anal/intstock_multprice', { codes }), (el, d) => {
      fill(el, list(d.output), (w) => {
        const diff = n(w.inter2_prdy_vrss);
        return `
          <a class="tr" href="stock.html?code=${esc(w.inter_shrn_iscd)}" data-code="${esc(w.inter_shrn_iscd)}">
            <span class="name-code"><b>${esc(w.inter_kor_isnm)}</b><span class="mono cap">${esc(w.inter_shrn_iscd)}</span></span>
            <span class="mono r" data-f="price">${fmt(n(w.inter2_prpr))}</span>
            <span class="mono r ${cls(diff)}" data-f="diff">${arrow(diff)}</span>
            <span class="mono r ${cls(diff)}" data-f="pct">${pct(n(w.prdy_ctrt))}</span>
            <span class="mono r muted" data-f="vol">${fmt(n(w.acml_vol))}</span>
          </a>`;
      });
    }, opt);
    loadWatch();

    // 실시간 체결로 관심종목 시세 갱신 (구독 한도 때문에 최대 30종목)
    const signedOf = (v, sign) => { const x = n(v); return x != null && (sign === '4' || sign === '5') && x > 0 ? -x : x; };
    Live.connect({ ccnl: codes.slice(0, 30) }, {
      ccnl(t) {
        const row = document.querySelector(`#watchRows [data-code="${t.mksc_shrn_iscd}"]`);
        if (!row) return;
        const price = n(t.stck_prpr);
        const diff = signedOf(t.prdy_vrss, t.prdy_vrss_sign);
        const cell = (f) => row.querySelector(`[data-f="${f}"]`);
        const prev = n((cell('price').textContent || '').replace(/[^\d.]/g, ''));
        cell('price').textContent = fmt(price);
        cell('diff').textContent = arrow(diff);
        cell('diff').className = `mono r ${cls(diff)}`;
        cell('pct').textContent = pct(signedOf(t.prdy_ctrt, t.prdy_vrss_sign));
        cell('pct').className = `mono r ${cls(diff)}`;
        cell('vol').textContent = fmt(n(t.acml_vol));
        if (prev && price !== prev) {
          row.classList.remove('flash-up', 'flash-dn');
          void row.offsetWidth; // 애니메이션 재시작
          row.classList.add(price > prev ? 'flash-up' : 'flash-dn');
        }
      },
      resync: () => loadWatch({ quiet: true }),
    });
  }

  // ── 순위 스냅샷 ──
  const RANKS = {
    up: { api: 'fluctuation', path: 'ranking_anal/fluctuation', params: { rank_sort_cls: '0', prc_cls: '1' }, metric: (r) => pct(n(r.prdy_ctrt)), mc: (r) => cls(n(r.prdy_ctrt)) },
    down: { api: 'fluctuation', path: 'ranking_anal/fluctuation', params: { rank_sort_cls: '1', prc_cls: '1' }, metric: (r) => pct(n(r.prdy_ctrt)), mc: (r) => cls(n(r.prdy_ctrt)) },
    volume: { api: 'volume_rank', path: 'ranking_anal/volume_rank', params: {}, metric: (r) => unit(n(r.acml_vol)) + '주', mc: () => 'muted' },
    power: { api: 'volume_power', path: 'ranking_anal/volume_power', params: { vol_cnt: '100000', trgt_exls_cls: '1100011101' }, metric: (r) => fmt(n(r.tday_rltv), 1), mc: () => 'up' },
  };
  const renderRank = (key) => {
    const cfg = RANKS[key];
    $('#rankApi').textContent = cfg.api;
    load('#rankRows', () => API.get(cfg.path, cfg.params), (el, d) => {
      fill(el, list(d.output).slice(0, 6), (r, i) => {
        const code = r.mksc_shrn_iscd || r.stck_shrn_iscd;
        return `
          <a href="stock.html?code=${esc(code)}" class="row" style="gap:12px;height:42px;padding:0 18px;border-bottom:1px solid var(--line-soft);font-size:13px">
            <span class="mono cap" style="width:18px;font-size:13px">${i + 1}</span>
            <span style="flex:1;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.hts_kor_isnm)}</span>
            <span class="mono muted">${fmt(n(r.stck_prpr))}</span>
            <span class="mono r ${cfg.mc(r)}" style="width:72px">${cfg.metric(r)}</span>
          </a>`;
      });
    });
  };
  renderRank('up');
  $('#rankSeg').addEventListener('seg:change', (e) => renderRank(e.detail));

  // ── 투자자별 순매수 + 프로그램 매매 ──
  const renderInvestors = (market) => {
    const sector = market === 'KSP' ? '0001' : '1001';
    load('#investorBars', () => API.get('price_anal/inquire_investor_daily_by_market', { market, sector_code: sector, date: KIS.ymd(), days: 1 }), (el, d) => {
      const o = first(d.output);
      $('#invDate').textContent = `단위 억원 · ${md(o.stck_bsop_date)} 기준`;
      const inv = [['개인', o.prsn_ntby_tr_pbmn], ['외국인', o.frgn_ntby_tr_pbmn], ['기관계', o.orgn_ntby_tr_pbmn]]
        .map(([k, v]) => [k, n(v) == null ? null : Math.round(n(v) / 100)]); // 백만원 → 억원
      const max = Math.max(1, ...inv.map(([, v]) => Math.abs(v || 0)));
      fill(el, inv, ([name, v]) => `
        <div class="col" style="gap:6px">
          <div class="between" style="font-size:13px"><span>${name}</span><span class="mono ${cls(v)}">${signed(v)}</span></div>
          <div class="diverge" role="img" aria-label="${name} ${signed(v)}억원">
            <div><span class="neg" style="width:${v < 0 ? Math.round(-v / max * 100) : 0}%"></span></div>
            <div><span class="pos" style="width:${v > 0 ? Math.round(v / max * 100) : 0}%"></span></div>
          </div>
        </div>`);
    });
    load('#progBox', () => API.get('price_anal/investor_program_trade_today', { market: market === 'KSP' ? '1' : '4' }), (el, d) => {
      const rows = list(d.output1);
      const sum = (k) => rows.reduce((acc, r) => acc + (n(r[k]) || 0), 0) / 100; // 백만원 → 억원
      const arb = Math.round(sum('arbt_ntby_amt'));
      const non = Math.round(sum('nabt_ntby_amt'));
      el.innerHTML = `
        <div class="between"><span class="cap">차익 순매수</span><span class="mono ${cls(arb)}">${signed(arb)}억</span></div>
        <div class="between"><span class="cap">비차익 순매수</span><span class="mono ${cls(non)}">${signed(non)}억</span></div>`;
    });
  };
  renderInvestors('KSP');
  $('#invSeg').addEventListener('seg:change', (e) => renderInvestors(e.detail));

  // ── 뉴스 ──
  load('#newsList', () => API.get('sector/news_title'), (el, d) => {
    fill(el, list(d.output).slice(0, 6), (x) => `
      <div class="col" style="padding:11px 18px;border-bottom:1px solid var(--line-soft)">
        <span style="font-size:13px;line-height:1.45;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(x.hts_pbnt_titl_cntt)}">${esc(x.hts_pbnt_titl_cntt)}</span>
        <span class="cap"><span class="mono">${md(x.data_dt)} ${hm(x.data_tm)}</span> · ${esc(x.dorg)}</span>
      </div>`);
  });
};
