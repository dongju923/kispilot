/* 순위 분석 — ranking_anal.* 13종 */
window.renderPage = function () {
  const { esc, fmt, cls, pct, arrow, unit, fill, load, $, $$ } = UI;
  const { n, list } = KIS;

  // 결산 기준 순위는 직전 연도 결산 자료로 조회
  const fiscal = { fiscal_year: String(new Date().getFullYear() - 1), quarter: '3' };

  /* 열 포맷: int(정수), f2(소수 2자리), pct(%), eok(억원 값), won(원 값), text */
  const F = {
    int: (v) => fmt(n(v)),
    f2: (v) => fmt(n(v), 2),
    pct: (v) => (n(v) == null ? '—' : `${fmt(n(v), 2)}%`),
    eok: (v) => unit(n(v) * 1e8),
    won: (v) => unit(n(v)),
    text: (v) => esc(v || '—'),
  };

  /* 각 순위: 라벨 · 정렬 옵션(파라미터명, [값, 이름]) · 지원 필터 · 기본 파라미터 · 추가 열 */
  const RANKS = {
    // prc_cls 1 = 전일 종가 대비 (기본값 0 은 저가/고가 대비라 일반적인 등락률 순위와 다르다)
    fluctuation: { label: '등락률', group: '시세', sort: ['rank_sort_cls', [['0', '상승률', { prc_cls: '1' }], ['1', '하락률', { prc_cls: '1' }], ['4', '변동률', { prc_cls: '0' }]]],
      filters: ['price', 'vol', 'excl'], cols: [['거래량', 'acml_vol', 'int']] },
    volume_rank: { label: '거래량', group: '시세', sort: ['blng_cls', [['0', '평균거래량'], ['1', '거래증가율'], ['3', '거래금액']]],
      filters: ['price', 'vol', 'excl'], cols: [['거래량', 'acml_vol', 'int'], ['거래대금', 'acml_tr_pbmn', 'won']] },
    volume_power: { label: '체결강도', group: '시세', filters: ['price', 'vol', 'excl'], params: { vol_cnt: '100000' },
      cols: [['체결강도', 'tday_rltv', 'f2'], ['거래량', 'acml_vol', 'int']] },
    quote_balance: { label: '호가잔량', group: '시세', sort: ['rank_sort_cls', [['0', '순매수잔량'], ['1', '순매도잔량'], ['2', '매수비율'], ['3', '매도비율']]],
      filters: ['price', 'vol', 'excl'], cols: [['순매수잔량', 'total_ntsl_bidp_rsqn', 'int'], ['매수잔량비', 'shnu_rsqn_rate', 'pct']] },
    exp_trans_updown: { label: '예상체결 등락', group: '시세', sort: ['rank_sort_cls', [['0', '상승률'], ['3', '하락률'], ['5', '체결량'], ['6', '거래대금']]],
      filters: ['vol'], cols: [['예상체결량', 'cntg_vol', 'int'], ['예상거래대금', 'antc_tr_pbmn', 'won']],
      note: '장 시작 전(08:30~09:00)에는 장전 예상, 장 중에는 당일 시초가 단일가 결과가 나옵니다.' },
    market_cap: { label: '시가총액', group: '규모·재무', filters: ['price', 'vol', 'excl'],
      cols: [['시가총액', 'stck_avls', 'eok'], ['시장 비중', 'mrkt_whol_avls_rlim', 'pct']] },
    finance_ratio: { label: '재무비율', group: '규모·재무', params: fiscal,
      sort: ['rank_sort_cls', [['7', '자본경상이익률'], ['11', '자기자본비율'], ['12', '부채비율'], ['15', '매출액증가율'], ['17', '영업이익증가율']]],
      filters: ['price', 'vol', 'excl'], cols: [['부채비율', 'lblt_rate', 'pct'], ['매출증가율', 'grs', 'pct']],
      note: `${fiscal.fiscal_year}년 결산 기준` },
    profit_asset_index: { label: '수익자산지표', group: '규모·재무', params: fiscal,
      sort: ['rank_sort_cls', [['0', '매출이익'], ['1', '영업이익'], ['3', '당기순이익'], ['4', '자산총계']]],
      filters: ['price', 'vol', 'excl'], cols: [['영업이익', 'bsop_prti', 'eok'], ['당기순이익', 'thtr_ntin', 'eok']],
      note: `${fiscal.fiscal_year}년 결산 기준` },
    market_value: { label: '시장가치', group: '규모·재무', params: fiscal,
      sort: ['rank_sort_cls', [['23', 'PER'], ['24', 'PBR'], ['26', 'PSR'], ['30', 'EV/EBITDA']]],
      filters: ['price', 'vol', 'excl'], cols: [['PER', 'per', 'f2'], ['PBR', 'pbr', 'f2']],
      note: `${fiscal.fiscal_year}년 결산 기준 · 모든 항목이 큰 값부터 정렬됩니다 (저PER 순 조회 불가).` },
    disparity: { label: '이격도', group: '괴리·수급', sort: ['rank_sort_cls', [['0', '상위'], ['1', '하위']]],
      params: { hour_cls: '20' }, filters: ['price', 'vol', 'excl'], cols: [['20일 이격도', 'd20_dsrt', 'f2'], ['60일 이격도', 'd60_dsrt', 'f2']],
      skip: (r) => n(r.d20_dsrt) === 0 },
    prefer_disparate_ratio: { label: '우선주 괴리율', group: '괴리·수급', filters: ['price', 'vol'],
      cols: [['우선주', 'prst_kor_isnm', 'text'], ['괴리율', 'dprt', 'pct']] },
    credit_balance: { label: '신용잔고', group: '괴리·수급', out: 'output2',
      sort: ['rank_sort_cls', [['0', '융자 잔고비율'], ['2', '융자 잔고금액'], ['3', '융자 증가'], ['5', '대주 잔고비율']]],
      filters: [], cols: [['융자잔고율', 'whol_loan_rmnd_rate', 'pct'], ['잔고 증가율', 'nday_vrss_loan_rmnd_inrt', 'pct']] },
    short_sale: { label: '공매도', group: '괴리·수급', sort: ['period_div', [['D', '일간'], ['M', '월간']]],
      filters: ['price', 'excl'], cols: [['공매도량', 'ssts_cntg_qty', 'int'], ['거래 비중', 'ssts_vol_rlim', 'pct']],
      note: '전 영업일 기준 집계입니다.' },
  };

  let active = 'fluctuation';
  let sortValue = null;
  let market = '0000';

  // 서브 내비
  const groups = [...new Set(Object.values(RANKS).map((r) => r.group))];
  $('#rankNav').innerHTML = groups.map((g) => `
    <div class="col" style="gap:2px">
      <div class="subnav__label">${esc(g)}</div>
      ${Object.entries(RANKS).filter(([, r]) => r.group === g).map(([fn, r]) => `
        <button type="button" class="subnav__item" data-fn="${fn}">
          <span>${esc(r.label)}</span><span class="mono">${fn}</span>
        </button>`).join('')}
    </div>`).join('');

  function exclCode() {
    // 투자위험/경고/주의, 관리종목, 정리매매, 불성실공시, 우선주, 거래정지, ETF, ETN, 신용주문불가, SPAC
    const bits = Array(10).fill('0');
    if ($('#exWarn').checked) { bits[0] = '1'; bits[1] = '1'; bits[5] = '1'; }
    if ($('#exPref').checked) bits[4] = '1';
    if ($('#exEtf').checked) { bits[6] = '1'; bits[7] = '1'; bits[9] = '1'; }
    return bits.join('');
  }

  function selectRank(fn) {
    active = fn;
    const cfg = RANKS[fn];
    $$('[data-fn]', $('#rankNav')).forEach((x) => {
      if (x.dataset.fn === fn) x.setAttribute('aria-current', 'true');
      else x.removeAttribute('aria-current');
    });
    $('#rankTitle').textContent = `${cfg.label} 순위`;
    $('#rankApi').textContent = fn;

    // 정렬 옵션
    $('#sortField').hidden = !cfg.sort;
    sortValue = cfg.sort ? cfg.sort[1][0][0] : null;
    $('#sortSeg').innerHTML = cfg.sort
      ? cfg.sort[1].map(([v, label], i) => `<button type="button" data-value="${v}" class="${i === 0 ? 'on' : ''}">${esc(label)}</button>`).join('')
      : '';
    // 지원 필터만 노출
    $('#priceField').hidden = !cfg.filters.includes('price');
    $('#volField').hidden = !cfg.filters.includes('vol');
    $('#exclField').hidden = !cfg.filters.includes('excl');
    $('#rankNote').hidden = !cfg.note;
    $('#rankNote').textContent = cfg.note || '';
    run();
  }

  function params() {
    const cfg = RANKS[active];
    const p = { ...(cfg.params || {}), sector_code: market };
    if (cfg.sort) {
      p[cfg.sort[0]] = sortValue;
      const opt = cfg.sort[1].find(([v]) => v === sortValue);
      Object.assign(p, (opt && opt[2]) || {});
    }
    if (cfg.filters.includes('price')) {
      p.price_1 = $('#pmin').value.replace(/[^\d]/g, '');
      p.price_2 = $('#pmax').value.replace(/[^\d]/g, '');
    }
    if (cfg.filters.includes('vol')) {
      const v = $('#vmin').value.replace(/[^\d]/g, '');
      if (v) p.vol_cnt = v;
    }
    if (cfg.filters.includes('excl')) p.trgt_exls_cls = exclCode();
    return p;
  }

  function run() {
    const cfg = RANKS[active];
    const cols = `44px minmax(0, 1.8fr) repeat(${3 + cfg.cols.length}, minmax(0, 1fr)) 56px`;
    const table = $('#rankTable');
    table.style.setProperty('--cols', cols);
    table.innerHTML = `
      <div class="tr th"><span>순위</span><span>종목</span><span class="r">현재가</span><span class="r">전일대비</span><span class="r">등락률</span>
        ${cfg.cols.map(([label]) => `<span class="r">${esc(label)}</span>`).join('')}<span class="r">관심</span></div>
      <div id="rankRows"></div>`;
    load('#rankRows', () => API.get(`ranking_anal/${active}`, params()), (el, d) => {
      let rows = list(d[cfg.out || 'output']);
      if (cfg.skip) rows = rows.filter((r) => !cfg.skip(r));
      fill(el, rows, (r, i) => {
        const code = r.mksc_shrn_iscd || r.stck_shrn_iscd;
        const diff = n(r.prdy_vrss);
        return `
          <div class="tr">
            <span class="mono cap" style="font-size:13px">${esc(r.data_rank || i + 1)}</span>
            <a class="name-code" href="stock.html?code=${esc(code)}"><b>${esc(r.hts_kor_isnm)}</b><span class="mono cap">${esc(code)}</span></a>
            <span class="mono r">${fmt(n(r.stck_prpr))}</span>
            <span class="mono r ${cls(diff)}">${arrow(diff)}</span>
            <span class="mono r ${cls(n(r.prdy_ctrt))}" style="font-weight:500">${pct(n(r.prdy_ctrt))}</span>
            ${cfg.cols.map(([, key, f]) => `<span class="${f === 'text' ? 'r' : 'mono r muted'}">${F[f](r[key])}</span>`).join('')}
            <span style="display:flex;justify-content:flex-end">${UI.starButton(code, r.hts_kor_isnm, true)}</span>
          </div>`;
      }, '조건에 맞는 종목이 없습니다.');
      $('#rankCount').textContent = `${rows.length}종목`;
      $('#rankTime').textContent = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    });
  }

  $('#rankNav').addEventListener('click', (e) => {
    const b = e.target.closest('[data-fn]');
    if (b && b.dataset.fn !== active) selectRank(b.dataset.fn);
  });
  $('#sortSeg').addEventListener('seg:change', (e) => { sortValue = e.detail; run(); });
  $('#marketSeg').addEventListener('seg:change', (e) => { market = e.detail; run(); });
  $('#refreshBtn').addEventListener('click', run);
  $('#rankFilters').addEventListener('submit', (e) => { e.preventDefault(); run(); });

  const fromUrl = new URLSearchParams(location.search).get('fn');
  selectRank(RANKS[fromUrl] ? fromUrl : 'fluctuation');
};
