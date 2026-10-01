/* 가격 차트 — TradingView Lightweight Charts(v4) 래퍼.
 *
 *   const pc = PriceChart.create(el, { panes: panesEl });
 *   pc.load({ code: '005930', tf: 'D' });              // 종목/ETF
 *   pc.load({ code: '0001', tf: '5m', kind: 'index' }); // 지수
 *   pc.load({...}, { quiet: true });                    // 자동 갱신: 로딩 표시 없이, 보던 구간 유지
 *   pc.tick({...});                                     // 실시간 체결 반영
 *   pc.setIndicators({ maType, ma, overlays, subs, volume });   // chart-tools.js 가 호출
 *
 * 데이터는 서버 /api/chart (src/kispilot/app/utils/chart.py) 에서 받고, 지표는 indicators.js 로 계산한다.
 * 분봉 time 은 KST 시각을 UTC 로 취급한 유닉스 초라서 차트에 KST 그대로 보인다.
 *
 * 보조 차트 설계 (v4 는 한 차트에 여러 칸을 나눌 수 없음)
 *   - 보조 지표마다 작은 차트를 panes 안에 따로 만든다.
 *   - 모든 차트에 같은 봉 시간 목록을 넣는다 (값이 없는 구간은 whitespace) → 봉 순번(logical)이 1:1 로 맞는다.
 *   - 한 차트의 보이는 구간(logical range)이 바뀌면 나머지에 그대로 적용, 십자선도 같은 시점으로 맞춘다.
 *   - 오른쪽 가격축 폭을 PRICE_AXIS_W 로 고정해 세로 정렬을 맞추고, 시간축은 가격 차트에만 보인다.
 *   - 실시간 체결은 캔들을 바로 갱신하고, 지표는 0.5초에 한 번 몰아서 다시 계산한다.
 */
