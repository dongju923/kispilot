/* 실시간 시세 — 서버 /api/stream (KIS 웹소켓 중계) 을 EventSource 로 받는다.
 *
 *   const live = Live.connect({ ccnl: ['005930'], book: ['005930'] }, {
 *     ccnl: (tick) => ...,        // 체결 1건
 *     book: (orderbook) => ...,   // 호가 갱신
 *     state: (on) => ...,         // true: 실시간 수신 중 / false: 끊김·일시정지 → 화면은 REST 로 대체
 *     resync: () => ...,          // 끊겼다가 다시 이어졌을 때: 놓친 구간을 REST 로 다시 조회
 *   });
 *
 * 연결 생명주기
 *   - 페이지를 떠나면(pagehide) 연결을 닫는다. 서버는 10초 뒤 KIS 구독을 해제한다.
 *   - 탭이 1분 넘게 숨겨지면 닫고, 다시 보이면 새로 연결한다.
 *   - 상단 '실시간' 칩을 누르면 일시정지/재개. 브라우저에 기억되고 열린 다른 탭에도 바로 적용된다.
 *     일시정지 = 브라우저 스트림을 실제로 닫는 것 (값을 무시하는 게 아님).
 *     서버는 다른 탭이 쓰지 않는 구독을 10초 뒤 해제하고, 구독이 없으면 1분 뒤 KIS 접속을 닫는다.
 */
(function () {
  const PAUSE_KEY = 'pykis.livePaused';
  const HIDDEN_CLOSE_MS = 60000;

  const LABEL = {
    idle: ['실시간 대기', 'var(--neutral-bar)'],
    connecting: ['실시간 연결 중', '#D9A441'],
    live: ['실시간', 'var(--ok)'],
    paused: ['실시간 일시정지', 'var(--neutral-bar)'],
    error: ['실시간 오류', 'var(--up)'],
    nokey: ['실시간 꺼짐', 'var(--neutral-bar)'],
    warn: ['실시간', 'var(--ok)'],
    limit: ['실시간 (일부)', '#D9A441'],
  };

  function chip() { return document.getElementById('liveChip'); }

  function paintChip(state, message = '') {
    const el = chip();
    if (!el) return;
    const [label, color] = LABEL[state] || LABEL.idle;
    el.hidden = false;
    el.dataset.state = state;
    el.innerHTML = `<span class="dot${state === 'live' ? ' pulse' : ''}" style="background:${color}"></span>${label}`;
    el.title = message || (state === 'paused' ? '눌러서 실시간 재개' : '눌러서 실시간 일시정지 (REST 조회로 전환)');
    el.setAttribute('aria-pressed', String(state !== 'paused'));
  }

  function connect(topics, handlers = {}) {
    const params = new URLSearchParams();
    Object.entries(topics).forEach(([kind, codes]) => {
      const list = (codes || []).filter(Boolean);
      if (list.length) params.set(kind, list.join(','));
    });
    if (![...params.keys()].length) return { close() {}, isLive: () => false };

    let es = null;
    let hiddenTimer = null;
    let on = false;
    let everLive = false;
    const setOn = (v) => {
      if (on === v) return;
      on = v;
      if (handlers.state) handlers.state(v);
      // 끊겼다가 다시 이어졌으면(재개·탭 복귀·재접속) 그 사이 놓친 값을 REST 로 한 번 채운다
      if (v && everLive && handlers.resync) handlers.resync();
      if (v) everLive = true;
    };

    let noKey = false;
    function open() {
      if (es || noKey) return;
      if (API.store.get(PAUSE_KEY) === '1') { paintChip('paused'); setOn(false); return; }
      paintChip('connecting');
      es = new EventSource(`/api/stream?${params}`);
      es.addEventListener('status', (e) => {
        const s = JSON.parse(e.data);
        paintChip(s.state, s.message);
        if (s.state === 'live' || s.state === 'warn' || s.state === 'limit') setOn(true);
        if (s.state === 'error') setOn(false);
      });
      ['ccnl', 'book', 'member', 'program'].forEach((kind) => {
        if (handlers[kind]) es.addEventListener(kind, (e) => handlers[kind](JSON.parse(e.data)));
      });
      es.onerror = () => {
        // 서버가 내려가거나 재시작 중: EventSource 가 스스로 재접속한다
        paintChip('connecting', '서버에 다시 연결하는 중…');
        setOn(false);
      };
    }

    function close() {
      if (es) { es.close(); es = null; }
      setOn(false);
    }

    const onVisibility = () => {
      if (document.hidden) {
        hiddenTimer = setTimeout(() => { close(); paintChip('idle', '탭이 숨겨져 연결을 쉬는 중'); }, HIDDEN_CLOSE_MS);
      } else {
        clearTimeout(hiddenTimer);
        open();
      }
    };
    const onToggle = () => {
      if (API.store.get(PAUSE_KEY) === '1') {
        API.store.set(PAUSE_KEY, '0');
        open();
      } else {
        API.store.set(PAUSE_KEY, '1');
        close();
        paintChip('paused');
      }
    };

    // 다른 탭에서 일시정지/재개하면 이 탭도 따라간다 (localStorage 변경은 다른 탭에만 알려진다)
    const onStorage = (e) => {
      if (e.key !== PAUSE_KEY) return;
      if (e.newValue === '1') { close(); paintChip('paused'); } else open();
    };

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('pagehide', close);
    window.addEventListener('storage', onStorage);
    chip()?.addEventListener('click', onToggle);
    // 실시간은 실전 앱키로만 된다 → 없으면 연결 시도(3초마다 재접속)를 하지 않는다
    API.session().then((s) => {
      if (s.modes.includes('real')) { open(); return; }
      noKey = true;
      paintChip('nokey', '실시간 시세는 실전 앱키가 필요합니다 (kispilot setup)');
      setOn(false);
    }).catch(() => open());

    return {
      close() {
        close();
        document.removeEventListener('visibilitychange', onVisibility);
        window.removeEventListener('pagehide', close);
        window.removeEventListener('storage', onStorage);
        chip()?.removeEventListener('click', onToggle);
      },
      isLive: () => on,
    };
  }

  window.Live = { connect };
})();
