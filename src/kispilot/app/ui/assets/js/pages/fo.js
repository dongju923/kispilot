/* 선물/옵션 — KOSPI200 선물 월물 · 옵션 전광판 (주간 / 야간) + 선택 종목 상세 (헤더 · 호가 · 체결 실시간) */
window.renderPage = async function () {
  const { esc, fmt, cls, signed, pct, arrow, fill, load, loadingHtml, errorHtml, $, $$ } = UI;
  const { n, hms } = KIS;
  const TAB_KEY = 'pykis.foTab';
  const PRODUCT_KEY = 'pykis.foProduct';
  const FUTURES_MS = 5000;
  const OPTIONS_MS = 30000;

  /* 장 구간 (공휴일 미반영). 주간 08:45–15:45, 야간 월~금 18:00–다음 날 06:00 */
  function foStatus(now = new Date()) {
    const day = now.getDay();
    const t = now.getHours() * 100 + now.getMinutes();
    const weekday = day >= 1 && day <= 5;
    if (weekday && t >= 845 && t < 1545) return { open: 'day', label: '주간장 · 08:45–15:45' };
    if ((weekday && t >= 1800) || (day >= 2 && day <= 6 && t < 600)) return { open: 'night', label: '야간장 · 18:00–06:00' };
    return { open: null, label: '장 마감' };
  }
  /* 열려 있는 장, 없으면 08:45–18:00 은 주간(방금 끝났거나 곧 열림) · 그 밖은 야간 */
  function defaultSession() {
    const st = foStatus();
    if (st.open) return st.open;
    const now = new Date();
    const t = now.getHours() * 100 + now.getMinutes();
    return t >= 845 && t < 1800 ? 'day' : 'night';
  }

  const params = new URLSearchParams(location.search);
  const pick = (v, allowed, fallback) => (allowed.includes(v) ? v : fallback);
  let session = pick(params.get('session'), ['day', 'night'], defaultSession());
  let tab = pick(params.get('tab') || API.store.get(TAB_KEY), ['futures', 'options'], 'futures');
  let product = pick(API.store.get(PRODUCT_KEY), ['regular', 'mini', 'weekly_thu', 'weekly_mon'], 'regular');
  let expiry = '';
  let selCode = (params.get('code') || '').trim().toUpperCase(); // 상세에서 보는 종목

  const setSeg = (sel, value) => document.querySelectorAll(`${sel} button`).forEach((b) => b.classList.toggle('on', b.dataset.value === value));
  const saveUrl = () => {
    const q = new URLSearchParams(location.search);
    q.set('session', session);
    q.set('tab', tab);
    if (selCode) q.set('code', selCode);
    history.replaceState(null, '', `${location.pathname}?${q}`);
  };

  // ── 장 상태 ──
  function paintStatus() {
    const st = foStatus();
    const on = st.open === session;
    $('#sessionChip').innerHTML = `<span class="dot${on ? ' pulse' : ''}" style="background:${on ? 'var(--ok)' : 'var(--neutral-bar)'}"></span>${
      on ? `${st.label} 운영 중` : `${session === 'day' ? '주간장' : '야간장'} 마감`}`;
    $('#sessionNote').textContent = on ? '' : '장 마감 기준 (마지막 거래 값)';
  }

  function paintIndex(idx) {
    if (!idx) return;
    $('#foIndex').textContent = fmt(idx.price, 2);
    $('#foIndex').className = `mono ${cls(idx.change)}`;
    $('#foIndexChg').className = `mono ${cls(idx.change)}`;
    $('#foIndexChg').textContent = `${signed(idx.change, 2)} (${pct(idx.change_rate)})`;
  }

  // ── 선물 전광판 ──
  let futuresBusy = false;
  async function loadFutures(opt) {
    if (futuresBusy) return;
    futuresBusy = true;
    const want = session;
    await load('#futuresRows', () => API.get('fo/futures', { session: want }), (el, d) => {
      if (want !== session) return;
      paintIndex(d.index);
      fill(el, d.rows, (r) => (r.error ? `
        <div class="tr">
          <span class="cap">${esc(r.product_label)}</span><span>${esc(r.expiry_label)}</span>
          <span class="r" style="grid-column: 3 / -1; color: var(--up-tag)">${esc(r.error)}</span>
        </div>` : `
        <div class="tr" data-code="${esc(r.code)}">
          <span class="cap">${esc(r.product_label)}</span>
          <span class="name-code"><b>${esc(r.expiry_label)}</b><span class="cap mono">${esc(r.code)}</span></span>
          <span class="mono r ${cls(r.change)}">${fmt(r.price, 2)}</span>
          <span class="mono r ${cls(r.change)}">${signed(r.change, 2)}</span>
          <span class="mono r ${cls(r.change_rate)}">${pct(r.change_rate)}</span>
          <span class="mono r">${fmt(r.volume)}</span>
          <span class="mono r muted">${fmt(r.open_interest)}</span>
          <span class="mono r">${signed(r.basis, 2)}</span>
          <span class="mono r muted">${r.days_left == null ? '—' : `${fmt(r.days_left)}일`}</span>
        </div>`), '선물 종목이 없습니다.');
      markSel();
      if (!selCode) select((d.rows.find((r) => !r.error) || {}).code);
      $('#futuresNote').textContent = `${d.as_of} 조회 · ${session === 'night' ? '야간은 미니선물이 거래되지 않습니다. ' : ''}${FUTURES_MS / 1000}초마다 갱신`;
    }, opt);
    futuresBusy = false;
  }

  // ── 옵션 전광판 ──
  const optionCells = (q, side) => {
    if (!q) return '<span></span><span></span><span></span><span></span>';
    if (q.error) {
      return side === 'call'
        ? `<span class="r" style="grid-column: span 4; color: var(--up-tag)" title="${esc(q.code)}">${esc(q.error)}</span>`
        : `<span style="grid-column: span 4; color: var(--up-tag)" title="${esc(q.code)}">${esc(q.error)}</span>`;
    }
    const at = `data-code="${esc(q.code)}" title="${esc(`${q.code} · 이론가 ${fmt(q.theory, 2)} · 내재변동성 ${fmt(q.iv, 2)} · 델타 ${fmt(q.delta, 4)}`)}"`;
    const cells = [
      `<span class="mono r muted" ${at}>${fmt(q.open_interest)}</span>`,
      `<span class="mono r" ${at}>${fmt(q.volume)}</span>`,
      `<span class="mono r ${cls(q.change_rate)}" ${at}>${pct(q.change_rate)}</span>`,
      `<span class="mono r ${cls(q.change)}" ${at} style="font-weight:600">${fmt(q.price, 2)}</span>`,
    ];
    return (side === 'call' ? cells : cells.reverse()).join('');
  };

  let optionsSeq = 0;
  let optionsBusy = false;
  async function loadOptions(opt = {}) {
    if (!expiry) return;
    if (opt.quiet && optionsBusy) return; // 자동 갱신이 앞 조회(약 3초)와 겹치지 않게
    const seq = ++optionsSeq;
    optionsBusy = true;
    const el = $('#optionsRows');
    if (!opt.quiet) {
      el.innerHTML = loadingHtml('옵션 시세를 모으는 중… (약 3초)');
      $('#optionsRef').textContent = '';
    }
    try {
      const d = await API.get('fo/board', { session, product, expiry });
      if (seq !== optionsSeq) return; // 그사이 상품·만기·장 구분을 바꿨으면 버린다
      fill(el, d.rows, (r) => `
        <div class="tr${r.strike === d.atm ? ' atm' : ''}">
          ${optionCells(r.call, 'call')}
          <span class="strike mono">${fmt(r.strike, 1)}</span>
          ${optionCells(r.put, 'put')}
        </div>`, '옵션 종목이 없습니다.');
      markSel();
      const ref = d.reference;
      $('#optionsRef').textContent = `기준 ${ref.source} ${fmt(ref.price, 2)} · ATM ${fmt(d.atm, 1)} · 행사가 ${fmt(d.strikes_total)}개 중 ${d.rows.length}개 · ${d.as_of} 조회`;
    } catch (e) {
      console.error(e);
      if (seq === optionsSeq && !opt.quiet) el.innerHTML = errorHtml(e);
    } finally {
      if (seq === optionsSeq) optionsBusy = false;
    }
  }

  async function loadExpiries() {
    const sel = $('#expirySel');
    sel.disabled = true;
    try {
      const list = await API.get('fo/expiries', { session, product });
      sel.innerHTML = list.map((x) => `<option value="${esc(x.expiry)}">${esc(x.label)}</option>`).join('');
      expiry = list.some((x) => x.expiry === expiry) ? expiry : (list[0] ? list[0].expiry : '');
      sel.value = expiry;
      if (!expiry) $('#optionsRows').innerHTML = UI.stateHtml('empty', '만기가 없습니다.');
    } catch (e) {
      console.error(e);
      sel.innerHTML = '';
      expiry = '';
      $('#optionsRows').innerHTML = errorHtml(e);
    }
    sel.disabled = false;
  }

  // ── 선택 종목 상세 (헤더 · 호가 · 체결) ──
  // KOSPI200 선물 코드는 A…, 콜 B…, 풋 C… (마스터 단축코드)
  const isFutures = (c) => c.startsWith('A');
  const marketDiv = (c) => (isFutures(c) ? (session === 'day' ? 'F' : 'CM') : (session === 'day' ? 'O' : 'EU'));
  // 실시간 종류 (서버 realtime_hub.KINDS): 주간 fut_/opt_, 야간 nfut_/nopt_
  const liveKind = (c, what) => `${session === 'night' ? 'n' : ''}${isFutures(c) ? 'fut' : 'opt'}_${what}`;
  const signedOf = (v, sign) => { const x = n(v); return x != null && (sign === '4' || sign === '5') && x > 0 ? -x : x; };

  let head = null;
  let ticks = [];
  let live = null;
  let pollTimer = null;

  function markSel() {
    $$('.board .sel').forEach((el) => el.classList.remove('sel'));
    if (selCode) $$(`.board [data-code="${selCode}"]`).forEach((el) => el.classList.add('sel'));
  }

  function renderHead() {
    if (!head) return;
    const c = cls(head.diff);
    const fut = isFutures(head.code);
    const stats = [
      ['시가', fmt(head.open, 2)], ['고가', fmt(head.high, 2), 'up'], ['저가', fmt(head.low, 2), 'dn'],
      ['거래량', fmt(head.volume)], ['미결제', fmt(head.oi)], ['미결제 증감', signed(head.oiChange), cls(head.oiChange)],['이론가', fmt(head.theory, 2)],
      ...(fut
        ? [['베이시스', signed(head.basis, 2)]]
        : [['행사가', fmt(head.strike, 1)],['내재변동성', fmt(head.iv, 2)], ['델타', fmt(head.delta, 4)]]),
      ['잔존일', head.daysLeft == null ? '—' : `${fmt(head.daysLeft)}일`],
    ];
    $('#foHead').innerHTML = `
      <div class="row" style="flex-wrap:wrap">
        <h2 class="stock-head__name">${esc(head.name)}</h2>
        <span class="mono cap" style="font-size:13px">${esc(head.code)}</span>
        <span class="chip sm">${fut ? '선물' : '옵션'}</span><span class="chip sm">${session === 'day' ? '주간' : '야간'}</span>
        <span class="api ml-auto">inquire_price</span>
      </div>
      <div class="stock-head__body">
        <div class="stock-head__price">
          <span class="price-big ${c}">${fmt(head.price, 2)}</span>
          <span class="mono ${c}" style="font-size:15px">${arrow(head.diff, 2)}&nbsp; ${pct(head.pct)}</span>
        </div>
        <dl class="stats" style="--n:${Math.ceil(stats.length / 2)}">
          ${stats.map(([k, v, vc]) => `<div><dt>${esc(k)}</dt><dd class="${vc || ''}">${esc(v)}</dd></div>`).join('')}
        </dl>
      </div>`;
  }
  let headQueued = false;
  const repaintHead = () => {
    if (headQueued) return;
    headQueued = true;
    requestAnimationFrame(() => { headQueued = false; renderHead(); });
  };

  const loadHead = (opt) => {
    const code = selCode;
    return load('#foHead', () => API.get('futureoption/inquire_price', { code, market_div: marketDiv(code) }), (el, d) => {
      if (code !== selCode) return;
      const o = d.output1 || {};
      head = {
        code, name: o.hts_kor_isnm || code, price: n(o.futs_prpr), diff: n(o.futs_prdy_vrss), pct: n(o.futs_prdy_ctrt),
        open: n(o.futs_oprc), high: n(o.futs_hgpr), low: n(o.futs_lwpr), volume: n(o.acml_vol),
        oi: n(o.hts_otst_stpl_qty), oiChange: n(o.otst_stpl_qty_icdc), theory: n(o.hts_thpr), basis: n(o.basis),
        strike: n(o.acpr), iv: n(o.hts_ints_vltl), delta: n(o.delta_val), daysLeft: n(o.hts_rmnn_dynu),
      };
      renderHead();
    }, opt);
  };

  const renderBook = (book) => UI.ladder($('#ladder'), book, { current: head && head.price, digits: 2 });
  const loadBook = (opt) => {
    const code = selCode;
    return load('#ladder', () => API.get('futureoption/inquire_asking_price', { code, market_div: marketDiv(code) }), (el, d) => {
      if (code === selCode) renderBook(KIS.orderbook(d.output2 || {}, 5, 'futs_')); // REST 호가는 옵션도 futs_ 필드
    }, opt);
  };

  // 체결 목록은 실시간으로만 쌓는다 (선물옵션은 REST 체결 목록 API 를 쓰지 않음). 직전 체결가보다 오르면 빨강·내리면 파랑.
  function renderTicks() {
    fill('#tickRows', ticks, (t) => `
      <div class="tr${t.fresh ? ` flash-${t.side === '5' ? 'dn' : 'up'}` : ''}">
        <span class="mono muted">${hms(t.time)}</span>
        <span class="mono r">${fmt(t.price, 2)}</span>
        <span class="mono r ${cls(t.pct)}">${pct(t.pct)}</span>
        <span class="mono r ${t.side === '5' ? 'dn' : t.side === '1' ? 'up' : 'flat'}">${fmt(t.qty)}</span>
      </div>`, live && live.isLive() ? '체결을 기다리는 중…' : '장 운영 중에 실시간 체결이 표시됩니다.');
    ticks.forEach((t) => { t.fresh = false; });
  }
  const setStrength = (s) => {
    $('#strength').textContent = s == null ? '—' : `${fmt(s, 2)}%`;
    $('#strength').className = `mono ${s >= 100 ? 'up' : 'dn'}`;
  };

  function onTick(t) {
    const fut = isFutures(selCode);
    const P = fut ? 'futs' : 'optn';
    if (t[`${P}_shrn_iscd`] !== selCode) return;
    const price = n(t[`${P}_prpr`]);
    if (!price) return;
    const diff = signedOf(t[`${P}_prdy_vrss`], t.prdy_vrss_sign);
    const rate = signedOf(fut ? t.futs_prdy_ctrt : t.prdy_ctrt, t.prdy_vrss_sign);
    if (head) {
      Object.assign(head, {
        price, diff, pct: rate,
        open: n(t[`${P}_oprc`]) || head.open, high: n(t[`${P}_hgpr`]) || head.high, low: n(t[`${P}_lwpr`]) || head.low,
        volume: n(t.acml_vol) ?? head.volume, oi: n(t.hts_otst_stpl_qty) ?? head.oi,
        oiChange: n(t.otst_stpl_qty_icdc) ?? head.oiChange, theory: n(t.hts_thpr) || head.theory,
      });
      if (fut) head.basis = n(t.thpr_basis) ?? head.basis;
      else Object.assign(head, { iv: n(t.hts_ints_vltl) ?? head.iv, delta: n(t.delta) ?? head.delta });
      repaintHead();
    }
    setStrength(n(t.cttr));
    const prev = ticks[0] ? ticks[0].price : price;
    ticks.unshift({ time: t.bsop_hour, price, pct: rate, qty: n(t.last_cnqn), side: price > prev ? '1' : price < prev ? '5' : '', fresh: true });
    ticks = ticks.slice(0, 50);
    renderTicks();
  }
  function onBook(b) {
    const fut = isFutures(selCode);
    if (b[`${fut ? 'futs' : 'optn'}_shrn_iscd`] !== selCode) return;
    renderBook(KIS.orderbook(b, 5, fut ? 'futs_' : 'optn_'));
  }

  // 실시간이 안 들어오는 동안(장 마감·일시정지·접속 실패)은 헤더·호가를 5초마다 REST 로 갱신한다
  const setPolling = (on) => {
    clearInterval(pollTimer);
    pollTimer = on ? setInterval(() => {
      if (!document.hidden) { loadHead({ quiet: true }); loadBook({ quiet: true }); }
    }, FUTURES_MS) : null;
  };

  async function select(code) {
    if (!code) return;
    selCode = code;
    saveUrl();
    markSel();
    head = null;
    ticks = [];
    setStrength(null);
    if (live) live.close();
    live = null;
    renderTicks();
    setPolling(true);
    await loadHead();
    loadBook();
    if (code !== selCode) return;
    const ccnl = liveKind(code, 'ccnl');
    const book = liveKind(code, 'book');
    live = Live.connect({ [ccnl]: [code], [book]: [code] }, {
      [ccnl]: onTick,
      [book]: onBook,
      state(on) { setPolling(!on); renderTicks(); },
      resync() { loadHead({ quiet: true }); loadBook({ quiet: true }); },
    });
  }

  // ── 화면 전환 ──
  let optionsReady = false; // 지금 장 구분·상품으로 만기 목록을 받았는지
  async function showTab() {
    $('#futuresPane').hidden = tab !== 'futures';
    $('#optionsPane').hidden = tab !== 'options';
    $('#boardApi').textContent = tab === 'futures' ? 'fo/futures · inquire_price' : 'fo/board · inquire_price';
    if (tab === 'options' && !optionsReady) {
      optionsReady = true;
      await loadExpiries();
      loadOptions();
    }
  }

  setSeg('#sessionSeg', session);
  setSeg('#tabSeg', tab);
  setSeg('#productSeg', product);
  saveUrl();
  paintStatus();

  $('#sessionSeg').addEventListener('seg:change', (e) => {
    session = e.detail;
    saveUrl();
    paintStatus();
    loadFutures();
    select(selCode);
    optionsReady = false;
    if (tab === 'options') showTab();
  });
  $('#tabSeg').addEventListener('seg:change', (e) => {
    tab = e.detail;
    API.store.set(TAB_KEY, tab);
    saveUrl();
    showTab();
  });
  $('#productSeg').addEventListener('seg:change', async (e) => {
    product = e.detail;
    API.store.set(PRODUCT_KEY, product);
    await loadExpiries();
    loadOptions();
  });
  $('#expirySel').addEventListener('change', (e) => { expiry = e.target.value; loadOptions(); });
  $('#optionsRefresh').addEventListener('click', () => loadOptions());
  ['#futuresRows', '#optionsRows'].forEach((id) => $(id).addEventListener('click', (e) => {
    const cell = e.target.closest('[data-code]');
    if (cell && cell.dataset.code !== selCode) select(cell.dataset.code);
  }));

  loadFutures(); // KOSPI200 지수도 여기서 받는다. 주소에 code 가 없으면 최근월 선물을 상세로 연다
  if (selCode) select(selCode);
  showTab();

  // ── 자동 갱신 (탭이 보일 때만) ──
  setInterval(() => {
    paintStatus();
    if (!document.hidden && tab === 'futures') loadFutures({ quiet: true });
  }, FUTURES_MS);
  setInterval(() => {
    if (!document.hidden && tab === 'options') loadOptions({ quiet: true });
  }, OPTIONS_MS);
};
