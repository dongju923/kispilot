/* 앱 골격 — 사이드바·상단 바를 그리고 공통 인터랙션(세그먼트 토글, 모드 전환, 종목 검색)을 붙인다.
 * 각 페이지 <body> 에 data-page / data-section / data-title 를 두고
 * <aside id="sidebar"> 와 <header id="topbar"> 자리를 비워 두면 된다.
 */
(function () {
  const NAV = [
    { label: '시장', items: [
      { id: 'dashboard', label: '대시보드', href: 'index.html', icon: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z' },
      { id: 'market', label: '시장·업종', href: 'market.html', icon: 'M3 17l6-6 4 4 8-8M15 7h6v6' },
      { id: 'ranking', label: '순위 분석', href: 'ranking.html', icon: 'M5 20V11M12 20V4M19 20v-6M3 20h18' },
    ]},
    { label: '종목', items: [
      { id: 'stock', label: '종목 분석', href: 'stock.html', icon: 'M7 3v18M4 8h6v8H4zM17 3v18M14 6h6v7h-6z' },
      { id: 'etf', label: 'ETF', href: 'etf.html', icon: 'M12 3l9 5-9 5-9-5zM3 13l9 5 9-5' },
    ]},
    { label: '매매', items: [
      { id: 'trade', label: '주문', href: 'trade.html', icon: 'M4 8h14l-4-4M20 16H6l4 4' },
      { id: 'account', label: '계좌', href: 'account.html', icon: 'M3 7h18v13H3zM6 7l2-3h8l2 3M16 14h2' },
    ]},
    { label: '전략', items: [
      { id: 'backtest', label: '백테스트', href: 'backtest.html', icon: 'M3 3v18h18M7 15l4-5 3 3 5-7' },
    ]},
  ];

  const icon = (d) => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;

  /* 장 운영 상태 (공휴일은 반영하지 않음). id 는 주문 화면이 호가 유형을 고를 때 쓴다.
     NXT: 프리마켓 08:00–08:50, 애프터마켓 15:30–20:00 */
  function marketStatus(now = new Date()) {
    const day = now.getDay();
    const t = now.getHours() * 100 + now.getMinutes();
    if (day === 0 || day === 6) return { id: 'closed', label: '휴장 (주말)', on: false };
    if (t >= 800 && t < 850) return { id: 'pre', label: '프리마켓 (NXT) · ~08:50', on: true };
    if (t >= 850 && t < 900) return { id: 'auction', label: '장전 · 동시호가', on: true };
    if (t >= 900 && t < 1520) return { id: 'regular', label: '정규장 · 09:00–15:30', on: true };
    if (t >= 1520 && t < 1530) return { id: 'auction', label: '장마감 동시호가', on: true };
    if (t >= 1530 && t < 2000) return { id: 'after', label: '애프터마켓 (NXT) · ~20:00', on: true };
    return { id: 'closed', label: '장 마감', on: false };
  }
  UI.marketStatus = marketStatus;

  function tokenText(tok) {
    if (!tok || !tok.issued) return '토큰 미발급 · 첫 조회 때 발급';
    const m = Math.floor(tok.seconds_left / 60);
    return `토큰 유효 · ${Math.floor(m / 60)}시간 ${m % 60}분`;
  }

  function renderSidebar(el, page) {
    el.className = 'sidebar';
    el.innerHTML = `
      <a class="brand" href="index.html">
        <span class="brand__mark" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24"><path d="M4.5 11.2 19.5 4.5l-6.7 15-2.1-6.4z" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></span>
        <span class="brand__text"><span class="brand__name">KISPilot</span><span class="brand__sub">Trading Console</span></span>
      </a>
      <nav class="nav" aria-label="주 메뉴">
        ${NAV.map((g) => `
          <div class="nav__group">
            <div class="nav__label">${g.label}</div>
            ${g.items.map((it) => `
              <a class="nav__item" href="${it.href}" title="${it.label}" ${it.id === page ? 'aria-current="page"' : ''}>
                ${icon(it.icon)}<span>${it.label}</span>
              </a>`).join('')}
          </div>`).join('')}
      </nav>
      <div class="acct">
        <div class="acct__row"><span>연결 계좌</span><span class="acct__mode" data-mode-badge></span></div>
        <div class="acct__no" data-account-no>—</div>
        <div class="acct__token"><span class="dot" data-token-dot></span><span data-token-text>세션 확인 중…</span></div>
      </div>`;
  }

  function renderTopbar(el, section, title, mode) {
    const st = marketStatus();
    el.className = 'topbar';
    el.innerHTML = `
      <div class="topbar__title"><span class="cap">${UI.esc(section)}</span><h1>${UI.esc(title)}</h1></div>
      <form class="search" role="search" data-search autocomplete="off">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B717C" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input type="search" name="q" aria-label="종목 검색" placeholder="종목명 또는 코드 검색 (예: 삼성전자, 005930)"
               role="combobox" aria-expanded="false" aria-controls="searchPop" aria-autocomplete="list">
        <span class="kbd">/</span>
        <ul class="search-pop" id="searchPop" role="listbox" hidden></ul>
      </form>
      <button type="button" class="chip live-chip" id="liveChip" hidden></button>
      <span class="chip" data-market-chip><span class="dot" style="background:${st.on ? 'var(--ok)' : 'var(--neutral-bar)'}"></span><span data-market-label>${st.label}</span></span>
      <div class="seg" role="group" aria-label="투자 모드" data-mode-seg>
        <button type="button" data-value="real" class="${mode === 'real' ? 'on' : ''}">실전</button>
        <button type="button" data-value="paper" class="${mode === 'paper' ? 'on' : ''}">모의</button>
      </div>`;
  }

  function applySession(s, mode) {
    UI.$$('[data-mode-badge]').forEach((b) => {
      b.textContent = mode === 'paper' ? '모의' : '실전';
      b.classList.toggle('paper', mode === 'paper');
    });
    UI.$$('[data-account-no]').forEach((n) => { n.textContent = (s && s.accounts[mode]) || '계좌 미설정'; });
    UI.$$('[data-mode-label]').forEach((n) => { n.textContent = mode === 'paper' ? '모의' : '실전'; });
    const tok = s && s.tokens[mode];
    UI.$$('[data-token-text]').forEach((n) => { n.textContent = s ? tokenText(tok) : '서버 연결 실패'; });
    UI.$$('[data-token-dot]').forEach((d) => { d.style.background = tok && tok.issued ? 'var(--ok)' : 'var(--neutral-bar)'; });
    if (s) {
      UI.$$('[data-mode-seg] button').forEach((b) => {
        const available = s.modes.includes(b.dataset.value);
        b.disabled = !available;
        if (!available) b.title = '이 모드의 앱키가 없습니다 (터미널에서 kispilot setup)';
      });
    }
  }

  /* 앱키가 하나도 없으면(처음 실행) 등록 방법을 페이지 위에 안내한다 */
  function renderSetupBanner(s) {
    const content = UI.$('main.content');
    if (!content || (s.modes && s.modes.length) || UI.$('.setup-banner')) return;
    const el = document.createElement('section');
    el.className = 'setup-banner';
    el.setAttribute('role', 'note');
    el.innerHTML = `
      <div class="setup-banner__title">한국투자증권 앱키를 등록해 주세요</div>
      <ol>
        <li><a href="https://apiportal.koreainvestment.com" target="_blank" rel="noopener">KIS Developers</a> 에서 Open API 를 신청하고 앱키·앱시크릿을 발급받습니다 (실전·모의투자 각각).</li>
        <li>터미널에서 <code>kispilot setup</code> 을 실행해 앱키·시크릿·계좌번호를 입력합니다. 키는 이 PC 의 OS 키체인에만 저장됩니다.</li>
        <li>이 서버를 다시 시작합니다 (<code>Ctrl+C</code> 후 <code>kispilot ui</code>).</li>
      </ol>
      <p class="cap">키 없이도 <a href="backtest.html">백테스트</a>와 종목 차트(yfinance)는 쓸 수 있습니다. 앱키는 채팅창이나 파일에 붙여넣지 마세요.</p>`;
    content.prepend(el);
  }

  /* ── 종목 검색 자동완성 ───────────────── */
  function bindSearch(form) {
    const input = form.querySelector('input');
    const pop = form.querySelector('.search-pop');
    const page = document.body.dataset.page;
    const target = ['etf', 'trade'].includes(page) ? `${page}.html`
      : location.pathname.match(/stock[\w-]*\.html$/) ? location.pathname.split('/').pop() : 'stock.html';
    let items = [];
    let active = -1;
    let timer;
    let seq = 0;

    const close = () => { pop.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; };
    const go = (code) => { location.href = `${target}?code=${encodeURIComponent(code)}`; };
    const paint = () => {
      pop.innerHTML = items.length
        ? items.map((it, i) => `
            <li role="option" id="sp-${i}" data-code="${UI.esc(it.code)}" aria-selected="${i === active}">
              <b>${UI.esc(it.name)}</b><span class="mono cap">${UI.esc(it.code)}</span><span class="cap ml-auto">${UI.esc(it.market)}</span>
            </li>`).join('')
        : '<li class="cap" aria-disabled="true">검색 결과가 없습니다.</li>';
      pop.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      input.setAttribute('aria-activedescendant', active >= 0 ? `sp-${active}` : '');
    };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) { close(); return; }
      timer = setTimeout(async () => {
        const my = ++seq;
        try {
          const rows = await API.get('search/stock', { q, limit: 8 });
          if (my !== seq) return;
          items = rows;
          active = rows.length ? 0 : -1;
          paint();
        } catch (e) {
          items = [];
          close();
        }
      }, 180);
    });
    input.addEventListener('keydown', (e) => {
      if (pop.hidden || !items.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); active = (active + 1) % items.length; paint(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); active = (active - 1 + items.length) % items.length; paint(); }
      if (e.key === 'Escape') close();
    });
    pop.addEventListener('mousedown', (e) => {
      const li = e.target.closest('[data-code]');
      if (li) { e.preventDefault(); go(li.dataset.code); }
    });
    input.addEventListener('blur', () => setTimeout(close, 120));
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      if (items[active]) go(items[active].code);
      else if (/^[0-9A-Z]{6}$/i.test(q)) go(q.toUpperCase());
      else location.href = `${target}?q=${encodeURIComponent(q)}`;
    });
  }

  /* 세그먼트 버튼: 형제 중 하나만 .on — 'seg:change' 이벤트로 값 전달 */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.seg button');
    if (!btn || btn.disabled) return;
    const seg = btn.parentElement;
    if (btn.classList.contains('on') && !seg.hasAttribute('data-mode-seg')) return;
    UI.$$('button', seg).forEach((b) => b.classList.toggle('on', b === btn));
    seg.dispatchEvent(new CustomEvent('seg:change', { detail: btn.dataset.value ?? btn.textContent.trim(), bubbles: true }));
  });

  /* '/' 로 검색창 포커스 */
  document.addEventListener('keydown', (e) => {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return;
    const input = UI.$('[data-search] input');
    if (input) { e.preventDefault(); input.focus(); }
  });

  document.addEventListener('DOMContentLoaded', async () => {
    const body = document.body;
    const mode = API.store.get(API.MODE_KEY) || 'real';
    body.dataset.mode = mode;

    const side = UI.$('#sidebar');
    const top = UI.$('#topbar');
    if (side) renderSidebar(side, body.dataset.page);
    if (top) renderTopbar(top, body.dataset.section || '', body.dataset.title || document.title, mode);
    applySession(null, mode);

    // 페이지를 열어 둔 채 장 구간이 바뀌면 표시를 고치고 'market:session' 으로 알린다 (주문 화면의 호가 유형 등)
    let sessionId = marketStatus().id;
    setInterval(() => {
      const st = marketStatus();
      const chip = UI.$('[data-market-chip]');
      if (chip) {
        chip.querySelector('[data-market-label]').textContent = st.label;
        chip.querySelector('.dot').style.background = st.on ? 'var(--ok)' : 'var(--neutral-bar)';
      }
      if (st.id !== sessionId) {
        sessionId = st.id;
        document.dispatchEvent(new CustomEvent('market:session', { detail: st }));
      }
    }, 30000);

    UI.$('[data-mode-seg]')?.addEventListener('seg:change', (e) => {
      if (e.detail === API.mode()) return;
      API.store.set(API.MODE_KEY, e.detail);
      location.reload(); // 계좌/주문 데이터를 새 모드로 다시 조회
    });
    const form = UI.$('[data-search]');
    if (form) bindSearch(form);

    /* 종목 탭 등 ?code= 를 이어받아야 하는 링크 */
    UI.$$('a[data-keep-query]').forEach((a) => { a.href = UI.withQuery(a.getAttribute('href')); });

    API.session()
      .then((s) => {
        // 앱키가 없는 모드가 저장돼 있으면 사용 가능한 모드로 되돌린다
        if (!s.modes.includes(mode) && s.default_mode) {
          API.store.set(API.MODE_KEY, s.default_mode);
          location.reload();
          return;
        }
        applySession(s, mode);
        renderSetupBanner(s);
      })
      .catch(() => {
        applySession(null, mode);
        UI.toast('서버에 연결할 수 없습니다. 터미널에서 kispilot ui 를 실행했는지 확인하세요.', 'error');
      });

    if (typeof window.renderPage === 'function') window.renderPage();
  });
})();
