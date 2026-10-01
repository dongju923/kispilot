/* 차트 도구 모음 — 이동평균 · 차트 지표 · 보조 차트 선택 메뉴.
 *
 *   ChartTools.mount({ toolbar, legend, panes, chart });   // chart = PriceChart.create(...)
 *
 * 선택이 바뀌면 chart.setIndicators() 로 넘기고, 계산·그리기는 chart.js + indicators.js 가 한다.
 *   - 이동평균: 계산 방식(단순·지수·가중) + 기간 MA5·20·60·120
 *   - 차트 지표: 가격 위에 겹쳐 그림 (볼린저밴드, Envelope, Parabolic SAR)
 *   - 보조 차트: 선택한 순서대로 가격 차트 아래 칸으로 쌓임. '거래량' 은 가격 차트 아래 막대.
 *
 * 지표: 가격 위에 겹쳐 그리는 지표(볼린저밴드, Envelope, Parabolic SAR, 일목균형표)와 보조 차트 지표 30여 종.
 * 선택 상태는 브라우저에 저장된다(localStorage 'pykis.chartTools').
 */
(function () {
  const KEY = 'pykis.chartTools';
  const { esc } = UI;

  const MA_DESC = { 5: '1주', 20: '1개월', 60: '3개월', 120: '6개월' };
  const MA_TYPES = [['sma', '단순', 'MA'], ['ema', '지수', 'EMA'], ['wma', '가중', 'WMA']];

  const OVERLAYS = [
    ['bb', '볼린저밴드', '20, 2σ', '#1D9BB0'],
    ['env', 'Envelope', '20, ±5%', '#B07A1D'],
    ['psar', 'Parabolic SAR', '0.02, 0.2', '#5E6470'],
    ['ichimoku', '일목균형표', '9, 26, 52', '#e67e22'],
  ];

  const SUB = [
    ['추세', [['macd', 'MACD', '12, 26, 9'], ['ppo', 'PPO', ''], ['trix', 'TRIX', '15'], ['dmi', 'DMI · ADX · ADXR', '14'],
      ['aroon', 'Aroon · Aroon Osc', '25'], ['sonar', 'SONAR', '10, 5'], ['mass', 'Mass Index', '25']]],
    ['모멘텀', [['rsi', 'RSI', '14'], ['stof', 'Stochastic Fast', '14, 3'], ['stos', 'Stochastic Slow', '14, 3, 3'],
      ['storsi', 'Stochastic RSI', ''], ['cci', 'CCI', '20'], ['wr', 'Williams %R', '14'], ['mom', '모멘텀', '10'],
      ['roc', 'ROC', '12'], ['disp', '이격도', '20'], ['psy', '투자심리도', '12'], ['uo', 'Ultimate Oscillator', '7, 14, 28'],
      ['elder', 'Elder Ray', '']]],
    ['거래량', [['vol', '거래량', ''], ['obv', 'OBV', ''], ['vr', 'Volume Ratio', '20'], ['ad', 'AD Line', ''],
      ['cmf', 'CMF', '20'], ['mfi', 'MFI', '14'], ['chosc', 'Chaikin Oscillator', ''], ['pvo', 'PVO', ''], ['pvi', 'PVI', ''],
      ['nvi', 'NVI', ''], ['force', 'Force Index', '13'], ['eom', 'EOM', '14']]],
    ['변동성', [['atr', 'ATR', '14'], ['chvol', 'Chaikin Volatility', '']]],
  ];
  const SUB_BY_ID = {};
  SUB.forEach(([, items]) => items.forEach(([id, name, params]) => { SUB_BY_ID[id] = { id, name, params }; }));

  const DEFAULT = { maType: 'sma', ma: { 5: true, 20: true, 60: true, 120: true }, overlay: {}, sub: ['vol', 'macd'] };

  function loadState() {
    try {
      const s = JSON.parse(API.store.get(KEY));
      if (s && s.ma) return { ...DEFAULT, ...s, sub: (s.sub || []).filter((id) => SUB_BY_ID[id]) };
    } catch (e) { /* 저장값 없음/손상 → 기본값 */ }
    return JSON.parse(JSON.stringify(DEFAULT));
  }

  const chevron = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

  function mount({ toolbar, legend, panes, chart }) {
    let s = loadState();
    let query = '';
    const MAS = PriceChart.MAS;
    const prefix = () => (MA_TYPES.find(([id]) => id === s.maType) || MA_TYPES[0])[2];
    const save = () => API.store.set(KEY, JSON.stringify(s));

    // ── 골격 ──
    const dd = (id, label, width, body) => `
      <div class="dd" data-dd="${id}">
        <button type="button" class="ddb" aria-haspopup="true" aria-expanded="false" aria-controls="ddp-${id}">${label}<span class="cnt" data-cnt="${id}"></span>${chevron}</button>
        <div class="ddp" id="ddp-${id}" style="width:${width}px" role="group" aria-label="${label} 선택" hidden>${body}</div>
      </div>`;

    const maBody = `
      <div class="ddh">계산 방식</div>
      <div class="seg" role="group" aria-label="이동평균 계산 방식" style="margin:0 4px;align-self:flex-start" data-matype>
        ${MA_TYPES.map(([id, label]) => `<button type="button" data-value="${id}">${label}</button>`).join('')}
      </div>
      <div class="ddh">기간</div>
      <div class="col" style="gap:0">
        ${MAS.map(([p, color]) => `
          <label class="opt"><input type="checkbox" data-ma="${p}"><span class="sw" style="background:${color}"></span><span class="mono" data-ma-label="${p}"></span><span class="cap ml-auto">${MA_DESC[p] || ''}</span></label>`).join('')}
      </div>
      <div class="ddf"><button type="button" class="lnk" data-ma-all="1">전체 선택</button><button type="button" class="lnk" data-ma-all="0">전체 해제</button></div>`;

    const ovBody = `
      <div class="ddh">가격 차트 위에 겹쳐 그리기</div>
      <div class="col" style="gap:0">
        ${OVERLAYS.map(([id, label, params, color]) => `
          <label class="opt"><input type="checkbox" data-ov="${id}"><span class="swd" style="border-color:${color}"></span><span>${esc(label)}</span><span class="mono cap ml-auto">${esc(params)}</span></label>`).join('')}
      </div>`;

    const subBody = `
      <label class="srch">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6B717C" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input type="search" aria-label="보조지표 검색" placeholder="지표 검색 (예: RSI, Stochastic)" data-sub-q>
      </label>
      <div data-sub-list style="max-height:292px;overflow-y:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 16px;align-items:start"></div>
      <div class="ddf"><span class="cap">선택한 순서대로 가격 차트 아래에 쌓입니다</span><button type="button" class="lnk ml-auto" data-sub-none>전체 해제</button></div>`;

    toolbar.innerHTML = dd('ma', '이동평균', 272, maBody) + dd('overlay', '차트 지표', 288, ovBody) + dd('sub', '보조 차트', 520, subBody);
    const $ = (sel) => toolbar.querySelector(sel);
    const $$ = (sel) => Array.from(toolbar.querySelectorAll(sel));

    // ── 그리기 ──
    function renderSubList() {
      const q = query.trim().toLowerCase();
      $('[data-sub-list]').innerHTML = SUB.map(([group, items]) => {
        const shown = items.filter(([, name]) => !q || name.toLowerCase().includes(q));
        if (!shown.length) return '';
        return `<div class="col" style="gap:0"><div class="ddh">${esc(group)}</div>${shown.map(([id, name, params]) => `
          <label class="opt"><input type="checkbox" data-sub="${id}" ${s.sub.includes(id) ? 'checked' : ''}><span>${esc(name)}</span><span class="mono cap ml-auto">${esc(params)}</span></label>`).join('')}</div>`;
      }).join('') || '<div class="cap" style="padding:8px">검색 결과가 없습니다.</div>';
    }

    function render() {
      // 개수 배지
      const counts = { ma: MAS.filter(([p]) => s.ma[p]).length, overlay: OVERLAYS.filter(([id]) => s.overlay[id]).length, sub: s.sub.length };
      Object.entries(counts).forEach(([id, n]) => {
        const el = $(`[data-cnt="${id}"]`);
        el.textContent = n;
        el.classList.toggle('zero', !n);
      });
      // 메뉴 안 체크 상태
      $$('[data-matype] button').forEach((b) => b.classList.toggle('on', b.dataset.value === s.maType));
      MAS.forEach(([p]) => {
        $(`[data-ma="${p}"]`).checked = !!s.ma[p];
        $(`[data-ma-label="${p}"]`).textContent = prefix() + p;
      });
      OVERLAYS.forEach(([id]) => { $(`[data-ov="${id}"]`).checked = !!s.overlay[id]; });
      renderSubList();

      // 가격 차트 위 범례
      const maOn = MAS.filter(([p]) => s.ma[p]).map(([p, color]) => `<span class="lg"><span class="sw" style="background:${color}"></span><span class="mono">${prefix()}${p}</span></span>`);
      const ovOn = OVERLAYS.filter(([id]) => s.overlay[id]).map(([, label, params, color]) => `<span class="lg"><span class="swd" style="border-color:${color}"></span>${esc(label)} <span class="mono cap">${esc(params)}</span></span>`);
      legend.innerHTML = [...maOn, ...ovOn].join('') || '<span class="cap">표시 중인 지표 없음</span>';

      // 차트에 반영 (보조 차트 칸은 chart.js 가 panes 안에 만든다. '거래량' 은 가격 차트 아래 막대)
      chart.setIndicators({
        maType: s.maType,
        ma: { ...s.ma },
        overlays: OVERLAYS.filter(([id]) => s.overlay[id]).map(([id]) => id),
        subs: s.sub.filter((id) => id !== 'vol').map((id) => SUB_BY_ID[id]),
        volume: s.sub.includes('vol'),
      });
    }

    const update = (fn) => { fn(); save(); render(); };

    // ── 메뉴 열고 닫기 (한 번에 하나) ──
    const closeAll = () => $$('.dd').forEach((d) => {
      d.querySelector('.ddb').setAttribute('aria-expanded', 'false');
      d.querySelector('.ddp').hidden = true;
    });
    toolbar.addEventListener('click', (e) => {
      const btn = e.target.closest('.ddb');
      if (!btn) return;
      const wasOpen = btn.getAttribute('aria-expanded') === 'true';
      closeAll();
      if (!wasOpen) {
        btn.setAttribute('aria-expanded', 'true');
        btn.parentElement.querySelector('.ddp').hidden = false;
      }
    });
    document.addEventListener('click', (e) => { if (!toolbar.contains(e.target)) closeAll(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAll(); });

    // ── 선택 이벤트 ──
    toolbar.addEventListener('change', (e) => {
      const t = e.target;
      if (t.dataset.ma) update(() => { s.ma = { ...s.ma, [t.dataset.ma]: t.checked }; });
      if (t.dataset.ov) update(() => { s.overlay = { ...s.overlay, [t.dataset.ov]: t.checked }; });
      if (t.dataset.sub) update(() => { s.sub = t.checked ? [...s.sub, t.dataset.sub] : s.sub.filter((x) => x !== t.dataset.sub); });
    });
    toolbar.addEventListener('click', (e) => {
      const all = e.target.closest('[data-ma-all]');
      if (all) update(() => { const v = all.dataset.maAll === '1'; s.ma = Object.fromEntries(MAS.map(([p]) => [p, v])); });
      if (e.target.closest('[data-sub-none]')) update(() => { s.sub = []; });
    });
    $('[data-matype]').addEventListener('seg:change', (e) => update(() => { s.maType = e.detail; }));
    $('[data-sub-q]').addEventListener('input', (e) => { query = e.target.value; renderSubList(); });
    panes.addEventListener('click', (e) => {
      const x = e.target.closest('[data-sub-remove]');
      if (x) update(() => { s.sub = s.sub.filter((id) => id !== x.dataset.subRemove); });
    });

    render();
    return { state: () => s };
  }

  window.ChartTools = { mount };
})();
