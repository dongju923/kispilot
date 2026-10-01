/* 종목 분석 — 재무·기업정보 탭 */
window.renderPage = async function () {
  const { esc, fmt, unit, load, $ } = UI;
  const { n, nf, list, first, dotDate, yymm } = KIS;
  const code = await API.currentCode('005930');

  load('#stockHead', () => API.loadStock(code), (el, s) => {
    document.title = `${s.name} · 재무·기업정보 · KISPilot`;
    UI.stockHeader(el, s, { compact: true });
  });

  // ── 기업 기본정보 ──
  const MARKET = { STK: '유가증권시장', KSQ: '코스닥', KNX: '코넥스' };
  const yn = (v, yes, no) => (v === 'Y' ? yes : v === 'N' ? no : '—');
  load('#companyInfo', () => API.get('info/search_stock_info', { code }), (el, d) => {
    const o = d.output || {};
    const listed = o.scts_mket_lstg_dt || o.kosdaq_mket_lstg_dt || o.frbd_mket_lstg_dt;
    const rows = [
      ['종목명', o.prdt_abrv_name || o.prdt_name],
      ['영문명', o.prdt_eng_name],
      ['시장', MARKET[o.mket_id_cd] || o.mket_id_cd],
      ['업종', o.idx_bztp_scls_cd_name || o.idx_bztp_mcls_cd_name],
      ['표준산업분류', o.std_idst_clsf_cd_name],
      ['상장일', dotDate(listed)],
      ['결산월', o.setl_mmdd ? `${Number(o.setl_mmdd.slice(0, 2))}월` : '—'],
      ['액면가', n(o.papr) ? `${fmt(n(o.papr))}원` : '—'],
      ['상장주식수', n(o.lstg_stqt) ? `${fmt(n(o.lstg_stqt))}주` : '—'],
      ['자본금', unit(n(o.cpta))],
      ['KOSPI200', yn(o.kospi200_item_yn, '편입', '미편입')],
      ['거래정지', yn(o.tr_stop_yn, '정지', '정상')],
      ['관리종목', yn(o.admn_item_yn, '지정', '해당 없음')],
    ];
    el.innerHTML = `<dl class="kv-list">${rows.map(([k, v]) => `<div class="kv" style="min-height:40px"><dt>${esc(k)}</dt><dd>${esc(v || '—')}</dd></div>`).join('')}</dl>`;
  });

  // ── 재무제표 ──
  const STMT = {
    income: {
      api: 'income_statement',
      rows: [['매출액', 'sale_account', 1], ['매출원가', 'sale_cost'], ['매출총이익', 'sale_totl_prfi'], ['영업이익', 'bsop_prti', 1], ['경상이익', 'op_prfi'], ['당기순이익', 'thtr_ntin', 1]],
    },
    balance: {
      api: 'balance_sheet',
      rows: [['유동자산', 'cras'], ['고정자산', 'fxas'], ['자산총계', 'total_aset', 1], ['유동부채', 'flow_lblt'], ['고정부채', 'fix_lblt'], ['부채총계', 'total_lblt', 1], ['자본금', 'cpfn'], ['자본총계', 'total_cptl', 1]],
    },
  };
  let stmt = 'income';
  let period = '0';

  const renderStatement = () => {
    const cfg = STMT[stmt];
    $('#stmtApi').textContent = cfg.api;
    $('#finNote').textContent = period === '1' ? '단위: 억원 · 분기 손익은 연 누적 값' : '단위: 억원';
    load('#finTable', () => API.get(`info/${cfg.api}`, { code, div_cls: period }), (el, d) => {
      // 응답은 최신순 → 최근 4개를 오래된 것부터
      const cols = list(d.output).slice(0, 4).reverse();
      if (!cols.length) { el.innerHTML = UI.stateHtml('empty', '재무 자료가 없습니다.'); return; }
      el.style.setProperty('--cols', `minmax(0, 1.4fr) repeat(${cols.length}, minmax(0, 1fr))`);
      el.innerHTML = `
        <div class="tr th"><span>항목</span>${cols.map((c) => `<span class="r">${yymm(c.stac_yymm)}</span>`).join('')}</div>
        ${cfg.rows.map(([label, key, strong]) => `
          <div class="tr" style="min-height:40px;${strong ? 'font-weight:500' : ''}">
            <span>${label}</span>${cols.map((c) => `<span class="mono r">${fmt(nf(c[key]))}</span>`).join('')}
          </div>`).join('')}`;
    });
  };

  // ── 투자 지표 (각 API 의 최신 행) ──
  const renderRatios = () => {
    const call = (api) => API.get(`info/${api}`, { code, div_cls: period }).then((d) => first(d.output)).catch(() => ({}));
    load('#ratioGroups', () => Promise.all(['financial_ratio', 'profit_ratio', 'stability_ratio', 'growth_ratio', 'other_major_ratios'].map(call)),
      (el, [fin, prof, stab, grow, other]) => {
        const base = fin.stac_yymm || prof.stac_yymm;
        $('#ratioBase').textContent = base ? `${yymm(base)} 기준` : '최근 결산 기준';
        const p = (v) => (nf(v) == null ? '—' : `${fmt(nf(v), 2)}%`);
        const x = (v, d = 2) => fmt(nf(v), d);
        const groups = [
          ['수익성 · 성장성', [
            ['ROE', p(fin.roe_val)], ['매출총이익률', p(prof.sale_totl_rate)], ['매출액순이익률', p(prof.sale_ntin_rate)],
            ['매출액 증가율', p(fin.grs)], ['영업이익 증가율', p(fin.bsop_prfi_inrt)],
          ]],
          ['안정성 · 가치', [
            ['부채비율', p(stab.lblt_rate || fin.lblt_rate)], ['유동비율', p(stab.crnt_rate)], ['유보율', p(fin.rsrv_rate)],
            ['EPS · BPS', `${x(fin.eps, 0)} · ${x(fin.bps, 0)}`], ['EV/EBITDA', x(other.ev_ebitda)],
          ]],
          ['기타', [
            ['차입금 의존도', p(stab.bram_depn)], ['자기자본 증가율', p(grow.equt_inrt)], ['총자산 증가율', p(grow.totl_aset_inrt)],
            ['주당매출액', x(fin.sps, 0)], ['EBITDA (억원)', x(other.ebitda, 0)],
          ]],
        ];
        el.innerHTML = groups.map(([label, items]) => `
          <div class="col" style="gap:8px">
            <span class="cap" style="font-weight:500">${esc(label)}</span>
            <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr));gap:10px">
              ${items.map(([k, v]) => `<div class="ratio"><span class="cap">${esc(k)}</span><span class="mono">${esc(v)}</span></div>`).join('')}
            </div>
          </div>`).join('');
      });
  };

  renderStatement();
  renderRatios();
  $('#stmtSeg').addEventListener('seg:change', (e) => { stmt = e.detail; renderStatement(); });
  $('#periodSeg').addEventListener('seg:change', (e) => { period = e.detail; renderStatement(); renderRatios(); });
};
