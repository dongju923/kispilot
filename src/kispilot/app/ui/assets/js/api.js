/* 서버(src/kispilot/app/main.py) API 클라이언트와 KIS 응답 변환 헬퍼.
 *
 *   API.get('price/inquire_price', { code: '005930' })   → data (KIS 응답 본문)
 *   API.post('order/buy_cash', { ... })                   → 주문 (헤더 자동 첨부)
 *   API.acct('order/inquire_balance', {...})              → 현재 모드(real/paper)로 조회
 *
 * 실패하면 ApiError(message, code) 를 던진다. 화면에서는 UI.load() 가 받아 표시한다.
 */
(function () {
  class ApiError extends Error {
    constructor(message, code = 'ERROR', status = 0) {
      super(message);
      this.code = code;
      this.status = status;
    }
  }

  async function request(url, options) {
    let res;
    try {
      res = await fetch(url, options);
    } catch (e) {
      throw new ApiError('서버에 연결할 수 없습니다. kispilot ui 가 실행 중인지 확인하세요.', 'NETWORK');
    }
    let body;
    try {
      body = await res.json();
    } catch (e) {
      throw new ApiError(`서버 응답을 읽을 수 없습니다 (HTTP ${res.status}).`, 'BAD_RESPONSE', res.status);
    }
    if (!body.ok) {
      const err = new ApiError(body.error || '요청이 실패했습니다.', body.code, res.status);
      err.data = body.data; // 예: 백테스트 전략 검증 오류 목록 { errors: [...] }
      throw err;
    }
    return body.data;
  }

  function query(params) {
    const q = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return;
      q.set(k, Array.isArray(v) ? v.join(',') : String(v));
    });
    const s = q.toString();
    return s ? `?${s}` : '';
  }

  const get = (path, params) => request(`/api/${path}${query(params)}`);
  const post = (path, body) => request(`/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'kispilot' },
    body: JSON.stringify(body || {}),
  });
  const del = (path) => request(`/api/${path}`, { method: 'DELETE', headers: { 'X-Requested-With': 'kispilot' } });

  /* ── 모드 ─────────────────────────────── */
  const MODE_KEY = 'pykis.mode';
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* 저장 불가 환경 */ } },
  };
  const mode = () => document.body.dataset.mode || store.get(MODE_KEY) || 'real';
  const isPaper = () => mode() === 'paper';

  /* 계좌/주문 조회: 현재 모드를 붙인다 */
  const acct = (path, params) => get(path, { ...params, mode: mode() });

  /* 실전 전용 API 를 모의 모드에서 부르면 서버 호출 없이 안내 */
  function realOnly(task) {
    if (isPaper()) return Promise.reject(new ApiError('실전 계좌 전용 기능입니다. 상단에서 실전 모드로 전환하세요.', 'REAL_ONLY'));
    return task();
  }

  let sessionPromise;
  const session = () => (sessionPromise ||= get('session'));

  /* ── KIS 값 변환 ───────────────────────── */
  const n = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const x = Number(String(v).replace(/,/g, ''));
    return Number.isFinite(x) ? x : null;
  };
  /* 재무 API 는 제공하지 않는 항목을 99.99 로 내려준다 */
  const nf = (v) => { const x = n(v); return x === 99.99 ? null : x; };
  const pad = (x) => String(x).padStart(2, '0');
  const ymd = (d = new Date()) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  const daysAgo = (k) => { const d = new Date(); d.setDate(d.getDate() - k); return ymd(d); };
  const daysAhead = (k) => daysAgo(-k);
  const md = (s) => (s && s.length >= 8 ? `${s.slice(4, 6)}/${s.slice(6, 8)}` : s || '');
  const dotDate = (s) => (s && s.length >= 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : s || '—');
  const yymm = (s) => (s && s.length >= 6 ? `${s.slice(0, 4)}.${s.slice(4, 6)}` : s || '');
  const hms = (s) => (s && s.length >= 6 ? `${s.slice(0, 2)}:${s.slice(2, 4)}:${s.slice(4, 6)}` : s || '');
  const hm = (s) => (s && s.length >= 4 ? `${s.slice(0, 2)}:${s.slice(2, 4)}` : s || '');
  const list = (v) => (Array.isArray(v) ? v : v ? [v] : []);
  const first = (v) => (Array.isArray(v) ? v[0] || {} : v || {});

  /* 호가(inquire_asking_price output1) → { asks:[[가격,잔량]...높은가격부터], bids, totalAsk, totalBid } */
  function orderbook(out, levels = 5) {
    const asks = [];
    const bids = [];
    for (let i = levels; i >= 1; i -= 1) asks.push([n(out[`askp${i}`]), n(out[`askp_rsqn${i}`])]);
    for (let i = 1; i <= levels; i += 1) bids.push([n(out[`bidp${i}`]), n(out[`bidp_rsqn${i}`])]);
    return {
      asks: asks.filter(([p]) => p),
      bids: bids.filter(([p]) => p),
      totalAsk: n(out.total_askp_rsqn),
      totalBid: n(out.total_bidp_rsqn),
    };
  }

  /* ── 종목 ─────────────────────────────── */
  const MARKET_NAME = { KOSPI: 'KOSPI', KOSDAQ: 'KOSDAQ' };
  const nameCache = new Map();

  /* 종목코드 → { code, name, market } (KIS 마스터 파일 검색, KIS 호출 없음) */
  async function stockMeta(code) {
    if (nameCache.has(code)) return nameCache.get(code);
    const task = get('search/stock', { q: code, limit: 5 })
      .then((rows) => rows.find((r) => r.code === code) || { code, name: code, market: '' })
      .catch(() => ({ code, name: code, market: '' }));
    nameCache.set(code, task);
    return task;
  }

  /* URL ?code= (없으면 마지막으로 본 종목, 그것도 없으면 기본값). ?q= 이름이면 검색해서 코드로 바꾼다 */
  async function currentCode(fallback, key = 'pykis.lastCode') {
    const params = new URLSearchParams(location.search);
    let code = (params.get('code') || '').trim();
    const q = (params.get('q') || '').trim();
    if (!code && q) {
      const rows = await get('search/stock', { q, limit: 1 }).catch(() => []);
      if (rows[0]) {
        code = rows[0].code;
        params.delete('q');
        params.set('code', code);
        history.replaceState(null, '', `${location.pathname}?${params}`);
      }
    }
    code = code || store.get(key) || fallback;
    store.set(key, code);
    return code;
  }

  /* inquire_price output + 메타 → 종목 헤더용 객체 */
  function stockFromPrice(out, meta) {
    return {
      code: meta.code,
      name: meta.name,
      market: MARKET_NAME[meta.market] || out.rprs_mrkt_kor_name || meta.market,
      sector: out.bstp_kor_isnm,
      price: n(out.stck_prpr),
      diff: n(out.prdy_vrss),
      pct: n(out.prdy_ctrt),
      open: n(out.stck_oprc),
      high: n(out.stck_hgpr),
      low: n(out.stck_lwpr),
      volume: n(out.acml_vol),
      marketCap: n(out.hts_avls) == null ? null : n(out.hts_avls) * 1e8, // 억원
      per: n(out.per),
      pbr: n(out.pbr),
      high52: n(out.w52_hgpr),
      low52: n(out.w52_lwpr),
      programNet: n(out.pgtr_ntby_qty),
      tick: n(out.aspr_unit),
      raw: out,
    };
  }

  /* 종목 헤더 데이터: 이름(마스터 검색) + 현재가(inquire_price) */
  async function loadStock(code) {
    const [meta, d] = await Promise.all([stockMeta(code), get('price/inquire_price', { code })]);
    return stockFromPrice(d.output || {}, meta);
  }

  /* ── 관심종목 (브라우저에 저장) ─────────── */
  const WATCH_KEY = 'pykis.watch';
  const WATCH_DEFAULT = ['005930', '000660', '373220', '207940', '005380', '035420', '068270'];
  const Watch = {
    list() {
      try {
        const v = JSON.parse(store.get(WATCH_KEY));
        return Array.isArray(v) ? v : WATCH_DEFAULT.slice();
      } catch (e) {
        return WATCH_DEFAULT.slice();
      }
    },
    has(code) { return Watch.list().includes(code); },
    toggle(code) {
      const cur = Watch.list();
      const next = cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code].slice(-30);
      store.set(WATCH_KEY, JSON.stringify(next));
      return next.includes(code);
    },
  };

  window.ApiError = ApiError;
  window.API = { get, post, del, acct, realOnly, session, mode, isPaper, stockMeta, loadStock, currentCode, store, MODE_KEY };
  window.KIS = { n, nf, ymd, daysAgo, daysAhead, md, dotDate, yymm, hms, hm, list, first, orderbook, stockFromPrice };
  window.Watch = Watch;
})();