(function () {
  const C = {
    up: '#C6302A', down: '#1D5BD6', text: '#4A505B', grid: '#F1EFEA', border: '#E4E2DB',
    upVol: 'rgba(198, 48, 42, .35)', downVol: 'rgba(29, 91, 214, .35)', zero: '#6b728080',
  };
  /* 이동평균 [기간, 색] — 색은 chart-tools.js 의 이동평균 메뉴와 같다 */
  const MAS = [[5, '#E8890C'], [20, '#7B3FC4'], [60, '#2E9E5B'], [120, '#8A8F99']];
  const MA_PREFIX = { sma: 'MA', ema: 'EMA', wma: 'WMA' };
  /* 주기별 처음 보여줄 봉 수 */
  const VISIBLE = { '1m': 390, '5m': 234, '30m': 140, D: 250, W: 156, M: 120, Y: 0 };
  const TF_LABEL = { '1m': '1분', '5m': '5분', '30m': '30분', D: '일', W: '주', M: '월', Y: '년' };
  const PRICE_AXIS_W = 72;
  const RECALC_MS = 500;

  const { fmt, esc } = UI;
  const isNum = (x) => typeof x === 'number' && !Number.isNaN(x);
  const timeKey = (t) => (typeof t === 'object' && t ? `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}` : String(t));
  const priceDigits = (v) => (Math.abs(v) < 10000 && v % 1 !== 0 ? 2 : 0);
  /* 보조 차트 축/값: 큰 값(OBV·AD 등)은 만·억 단위로 */
  const subFmt = (v) => (!isNum(v) ? '—' : Math.abs(v) >= 1e5 ? UI.unit(v) : fmt(v, Math.abs(v) >= 1000 ? 0 : 2));

  function timeLabel(t, intraday) {
    if (!intraday) return typeof t === 'string' ? t.replace(/-/g, '.') : timeKey(t).replace(/-/g, '.');
    const d = new Date(t * 1000);
    const p = (x) => String(x).padStart(2, '0');
    return `${d.getUTCFullYear()}.${p(d.getUTCMonth() + 1)}.${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
  }

  const baseOptions = (LWC) => ({
    autoSize: true,
    layout: { background: { type: 'solid', color: '#FFFFFF' }, textColor: C.text, fontFamily: "'IBM Plex Mono', 'IBM Plex Sans KR', monospace", fontSize: 11 },
    grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
    crosshair: { mode: LWC.CrosshairMode.Normal },
    rightPriceScale: { borderColor: C.border, minimumWidth: PRICE_AXIS_W },
    timeScale: { borderColor: C.border, rightOffset: 4, minBarSpacing: 0.5 },
  });

  function create(host, { panes = null } = {}) {
    if (!window.LightweightCharts) {
      host.innerHTML = UI.stateHtml('error', '차트 라이브러리를 불러오지 못했습니다 (인터넷 연결 확인).');
      return { load() {}, tick() {}, setIndicators() {}, destroy() {} };
    }
    const LWC = window.LightweightCharts;
    host.classList.add('chart-box');
    host.innerHTML = '<div class="chart-canvas"></div><div class="chart-tip" hidden></div><div class="chart-state" hidden></div>';
    const canvas = host.querySelector('.chart-canvas');
    const tip = host.querySelector('.chart-tip');
    const overlay = host.querySelector('.chart-state');

    const chart = LWC.createChart(canvas, {
      ...baseOptions(LWC),
      rightPriceScale: { borderColor: C.border, minimumWidth: PRICE_AXIS_W, scaleMargins: { top: 0.08, bottom: 0.26 } },
      // 거래량 영역 때문에 가격 축이 0 아래로 이어지므로 음수 눈금은 비운다
      localization: { locale: 'ko-KR', priceFormatter: (p) => (p < 0 ? '' : fmt(p, priceDigits(p))) },
    });
    const candles = chart.addCandlestickSeries({
      upColor: C.up, downColor: C.down, borderUpColor: C.up, borderDownColor: C.down, wickUpColor: C.up, wickDownColor: C.down,
    });
    const volume = chart.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    const lineOpts = { lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
    const maLines = MAS.map(([, color]) => chart.addLineSeries({ ...lineOpts, color }));

    let cfg = { maType: 'sma', ma: { 5: true, 20: true, 60: true, 120: true }, overlays: [], subs: [], volume: true };
    let state = { bars: [], byTime: new Map(), intraday: false, key: '', tf: 'D', decimals: 0 };
    let maValues = MAS.map(() => []);
    let overlaySeries = []; // [{ id, series:[...], lines }]
    let subPanes = [];      // [{ id, el, chart, series, hist, res, valuesEl }]
    let seq = 0;

    // ── 계산 결과 → 차트 데이터 (NaN 은 whitespace 로 넣어 봉 순번을 맞춘다) ──
    // ahead: 마지막 봉 뒤의 미래 시각들 — values[n + j] 를 그 자리에 넣는다 (일목 선행스팬)
    const asLine = (values, ahead = []) => {
      const n = state.bars.length;
      const pt = (time, v) => (isNum(v) ? { time, value: v } : { time });
      return state.bars.map((b, i) => pt(b.time, values[i])).concat(ahead.map((t, j) => pt(t, values[n + j])));
    };

    /* 마지막 봉 다음부터 k 개의 봉 시각 (주말은 건너뛰고 휴장일은 모름 → 근사).
       미래 칸은 가격 차트에만 생기고 보조 차트는 실제 봉까지만 있어, 봉 순번 0..n-1 은 그대로 맞는다. */
    function futureTimes(k) {
      const out = [];
      const last = state.bars[state.bars.length - 1].time;
      const weekday = (d) => { while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1); return d; };
      if (state.intraday) {
        const step = { '1m': 1, '5m': 5, '30m': 30 }[state.tf] * 60;
        let t = last;
        while (out.length < k) {
          t += step;
          const d = new Date(t * 1000);
          if (d.getUTCHours() * 60 + d.getUTCMinutes() > 15 * 60 + 30) { // 장 마감 뒤 → 다음 거래일 09:00
            t = weekday(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1, 9))).getTime() / 1000;
          }
          out.push(t);
        }
        return out;
      }
      const [y, m, day] = timeKey(last).split('-').map(Number);
      const d = new Date(Date.UTC(y, m - 1, day));
      for (let j = 1; j <= k; j += 1) {
        if (state.tf === 'D') { d.setUTCDate(d.getUTCDate() + 1); weekday(d); out.push(d.toISOString().slice(0, 10)); }
        else if (state.tf === 'W') { d.setUTCDate(d.getUTCDate() + 7); out.push(d.toISOString().slice(0, 10)); }
        else if (state.tf === 'M') out.push(new Date(Date.UTC(y, m - 1 + j, 1)).toISOString().slice(0, 10));
        else out.push(`${y + j}-01-01`);
      }
      return out;
    }
    const AHEAD = { ichimoku: 26 };
    const aheadBars = () => Math.max(0, ...cfg.overlays.map((id) => AHEAD[id] || 0));

    function applyMas() {
      const closes = state.bars.map((b) => b.close);
      MAS.forEach(([p], k) => {
        const on = !!cfg.ma[p];
        maValues[k] = on ? Indicators.ma(cfg.maType, closes, p) : [];
        maLines[k].applyOptions({ visible: on });
        maLines[k].setData(on ? asLine(maValues[k]) : []);
      });
    }

    function applyOverlays() {
      overlaySeries.forEach((o) => o.series.forEach((s) => chart.removeSeries(s)));
      overlaySeries = cfg.overlays.map((id) => {
        const res = Indicators.overlay(id, state.bars);
        const ahead = res.ahead ? futureTimes(res.ahead) : [];
        const series = res.lines.map((l) => {
          const s = chart.addLineSeries({
            ...lineOpts, color: l.color,
            lineStyle: l.style === 'dashed' ? LWC.LineStyle.Dashed : LWC.LineStyle.Solid,
            ...(l.dots ? { lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 1.5 } : {}),
          });
          s.setData(asLine(l.values, l.values.length > state.bars.length ? ahead : []));
          return s;
        });
        if (res.cloud) series[res.cloud.a].attachPrimitive(cloudPrimitive(res.lines[res.cloud.a].values, res.lines[res.cloud.b].values, res.cloud));
        return { id, series, lines: res.lines };
      });
    }

    /* 두 선 사이 채우기 (일목 구름). v4 에는 띠를 채우는 시리즈가 없어 series primitive 로 캔들 뒤에 직접 그린다.
       구간 i→i+1 을 i 시점의 A≥B 여부로 색칠한다 (원본 fill_between 과 동일). */
    function cloudPrimitive(a, b, { up, down }) {
      let attached = null;
      const renderer = {
        draw() {},
        drawBackground(target) {
          if (!attached) return;
          const ts = attached.chart.timeScale();
          const r = ts.getVisibleLogicalRange();
          if (!r) return;
          const y = (v) => candles.priceToCoordinate(v);
          const from = Math.max(0, Math.floor(r.from) - 1);
          const to = Math.min(a.length - 2, Math.ceil(r.to) + 1);
          target.useMediaCoordinateSpace(({ context: ctx }) => {
            const paths = { [up]: new Path2D(), [down]: new Path2D() };
            for (let i = from; i <= to; i += 1) {
              if (![a[i], b[i], a[i + 1], b[i + 1]].every(isNum)) continue;
              const x0 = ts.logicalToCoordinate(i);
              const x1 = ts.logicalToCoordinate(i + 1);
              const ys = [y(a[i]), y(a[i + 1]), y(b[i + 1]), y(b[i])];
              if (x0 === null || x1 === null || ys.includes(null)) continue;
              const p = paths[a[i] >= b[i] ? up : down];
              p.moveTo(x0, ys[0]); p.lineTo(x1, ys[1]); p.lineTo(x1, ys[2]); p.lineTo(x0, ys[3]); p.closePath();
            }
            Object.entries(paths).forEach(([color, p]) => { ctx.fillStyle = color; ctx.fill(p); });
          });
        },
      };
      const view = { renderer: () => renderer, zOrder: () => 'bottom' };
      return {
        attached(p) { attached = p; },
        detached() { attached = null; },
        paneViews: () => [view],
        updateAllViews() {},
      };
    }

    // ── 보조 차트 칸 ──
    const paneKey = (subs) => subs.map((s) => s.id).join(',');
    let builtPaneKey = '';

    function buildPanes() {
      if (!panes) return;
      const key = paneKey(cfg.subs);
      if (key === builtPaneKey) return;
      subPanes.forEach((p) => p.chart.remove());
      subPanes = [];
      panes.innerHTML = '';
      builtPaneKey = key;
      cfg.subs.forEach((meta) => {
        const el = document.createElement('div');
        el.className = 'sub-pane';
        el.innerHTML = `
          <div class="pane-h"><span style="font-weight:600">${esc(meta.name)}</span><span class="mono cap">${esc(meta.params || '')}</span>
            <span class="pane-vals" data-vals></span>
            <button type="button" class="xbtn ml-auto" data-sub-remove="${esc(meta.id)}" aria-label="${esc(meta.name)} 보조 차트 닫기">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
          <div class="sub-canvas"></div>`;
        panes.appendChild(el);
        const base = baseOptions(LWC);
        const sc = LWC.createChart(el.querySelector('.sub-canvas'), {
          ...base,
          layout: { ...base.layout, attributionLogo: false }, // 출처 표시는 가격 차트에 한 번만
          rightPriceScale: { borderColor: C.border, minimumWidth: PRICE_AXIS_W, scaleMargins: { top: 0.12, bottom: 0.08 } },
          timeScale: { borderColor: C.border, visible: false, rightOffset: 4, minBarSpacing: 0.5 },
          localization: { locale: 'ko-KR', priceFormatter: subFmt },
          handleScale: { axisPressedMouseMove: { time: true, price: false } },
        });
        const pane = { id: meta.id, meta, el, chart: sc, series: [], hist: null, res: null, valuesEl: el.querySelector('[data-vals]') };
        sc.timeScale().subscribeVisibleLogicalRangeChange((r) => syncRange(sc, r));
        sc.subscribeCrosshairMove((param) => onCrosshair(sc, param));
        subPanes.push(pane);
      });
    }

    function applySubs() {
      subPanes.forEach((p) => {
        p.series.forEach((s) => p.chart.removeSeries(s));
        if (p.hist) p.chart.removeSeries(p.hist);
        p.series = [];
        p.hist = null;
        p.res = Indicators.sub(p.id, state.bars);
        if (!p.res) return;
        if (p.res.hist) {
          p.hist = p.chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
          p.hist.setData(state.bars.map((b, i) => {
            const v = p.res.hist.values[i];
            return isNum(v) ? { time: b.time, value: v, color: v >= 0 ? C.upVol : C.downVol } : { time: b.time };
          }));
        }
        p.series = p.res.lines.map((l, k) => {
          const s = p.chart.addLineSeries({ ...lineOpts, color: l.color, lastValueVisible: k === 0, crosshairMarkerVisible: true });
          s.setData(asLine(l.values));
          return s;
        });
        const anchor = p.series[0] || p.hist;
        const level = (price, color) => anchor && anchor.createPriceLine({ price, color, lineWidth: 1, lineStyle: LWC.LineStyle.Dashed, axisLabelVisible: false });
        (p.res.hlines || []).forEach(([v, color]) => level(v, color));
        if (p.res.zero) level(0, C.zero);
      });
    }

    function recalcAll() {
      if (!state.bars.length) return;
      // 보조 차트에 데이터를 넣는 동안 그 차트의 기본 구간이 가격 차트로 역전파되지 않게 막고,
      // 다 넣은 뒤 가격 차트의 구간을 보조 차트에 맞춘다.
      const range = chart.timeScale().getVisibleLogicalRange();
      syncing = true;
      try {
        applyMas();
        applyOverlays();
        buildPanes();
        applySubs();
      } finally {
        syncing = false;
      }
      if (range) {
        chart.timeScale().setVisibleLogicalRange(range);
        subPanes.forEach((p) => p.chart.timeScale().setVisibleLogicalRange(range));
      }
      paintValues(null);
    }

    let recalcTimer = null;
    const scheduleRecalc = () => {
      if (recalcTimer) return;
      recalcTimer = setTimeout(() => { recalcTimer = null; recalcAll(); }, RECALC_MS);
    };

    // ── 보이는 구간 · 십자선 동기화 ──
    let syncing = false;
    function syncRange(src, range) {
      if (syncing || !range) return;
      syncing = true;
      [chart, ...subPanes.map((p) => p.chart)].forEach((c) => { if (c !== src) c.timeScale().setVisibleLogicalRange(range); });
      syncing = false;
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange((r) => syncRange(chart, r));

    let xsync = false;
    function onCrosshair(src, param) {
      if (xsync) return;
      const i = param && param.time !== undefined ? state.byTime.get(timeKey(param.time)) : undefined;
      xsync = true;
      [{ c: chart, s: candles, v: (k) => state.bars[k] && state.bars[k].close },
        ...subPanes.map((p) => ({ c: p.chart, s: p.series[0] || p.hist, v: (k) => (p.res ? (p.res.lines[0] || p.res.hist).values[k] : NaN) }))]
        .forEach(({ c, s, v }) => {
          if (c === src || !s) return;
          if (i === undefined) c.clearCrosshairPosition();
          else { const val = v(i); c.setCrosshairPosition(isNum(val) ? val : 0, state.bars[i].time, s); }
        });
      xsync = false;
      paintValues(i === undefined ? null : i);
      paintTip(i);
    }
    chart.subscribeCrosshairMove((param) => onCrosshair(chart, param));

    // ── 정보 박스 (캔들 옆) ──
    function paintTip(i) {
      const bar = i === undefined ? null : state.bars[i];
      if (!bar) { tip.hidden = true; return; }
      const prev = i > 0 ? state.bars[i - 1].close : bar.open;
      const chg = prev ? ((bar.close - prev) / prev) * 100 : 0;
      const c = chg > 0 ? 'up' : chg < 0 ? 'dn' : 'flat';
      const d = state.decimals;
      const mas = MAS.map(([p, color], k) => (cfg.ma[p] && isNum(maValues[k][i])
        ? `<div class="tip-row"><span style="color:${color}">${MA_PREFIX[cfg.maType]}${p}</span><b>${fmt(maValues[k][i], d)}</b></div>` : '')).join('');
      tip.innerHTML = `
        <div class="tip-time">${esc(timeLabel(bar.time, state.intraday))} · ${TF_LABEL[state.tf]}</div>
        <div class="tip-row"><span>시가</span><b>${fmt(bar.open, d)}</b></div>
        <div class="tip-row"><span>고가</span><b class="up">${fmt(bar.high, d)}</b></div>
        <div class="tip-row"><span>저가</span><b class="dn">${fmt(bar.low, d)}</b></div>
        <div class="tip-row"><span>종가</span><b class="${c}">${fmt(bar.close, d)}</b></div>
        <div class="tip-row"><span>전 봉 대비</span><b class="${c}">${chg > 0 ? '+' : ''}${fmt(chg, 2)}%</b></div>
        <div class="tip-row"><span>거래량</span><b>${fmt(bar.volume)}</b></div>${mas ? `<div class="tip-sep"></div>${mas}` : ''}`;
      tip.hidden = false;
      const x = chart.timeScale().timeToCoordinate(bar.time);
      if (x === null) { tip.hidden = true; return; }
      const boxW = host.clientWidth - PRICE_AXIS_W;
      const w = tip.offsetWidth;
      const h = tip.offsetHeight;
      const gap = 14;
      const left = x + gap + w > boxW ? x - gap - w : x + gap;
      const yHigh = candles.priceToCoordinate(bar.high);
      const top = Math.min(Math.max(8, (yHigh === null ? 8 : yHigh) - h / 2), host.clientHeight - h - 32);
      tip.style.transform = `translate(${Math.max(4, left)}px, ${Math.max(4, top)}px)`;
    }

    /* 보조 차트 머리글: 십자선 위치(없으면 마지막 봉)의 지표 값 */
    function paintValues(i) {
      subPanes.forEach((p) => {
        if (!p.res) { p.valuesEl.innerHTML = ''; return; }
        const k = i === null || i === undefined ? state.bars.length - 1 : i;
        const items = p.res.lines.map((l) => `<span style="color:${l.color}">${esc(l.name)} <b>${subFmt(l.values[k])}</b></span>`);
        if (p.res.hist) items.push(`<span class="cap">${esc(p.res.hist.name)} <b>${subFmt(p.res.hist.values[k])}</b></span>`);
        p.valuesEl.innerHTML = items.join('');
      });
    }

    function showState(kind, msg) {
      overlay.hidden = !kind;
      overlay.innerHTML = kind ? UI.stateHtml(kind, msg) : '';
    }

    async function load({ code, tf = 'D', kind = 'stock' }, { quiet = false } = {}) {
      const my = ++seq;
      const key = `${kind}:${code}:${tf}`;
      if (!quiet) showState('loading', '차트 불러오는 중…');
      let data;
      try {
        data = await API.get('chart', { code, tf, kind });
      } catch (e) {
        if (my !== seq) return;
        if (!quiet) showState('error', e.message);
        return;
      }
      if (my !== seq) return;
      showState(null);

      const bars = data.bars;
      const range = key === state.key ? chart.timeScale().getVisibleLogicalRange() : null;
      state = {
        bars, key, tf, intraday: data.intraday,
        byTime: new Map(bars.map((b, i) => [String(b.time), i])),
        decimals: kind === 'index' || bars.some((b) => b.close % 1 !== 0) ? 2 : 0,
      };

      chart.applyOptions({ timeScale: { timeVisible: data.intraday, secondsVisible: false } });
      // 월·년봉은 수십 년 구간이라 로그 축으로 (초기 가격대가 바닥에 눌리지 않게)
      chart.priceScale('right').applyOptions({ mode: tf === 'M' || tf === 'Y' ? LWC.PriceScaleMode.Logarithmic : LWC.PriceScaleMode.Normal });
      candles.applyOptions({ priceFormat: { type: 'price', precision: state.decimals, minMove: state.decimals ? 0.01 : 1 } });
      candles.setData(bars);
      volume.setData(bars.map((b, i) => ({ time: b.time, value: b.volume, color: b.close >= (i ? bars[i - 1].close : b.open) ? C.upVol : C.downVol })));

      if (range) chart.timeScale().setVisibleLogicalRange(range);
      recalcAll();
      if (!range) { // 처음 여는 구간은 미래 칸(일목 선행스팬)이 생긴 뒤에 잡아야 그 칸까지 보인다
        const count = VISIBLE[tf];
        if (count && bars.length > count) chart.timeScale().setVisibleLogicalRange({ from: bars.length - count, to: bars.length + 3 + aheadBars() });
        else chart.timeScale().fitContent();
      }
      host.dataset.sources = (data.sources || []).join(' · ');
      host.dispatchEvent(new CustomEvent('chart:loaded', { detail: data, bubbles: true }));
    }

    /* 실시간 체결 1건 반영. t: { date:'YYYYMMDD', time:'HHMMSS', price, qty, acmlVol, open, high, low } */
    function tick(t) {
      const bars = state.bars;
      if (!bars.length || !t.price || !t.date) return;
      const last = bars[bars.length - 1];
      let bar;
      if (state.intraday) {
        const step = { '1m': 1, '5m': 5, '30m': 30 }[state.tf];
        const mins = Number(t.time.slice(0, 2)) * 60 + Number(t.time.slice(2, 4));
        const b = Math.floor(mins / step) * step;
        const time = Date.UTC(+t.date.slice(0, 4), +t.date.slice(4, 6) - 1, +t.date.slice(6, 8), Math.floor(b / 60), b % 60) / 1000;
        if (time < last.time) return;
        bar = time === last.time
          ? { ...last, high: Math.max(last.high, t.price), low: Math.min(last.low, t.price), close: t.price, volume: last.volume + (t.qty || 0) }
          : { time, open: t.price, high: t.price, low: t.price, close: t.price, volume: t.qty || 0 };
      } else {
        const day = `${t.date.slice(0, 4)}-${t.date.slice(4, 6)}-${t.date.slice(6, 8)}`;
        if (day < last.time) return;
        if (state.tf === 'D') {
          bar = { time: day, open: t.open || t.price, high: t.high || t.price, low: t.low || t.price, close: t.price, volume: t.acmlVol || 0 };
          if (day === last.time) bar.open = last.open;
        } else { // 주·월·년: 진행 중인 마지막 봉만 갱신
          bar = { ...last, high: Math.max(last.high, t.price), low: Math.min(last.low, t.price), close: t.price };
        }
      }

      if (bar.time === last.time) bars[bars.length - 1] = bar;
      else { bars.push(bar); state.byTime.set(String(bar.time), bars.length - 1); }
      const i = bars.length - 1;
      // update() 는 넘긴 객체의 time 을 'YYYY-MM-DD' → {year,month,day} 로 바꿔 놓으므로 복사본을 넘긴다
      candles.update({ ...bar });
      volume.update({ time: bar.time, value: bar.volume, color: bar.close >= (i ? bars[i - 1].close : bar.open) ? C.upVol : C.downVol });
      scheduleRecalc();
    }

    /* 지표 선택 반영. subs: [{ id, name, params }] (선택 순서대로 아래에 쌓임), volume: 거래량 막대 */
    function setIndicators(next) {
      const prevAhead = aheadBars();
      cfg = { ...cfg, ...next, subs: (next.subs || cfg.subs).filter((s) => Indicators.hasSub(s.id)) };
      volume.applyOptions({ visible: !!cfg.volume });
      chart.applyOptions({ rightPriceScale: { scaleMargins: { top: 0.08, bottom: cfg.volume ? 0.26 : 0.06 } } });
      recalcAll();
      if (!state.bars.length) { buildPanes(); return; }
      // 미래 칸이 생겼고 최신 봉을 보고 있었다면 그만큼 밀어 미래 구름이 보이게
      const add = aheadBars() - prevAhead;
      const r = chart.timeScale().getVisibleLogicalRange();
      if (add > 0 && r && r.to >= state.bars.length - 1) chart.timeScale().setVisibleLogicalRange({ from: r.from + add, to: r.to + add });
    }

    return {
      load,
      tick,
      setIndicators,
      destroy() {
        subPanes.forEach((p) => p.chart.remove());
        chart.remove();
      },
    };
  }

  window.PriceChart = { create, TF_LABEL, MAS, MA_PREFIX };
})();
