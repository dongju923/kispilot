/* 계좌 */
window.renderPage = function () {
  const { esc, fmt, cls, signed, pct, fill, load, $ } = UI;
  const { n, list, first, md, dotDate } = KIS;

  // ── 잔고 (실전/모의 공통) ──
  const COLORS = ['#17191E', '#D9A441', '#4A505B', '#8E939D', '#C9B37E', '#B9B5AB'];
  $('#kpiTiles').innerHTML = UI.loadingHtml();
  $('#allocBox').innerHTML = UI.loadingHtml();
  load('#holdRows', () => API.acct('order/inquire_balance'), (el, d) => {
    const s = first(d.output2);
    const holds = list(d.output1).filter((h) => n(h.hldg_qty) > 0).sort((a, b) => n(b.evlu_amt) - n(a.evlu_amt));
    const pl = n(s.evlu_pfls_smtl_amt);
    const buy = n(s.pchs_amt_smtl_amt);

    $('#kpiTiles').innerHTML = `
      <div class="tile dark">
        <div class="between"><span class="cap">총 평가금액</span><span class="api">inquire_balance</span></div>
        <span class="tile__value lg">${fmt(n(s.tot_evlu_amt))}<span class="unit"> 원</span></span>
      </div>
      ${[
        ['예수금 (D+2)', fmt(n(s.prvs_rcdl_excc_amt)), ''],
        ['주식 평가금액', fmt(n(s.scts_evlu_amt)), ''],
        ['평가 손익', `${signed(pl)} <span style="font-size:13px">${pct(buy ? (pl / buy) * 100 : null)}</span>`, cls(pl)],
        ['순자산', fmt(n(s.nass_amt)), ''],
      ].map(([k, v, c]) => `<div class="tile"><span class="cap">${k}</span><span class="tile__value ${c}">${v}</span></div>`).join('')}`;

    const total = holds.reduce((sum, h) => sum + (n(h.evlu_amt) || 0), 0);
    $('#holdCount').textContent = `${holds.length}종목`;
    fill(el, holds, (h) => {
      const hpl = n(h.evlu_pfls_amt);
      const wt = total ? (n(h.evlu_amt) / total) * 100 : 0;
      return `
        <a class="tr tall" href="stock.html?code=${esc(h.pdno)}">
          <span style="font-weight:500">${esc(h.prdt_name)}</span>
          <span class="mono r">${fmt(n(h.hldg_qty))}</span>
          <span class="mono r muted">${fmt(n(h.pchs_avg_pric))}</span>
          <span class="mono r">${fmt(n(h.prpr))}</span>
          <span class="mono r">${fmt(n(h.evlu_amt))}</span>
          <span class="mono r ${cls(hpl)}">${signed(hpl)}</span>
          <span class="mono r ${cls(hpl)}" style="font-weight:500">${pct(n(h.evlu_pfls_rt))}</span>
          <span class="row" style="justify-content:flex-end;gap:6px"><span class="meter"><span style="width:${wt.toFixed(0)}%"></span></span><span class="mono cap">${wt.toFixed(0)}%</span></span>
        </a>`;
    }, '보유 종목이 없습니다.');

    // 자산 구성: 상위 5종목 + 기타 + 예수금
    const cash = n(s.prvs_rcdl_excc_amt) || 0;
    const parts = holds.slice(0, 5).map((h) => ({ label: h.prdt_name, v: n(h.evlu_amt) || 0 }));
    const rest = holds.slice(5).reduce((sum, h) => sum + (n(h.evlu_amt) || 0), 0);
    if (rest) parts.push({ label: '기타 종목', v: rest });
    parts.push({ label: '예수금 (D+2)', v: cash });
    const all = parts.reduce((sum, p) => sum + p.v, 0);
    const box = $('#allocBox');
    if (!all) { box.innerHTML = UI.stateHtml('empty', '평가 자산이 없습니다.'); return; }
    parts.forEach((p, i) => { p.color = p.label === '예수금 (D+2)' ? '#E4E2DB' : COLORS[i % COLORS.length]; p.pct = (p.v / all) * 100; });
    box.innerHTML = `
      <div class="stack" style="height:12px;border-radius:6px" role="img" aria-label="${esc(parts.map((p) => `${p.label} ${p.pct.toFixed(0)}%`).join(', '))}">
        ${parts.map((p) => `<div style="width:${p.pct}%;background:${p.color}"></div>`).join('')}
      </div>
      <div class="col" style="gap:8px;font-size:13px">
        ${parts.map((p) => `<div class="row" style="gap:8px"><span class="swatch" style="background:${p.color}"></span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.label)}</span><span class="mono ml-auto">${p.pct.toFixed(1)}%</span></div>`).join('')}
      </div>`;
  }).then((d) => {
    if (d !== undefined) return;
    const msg = UI.stateHtml('empty', '잔고를 불러오지 못했습니다. 보유 종목 카드의 오류를 확인하세요.');
    $('#kpiTiles').innerHTML = msg;
    $('#allocBox').innerHTML = msg;
  });

  // ── 통합 증거금 (실전 전용) ──
  load('#marginList', () => API.realOnly(() => API.get('account/inquire_intgr_margin')), (el, d) => {
    const o = d.output || {};
    const rows = [
      ['주식 현금 주문가능', fmt(n(o.stck_cash_ord_psbl_amt))],
      ['증거금 100% 최대 주문가능', fmt(n(o.stck_cash100_max_ord_psbl_amt))],
      ['계좌 증거금률', o.acmga_rt ? `${fmt(n(o.acmga_rt), 0)}%` : '—'],
      ['미수금', fmt(n(o.rcvb_amt))],
    ];
    el.innerHTML = `<dl class="kv-list">${rows.map(([k, v]) => `<div class="kv"><dt>${k}</dt><dd class="mono">${v}</dd></div>`).join('')}</dl>`;
  });

  // ── 손익 분석 (실전 전용) ──
  const toIso = (s) => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  $('#from').value = toIso(KIS.daysAgo(30));
  $('#to').value = toIso(KIS.ymd());
  const range = () => ({ inqr_strt_dt: $('#from').value.replace(/-/g, ''), inqr_end_dt: $('#to').value.replace(/-/g, '') });

  const summaryHtml = (items) => items.map(([k, v, c]) => `<div class="between"><span class="cap" style="font-size:13px">${k}</span><span class="mono ${c || ''}">${v}</span></div>`).join('');

  const PL = {
    period: {
      api: 'inquire_period_profit', path: 'account/inquire_period_profit',
      cols: 'repeat(5, minmax(0, 1fr))', head: ['일자', '매수금액', '매도금액', '실현손익', '손익률'],
      rows: (d) => list(d.output1), row: (r) => [md(r.trad_dt), fmt(n(r.buy_amt)), fmt(n(r.sll_amt)), [signed(n(r.rlzt_pfls)), cls(n(r.rlzt_pfls))], [pct(n(r.pfls_rt)), cls(n(r.pfls_rt))]],
      summary: (d) => { const s = d.output2 || {}; const p = n(s.tot_rlzt_pfls); return [['총 실현손익', signed(p), cls(p)], ['매수 거래금액', fmt(n(s.buy_tr_amt_smtl))], ['매도 거래금액', fmt(n(s.sll_tr_amt_smtl))], ['수수료', fmt(n(s.tot_fee))], ['제세금', fmt(n(s.tot_tltx))]]; },
    },
    trade: {
      api: 'inquire_period_trade_profit', path: 'account/inquire_period_trade_profit',
      cols: '72px minmax(0, 1.4fr) repeat(4, minmax(0, 1fr))', head: ['일자', '종목', '매수금액', '매도금액', '실현손익', '손익률'],
      rows: (d) => list(d.output1), row: (r) => [md(r.trad_dt), [esc(r.prdt_name), ''], fmt(n(r.buy_amt)), fmt(n(r.sll_amt)), [signed(n(r.rlzt_pfls)), cls(n(r.rlzt_pfls))], [pct(n(r.pfls_rt)), cls(n(r.pfls_rt))]],
      summary: (d) => { const s = d.output2 || {}; const p = n(s.tot_rlzt_pfls); return [['총 실현손익', signed(p), cls(p)], ['총 수익률', pct(n(s.tot_pftrt))], ['매수 거래금액', fmt(n(s.buy_tr_amt_smtl))], ['매도 거래금액', fmt(n(s.sll_tr_amt_smtl))], ['수수료 + 세금', fmt((n(s.tot_fee) || 0) + (n(s.tot_tltx) || 0))]]; },
    },
    rights: {
      api: 'inquire_period_rights', path: 'account/inquire_period_rights',
      cols: '96px minmax(0, 1.4fr) repeat(3, minmax(0, 1fr))', head: ['기준일', '종목', '권리유형', '배정수량', '배정금액'],
      rows: (d) => list(d.output1), row: (r) => [dotDate(r.bass_dt), [esc(r.prdt_name), ''], [esc(r.rght_type_cd), ''], fmt(n(r.tot_alct_qty)), fmt(n(r.last_alct_amt))],
      summary: (d) => [['권리 발생 건수', `${list(d.output1).length}건`]],
    },
  };
  let plKind = 'period';

  function renderPL() {
    const cfg = PL[plKind];
    $('#plApi').textContent = cfg.api;
    const table = $('#plTable');
    table.style.setProperty('--cols', cfg.cols);
    table.innerHTML = `<div class="tr th">${cfg.head.map((h, i) => `<span class="${i < (cfg.head.length > 5 ? 2 : 1) ? '' : 'r'}">${h}</span>`).join('')}</div><div id="plRows" class="tbl-scroll" style="max-height:400px"></div>`;
    const task = () => API.realOnly(() => API.get(cfg.path, range()));
    $('#plSummary').innerHTML = UI.loadingHtml();
    load('#plRows', task, (el, d) => {
      $('#plSummary').innerHTML = summaryHtml(cfg.summary(d));
      const textCols = cfg.head.length > 5 ? 2 : 1;
      fill(el, cfg.rows(d), (r) => `<div class="tr">${cfg.row(r).map((c, i) => {
        const [v, k] = Array.isArray(c) ? c : [esc(c), 'muted'];
        return `<span class="${i < textCols ? '' : 'mono r'} ${k}">${v}</span>`;
      }).join('')}</div>`);
    }).then((d) => { if (d === undefined) $('#plSummary').innerHTML = ''; });
  }

  renderPL();
  $('#plSeg').addEventListener('seg:change', (e) => { plKind = e.detail; renderPL(); });
  $('#plForm').addEventListener('submit', (e) => { e.preventDefault(); renderPL(); });
};
