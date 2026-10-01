/* 백테스트 — 기본 전략 / 커스텀 전략을 종목·기간·초기 자본으로 돌려 성과와 거래 내역을 보여준다.
 *
 *   GET  /api/backtest/options                 기본 전략 · 지표 카탈로그 · 저장된 커스텀 전략
 *   POST /api/backtest/run                     실행 (계산은 서버: src/kispilot/app/utils/backtest.py)
 *   GET/POST/DELETE /api/backtest/strategies   커스텀 전략 저장·불러오기·삭제
 *
 * 설정은 브라우저에 저장된다(localStorage 'pykis.backtest').
 */
window.renderPage = async function () {
  const { esc, fmt, cls, $, $$, toast } = UI;
  const LS_KEY = 'pykis.backtest';
  const RISK_KEYS = [['stop_loss', '손절', '진입가 대비 하락'], ['take_profit', '익절', '진입가 대비 상승'], ['trailing_stop', '트레일링 스탑', '보유 중 고점 대비 하락']];
  const REASON_COLOR = { signal: '#3D424B', stop_loss: '#1D5BD6', take_profit: '#C88A12', trailing_stop: '#7B3FC4', open_at_end: '#6B717C' };
  const IND_COLORS = ['#E8890C', '#7B3FC4', '#1D9BB0', '#2E9E5B', '#C6302A', '#5E6470', '#B07A1D', '#1D5BD6'];
  const isNum = (x) => typeof x === 'number' && Number.isFinite(x);
  const sgnPct = (x, d = 2) => (isNum(x) ? `${x > 0 ? '+' : x < 0 ? '−' : ''}${fmt(Math.abs(x), d)}%` : '—');
  const toNum = (v) => { const x = Number(String(v ?? '').replace(/[^\d.\-]/g, '')); return Number.isFinite(x) ? x : NaN; };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const dot = (s) => (s ? s.replace(/-/g, '.') : '—');
  const short = (s) => (s ? s.slice(2).replace(/-/g, '.') : '—');

  // ── 옵션 ─────────────────────────────────
  let opts;
  try {
    opts = await API.get('backtest/options');
  } catch (e) {
    $('#btForm').innerHTML = UI.errorHtml(e);
    return;
  }
  const STRAT = Object.fromEntries(opts.strategies.map((s) => [s.id, s]));
  const IND = Object.fromEntries(opts.indicators.map((i) => [i.key, i]));
  const IND_CATS = [...new Set(opts.indicators.map((i) => i.category))];
  const OPS = opts.operators;
  const CANDLE = opts.candle_signals;
  const PRICE = opts.price_fields;
  const isCandle = (key) => IND[key] && IND[key].category === '캔들스틱';

  // ── 상태 ─────────────────────────────────
  const defaultCustom = () => ({
    name: '나의 커스텀 전략', description: '',
    indicators: [{ id: 'sma_5', indicator: 'sma', params: { period: 5 } }, { id: 'sma_20', indicator: 'sma', params: { period: 20 } }],
    entry: { logic: 'and', conditions: [{ left: { type: 'indicator', ref: 'sma_5' }, operator: 'cross_up', right: { type: 'indicator', ref: 'sma_20' } }] },
    exit: { logic: 'and', conditions: [{ left: { type: 'indicator', ref: 'sma_5' }, operator: 'cross_down', right: { type: 'indicator', ref: 'sma_20' } }] },
  });
  const defaults = () => {
    const end = new Date();
    const start = new Date(end); start.setFullYear(end.getFullYear() - 5);
    return {
      kind: 'basic', basicId: 'sma_crossover', basicParams: {}, custom: defaultCustom(), savedFile: '',
      code: '005930', period: '5', start: iso(start), end: iso(end), capital: 10000000, bench: '0001',
      risk: { stop_loss: { enabled: false, pct: 5 }, take_profit: { enabled: false, pct: 10 }, trailing_stop: { enabled: false, pct: 5 } },
      fee: { ...opts.fee_defaults },
    };
  };
  let st = defaults();
  try {
    const saved = JSON.parse(API.store.get(LS_KEY) || 'null');
    if (saved && typeof saved === 'object') st = { ...st, ...saved, risk: { ...st.risk, ...saved.risk }, fee: { ...st.fee, ...saved.fee } };
  } catch (e) { /* 손상된 저장값 → 기본값 */ }
  if (!STRAT[st.basicId]) st.basicId = opts.strategies[0].id;
  const urlCode = new URLSearchParams(location.search).get('code');
  if (urlCode && /^[0-9A-Z]{6}$/i.test(urlCode)) st.code = urlCode.toUpperCase();
  // 기간 빠른 선택은 오늘 기준으로 다시 계산
  if (st.period && st.period !== 'custom') applyPeriod(st.period, false);
  let saveTimer;
  const persist = () => { clearTimeout(saveTimer); saveTimer = setTimeout(() => API.store.set(LS_KEY, JSON.stringify(st)), 200); };

  function applyPeriod(p, render = true) {
    st.period = p;
    const end = new Date();
    st.end = iso(end);
    if (p === 'max') st.start = '1980-01-01';
    else { const s = new Date(end); s.setFullYear(end.getFullYear() - Number(p)); st.start = iso(s); }
    if (render) renderPeriod();
  }

  // ── 전략 종류 탭 ─────────────────────────
  function renderKind() {
    $$('#kindTabs [data-kind]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.kind === st.kind)));
    $('#basicPane').hidden = st.kind !== 'basic';
    $('#customPane').hidden = st.kind !== 'custom';
    renderRiskBadge();
  }
  $('#kindTabs').addEventListener('click', (e) => {
    const b = e.target.closest('[data-kind]');
    if (!b) return;
    st.kind = b.dataset.kind;
    renderKind();
    persist();
  });

  // ── 기본 전략 ────────────────────────────
  const paramsOf = (sid) => ({ ...Object.fromEntries(STRAT[sid].params.map((p) => [p.name, p.default])), ...(st.basicParams[sid] || {}) });
  const riskText = (r) => (r ? [r.stop_loss_pct && `손절 ${r.stop_loss_pct}%`, r.take_profit_pct && `익절 ${r.take_profit_pct}%`, r.trailing_stop_pct && `트레일링 ${r.trailing_stop_pct}%`].filter(Boolean).join(' · ') : '');

  function renderBasicList() {
    $('#stratCount').textContent = `${opts.strategies.length}개`;
    $('#stratList').innerHTML = opts.categories.map((c) => {
      const items = opts.strategies.filter((s) => s.category === c.key);
      if (!items.length) return '';
      return `<div class="grp">${esc(c.label)}</div>${items.map((s) => `
        <label class="strat-row"><input type="radio" name="basicStrat" value="${esc(s.id)}" ${s.id === st.basicId ? 'checked' : ''}>
          <span>${esc(s.label)}</span>${s.default_risk ? `<span class="badge">${esc(riskText(s.default_risk))}</span>` : ''}</label>`).join('')}`;
    }).join('');
  }

  function renderBasicDetail() {
    const s = STRAT[st.basicId];
    const pv = paramsOf(s.id);
    $('#basicDetail').innerHTML = `
      <div class="row" style="gap: 8px"><b style="font-size: 14px">${esc(s.label)}</b><span class="badge ml-auto">${esc(s.category_label)}</span></div>
      <p class="cap" style="margin: 0; line-height: 1.55; color: var(--ink-2)">${esc(s.description)}</p>
      <div class="pgrid">${s.params.map((p) => `
        <label>${esc(p.label)}<input class="input sm mono r" data-bparam="${esc(p.name)}" type="number" min="${p.min}" max="${p.max}" step="${p.step}" value="${pv[p.name]}">
          <span class="cap mono" style="font-size: 11px">${p.min} ~ ${p.max}</span></label>`).join('')}</div>`;
  }

  function applyDefaultRisk(s) {
    if (!s.default_risk) return;
    const r = s.default_risk;
    st.risk.stop_loss = { enabled: r.stop_loss_pct != null, pct: r.stop_loss_pct ?? st.risk.stop_loss.pct };
    st.risk.take_profit = { enabled: r.take_profit_pct != null, pct: r.take_profit_pct ?? st.risk.take_profit.pct };
    st.risk.trailing_stop = { enabled: r.trailing_stop_pct != null, pct: r.trailing_stop_pct ?? st.risk.trailing_stop.pct };
    renderRisk();
  }

  $('#stratList').addEventListener('change', (e) => {
    if (e.target.name !== 'basicStrat') return;
    st.basicId = e.target.value;
    applyDefaultRisk(STRAT[st.basicId]);
    renderBasicDetail();
    renderRiskBadge();
    persist();
  });
  $('#basicDetail').addEventListener('change', (e) => {
    const name = e.target.dataset.bparam;
    if (!name) return;
    const p = STRAT[st.basicId].params.find((x) => x.name === name);
    let v = toNum(e.target.value);
    if (!Number.isFinite(v)) v = p.default;
    v = Math.min(p.max, Math.max(p.min, p.type === 'int' ? Math.round(v) : v));
    e.target.value = v;
    st.basicParams[st.basicId] = { ...(st.basicParams[st.basicId] || {}), [name]: v };
    persist();
  });

  // ── 커스텀 전략 ──────────────────────────
  const C = () => st.custom;
  const indLabel = (inst) => {
    const meta = IND[inst.indicator];
    const ps = meta ? meta.params.map((p) => inst.params?.[p.name] ?? p.default).join(', ') : '';
    return `${meta ? meta.label : inst.indicator}${ps ? ` (${ps})` : ''}`;
  };
  function autoId(key, params, except) {
    const period = params.period;
    const base = typeof period === 'number' ? `${key}_${Math.round(period)}` : key;
    const used = new Set(C().indicators.filter((i) => i !== except).map((i) => i.id));
    let id = base;
    for (let n = 2; used.has(id); n += 1) id = `${base}_${n}`;
    return id;
  }
  const renameRefs = (from, to) => ['entry', 'exit'].forEach((g) => C()[g].conditions.forEach((c) => {
    ['left', 'right'].forEach((side) => { if (c[side] && c[side].type === 'indicator' && c[side].ref === from) c[side].ref = to; });
  }));

  function renderSaved() {
    $('#savedSel').innerHTML = `<option value="">— 저장 안 한 전략 —</option>${opts.saved.map((s) => `<option value="${esc(s.file)}" ${s.file === st.savedFile ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}`;
    $('#delCustom').disabled = !st.savedFile;
  }

  function operandOptions(selected, { allowValue }) {
    const inds = C().indicators.map((i) => `<option value="i:${esc(i.id)}" ${selected === `i:${i.id}` ? 'selected' : ''}>${esc(i.id)}</option>`).join('');
    const prices = PRICE.map((p) => `<option value="p:${p.key}" ${selected === `p:${p.key}` ? 'selected' : ''}>${esc(p.label)}</option>`).join('');
    return `${inds ? `<optgroup label="지표">${inds}</optgroup>` : ''}<optgroup label="가격">${prices}</optgroup>${allowValue ? `<option value="v" ${selected === 'v' ? 'selected' : ''}>값 입력</option>` : ''}`;
  }
  const opKey = (o) => (!o ? '' : o.type === 'indicator' ? `i:${o.ref}` : o.type === 'price' ? `p:${o.field}` : 'v');
  const fromKey = (k, value) => (k.startsWith('i:') ? { type: 'indicator', ref: k.slice(2) } : k.startsWith('p:') ? { type: 'price', field: k.slice(2) } : { type: 'value', value: Number(value) || 0 });
  const instOf = (o) => (o && o.type === 'indicator' ? C().indicators.find((i) => i.id === o.ref) : null);

  function renderConditions() {
    const groups = [['entry', '진입', 'tag-b', '진입 조건'], ['exit', '청산', 'tag-s', '청산 조건 (선택)']];
    $('#condGroups').innerHTML = groups.map(([g, title, tagCls, aria]) => {
      const grp = C()[g];
      const rows = grp.conditions.map((c, k) => {
        const inst = instOf(c.left);
        const candle = inst && isCandle(inst.indicator);
        const opSel = candle
          ? CANDLE.map((o) => `<option value="${o.key}" ${c.candle_signal === o.key ? 'selected' : ''}>${esc(o.label)}</option>`).join('')
          : OPS.map((o) => `<option value="${o.key}" ${c.operator === o.key ? 'selected' : ''}>${esc(o.label)}</option>`).join('');
        const rk = opKey(c.right);
        return `
          <div class="crow" data-g="${g}" data-k="${k}">
            <select class="input sel mono" data-f="left" aria-label="${title} 조건 ${k + 1} 좌변">${operandOptions(opKey(c.left), { allowValue: false })}</select>
            <select class="input sel" data-f="${candle ? 'candle' : 'op'}" aria-label="${title} 조건 ${k + 1} 연산자">${opSel}</select>
            ${candle ? '<span class="cap" style="font-size: 11px">캔들 신호</span>' : `
              <div class="rhs"><select class="input sel mono" data-f="right" aria-label="${title} 조건 ${k + 1} 우변" style="flex: 1; min-width: 0">${operandOptions(rk, { allowValue: true })}</select>
              ${rk === 'v' ? `<input class="input val mono r" data-f="value" type="number" step="any" value="${esc(c.right.value)}" aria-label="${title} 조건 ${k + 1} 값">` : ''}</div>`}
            <button type="button" class="xb" data-act="rm-cond" aria-label="${title} 조건 ${k + 1} 삭제"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
          </div>`;
      }).join('');
      return `
        <div class="cgroup ${g}" aria-label="${aria}">
          <div class="row" style="gap: 8px"><span class="tag ${tagCls}">${title}</span><span class="cap">${grp.conditions.length ? (grp.logic === 'or' ? '하나라도 충족' : '모두 충족') : (g === 'exit' ? '없음 → 손절·익절로 청산' : '조건을 추가하세요')}</span>
            <div class="seg ml-auto" role="group" aria-label="${title} 조건 묶음" data-logic="${g}">
              <button type="button" data-value="and" class="${grp.logic !== 'or' ? 'on' : ''}">AND</button><button type="button" data-value="or" class="${grp.logic === 'or' ? 'on' : ''}">OR</button></div></div>
          ${rows}
          <button type="button" class="btn btn-sm" data-act="add-cond" data-g="${g}" style="align-self: flex-start; background: transparent">+ 조건 추가</button>
        </div>`;
    }).join('');
  }

  function renderIndicators() {
    const list = C().indicators;
    $('#indCount').textContent = list.length ? `${list.length}` : '';
    $('#indList').innerHTML = list.length ? list.map((inst, k) => {
      const meta = IND[inst.indicator];
      return `
        <div class="ind-row" data-k="${k}">
          <div class="top"><b class="mono" style="color: ${IND_COLORS[k % IND_COLORS.length]}">${esc(inst.id)}</b>
            <span class="cap" style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" title="${esc(meta ? meta.description : '')}">${esc(meta ? meta.label : inst.indicator)}</span>
            <button type="button" class="xb" data-act="rm-ind" aria-label="${esc(inst.id)} 지표 빼기"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
          ${meta && meta.params.length ? `<div class="params">${meta.params.map((p) => `
            <label>${esc(p.label)}<input class="input mono r" type="number" data-iparam="${esc(p.name)}" min="${p.min}" max="${p.max}" step="${p.step}" value="${inst.params?.[p.name] ?? p.default}"></label>`).join('')}</div>` : ''}
        </div>`;
    }).join('') : '<span class="cap">지표를 추가하면 조건에서 쓸 수 있습니다. 가격(종가 등)은 지표 없이도 쓸 수 있습니다.</span>';
  }

  function renderIndPicker() {
    const cat = $('#indCat').value || IND_CATS[0];
    $('#indCat').innerHTML = IND_CATS.map((c) => `<option ${c === cat ? 'selected' : ''}>${esc(c)}</option>`).join('');
    const items = opts.indicators.filter((i) => i.category === cat);
    $('#indKey').innerHTML = items.map((i) => `<option value="${esc(i.key)}">${esc(i.label)}</option>`).join('');
    renderIndDesc();
  }
  const renderIndDesc = () => { const m = IND[$('#indKey').value]; $('#indDesc').textContent = m ? m.description : ''; };

  function renderCustom() {
    renderSaved();
    $('#cName').value = C().name || '';
    $('#cDesc').value = C().description || '';
    renderIndicators();
    renderConditions();
  }

  $('#indCat').addEventListener('change', renderIndPicker);
  $('#indKey').addEventListener('change', renderIndDesc);
  $('#indAdd').addEventListener('click', () => {
    const key = $('#indKey').value;
    const meta = IND[key];
    if (!meta) return;
    const params = Object.fromEntries(meta.params.map((p) => [p.name, p.default]));
    C().indicators.push({ id: autoId(key, params), indicator: key, params });
    renderIndicators();
    renderConditions();
    persist();
  });
  $('#indList').addEventListener('click', (e) => {
    if (!e.target.closest('[data-act="rm-ind"]')) return;
    const k = Number(e.target.closest('.ind-row').dataset.k);
    const removed = C().indicators.splice(k, 1)[0];
    let dropped = 0;
    ['entry', 'exit'].forEach((g) => {
      const before = C()[g].conditions.length;
      C()[g].conditions = C()[g].conditions.filter((c) => !['left', 'right'].some((s) => c[s] && c[s].type === 'indicator' && c[s].ref === removed.id));
      dropped += before - C()[g].conditions.length;
    });
    if (dropped) toast(`${removed.id} 를 쓰던 조건 ${dropped}개도 지웠습니다.`);
    renderIndicators();
    renderConditions();
    persist();
  });
  $('#indList').addEventListener('change', (e) => {
    const name = e.target.dataset.iparam;
    if (!name) return;
    const inst = C().indicators[Number(e.target.closest('.ind-row').dataset.k)];
    const p = IND[inst.indicator].params.find((x) => x.name === name);
    let v = toNum(e.target.value);
    if (!Number.isFinite(v)) v = p.default;
    v = Math.min(p.max, Math.max(p.min, p.type === 'int' ? Math.round(v) : v));
    inst.params = { ...inst.params, [name]: v };
    // 이름이 sma_5 처럼 기간을 담고 있으면 새 기간에 맞춰 바꾸고 조건의 참조도 함께 바꾼다
    const newId = autoId(inst.indicator, inst.params, inst);
    if (newId !== inst.id) { renameRefs(inst.id, newId); inst.id = newId; }
    renderIndicators();
    renderConditions();
    persist();
  });

  $('#condGroups').addEventListener('click', (e) => {
    const add = e.target.closest('[data-act="add-cond"]');
    if (add) {
      const ids = C().indicators.filter((i) => !isCandle(i.indicator)).map((i) => i.id);
      const left = ids[0] ? { type: 'indicator', ref: ids[0] } : { type: 'price', field: 'close' };
      const right = ids[1] ? { type: 'indicator', ref: ids[1] } : { type: 'value', value: 0 };
      C()[add.dataset.g].conditions.push({ left, operator: 'gt', right });
      renderConditions();
      persist();
      return;
    }
    const rm = e.target.closest('[data-act="rm-cond"]');
    if (rm) {
      const row = rm.closest('.crow');
      C()[row.dataset.g].conditions.splice(Number(row.dataset.k), 1);
      renderConditions();
      persist();
    }
  });
  $('#condGroups').addEventListener('seg:change', (e) => {
    const g = e.target.closest('[data-logic]');
    if (!g) return;
    C()[g.dataset.logic].logic = e.detail;
    renderConditions();
    persist();
  });
  $('#condGroups').addEventListener('change', (e) => {
    const row = e.target.closest('.crow');
    if (!row) return;
    const c = C()[row.dataset.g].conditions[Number(row.dataset.k)];
    const f = e.target.dataset.f;
    if (f === 'left') {
      c.left = fromKey(e.target.value);
      const inst = instOf(c.left);
      if (inst && isCandle(inst.indicator)) { c.candle_signal = c.candle_signal || 'bullish'; c.operator = ''; c.right = { type: 'value', value: 0 }; }
      else { delete c.candle_signal; if (!c.operator) c.operator = 'gt'; }
    } else if (f === 'op') c.operator = e.target.value;
    else if (f === 'candle') c.candle_signal = e.target.value;
    else if (f === 'right') c.right = fromKey(e.target.value, 0);
    else if (f === 'value') c.right = { type: 'value', value: toNum(e.target.value) || 0 };
    renderConditions();
    persist();
  });

  $('#cName').addEventListener('input', (e) => { C().name = e.target.value; persist(); });
  $('#cDesc').addEventListener('input', (e) => { C().description = e.target.value; persist(); });

  function showCustomErrors(errors, title = '전략 설정을 확인하세요.') {
    const box = $('#customErr');
    box.hidden = !errors;
    box.innerHTML = errors ? `${esc(title)}${errors.length ? `<ul>${errors.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}` : '';
  }

  $('#savedSel').addEventListener('change', async (e) => {
    const file = e.target.value;
    if (!file) { st.savedFile = ''; renderSaved(); persist(); return; }
    try {
      const spec = await API.get(`backtest/strategies/${encodeURIComponent(file)}`);
      st.custom = { name: spec.name, description: spec.description, indicators: spec.indicators, entry: spec.entry, exit: spec.exit };
      st.savedFile = file;
      // 저장된 리스크·비용을 화면 설정에 반영
      RISK_KEYS.forEach(([k]) => { if (spec.risk && spec.risk[k]) st.risk[k] = { ...spec.risk[k] }; });
      if (spec.fee) st.fee = { ...spec.fee };
      showCustomErrors(null);
      renderCustom();
      renderRisk();
      renderFee();
      persist();
      toast(`'${spec.name}' 을(를) 불러왔습니다.`, 'ok');
    } catch (err) {
      toast(`불러오기 실패: ${err.message}`, 'error');
      renderSaved();
    }
  });
  $('#newCustom').addEventListener('click', () => {
    st.custom = defaultCustom();
    st.savedFile = '';
    showCustomErrors(null);
    renderCustom();
    persist();
  });
  $('#delCustom').addEventListener('click', async () => {
    const item = opts.saved.find((s) => s.file === st.savedFile);
    if (!item || !window.confirm(`저장된 전략 '${item.name}' 을(를) 삭제할까요?`)) return;
    try {
      const r = await API.del(`backtest/strategies/${encodeURIComponent(item.file)}`);
      opts.saved = r.saved;
      st.savedFile = '';
      renderSaved();
      persist();
      toast('삭제했습니다.', 'ok');
    } catch (err) {
      toast(`삭제 실패: ${err.message}`, 'error');
    }
  });
  $('#saveCustom').addEventListener('click', async () => {
    try {
      const r = await API.post('backtest/strategies', { strategy: C(), risk: st.risk, fee: feeBody() });
      opts.saved = r.saved;
      st.savedFile = r.file;
      showCustomErrors(null);
      renderSaved();
      persist();
      toast(`'${r.name}' 저장 완료`, 'ok');
    } catch (err) {
      showCustomErrors(err.data && err.data.errors ? err.data.errors : [], err.message);
    }
  });

  // ── 종목 ─────────────────────────────────
  let codeMeta = null;
  async function renderCode() {
    codeMeta = await API.stockMeta(st.code);
    $('#codeInput').value = codeMeta.name || st.code;
    $('#codeInfo').textContent = `${st.code}${codeMeta.market ? ` · ${codeMeta.market}` : ''} · 일봉`;
  }
  (function bindCodePicker() {
    const input = $('#codeInput');
    const pop = $('#codePop');
    let items = [];
    let active = -1;
    let timer;
    let seq = 0;
    const close = () => { pop.hidden = true; input.setAttribute('aria-expanded', 'false'); };
    const paint = () => {
      pop.innerHTML = items.length
        ? items.map((it, i) => `<li role="option" id="cp-${i}" data-code="${esc(it.code)}" aria-selected="${i === active}"><b>${esc(it.name)}</b><span class="mono cap">${esc(it.code)}</span><span class="cap ml-auto">${esc(it.market)}</span></li>`).join('')
        : '<li class="cap" aria-disabled="true">검색 결과가 없습니다.</li>';
      pop.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };
    const pick = (it) => {
      st.code = it.code;
      // 코스닥 종목이면 벤치마크를 KOSDAQ 으로 (없음을 고른 경우는 유지)
      if (st.bench) st.bench = it.market === 'KOSDAQ' ? '1001' : st.bench === '1001' ? '0001' : st.bench;
      renderBench();
      close();
      renderCode();
      persist();
    };
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) { close(); return; }
      timer = setTimeout(async () => {
        const my = ++seq;
        const rows = await API.get('search/stock', { q, limit: 8 }).catch(() => []);
        if (my !== seq) return;
        items = rows;
        active = rows.length ? 0 : -1;
        paint();
      }, 180);
    });
    input.addEventListener('keydown', (e) => {
      if (pop.hidden || !items.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % items.length; paint(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + items.length) % items.length; paint(); }
      if (e.key === 'Enter') { e.preventDefault(); if (items[active]) pick(items[active]); }
      if (e.key === 'Escape') close();
    });
    pop.addEventListener('mousedown', (e) => {
      const li = e.target.closest('[data-code]');
      if (li) { e.preventDefault(); pick(items.find((x) => x.code === li.dataset.code)); }
    });
    input.addEventListener('blur', () => setTimeout(() => { close(); if (codeMeta) input.value = codeMeta.name || st.code; }, 150));
  }());

  // ── 기간 · 자본 · 벤치마크 · 리스크 · 비용 ──
  function renderPeriod() {
    $$('#periodSeg button').forEach((b) => b.classList.toggle('on', b.dataset.value === st.period));
    $('#startDt').value = st.start;
    $('#endDt').value = st.end;
  }
  $('#periodSeg').addEventListener('seg:change', (e) => { applyPeriod(e.detail); persist(); });
  ['#startDt', '#endDt'].forEach((sel) => $(sel).addEventListener('change', () => {
    st.start = $('#startDt').value;
    st.end = $('#endDt').value;
    st.period = 'custom';
    renderPeriod();
    persist();
  }));

  function renderCapital() {
    $('#capital').value = fmt(st.capital);
    $$('#capBtns [data-cap]').forEach((b) => { b.style.borderColor = Number(b.dataset.cap) === st.capital ? 'var(--ink)' : ''; b.style.fontWeight = Number(b.dataset.cap) === st.capital ? '600' : ''; });
  }
  $('#capital').addEventListener('change', (e) => { const v = toNum(e.target.value); if (v > 0) st.capital = Math.round(v); renderCapital(); persist(); });
  $('#capBtns').addEventListener('click', (e) => { const b = e.target.closest('[data-cap]'); if (!b) return; st.capital = Number(b.dataset.cap); renderCapital(); persist(); });

  const renderBench = () => $$('#benchSeg button').forEach((b) => b.classList.toggle('on', b.dataset.value === st.bench));
  $('#benchSeg').addEventListener('seg:change', (e) => { st.bench = e.detail; persist(); });

  function renderRisk() {
    $('#riskRows').innerHTML = RISK_KEYS.map(([k, label, hint]) => {
      const r = st.risk[k];
      return `
        <div class="risk-row">
          <input type="checkbox" class="sw-in" role="switch" data-risk="${k}" aria-label="${label} 사용" ${r.enabled ? 'checked' : ''}>
          <div class="col" style="gap: 0"><span style="font-size: 13px; font-weight: 500">${label}</span><span class="cap" style="font-size: 11px">${hint}</span></div>
          <div class="pct"><input class="input sm mono r" data-riskpct="${k}" type="number" min="${opts.risk_pct_range.min}" max="${opts.risk_pct_range.max}" step="0.5" value="${r.pct}" aria-label="${label} 비율" ${r.enabled ? '' : 'disabled'}><span class="cap">%</span></div>
        </div>`;
    }).join('');
  }
  function renderRiskBadge() {
    const s = STRAT[st.basicId];
    const b = $('#riskBadge');
    b.hidden = !(st.kind === 'basic' && s.default_risk);
    b.textContent = s.default_risk ? `전략 기본값 ${riskText(s.default_risk)}` : '';
  }
  $('#riskRows').addEventListener('change', (e) => {
    const k = e.target.dataset.risk || e.target.dataset.riskpct;
    if (!k) return;
    if (e.target.dataset.risk) st.risk[k].enabled = e.target.checked;
    else {
      const v = toNum(e.target.value);
      st.risk[k].pct = Number.isFinite(v) ? Math.min(opts.risk_pct_range.max, Math.max(opts.risk_pct_range.min, v)) : st.risk[k].pct;
    }
    renderRisk();
    persist();
  });

  const feeBody = () => ({ commission: st.fee.commission, tax: st.fee.tax, slippage: st.fee.slippage });
  function renderFee() {
    $('#feeCommission').value = st.fee.commission;
    $('#feeTax').value = st.fee.tax;
    $('#feeSlip').value = st.fee.slippage;
  }
  [['#feeCommission', 'commission'], ['#feeTax', 'tax'], ['#feeSlip', 'slippage']].forEach(([sel, k]) => $(sel).addEventListener('change', (e) => {
    const v = toNum(e.target.value);
    st.fee[k] = Number.isFinite(v) && v >= 0 ? v : opts.fee_defaults[k];
    renderFee();
    persist();
  }));

  // ── 차트 ─────────────────────────────────
  const LWC = window.LightweightCharts;
  const AXIS_W = 80;
  const charts = {};
  let result = null;
  let unit = 'pct';
  const baseOpts = () => ({
    autoSize: true,
    layout: { background: { type: 'solid', color: '#FFFFFF' }, textColor: '#4A505B', fontFamily: "'IBM Plex Mono', 'IBM Plex Sans KR', monospace", fontSize: 11 },
    grid: { vertLines: { color: '#F1EFEA' }, horzLines: { color: '#F1EFEA' } },
    crosshair: { mode: LWC.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#E4E2DB', minimumWidth: AXIS_W },
    timeScale: { borderColor: '#E4E2DB', rightOffset: 3, minBarSpacing: 0.3 },
    localization: { locale: 'ko-KR' },
  });

  function ensureCharts() {
    if (charts.eq || !LWC) return !!charts.eq;
    const eq = LWC.createChart($('#eqChart'), { ...baseOpts(), timeScale: { ...baseOpts().timeScale, visible: false } });
    const dd = LWC.createChart($('#ddChart'), { ...baseOpts(), layout: { ...baseOpts().layout, attributionLogo: false }, timeScale: { ...baseOpts().timeScale, visible: false },
      localization: { locale: 'ko-KR', priceFormatter: (v) => `${fmt(v, 0)}%` } });
    const px = LWC.createChart($('#pxChart'), { ...baseOpts(), layout: { ...baseOpts().layout, attributionLogo: false },
      localization: { locale: 'ko-KR', priceFormatter: (v) => fmt(v, v % 1 ? 2 : 0) } });
    charts.eq = eq; charts.dd = dd; charts.px = px;
    charts.bench = eq.addLineSeries({ color: '#9AA0AA', lineWidth: 1.5, lineStyle: LWC.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
    charts.strat = eq.addLineSeries({ color: '#17191E', lineWidth: 2, priceLineVisible: false });
    charts.ddBench = dd.addLineSeries({ color: '#9AA0AA', lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    charts.ddStrat = dd.addBaselineSeries({ baseValue: { type: 'price', price: 0 }, topLineColor: 'rgba(0,0,0,0)', topFillColor1: 'rgba(0,0,0,0)', topFillColor2: 'rgba(0,0,0,0)',
      bottomLineColor: '#1D5BD6', bottomFillColor1: 'rgba(29,91,214,.06)', bottomFillColor2: 'rgba(29,91,214,.28)', lineWidth: 1, priceLineVisible: false });
    charts.hold = px.addHistogramSeries({ priceScaleId: 'hold', color: 'rgba(198,48,42,.07)', priceLineVisible: false, lastValueVisible: false });
    px.priceScale('hold').applyOptions({ scaleMargins: { top: 0, bottom: 0 }, visible: false });
    charts.candles = px.addCandlestickSeries({ upColor: '#C6302A', downColor: '#1D5BD6', borderUpColor: '#C6302A', borderDownColor: '#1D5BD6', wickUpColor: '#C6302A', wickDownColor: '#1D5BD6', priceLineVisible: false });

    // 세 차트의 보이는 구간·십자선을 맞춘다 (같은 날짜 목록이라 봉 순번이 1:1)
    const all = [eq, dd, px];
    let syncing = false;
    all.forEach((c) => c.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (syncing || !r) return;
      syncing = true;
      all.forEach((o) => { if (o !== c) o.timeScale().setVisibleLogicalRange(r); });
      syncing = false;
    }));
    let xsync = false;
    const targets = () => [[eq, charts.strat, (i) => eqValue(i)], [dd, charts.ddStrat, (i) => ddValue(i)], [px, charts.candles, (i) => result.series.close[i]]];
    all.forEach((c) => c.subscribeCrosshairMove((param) => {
      if (xsync || !result) return;
      const i = param && param.time ? dateIndex.get(typeof param.time === 'string' ? param.time : `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`) : undefined;
      xsync = true;
      targets().forEach(([o, s, v]) => {
        if (o === c) return;
        if (i === undefined) o.clearCrosshairPosition();
        else { const val = v(i); o.setCrosshairPosition(isNum(val) ? val : 0, result.series.dates[i], s); }
      });
      xsync = false;
      paintHover(i);
    }));
    return true;
  }

  let dateIndex = new Map();
  let ddS = [];
  let ddB = [];
  const eqValue = (i) => { const v = result.series.equity[i]; return unit === 'pct' ? (v / result.meta.capital - 1) * 100 : v; };
  const ddValue = (i) => ddS[i];
  const drawdown = (arr) => { let pk = -Infinity; return arr.map((v) => { if (!isNum(v)) return null; pk = Math.max(pk, v); return (v / pk - 1) * 100; }); };

  function paintHover(i) {
    const el = $('#mddText');
    if (!result) return;
    if (i === undefined) { el.innerHTML = mddLabel(); return; }
    const s = result.series;
    const cap = result.meta.capital;
    const b = s.bench && isNum(s.bench[i]) ? ` · ${esc(result.meta.benchmark.label)} ${sgnPct((s.bench[i] / cap - 1) * 100)}` : '';
    el.innerHTML = `${dot(s.dates[i])} · 전략 <b class="${cls(s.equity[i] - cap)}">${sgnPct((s.equity[i] / cap - 1) * 100)}</b>${b} · 낙폭 <span class="dn">${sgnPct(ddS[i])}</span>`;
  }
  const mddLabel = () => { const m = result.metrics; return `최대 <b class="dn">${sgnPct(m.max_drawdown)}</b>`; };

  function applyUnit() {
    if (!result || !charts.eq) return;
    const s = result.series;
    const cap = result.meta.capital;
    const conv = (v) => (unit === 'pct' ? (v / cap - 1) * 100 : v);
    const line = (arr) => s.dates.map((d, i) => (isNum(arr[i]) ? { time: d, value: conv(arr[i]) } : { time: d }));
    charts.eq.applyOptions({ localization: { locale: 'ko-KR', priceFormatter: unit === 'pct' ? (v) => sgnPct(v, 1) : (v) => `${fmt(v / 1e4)}만` } });
    charts.strat.setData(line(s.equity));
    charts.bench.setData(s.bench ? line(s.bench) : []);
  }
  $('#unitSeg').addEventListener('seg:change', (e) => { unit = e.detail; applyUnit(); });

  function drawCharts() {
    if (!ensureCharts()) return;
    const s = result.series;
    dateIndex = new Map(s.dates.map((d, i) => [d, i]));
    ddS = drawdown(s.equity);
    ddB = s.bench ? drawdown(s.bench) : [];
    applyUnit();
    charts.ddStrat.setData(s.dates.map((d, i) => (isNum(ddS[i]) ? { time: d, value: ddS[i] } : { time: d })));
    charts.ddBench.setData(s.bench ? s.dates.map((d, i) => (isNum(ddB[i]) ? { time: d, value: ddB[i] } : { time: d })) : []);
    const digits = s.close.some((v) => v % 1) ? 2 : 0;
    // 기간 중 가격이 몇 배로 변하면 초반 거래가 바닥에 눌리지 않도록 로그 축
    const lo = Math.min(...s.low.filter(isNum));
    const hi = Math.max(...s.high.filter(isNum));
    charts.px.priceScale('right').applyOptions({ mode: hi / lo > 2.5 ? LWC.PriceScaleMode.Logarithmic : LWC.PriceScaleMode.Normal });
    charts.candles.applyOptions({ priceFormat: { type: 'price', precision: digits, minMove: digits ? 0.01 : 1 } });
    charts.candles.setData(s.dates.map((d, i) => ({ time: d, open: s.open[i], high: s.high[i], low: s.low[i], close: s.close[i] })));
    charts.hold.setData(s.dates.map((d, i) => (s.holding[i] ? { time: d, value: 1 } : { time: d })));
    const markers = [];
    result.trades.forEach((t) => {
      markers.push({ time: t.entry_date, position: 'belowBar', color: '#C6302A', shape: 'arrowUp', size: 0.8 });
      markers.push({ time: t.exit_date, position: 'aboveBar', color: REASON_COLOR[t.reason] || '#3D424B', shape: 'arrowDown', size: 0.8 });
    });
    markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    charts.candles.setMarkers(markers);
    charts.px.timeScale().fitContent();
    $('#mddText').innerHTML = mddLabel();
  }

  function focusTrade(t) {
    if (!charts.px) return;
    const a = dateIndex.get(t.entry_date);
    const b = dateIndex.get(t.exit_date);
    if (a === undefined || b === undefined) return;
    const pad = Math.max(15, Math.round((b - a) * 0.8));
    charts.px.timeScale().setVisibleLogicalRange({ from: a - pad, to: b + pad });
    $('#pxChart').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  // ── 결과 표시 ────────────────────────────
  function renderHead() {
    const m = result.meta;
    const name = codeMeta && codeMeta.code === m.code ? codeMeta.name : m.code;
    const params = Object.values(m.params || {}).join(', ');
    const risk = riskText(m.risk);
    const bench = m.benchmark ? ` · 벤치마크 ${m.benchmark.label}` : '';
    $('#resHead').innerHTML = `
      <div class="col" style="gap: 3px; min-width: 0">
        <div class="row" style="gap: 8px; flex-wrap: wrap"><b style="font-size: 15px">${esc(m.label)}</b><span class="cap mono">${esc([params, risk].filter(Boolean).join(' · '))}</span></div>
        <span class="cap mono">${esc(name)} ${esc(m.code)} · ${dot(m.start)} – ${dot(m.end)} · ${fmt(m.bars)}봉 · 초기 ${fmt(m.capital)}원${esc(bench)}</span>
        <span class="cap" style="font-size: 11px">데이터: ${esc([...m.sources, ...(m.bench_sources || []).map((x) => `지수 ${x}`)].join(' · '))} · 지표 워밍업 ${fmt(m.warmup_bars)}봉 · 수수료 ${m.fee.commission}% · 거래세 ${m.fee.tax}% · 슬리피지 ${m.fee.slippage}%</span>
      </div>`;
  }

  function renderKpis() {
    const m = result.metrics;
    const b = m.bench;
    const wins = result.trades.filter((t) => t.pnl > 0);
    const losses = result.trades.filter((t) => t.pnl < 0);
    const avgPct = (arr) => (arr.length ? arr.reduce((s, t) => s + (t.pnl_pct || 0), 0) / arr.length : null);
    const tile = (label, value, vcls, sub) => `<div class="kpi"><span class="cap">${label}</span><span class="v ${vcls || ''}">${value}</span><span class="s">${sub}</span></div>`;
    const pf = m.profit_factor;
    $('#kpis').innerHTML = [
      tile('총수익률', sgnPct(m.total_return, 1), cls(m.total_return), `최종 ${fmt(result.meta.final)}원`),
      tile('CAGR', sgnPct(m.cagr, 1), cls(m.cagr), '연 복리 수익률'),
      tile('최대 낙폭 (MDD)', sgnPct(m.max_drawdown, 1), 'dn', '고점 대비 최대 하락'),
      tile('샤프 비율', isNum(m.sharpe) ? fmt(m.sharpe, 2) : '—', '', '일간 수익률 연율화 · 무위험 0%'),
      tile('승률 / 거래 수', m.total_trades ? `${fmt(m.win_rate, 1)}%` : '—', '', `${wins.length}승 ${losses.length}패 · ${m.total_trades}회`),
      tile('손익비 (Profit factor)', pf == null ? (wins.length && !losses.length ? '∞' : '—') : fmt(pf, 2), '', '총이익 ÷ 총손실'),
      tile('평균 익절 / 손절', `${sgnPct(avgPct(wins), 1)} / ${sgnPct(avgPct(losses), 1)}`, 'sm', `${m.avg_win ? '+' + fmt(m.avg_win) : '0'} / ${m.avg_loss ? '−' + fmt(Math.abs(m.avg_loss)) : '0'}원`),
      result.meta.benchmark
        ? tile(`벤치마크 · ${esc(result.meta.benchmark.label)}`, b ? sgnPct(b.total_return, 1) : '—', b ? cls(b.total_return) : '', b ? `전략 초과수익 ${sgnPct(m.total_return - b.total_return, 1).replace('%', '%p')}` : '지수 데이터를 받지 못했습니다')
        : tile('벤치마크', '—', '', '벤치마크 없음'),
    ].join('');
  }

  function renderCompare() {
    const m = result.metrics;
    const b = m.bench;
    $('#benchLegend').hidden = !result.series.bench;
    $('#benchName').textContent = result.meta.benchmark ? result.meta.benchmark.label : '';
    if (!b) { $('#cmpTable').innerHTML = ''; return; }
    const rows = [['총수익률', m.total_return, b.total_return, '%', 1], ['CAGR', m.cagr, b.cagr, '%', 1], ['최대 낙폭', m.max_drawdown, b.max_drawdown, '%', 1], ['샤프 비율', m.sharpe, b.sharpe, '', 2]];
    const f = (v, u, d) => (isNum(v) ? (u ? sgnPct(v, d) : fmt(v, d)) : '—');
    $('#cmpTable').innerHTML = `
      <div class="cmp h"><span>전략 vs ${esc(result.meta.benchmark.label)}</span><span class="r">전략</span><span class="r">${esc(result.meta.benchmark.label)}</span><span class="r">차이</span></div>
      ${rows.map(([label, s, bv, u, d]) => {
        const diff = isNum(s) && isNum(bv) ? s - bv : null;
        return `<div class="cmp"><span class="cap" style="font-size: 13px">${label}</span><span class="mono r ${u ? cls(s) : ''}">${f(s, u, d)}</span><span class="mono r ${u ? cls(bv) : ''}">${f(bv, u, d)}</span><span class="mono r ${cls(diff)}" style="font-weight: 600">${isNum(diff) ? (u ? sgnPct(diff, d).replace('%', '%p') : `${diff > 0 ? '+' : ''}${fmt(diff, d)}`) : '—'}</span></div>`;
      }).join('')}`;
  }

  let flt = 'all';
  let selTrade = -1;
  function renderTrades() {
    const all = result.trades;
    const rows = all.map((t, i) => ({ t, i })).filter(({ t }) => (flt === 'all' ? true : flt === 'win' ? t.pnl > 0 : t.pnl <= 0));
    $('#tradeCount').textContent = `${rows.length}건`;
    const r = result.stats.reasons;
    $('#reasonTags').innerHTML = Object.entries(r).filter(([, n]) => n).map(([k, n]) => `<span class="rtag ${k}">${esc(result.trades.find((t) => t.reason === k).reason_label)} ${n}</span>`).join('');
    const sig = result.meta.kind === 'basic' ? '전략 매수 신호' : '진입 조건 충족';
    $('#tradeRows').innerHTML = rows.length ? rows.map(({ t, i }) => {
      const out = t.reason === 'signal' ? [`${short(t.exit_signal)} <span class="muted">→</span> ${short(t.exit_date)}`, result.meta.kind === 'basic' ? '전략 매도 신호' : '청산 조건 충족', '다음 봉 시가']
        : t.reason === 'stop_loss' ? [`${short(t.exit_date)} 장중`, '저가가 손절선에 닿음', `손절선 −${result.meta.risk.stop_loss_pct}%`]
          : t.reason === 'take_profit' ? [`${short(t.exit_date)} 장중`, '고가가 익절선에 닿음', `익절선 +${result.meta.risk.take_profit_pct}%`]
            : t.reason === 'trailing_stop' ? [`${short(t.exit_date)} 장중`, '고점 대비 하락선에 닿음', `고점 대비 −${result.meta.risk.trailing_stop_pct}%`]
              : [`${short(t.exit_date)} 종가`, '백테스트 기간 종료', '마지막 종가'];
      return `
        <div class="tr ${i === selTrade ? 'sel' : ''}" data-i="${i}" tabindex="0" role="button" aria-label="${i + 1}번 거래 차트에서 보기">
          <span class="mono cap">${i + 1}</span>
          <div class="cell2"><span class="mono">${short(t.entry_signal)} <span class="muted">→</span> ${short(t.entry_date)}</span><span class="cap">${sig}</span></div>
          <div class="cell2 r"><span class="mono">${fmt(t.entry_price)}</span><span class="cap">다음 봉 시가</span></div>
          <div class="cell2"><span class="mono">${out[0]}</span><span class="cap">${out[1]}</span></div>
          <div class="cell2 r"><span class="mono">${fmt(t.exit_price)}</span><span class="cap">${out[2]}</span></div>
          <span class="c"><span class="rtag ${t.reason}">${esc(t.reason_label)}</span></span>
          <span class="mono r">${fmt(t.qty)}</span>
          <span class="mono r muted">${t.hold == null ? '—' : `${t.hold}일`}</span>
          <span class="mono r ${cls(t.pnl)}" style="font-weight: 500">${UI.signed(t.pnl)}</span>
          <span class="mono r ${cls(t.pnl)}">${sgnPct(t.pnl_pct)}</span>
        </div>`;
    }).join('') : UI.stateHtml('empty', all.length ? '조건에 맞는 거래가 없습니다.' : '기간 안에 체결된 거래가 없습니다. 조건이나 기간을 바꿔 보세요.');
    const s = result.stats;
    const bar = $('#sumBar');
    bar.hidden = false;
    bar.innerHTML = `
      <span class="cap">합계 손익</span><b class="mono ${cls(s.total_pnl)}">${UI.signed(s.total_pnl)}원</b>
      <span class="cap">평균 보유</span><span class="mono">${isNum(s.avg_hold) ? `${fmt(s.avg_hold, 1)}일` : '—'}</span>
      <span class="cap">보유 비율</span><span class="mono">${fmt(s.exposure, 1)}%</span>
      <span class="cap">최대 연속 손실</span><span class="mono">${s.max_loss_streak}회</span>
      <span class="cap ml-auto">손익은 수수료·거래세·슬리피지 반영 · 보유는 거래일 수 · 신호일은 조건이 충족된 봉, 체결일은 그다음 봉</span>`;
    $('#csvBtn').disabled = !all.length;
  }
  $('#fltSeg').addEventListener('seg:change', (e) => { flt = e.detail; if (result) renderTrades(); });
  const pickRow = (row) => {
    if (!row || !result) return;
    selTrade = Number(row.dataset.i);
    $$('#tradeRows .tr').forEach((r) => r.classList.toggle('sel', Number(r.dataset.i) === selTrade));
    focusTrade(result.trades[selTrade]);
  };
  $('#tradeRows').addEventListener('click', (e) => pickRow(e.target.closest('.tr[data-i]')));
  $('#tradeRows').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pickRow(e.target.closest('.tr[data-i]')); } });

  $('#csvBtn').addEventListener('click', () => {
    if (!result) return;
    const head = ['번호', '매수신호일', '매수일', '매수가', '청산신호일', '청산일', '청산가', '청산사유', '수량', '보유일', '손익(원)', '수익률(%)'];
    const rows = result.trades.map((t, i) => [i + 1, t.entry_signal || '', t.entry_date, t.entry_price, t.exit_signal || '', t.exit_date, t.exit_price, t.reason_label, t.qty, t.hold ?? '', t.pnl, t.pnl_pct]);
    const csv = [head, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    a.download = `backtest_${result.meta.code}_${result.meta.start}_${result.meta.end}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  // ── 실행 ─────────────────────────────────
  function requestBody() {
    const strategy = st.kind === 'basic'
      ? { kind: 'basic', id: st.basicId, params: paramsOf(st.basicId) }
      : { kind: 'custom', spec: C() };
    return { code: st.code, start: st.start, end: st.end, capital: st.capital, benchmark: st.bench, strategy, risk: st.risk, fee: feeBody() };
  }

  $('#btForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('#runBtn');
    btn.disabled = true;
    btn.querySelector('span').textContent = '계산 중…';
    showCustomErrors(null);
    $('#resHead').innerHTML = UI.loadingHtml('백테스트 계산 중… (처음 조회하는 종목은 일봉을 받느라 몇 초 걸립니다)');
    try {
      result = await API.post('backtest/run', requestBody());
      selTrade = -1;
      renderHead();
      renderKpis();
      drawCharts();
      renderCompare();
      renderTrades();
    } catch (err) {
      const errors = err.data && err.data.errors;
      if (errors && st.kind === 'custom') showCustomErrors(errors, err.message);
      $('#resHead').innerHTML = UI.errorHtml(err);
      toast(`백테스트 실패: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.querySelector('span').textContent = '백테스트 실행';
    }
  });

  // ── 시작 ─────────────────────────────────
  renderKind();
  renderBasicList();
  renderBasicDetail();
  renderIndPicker();
  renderCustom();
  renderPeriod();
  renderCapital();
  renderBench();
  renderRisk();
  renderRiskBadge();
  renderFee();
  renderCode();
  persist();
};
