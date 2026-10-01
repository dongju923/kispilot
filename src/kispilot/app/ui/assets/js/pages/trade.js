/* 주문 화면 — 현금/신용/예약 주문, 정정·취소, 미체결·체결 조회.
 * 주문은 확인 창을 거친 뒤 POST /api/order/* 로, 상단에서 고른 모드(실전/모의)로 보낸다.
 */
window.renderPage = async function () {
  const { esc, fmt, cls, pct, fill, load, tickSize, toast, $, $$ } = UI;
  const { n, list, first, md, hm } = KIS;
  const code = await API.currentCode('005930');
  const paper = API.isPaper();

  const SIDE_LABEL = { buy: '매수', sell: '매도', modify: '정정' };
  const KIND_LABEL = { cash: '현금', credit: '신용', reserve: '예약' };
  // 호가 유형(ORD_DVSN). 애프터마켓(NXT, 15:30–20:00)에는 애프터 전용 유형만 받는다 — 모의투자는 KRX 만 지원해 정규 유형 유지.
  // 예약주문은 다음 영업일 장 시작에 나가므로 언제나 정규 유형이다.
  const OTYPES = {
    regular: [['00', '지정가'], ['01', '시장가'], ['02', '조건부지정가'], ['03', '최유리지정가'], ['04', '최우선지정가'], ['05', '장전 시간외']],
    after: [['41', '애프터 지정가'], ['44', '애프터 최유리지정가'], ['47', '애프터 최우선지정가']],
  };
  const NO_PRICE = ['01', '03', '04', '05', '44', '47']; // 시장가·최유리·최우선·장전시간외는 가격 입력 없음
  const RESERVE_TYPES = ['00', '01', '02', '05'];
  let session = UI.marketStatus();
  const CREDIT_TYPES = {
    buy: [['21', '자기융자 신규'], ['23', '유통융자 신규']],
    sell: [['25', '자기융자 상환'], ['27', '유통융자 상환'], ['24', '자기대주 신규'], ['22', '유통대주 신규']],
  };

  const side0 = new URLSearchParams(location.search).get('side');
  const state = {
    side: side0 === 'sell' ? 'sell' : 'buy',
    kind: 'cash',
    price: 0,
    qty: 1,
    stock: null,
    cash: null,       // inquire_psbl_order
    creditMax: null,  // inquire_credit_psamount
    holding: null,    // inquire_balance 에서 이 종목
    target: null,     // 정정·취소 대상 주문
    openKind: 'open',
    openRows: [],
  };

  const priceEl = $('#price');
  const qtyEl = $('#qty');
  const toNum = (v) => Number(String(v).replace(/[^\d]/g, '')) || 0;
  const noPrice = () => NO_PRICE.includes($('#otype').value);
  const unitPrice = () => (noPrice() ? (state.stock && state.stock.price) || 0 : state.price);
  const tickFor = (p) => (state.stock && state.stock.tick && tickSize(p) === tickSize(state.stock.price) ? state.stock.tick : tickSize(p));

  // 모의투자에서 안 되는 기능 잠그기
  if (paper) {
    $$('[data-real-only]').forEach((b) => { b.disabled = true; b.title = '실전 계좌 전용'; });
  }

  // ── 종목 · 호가 ──────────────────────────
  async function loadStock() {
    try {
      state.stock = await API.loadStock(code);
    } catch (e) {
      $('#orderStock').innerHTML = UI.errorHtml(e);
      return;
    }
    document.title = `${state.stock.name} 주문 · KISPilot`;
    $('#orderStock').href = `stock.html?code=${encodeURIComponent(code)}`;
    renderStockBox();
    if (!state.price) state.price = state.stock.price || 0;
  }

  function renderStockBox() {
    const s = state.stock;
    $('#orderStock').innerHTML = `
      <span class="col" style="gap:0"><span style="font-weight:600;font-size:15px">${esc(s.name)}</span><span class="mono cap">${esc(code)} · ${esc(s.market || '')}</span></span>
      <span class="col r" style="gap:0"><span class="mono ${cls(s.diff)}" style="font-weight:500">${fmt(s.price)}</span><span class="mono ${cls(s.diff)}" style="font-size:12px">${pct(s.pct)}</span></span>`;
  }

  const renderBook = (book) => UI.ladder($('#ladder'), book, { clickable: true, current: state.stock && state.stock.price, showTotal: false });
  const loadBook = () => load('#ladder', () => API.get('price/inquire_asking_price', { code }), (el, d) => {
    renderBook(KIS.orderbook(d.output1 || {}, 5));
  });
  $('#ladder').addEventListener('ladder:pick', (e) => {
    if (noPrice()) $('#otype').value = OTYPES[otypeSet || 'regular'][0][0]; // 지정가 (정규 00 / 애프터 41)
    state.price = e.detail;
    sync();
  });
  $('#bookRefresh').addEventListener('click', loadBook);

  // ── 보유 · 주문가능 ─────────────────────
  const loadHolding = () => load('#holdInfo', () => API.acct('order/inquire_balance'), (el, d) => {
    const h = list(d.output1).find((r) => r.pdno === code && n(r.hldg_qty) > 0);
    state.holding = h ? {
      qty: n(h.hldg_qty), sellable: n(h.ord_psbl_qty), avg: n(h.pchs_avg_pric), pl: n(h.evlu_pfls_amt), rate: n(h.evlu_pfls_rt),
    } : { qty: 0, sellable: 0 };
    const x = state.holding;
    el.innerHTML = h ? `
      <dl class="kv-list">
        <div class="kv"><dt>보유 수량</dt><dd class="mono">${fmt(x.qty)}주</dd></div>
        <div class="kv"><dt>매도 가능</dt><dd class="mono">${fmt(x.sellable)}주</dd></div>
        <div class="kv"><dt>평균 매입가</dt><dd class="mono">${fmt(x.avg)}</dd></div>
        <div class="kv"><dt>평가 손익</dt><dd class="mono ${cls(x.pl)}">${UI.signed(x.pl)} (${pct(x.rate)})</dd></div>
      </dl>` : UI.stateHtml('empty', '이 종목은 보유하고 있지 않습니다.');
    sync();
  });

  const loadCash = () => API.acct('order/inquire_psbl_order', { pdno: code, ord_dvsn: '01' })
    .then((d) => {
      const o = d.output || {};
      state.cash = { cash: n(o.ord_psbl_cash), buyable: n(o.nrcvb_buy_amt), maxMarket: n(o.nrcvb_buy_qty) };
    })
    .catch((e) => { state.cash = { error: e.message }; })
    .finally(sync);

  function loadCreditMax() {
    if (paper || state.kind !== 'credit' || state.side !== 'buy') return;
    state.creditMax = null;
    API.get('order/inquire_credit_psamount', {
      pdno: code, ord_unpr: noPrice() ? '' : String(state.price), ord_dvsn: $('#otype').value, crdt_type: $('#crdtType').value,
    }).then((d) => { state.creditMax = n((d.output || {}).max_buy_qty) ?? n((d.output || {}).nrcvb_buy_qty); })
      .catch((e) => { state.creditMax = { error: e.message }; })
      .finally(sync);
  }

  function maxQty() {
    if (state.side === 'modify') return state.target ? state.target.left : 0;
    if (state.side === 'sell') return (state.holding && state.holding.sellable) || 0;
    if (state.kind === 'credit') return typeof state.creditMax === 'number' ? state.creditMax : 0;
    const p = unitPrice();
    if (!state.cash || state.cash.error || !p) return 0;
    return Math.floor((state.cash.buyable ?? state.cash.cash ?? 0) / p);
  }

  function renderAvail() {
    const box = $('#availBox');
    let rows;
    let api;
    if (state.side === 'modify') {
      api = paper ? 'inquire_daily_ccld' : 'inquire_psbl_rvsecncl';
      rows = [['정정 가능 수량', state.target ? `${fmt(state.target.left)}주` : '—']];
    } else if (state.side === 'sell') {
      api = 'inquire_balance';
      rows = [['매도 가능', state.holding ? `${fmt(state.holding.sellable)}주` : '조회 중…'], ['평균 매입가', state.holding ? fmt(state.holding.avg) : '—']];
    } else if (state.kind === 'credit') {
      api = 'inquire_credit_psamount';
      const m = state.creditMax;
      rows = [['신용 최대 매수', m && m.error ? m.error : m == null ? '조회 중…' : `${fmt(m)}주`]];
    } else {
      api = 'inquire_psbl_order';
      const c = state.cash;
      rows = c && c.error ? [['주문 가능', c.error]]
        : [['주문가능 현금', c ? fmt(c.cash) : '조회 중…'], ['최대 매수 가능 (현재 가격)', c ? `${fmt(maxQty())}주` : '—']];
    }
    box.innerHTML = `
      <div class="row" style="gap:6px"><span style="font-weight:600">주문 가능</span><span class="api ml-auto">${api}</span></div>
      ${rows.map(([k, v]) => `<div class="between"><span class="cap" style="font-size:13px">${esc(k)}</span><span class="mono r">${esc(v)}</span></div>`).join('')}`;
  }

  // ── 주문 입력 상태 반영 ─────────────────
  function apiName() {
    if (state.side === 'modify') return state.target && state.target.resv ? 'cancel_reservation' : 'revise_order';
    if (state.kind === 'cash') return `${state.side}_cash`;
    if (state.kind === 'credit') return `${state.side}_credit`;
    return `reserve_${state.side}_order`;
  }

  function blockReason() {
    if (state.side === 'modify') {
      if (!state.target) return '오른쪽 미체결 목록에서 [정정] 을 눌러 대상 주문을 고르세요.';
      if (state.target.resv) return '예약주문은 취소만 지원합니다.';
    }
    if (!state.stock) return '종목 정보를 불러오지 못했습니다.';
    if (state.qty <= 0) return '수량을 입력하세요.';
    if (state.side === 'sell' && state.holding && state.qty > state.holding.sellable) {
      return `매도 가능 수량(${fmt(state.holding.sellable)}주)을 넘었습니다.`;
    }
    if (state.side === 'modify' && state.qty > state.target.left) return `정정 가능 수량(${fmt(state.target.left)}주)을 넘었습니다.`;
    if (state.side === 'buy' && state.kind === 'cash' && state.cash && !state.cash.error && state.qty > maxQty()) {
      return `최대 매수 가능 수량(${fmt(maxQty())}주)을 넘었습니다.`;
    }
    if (!noPrice() && state.price <= 0) return '가격을 입력하세요.';
    if (state.kind === 'credit' && state.side === 'sell' && !$('#loanDt').value) return '신용 매도(상환)는 대출일자가 필요합니다.';
    return '';
  }

  // 호가 유형 목록: 장 구간·주문 구분이 바뀔 때만 다시 채운다 (같은 코드가 새 목록에도 있으면 선택 유지)
  let otypeSet = '';
  function fillOtypes() {
    const set = !paper && session.id === 'after' && (state.kind !== 'reserve' || state.side === 'modify') ? 'after' : 'regular';
    if (set === otypeSet) return;
    const sel = $('#otype');
    const prev = sel.value;
    otypeSet = set;
    sel.innerHTML = OTYPES[set].map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    if (OTYPES[set].some(([v]) => v === prev)) sel.value = prev;
    $('#otypeNote').textContent = set === 'after' ? '(애프터마켓 · NXT 15:30–20:00)' : '';
  }

  function sync() {
    fillOtypes();
    const modify = state.side === 'modify';
    priceEl.disabled = noPrice();
    priceEl.value = noPrice() ? '' : fmt(state.price);
    priceEl.placeholder = noPrice() ? $('#otype').selectedOptions[0].textContent : '';
    $$('[data-step="price"]').forEach((b) => { b.disabled = noPrice(); });
    qtyEl.value = fmt(state.qty);
    $('#orderTotal').textContent = fmt(unitPrice() * state.qty);

    $$('#sideTabs [data-side]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.side === state.side)));
    $('#kindRow').hidden = modify;
    $('#creditRow').hidden = modify || state.kind !== 'credit';
    $('#reserveRow').hidden = modify || state.kind !== 'reserve';
    $$('#otype option').forEach((o) => { o.disabled = state.kind === 'reserve' && !modify && !RESERVE_TYPES.includes(o.value); });
    $('#loanReq').textContent = state.side === 'sell' ? '(필수)' : '(선택)';

    const tb = $('#targetBox');
    tb.hidden = !modify;
    tb.innerHTML = state.target
      ? `<span class="cap">정정·취소 대상</span><span><b>${esc(state.target.name)}</b> · ${state.target.side === 'buy' ? '매수' : '매도'} · ${fmt(state.target.price)}원 · 미체결 ${fmt(state.target.left)}주</span><span class="mono cap">${state.target.resv ? `예약순번 ${esc(state.target.seq)}` : `주문번호 ${esc(state.target.odno)}`}</span>`
      : '<span class="cap">미체결 목록에서 [정정] 을 누르면 여기에 표시됩니다.</span>';

    const submit = $('#submitBtn');
    submit.textContent = modify ? '정정 주문' : `${KIND_LABEL[state.kind] === '현금' ? '' : KIND_LABEL[state.kind] + ' '}${SIDE_LABEL[state.side]} 주문`;
    submit.className = `submit ${state.side === 'buy' ? '' : state.side}`;
    $('#cancelBtn').hidden = !(modify && state.target);
    $('#orderApi').textContent = apiName();

    const reason = blockReason();
    submit.disabled = !!reason;
    const note = $('#orderNote');
    if (reason) {
      note.className = 'cap c note warn';
      note.textContent = reason;
    } else {
      note.className = 'cap c';
      note.innerHTML = `${paper ? '모의' : '실전'} 계좌 <span data-account-no></span> · 제출 전 확인 창이 뜹니다`;
      API.session().then((s) => { const a = note.querySelector('[data-account-no]'); if (a) a.textContent = s.accounts[API.mode()] || ''; }).catch(() => {});
    }
    renderAvail();
  }

  // 신용 유형 옵션
  function fillCreditTypes() {
    const types = CREDIT_TYPES[state.side === 'sell' ? 'sell' : 'buy'];
    $('#crdtType').innerHTML = types.map(([v, l]) => `<option value="${v}">${v} · ${l}</option>`).join('');
  }

  // ── 입력 이벤트 ─────────────────────────
  $('#sideTabs').addEventListener('click', (e) => {
    const b = e.target.closest('[data-side]');
    if (!b) return;
    state.side = b.dataset.side;
    if (state.side !== 'modify') state.target = null;
    fillCreditTypes();
    loadCreditMax();
    sync();
  });
  $('#kindSeg').addEventListener('seg:change', (e) => {
    state.kind = e.detail;
    if (state.kind === 'reserve' && !RESERVE_TYPES.includes($('#otype').value)) $('#otype').value = '00';
    loadCreditMax();
    sync();
  });
  $('#otype').addEventListener('change', () => { loadCreditMax(); sync(); });
  document.addEventListener('market:session', (e) => { session = e.detail; sync(); });
  $('#crdtType').addEventListener('change', loadCreditMax);
  $('#loanDt').addEventListener('change', sync);

  $('#orderForm').addEventListener('click', (e) => {
    const b = e.target.closest('[data-step]');
    if (!b) return;
    const dir = Number(b.dataset.dir);
    if (b.dataset.step === 'price') {
      const t = dir < 0 ? tickFor(Math.max(1, state.price - 1)) : tickFor(state.price);
      state.price = Math.max(t, state.price + dir * t);
    } else {
      state.qty = Math.max(1, state.qty + dir);
    }
    sync();
  });
  priceEl.addEventListener('change', () => { state.price = toNum(priceEl.value) || state.price; sync(); });
  qtyEl.addEventListener('change', () => { state.qty = Math.max(1, toNum(qtyEl.value)); sync(); });
  $('#ratioBtns').addEventListener('click', (e) => {
    const b = e.target.closest('[data-ratio]');
    if (!b) return;
    const max = maxQty();
    if (!max) { toast('주문 가능 수량이 없습니다.', 'error'); return; }
    state.qty = Math.max(1, Math.floor(max * Number(b.dataset.ratio)));
    sync();
  });

  // ── 확인 창 ──────────────────────────────
  const dlg = $('#confirmDlg');
  function confirmDialog(title, rows, okClass, okText, warn) {
    $('#confirmTitle').textContent = title;
    fill('#confirmBody', rows, ([k, v]) => `<div class="kv"><dt>${esc(k)}</dt><dd class="mono">${esc(v)}</dd></div>`);
    $('#confirmOk').className = `btn ${okClass}`;
    $('#confirmOk').textContent = okText;
    $('#confirmWarn').textContent = warn || '';
    return new Promise((resolve) => {
      dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'), { once: true });
      dlg.returnValue = '';
      dlg.showModal();
    });
  }

  function buildRequest() {
    const ordDvsn = $('#otype').value;
    const unpr = noPrice() ? '' : String(state.price);
    const qty = String(state.qty);
    if (state.side === 'modify') {
      const t = state.target;
      return {
        path: 'order/revise_order',
        body: { krx_fwdg_ord_orgno: t.orgno, orgn_odno: t.odno, ord_dvsn: ordDvsn, ord_qty: qty, ord_unpr: unpr, qty_all_ord_yn: state.qty >= t.left ? 'Y' : 'N', mode: API.mode() },
      };
    }
    if (state.kind === 'cash') {
      return { path: `order/${state.side}_cash`, body: { code, ord_qty: qty, ord_dvsn: ordDvsn, ord_unpr: unpr, mode: API.mode() } };
    }
    if (state.kind === 'credit') {
      const body = { code, ord_qty: qty, ord_dvsn: ordDvsn, ord_unpr: unpr, crdt_type: $('#crdtType').value };
      const loan = $('#loanDt').value.replace(/-/g, '');
      if (loan) body.loan_dt = loan;
      return { path: `order/${state.side}_credit`, body };
    }
    const body = { pdno: code, ord_qty: qty, ord_dvsn_cd: ordDvsn, ord_unpr: unpr || '0' };
    const end = $('#rsvnEnd').value.replace(/-/g, '');
    if (end) body.rsvn_ord_end_dt = end;
    return { path: `order/reserve_${state.side}_order`, body };
  }

  function orderNo(d) {
    const o = Array.isArray(d.output) ? d.output[0] || {} : d.output || {};
    return o.ODNO || o.odno || o.rsvn_ord_seq || '';
  }

  async function send(path, body, okMsg) {
    try {
      const d = await API.post(path, body);
      const no = orderNo(d);
      toast(`${okMsg}${no ? ` · 번호 ${no}` : ''} — ${(d.msg1 || d.msg || '').trim()}`, 'ok');
      state.target = null;
      if (state.side === 'modify') state.side = 'buy';
      refreshAfterOrder();
    } catch (e) {
      if (e.code === 'KIS_ORDER_UNKNOWN') {
        // 전송은 됐는데 응답을 못 받음 → 접수됐을 수 있으니 목록을 다시 조회해 보여준다 (재전송 금지)
        toast(e.message, 'error');
        loadOpen();
        loadFills();
        loadHolding();
        return;
      }
      toast(`주문 실패: ${e.message}${e.code ? ` [${e.code}]` : ''}`, 'error');
    }
  }

  $('#orderForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (blockReason()) return;
    const req = buildRequest();
    const s = state.stock;
    const otypeName = $('#otype').selectedOptions[0].textContent;
    const rows = state.side === 'modify'
      ? [['대상', `${state.target.name} (${state.target.odno})`], ['정정 가격', noPrice() ? otypeName : `${fmt(state.price)}원`], ['정정 수량', `${fmt(state.qty)}주`]]
      : [['종목', `${s.name} (${code})`], ['구분', `${KIND_LABEL[state.kind]} ${SIDE_LABEL[state.side]} · ${otypeName}`],
        ['가격', noPrice() ? otypeName : `${fmt(state.price)}원`], ['수량', `${fmt(state.qty)}주`], ['예상 금액', `${fmt(unitPrice() * state.qty)}원`]];
    rows.push(['계좌', `${paper ? '모의' : '실전'} · ${req.path.split('/')[1]}`]);
    const okClass = state.side === 'sell' ? 'btn-sell' : state.side === 'modify' ? 'btn-dark' : 'btn-buy';
    const ok = await confirmDialog(`${state.side === 'modify' ? '정정' : SIDE_LABEL[state.side]} 주문 확인`, rows, okClass, '주문 전송',
      paper ? '' : '실전 계좌로 실제 주문이 나갑니다.');
    if (ok) send(req.path, req.body, state.side === 'modify' ? '정정 주문 접수' : '주문 접수');
  });

  async function cancelOrder(t) {
    const rows = [['대상', `${t.name}`], ['구분', `${t.side === 'buy' ? '매수' : '매도'} · ${fmt(t.price)}원`], ['취소 수량', `${fmt(t.left)}주 (잔량 전부)`]];
    const ok = await confirmDialog(t.resv ? '예약주문 취소' : '주문 취소', rows, 'btn-dark', '취소 전송', paper ? '' : '실전 계좌 주문을 취소합니다.');
    if (!ok) return;
    if (t.resv) {
      send('order/cancel_reservation', { rsvn_ord_seq: t.seq }, '예약 취소 접수');
    } else {
      send('order/cancel_order', {
        krx_fwdg_ord_orgno: t.orgno, orgn_odno: t.odno, ord_dvsn: t.dvsn || '00', ord_qty: String(t.left), qty_all_ord_yn: 'Y', mode: API.mode(),
      }, '취소 주문 접수');
    }
  }
  $('#cancelBtn').addEventListener('click', () => state.target && cancelOrder(state.target));

  // ── 미체결 / 예약 ────────────────────────
  const sideOf = (cd) => (cd === '01' ? 'sell' : 'buy'); // 01 매도, 02 매수
  const sideTag = (side) => `<span class="tag ${side === 'buy' ? 'tag-b' : 'tag-s'}">${side === 'buy' ? '매수' : '매도'}</span>`;

  function fetchOpen() {
    if (paper) {
      const today = KIS.ymd();
      return API.acct('order/inquire_daily_ccld', { inqr_strt_dt: today, inqr_end_dt: today, ccld_dvsn: '02' }).then((d) => list(d.output1)
        .filter((r) => n(r.rmn_qty) > 0 && r.cncl_yn !== 'Y')
        .map((r) => ({ odno: r.odno, orgno: r.ord_gno_brno, name: r.prdt_name, code: r.pdno, side: sideOf(r.sll_buy_dvsn_cd), price: n(r.ord_unpr), qty: n(r.ord_qty), left: n(r.rmn_qty), time: r.ord_tmd, dvsn: r.ord_dvsn_cd })));
    }
    return API.get('order/inquire_psbl_rvsecncl').then((d) => list(d.output)
      .filter((r) => n(r.psbl_qty) > 0)
      .map((r) => ({ odno: r.odno, orgno: r.ord_gno_brno, name: r.prdt_name, code: r.pdno, side: sideOf(r.sll_buy_dvsn_cd), price: n(r.ord_unpr), qty: n(r.ord_qty), left: n(r.psbl_qty), time: r.ord_tmd, dvsn: r.ord_dvsn_cd })));
  }

  function fetchResv() {
    return API.realOnly(() => API.get('order/inquire_order_resv_ccnl', { rsvn_ord_ord_dt: KIS.daysAgo(30), rsvn_ord_end_dt: KIS.ymd(), prcs_dvsn_cd: '2', cncl_yn: 'Y' }))
      .then((d) => list(d.output).map((r) => ({
        resv: true, seq: r.rsvn_ord_seq, name: r.kor_item_shtn_name, code: r.pdno, side: sideOf(r.sll_buy_dvsn_cd),
        price: n(r.ord_rsvn_unpr), qty: n(r.ord_rsvn_qty), left: (n(r.ord_rsvn_qty) || 0) - (n(r.tot_ccld_qty) || 0), time: r.rsvn_end_dt, status: r.prcs_rslt,
      })));
  }

  function loadOpen() {
    const resv = state.openKind === 'resv';
    $('#openApis').innerHTML = (resv ? ['inquire_order_resv_ccnl', 'cancel_reservation'] : [paper ? 'inquire_daily_ccld' : 'inquire_psbl_rvsecncl', 'revise_order', 'cancel_order'])
      .map((a) => `<span class="api">${a}</span>`).join('');
    load('#openRows', resv ? fetchResv : fetchOpen, (el, rows) => {
      state.openRows = rows;
      fill(el, rows, (r, i) => `
        <div class="tr xtall">
          <div class="col" style="gap:3px"><span class="row" style="gap:6px">${sideTag(r.side)}<a href="trade.html?code=${esc(r.code)}" style="font-weight:500">${esc(r.name)}</a></span>
            <span class="mono cap">${r.resv ? `예약 ~${KIS.dotDate(r.time)} · #${esc(r.seq)}` : `${hm(r.time)} · #${esc(r.odno)}`}</span></div>
          <div class="col r" style="gap:3px"><span class="mono">${fmt(r.price)}</span><span class="mono cap">${fmt(r.left)} / ${fmt(r.qty)}주</span></div>
          <div class="row" style="justify-content:flex-end;gap:6px">
            <button type="button" class="btn btn-sm" data-act="revise" data-i="${i}" ${r.resv || r.code !== code ? 'disabled title="이 종목 화면에서만 정정할 수 있습니다"' : ''}>정정</button>
            <button type="button" class="btn btn-sm" data-act="cancel" data-i="${i}">취소</button>
          </div>
        </div>`, resv ? '대기 중인 예약주문이 없습니다.' : '미체결 주문이 없습니다.');
    });
  }
  $('#openSeg').addEventListener('seg:change', (e) => { state.openKind = e.detail; loadOpen(); });
  $('#openRefresh').addEventListener('click', loadOpen);
  $('#openRows').addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]');
    if (!b || b.disabled) return;
    const row = state.openRows[Number(b.dataset.i)];
    if (!row) return;
    if (b.dataset.act === 'cancel') { cancelOrder(row); return; }
    state.side = 'modify';
    state.target = row;
    state.price = row.price;
    state.qty = row.left;
    if (row.dvsn && $(`#otype option[value="${row.dvsn}"]`)) $('#otype').value = row.dvsn;
    sync();
    $('#orderForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // ── 체결 내역 ────────────────────────────
  let fillDays = 0;
  const loadFills = () => load('#fillRows', () => API.acct('order/inquire_daily_ccld', { inqr_strt_dt: KIS.daysAgo(fillDays), inqr_end_dt: KIS.ymd(), ccld_dvsn: '01' }), (el, d) => {
    const rows = list(d.output1).filter((r) => n(r.tot_ccld_qty) > 0);
    fill(el, rows, (f) => `
      <div class="tr">
        <span class="mono muted">${md(f.ord_dt)} ${hm(f.ord_tmd)}</span>
        <span class="row" style="gap:6px">${sideTag(sideOf(f.sll_buy_dvsn_cd))}<span style="overflow:hidden;text-overflow:ellipsis">${esc(f.prdt_name)}</span></span>
        <span class="mono r">${fmt(n(f.avg_prvs))}</span>
        <span class="mono r">${fmt(n(f.tot_ccld_qty))}</span>
        <span class="mono r muted">${fmt(n(f.tot_ccld_amt))}</span>
      </div>`, '체결 내역이 없습니다.');
  });
  $('#fillSeg').addEventListener('seg:change', (e) => { fillDays = Number(e.detail); loadFills(); });

  function refreshAfterOrder() {
    loadOpen();
    loadFills();
    loadHolding();
    loadCash();
    loadBook();
    sync();
  }

  // ── 시작 ─────────────────────────────────
  fillCreditTypes();
  sync();
  await loadStock();
  sync();
  loadBook();
  loadHolding();
  loadCash();
  loadOpen();
  loadFills();

  // ── 실시간: 호가창과 현재가 (끊기면 호가 새로고침 버튼으로 수동 조회) ──
  const signedOf = (v, sign) => { const x = n(v); return x != null && (sign === '4' || sign === '5') && x > 0 ? -x : x; };
  Live.connect({ book: [code], ccnl: [code] }, {
    book: (b) => renderBook(KIS.orderbook(b, 5)),
    ccnl(t) {
      if (!state.stock || !n(t.stck_prpr)) return;
      Object.assign(state.stock, { price: n(t.stck_prpr), diff: signedOf(t.prdy_vrss, t.prdy_vrss_sign), pct: signedOf(t.prdy_ctrt, t.prdy_vrss_sign) });
      renderStockBox();
      if (noPrice()) $('#orderTotal').textContent = fmt(unitPrice() * state.qty); // 시장가는 현재가로 예상 금액 계산
    },
    state(on) { $('#bookRefresh').hidden = on; },
    resync() {
      loadBook();
      API.loadStock(code).then((s) => { state.stock = s; renderStockBox(); }).catch(() => {});
    },
  });
};
