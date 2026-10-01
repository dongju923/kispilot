/* 공통 UI 헬퍼 — 숫자 포맷, 로딩/오류 상태, 목록 렌더링, 여러 화면이 공유하는 조각(종목 헤더, 호가창). */
(function () {
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

  const isNum = (n) => typeof n === 'number' && !Number.isNaN(n);
  const fmt = (n, d = 0) => (isNum(n)
    ? n.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d })
    : '—');
  const sign = (n) => (n > 0 ? '+' : n < 0 ? '−' : '');
  const cls = (n) => (n > 0 ? 'up' : n < 0 ? 'dn' : 'flat');
  const signed = (n, d = 0) => (isNum(n) ? sign(n) + fmt(Math.abs(n), d) : '—');
  const pct = (n, d = 2) => (isNum(n) ? signed(n, d) + '%' : '—');
  const arrow = (n, d = 0) => (isNum(n) ? (n > 0 ? '▲' : n < 0 ? '▼' : '') + fmt(Math.abs(n), d) : '—');

  /* 큰 금액(원 단위)을 조/억 단위로 */
  function unit(n) {
    if (!isNum(n)) return '—';
    const a = Math.abs(n);
    const s = n < 0 ? '−' : '';
    if (a >= 1e11) return s + fmt(a / 1e12, 1) + '조';
    if (a >= 1e8) return s + fmt(Math.round(a / 1e8)) + '억';
    if (a >= 1e4) return s + fmt(Math.round(a / 1e4)) + '만';
    return s + fmt(a);
  }
  const signedUnit = (n) => (isNum(n) ? (n > 0 ? '+' : '') + unit(n) : '—');

  /* 호가 단위(KRX 기준) */
  function tickSize(p) {
    if (p < 2000) return 1;
    if (p < 5000) return 5;
    if (p < 20000) return 10;
    if (p < 50000) return 50;
    if (p < 200000) return 100;
    if (p < 500000) return 500;
    return 1000;
  }

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* 컨테이너에 목록을 채운다. 비어 있으면 empty 문구 */
  function fill(target, items, tpl, empty = '조회된 내역이 없습니다.') {
    const el = typeof target === 'string' ? $(target) : target;
    if (!el) return;
    el.innerHTML = items.length ? items.map(tpl).join('') : stateHtml('empty', empty);
  }

  /* ── 로딩 / 오류 상태 ─────────────────── */
  function stateHtml(kind, message, code) {
    const icon = kind === 'loading' ? '<span class="spin" aria-hidden="true"></span>' : '';
    const codeHtml = code ? ` <span class="mono">[${esc(code)}]</span>` : '';
    return `<div class="state ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${icon}<span>${esc(message)}${codeHtml}</span></div>`;
  }
  const loadingHtml = (msg = '불러오는 중…') => stateHtml('loading', msg);
  const errorHtml = (e) => {
    // 앱키 미등록: 카드마다 같은 오류를 띄우지 않고 짧게 안내 (자세한 방법은 상단 배너)
    if (e && e.code === 'NO_CREDENTIALS') return stateHtml('empty', '앱키를 등록하면 볼 수 있습니다.');
    return stateHtml(e && e.code === 'REAL_ONLY' ? 'empty' : 'error', (e && e.message) || '불러오지 못했습니다.',
      e && e.code && !['REAL_ONLY', 'NETWORK', 'ERROR'].includes(e.code) ? e.code : '');
  };

  /* task() 결과를 render(el, data) 로 그린다. 실패하면 카드 안에 사유를 표시.
   * quiet=true(자동 갱신)면 로딩 표시 없이 기존 내용을 유지하고, 실패해도 기존 내용을 남긴다. */
  async function load(target, task, render, { quiet = false } = {}) {
    const el = typeof target === 'string' ? $(target) : target;
    if (!el) return undefined;
    if (!quiet) el.innerHTML = loadingHtml();
    try {
      const data = await task();
      render(el, data);
      return data;
    } catch (e) {
      console.error(e);
      if (!quiet) el.innerHTML = errorHtml(e);
      return undefined;
    }
  }

  /* 현재 URL 의 ?code= 를 유지한 링크 */
  function withQuery(href) {
    const code = new URLSearchParams(location.search).get('code');
    return code ? `${href}?code=${encodeURIComponent(code)}` : href;
  }

  /* ── 알림 ─────────────────────────────── */
  let toastTimer;
  function toast(msg, kind = '') {
    let t = $('#toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'toast';
      t.className = 'toast';
      t.setAttribute('role', 'status');
      t.setAttribute('aria-live', 'polite');
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.className = `toast show ${kind}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), kind === 'error' ? 5000 : 2800);
  }

  const STAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/></svg>';
  const STAR_O = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/></svg>';

  /* 관심종목 별 버튼 (data-watch="종목코드") */
  const starButton = (code, name, ghost = false) => {
    const on = window.Watch && Watch.has(code);
    return `<button type="button" class="icon-btn${ghost ? ' ghost' : ''}" data-watch="${esc(code)}" aria-pressed="${on}" aria-label="${esc(name || code)} 관심종목">${on ? STAR : STAR_O}</button>`;
  };

  /* 종목 헤더. compact=true 면 한 줄 요약형(수급·재무 탭) */
  function stockHeader(el, s, { compact = false, api = 'inquire_price', stats, tradeHref } = {}) {
    if (!el) return;
    const c = cls(s.diff);
    const href = (side) => (tradeHref ? tradeHref(side) : `trade.html?code=${encodeURIComponent(s.code)}&side=${side}`);
    const actions = `
      <a class="btn btn-buy" href="${href('buy')}">매수</a>
      <a class="btn btn-sell" href="${href('sell')}">매도</a>`;
    const tags = (s.tags || [s.market, s.sector]).filter(Boolean).map((t) => `<span class="chip sm">${esc(t)}</span>`).join('');

    if (compact) {
      el.className = 'card stock-head compact';
      el.innerHTML = `
        <h2 class="stock-head__name">${esc(s.name)}</h2>
        <span class="mono cap" style="font-size:13px">${esc(s.code)}</span>
        ${tags}
        ${starButton(s.code, s.name)}
        <span class="mono ${c}" style="font-size:22px;font-weight:500;margin-left:12px">${fmt(s.price)}</span>
        <span class="mono ${c}">${arrow(s.diff)}&nbsp; ${pct(s.pct)}</span>
        <span class="api ml-auto">${esc(api)}</span>${actions}`;
      return;
    }

    const list = stats || [
      ['시가', fmt(s.open)], ['고가', fmt(s.high), 'up'], ['저가', fmt(s.low), 'dn'],
      ['거래량', s.volume == null ? '—' : `${unit(s.volume)}주`], ['시가총액', unit(s.marketCap)],
      ['PER', fmt(s.per, 2)], ['PBR', fmt(s.pbr, 2)], ['52주 최고', fmt(s.high52)], ['52주 최저', fmt(s.low52)],
    ];
    el.className = 'card stock-head';
    el.innerHTML = `
      <div class="row" style="flex-wrap:wrap">
        <h2 class="stock-head__name">${esc(s.name)}</h2>
        <span class="mono cap" style="font-size:13px">${esc(s.code)}</span>
        ${tags}
        ${starButton(s.code, s.name)}
        <span class="api ml-auto">${esc(api)}</span>
        ${actions}
      </div>
      <div class="stock-head__body">
        <div class="stock-head__price">
          <span class="price-big ${c}">${fmt(s.price)}</span>
          <span class="mono ${c}" style="font-size:15px">${arrow(s.diff)}&nbsp; ${pct(s.pct)}</span>
        </div>
        <dl class="stats" style="--n:${list.length}">
          ${list.map(([k, v, vc]) => `<div><dt>${esc(k)}</dt><dd class="${vc || ''}">${esc(v)}</dd></div>`).join('')}
        </dl>
      </div>`;
  }

  /* 호가창. clickable=true 면 가격이 버튼이 되어 'ladder:pick' 이벤트를 보낸다 */
  function ladder(el, book, { clickable = false, current, showTotal = true } = {}) {
    if (!el) return;
    const qtys = [...book.asks, ...book.bids].map((x) => x[1] || 0);
    const max = Math.max(1, ...qtys);
    const w = (q) => Math.round(((q || 0) / max) * 100) + '%';
    const priceCell = (p, side) => {
      const cur = p === current ? ' current' : '';
      return clickable
        ? `<button type="button" class="ladder__price ${side}${cur}" data-price="${p}">${fmt(p)}</button>`
        : `<span class="ladder__price ${side}${cur}">${fmt(p)}</span>`;
    };
    const askRows = book.asks.map(([p, q]) => `
      <div class="ladder__row">
        <div class="ladder__qty ask"><i style="width:${w(q)}"></i><span>${fmt(q)}</span></div>
        ${priceCell(p, 'ask')}<span></span>
      </div>`).join('');
    const bidRows = book.bids.map(([p, q]) => `
      <div class="ladder__row">
        <span></span>${priceCell(p, 'bid')}
        <div class="ladder__qty bid"><i style="width:${w(q)}"></i><span>${fmt(q)}</span></div>
      </div>`).join('');
    const foot = showTotal && book.totalAsk != null ? `
      <div class="ladder__row foot">
        <span class="mono r dn">${fmt(book.totalAsk)}</span><span class="c cap">총잔량</span><span class="mono up">${fmt(book.totalBid)}</span>
      </div>` : '';
    const empty = !book.asks.length && !book.bids.length ? stateHtml('empty', '호가가 없습니다 (장 운영 시간 외).') : '';
    el.innerHTML = `
      <div class="ladder__row head"><span class="r">매도잔량</span><span class="c">${clickable ? '가격 선택' : '호가'}</span><span>매수잔량</span></div>
      ${empty || askRows + bidRows}${foot}`;
    if (clickable && !el.dataset.bound) {
      el.dataset.bound = '1';
      el.addEventListener('click', (e) => {
        const b = e.target.closest('[data-price]');
        if (b) el.dispatchEvent(new CustomEvent('ladder:pick', { detail: Number(b.dataset.price), bubbles: true }));
      });
    }
  }

  /* 관심종목 별 토글 → 브라우저에 저장 */
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-watch]');
    if (!b || !window.Watch) return;
    const on = Watch.toggle(b.dataset.watch);
    b.setAttribute('aria-pressed', String(on));
    b.innerHTML = on ? STAR : STAR_O;
    toast(on ? '관심종목에 추가했습니다.' : '관심종목에서 뺐습니다.');
  });

  window.UI = {
    esc, fmt, sign, cls, signed, pct, arrow, unit, signedUnit, tickSize, $, $$,
    fill, load, loadingHtml, errorHtml, stateHtml, withQuery, toast, starButton, stockHeader, ladder,
  };
})();
