/* 종목 분석 — 투자자·수급 탭 */
window.renderPage = async function () {
  const { esc, fmt, cls, signed, unit, fill, load, $ } = UI;
  const { n, list, first, md, hm } = KIS;
  const code = await API.currentCode('005930');

  const stockTask = API.loadStock(code);
  load('#stockHead', () => stockTask, (el, s) => {
    document.title = `${s.name} · 투자자·수급 · KISPilot`;
    UI.stockHeader(el, s, { compact: true });
  });

  // ── 요약 타일 ──
  const tile = (id, label, api) => `
    <div class="tile" style="padding:12px 16px;gap:4px" id="${id}">
      <span class="cap">${label}</span><span class="tile__value">—</span><span><span class="api">${api}</span></span>
    </div>`;
  $('#flowTiles').innerHTML = tile('tFrgn', '외국인 순매수 (최근일)', 'inquire_investor')
    + tile('tOrgn', '기관 순매수 (최근일)', 'inquire_investor')
    + tile('tGlob', '외국계 회원사 순매수 (당일)', 'frgnmem_pchs_trend')
    + tile('tProg', '프로그램 순매수 (당일)', 'inquire_price');
  const setTile = (id, v, suffix = '주') => {
    const el = $(`#${id} .tile__value`);
    el.textContent = v == null ? '—' : `${signed(v)}${suffix}`;
    el.className = `tile__value ${cls(v)}`;
  };
  stockTask.then((s) => setTile('tProg', s.programNet)).catch(() => {});
  API.get('price_anal/frgnmem_pchs_trend', { code })
    .then((d) => setTile('tGlob', n(first(d.output).glob_ntby_qty))).catch(() => {});

  // ── 투자자별 (inquire_investor) + 외인 소진율 (inquire_daily_price) ──
  load('#investorRows', () => Promise.all([
    API.get('price/inquire_investor', { code }),
    API.get('price/inquire_daily_price', { code }).catch(() => ({ output: [] })),
  ]), (el, [inv, daily]) => {
    const hold = new Map(list(daily.output).map((r) => [r.stck_bsop_date, n(r.hts_frgn_ehrt)]));
    const rows = list(inv.output).filter((r) => r.prsn_ntby_qty !== '' && r.prsn_ntby_qty != null);
    if (rows[0]) { setTile('tFrgn', n(rows[0].frgn_ntby_qty)); setTile('tOrgn', n(rows[0].orgn_ntby_qty)); }
    fill(el, rows, (r) => {
      const [a, b, c] = [n(r.prsn_ntby_qty), n(r.frgn_ntby_qty), n(r.orgn_ntby_qty)];
      const h = hold.get(r.stck_bsop_date);
      return `
        <div class="tr">
          <span class="mono">${md(r.stck_bsop_date)}</span>
          <span class="mono r ${cls(a)}">${signed(a)}</span>
          <span class="mono r ${cls(b)}">${signed(b)}</span>
          <span class="mono r ${cls(c)}">${signed(c)}</span>
          <span class="mono r muted">${h == null ? '—' : fmt(h, 2) + '%'}</span>
        </div>`;
    });
  });

  // ── 회원사 ──
  // REST(inquire_member) 와 실시간(member) 이 같은 모양(o)으로 그린다
  function renderMember(el, o) {
    const side = (prefix, qtyKey, c) => [1, 2, 3, 4, 5]
      .map((i) => ({ name: o[`${prefix}_mbcr_name${i}`], qty: n(o[`${qtyKey}${i}`]), glob: o[`${prefix}_mbcr_glob_yn_${i}`] === 'Y' }))
      .filter((m) => m.name)
      .map((m) => `<div class="tr"><span>${esc(m.name)}${m.glob ? ' <span class="cap">외국계</span>' : ''}</span><span class="mono r ${c}">${fmt(m.qty)}</span></div>`)
      .join('') || UI.stateHtml('empty', '자료가 없습니다.');
    const glob = n(o.glob_ntby_qty);
    el.innerHTML = `
      <div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));gap:0">
        <div class="tbl" style="--cols:repeat(2,minmax(0,1fr));border-right:1px solid var(--line-mid)">
          <div class="tr th"><span>매도 상위</span><span class="r">수량</span></div>${side('seln', 'total_seln_qty', 'dn')}
        </div>
        <div class="tbl" style="--cols:repeat(2,minmax(0,1fr))">
          <div class="tr th"><span>매수 상위</span><span class="r">수량</span></div>${side('shnu', 'total_shnu_qty', 'up')}
        </div>
      </div>
      <div class="between" style="padding:12px 18px;font-size:13px"><span class="cap">외국계 합계 순매수</span><span class="mono ${cls(glob)}">${signed(glob)}주</span></div>`;
  }
  const loadMember = () => load('#memberBox', () => API.get('price/inquire_member', { code }), (el, d) => renderMember(el, d.output || {}));
  loadMember();

  // ── 프로그램 매매 ──
  let progKind = 'time';
  let progRows = [];
  const drawProgram = () => {
    const daily = progKind === 'daily';
    fill('#programRows', progRows, (p) => {
      const net = n(p.whol_smtn_ntby_qty);
      return `
        <div class="tr">
          <span class="mono">${daily ? md(p.stck_bsop_date) : hm(p.bsop_hour)}</span>
          <span class="mono r muted">${fmt(n(p.whol_smtn_seln_vol))}</span>
          <span class="mono r muted">${fmt(n(p.whol_smtn_shnu_vol))}</span>
          <span class="mono r ${cls(net)}">${signed(net)}</span>
        </div>`;
    });
  };
  const renderProgram = (kind) => {
    progKind = kind;
    const daily = kind === 'daily';
    $('#progApi').textContent = daily ? 'program_trade_by_stock_daily' : 'program_trade_by_stock';
    $('#progCol').textContent = daily ? '일자' : '시간';
    load('#programRows', () => API.get(daily ? 'price_anal/program_trade_by_stock_daily' : 'price_anal/program_trade_by_stock', { code }), (el, d) => {
      progRows = list(d.output);
      drawProgram();
    });
  };
  renderProgram('time');
  $('#progSeg').addEventListener('seg:change', (e) => renderProgram(e.detail));

  // ── 공매도 / 대차 ──
  const renderShort = (kind) => {
    const table = $('#shortTable');
    const start = KIS.daysAgo(45);
    if (kind === 'loan') {
      $('#shortApi').textContent = 'daily_loan_trans';
      table.innerHTML = '<div class="tr th"><span>일자</span><span class="r">신규(체결)</span><span class="r">상환</span><span class="r">잔고 (금액)</span></div><div id="shortRows" class="tbl-scroll" style="max-height:342px"></div>';
      load('#shortRows', () => API.get('price_anal/daily_loan_trans', { market: '3', code, start_date: start, end_date: KIS.ymd() }), (el, d) => {
        fill(el, list(d.output1), (r) => `
          <div class="tr">
            <span class="mono">${md(r.bsop_date)}</span>
            <span class="mono r">${fmt(n(r.new_stcn))}</span>
            <span class="mono r muted">${fmt(n(r.rdmp_stcn))}</span>
            <span class="mono r muted">${fmt(n(r.rmnd_stcn))} <span class="cap">(${unit(n(r.rmnd_amt) * 1e6)})</span></span>
          </div>`);
      });
    } else {
      $('#shortApi').textContent = 'daily_short_sale';
      table.innerHTML = '<div class="tr th"><span>일자</span><span class="r">공매도량</span><span class="r">거래 비중</span><span class="r">공매도 대금</span></div><div id="shortRows" class="tbl-scroll" style="max-height:342px"></div>';
      load('#shortRows', () => API.get('price_anal/daily_short_sale', { code, start_date: start, end_date: KIS.ymd() }), (el, d) => {
        fill(el, list(d.output2), (r) => `
          <div class="tr">
            <span class="mono">${md(r.stck_bsop_date)}</span>
            <span class="mono r">${fmt(n(r.ssts_cntg_qty))}</span>
            <span class="mono r muted">${fmt(n(r.ssts_vol_rlim), 2)}%</span>
            <span class="mono r muted">${unit(n(r.ssts_tr_pbmn))}</span>
          </div>`);
      });
    }
  };
  renderShort('short');
  $('#shortSeg').addEventListener('seg:change', (e) => renderShort(e.detail));

  // ── 실시간: 회원사 · 프로그램 매매 ──
  Live.connect({ member: [code], program: [code] }, {
    member(m) {
      // 실시간 필드명(seln2_/byov_) → REST(inquire_member) 필드명
      const o = { glob_ntby_qty: m.glob_ntby_qty };
      for (let i = 1; i <= 5; i += 1) {
        o[`seln_mbcr_name${i}`] = m[`seln2_mbcr_name${i}`];
        o[`shnu_mbcr_name${i}`] = m[`byov_mbcr_name${i}`];
        o[`total_seln_qty${i}`] = m[`total_seln_qty${i}`];
        o[`total_shnu_qty${i}`] = m[`total_shnu_qty${i}`];
        o[`seln_mbcr_glob_yn_${i}`] = m[`seln_mbcr_glob_yn_${i}`];
        o[`shnu_mbcr_glob_yn_${i}`] = m[`shnu_mbcr_glob_yn_${i}`];
      }
      renderMember($('#memberBox'), o);
      setTile('tGlob', n(m.glob_ntby_qty));
    },
    program(p) {
      // 실시간 값은 당일 누적 → 같은 분이면 맨 위 행을 바꾸고, 새 분이면 행을 추가
      setTile('tProg', n(p.ntby_cnqn));
      if (progKind !== 'time') return;
      const row = { bsop_hour: p.stck_cntg_hour, whol_smtn_seln_vol: p.seln_cnqn, whol_smtn_shnu_vol: p.shnu_cnqn, whol_smtn_ntby_qty: p.ntby_cnqn };
      if (progRows[0] && String(progRows[0].bsop_hour).slice(0, 4) === String(row.bsop_hour).slice(0, 4)) progRows[0] = row;
      else progRows.unshift(row);
      progRows = progRows.slice(0, 60);
      drawProgram();
    },
    resync() {
      loadMember();
      renderProgram(progKind);
    },
  });
};
