/* 기술적 지표 계산 — 봉 배열에서 지표 값 배열을 만든다 (화면용, 브라우저에서 계산).
 *
 * 계산식은 널리 쓰이는 표준 정의를 따르며, 같은 데이터의 pandas 계산 결과와 값을 대조해 검증했다.
 * 값이 없는 구간은 NaN. pandas rolling 처럼 구간에 NaN 이 하나라도 있으면 결과도 NaN 이다.
 *
 *   Indicators.ma('ema', closes, 20)        → number[]
 *   Indicators.overlay('bb', bars)          → { lines:[{name,color,values,style?,dots?}], cloud?, ahead? }
 *     ahead: 마지막 봉 뒤로 이어지는 봉 수 (일목 선행스팬). 그 선의 values 길이는 bars.length + ahead.
 *   Indicators.sub('macd', bars)            → { lines:[...], hist?:{values}, hlines:[], zero }
 */
(function () {
  const nan = (n) => new Array(n).fill(NaN);
  const isNum = (x) => typeof x === 'number' && !Number.isNaN(x);

  // ── 기본 함수 ─────────────────────────────────────────────
  function sma(a, p) {
    const out = nan(a.length);
    let sum = 0;
    let bad = 0; // 창 안의 NaN 개수
    for (let i = 0; i < a.length; i += 1) {
      if (isNum(a[i])) sum += a[i]; else bad += 1;
      if (i >= p) { if (isNum(a[i - p])) sum -= a[i - p]; else bad -= 1; }
      if (i >= p - 1 && bad === 0) out[i] = sum / p;
    }
    return out;
  }

  /* 첫 유효값에서 시작하는 지수이동평균 (이전 값이 NaN 이면 NaN 이 이어진다 — 원본과 동일) */
  function ema(a, p) {
    const out = nan(a.length);
    const k = 2 / (p + 1);
    let started = false;
    for (let i = 0; i < a.length; i += 1) {
      if (!isNum(a[i])) continue;
      if (!started) { out[i] = a[i]; started = true; } else out[i] = a[i] * k + out[i - 1] * (1 - k);
    }
    return out;
  }

  function wma(a, p) {
    const out = nan(a.length);
    const ws = (p * (p + 1)) / 2;
    for (let i = p - 1; i < a.length; i += 1) {
      let s = 0;
      for (let j = 0; j < p; j += 1) s += a[i - p + 1 + j] * (j + 1);
      out[i] = s / ws;
    }
    return out;
  }

  function wilder(a, p) {
    const out = nan(a.length);
    let started = false;
    for (let i = 0; i < a.length; i += 1) {
      if (!isNum(a[i])) continue;
      if (!started) { out[i] = a[i]; started = true; } else out[i] = (out[i - 1] * (p - 1) + a[i]) / p;
    }
    return out;
  }

  function rollingStd(a, p) { // 표본 표준편차 (pandas 기본 ddof=1)
    const out = nan(a.length);
    for (let i = p - 1; i < a.length; i += 1) {
      let m = 0;
      for (let j = i - p + 1; j <= i; j += 1) m += a[j];
      m /= p;
      let v = 0;
      for (let j = i - p + 1; j <= i; j += 1) v += (a[j] - m) ** 2;
      out[i] = Math.sqrt(v / (p - 1));
    }
    return out;
  }

  const sub2 = (a, b) => a.map((x, i) => x - b[i]);
  const highest = (a, from, to) => { let m = -Infinity; for (let j = from; j <= to; j += 1) if (a[j] > m) m = a[j]; return m; };
  const lowest = (a, from, to) => { let m = Infinity; for (let j = from; j <= to; j += 1) if (a[j] < m) m = a[j]; return m; };

  function cols(bars) {
    return {
      O: bars.map((b) => b.open), H: bars.map((b) => b.high), L: bars.map((b) => b.low),
      C: bars.map((b) => b.close), V: bars.map((b) => b.volume || 0), n: bars.length,
    };
  }

  // ── 공용 중간값 ───────────────────────────────────────────
  function stochastic(H, L, C, n, kp, dp) {
    const k = nan(n);
    for (let i = kp - 1; i < n; i += 1) {
      const hh = highest(H, i - kp + 1, i);
      const ll = lowest(L, i - kp + 1, i);
      k[i] = hh !== ll ? ((C[i] - ll) / (hh - ll)) * 100 : 50;
    }
    return [k, sma(k, dp)];
  }

  function rsi(C, n, p = 14) {
    const out = nan(n);
    if (n <= p) return out;
    const gain = new Array(n).fill(0);
    const loss = new Array(n).fill(0);
    for (let i = 1; i < n; i += 1) {
      const d = C[i] - C[i - 1];
      if (d > 0) gain[i] = d; else loss[i] = -d;
    }
    let ag = 0;
    let al = 0;
    for (let i = 1; i <= p; i += 1) { ag += gain[i]; al += loss[i]; }
    ag /= p; al /= p;
    for (let i = p; i < n; i += 1) {
      if (i > p) { ag = (ag * (p - 1) + gain[i]) / p; al = (al * (p - 1) + loss[i]) / p; }
      out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al);
    }
    return out;
  }

  function clv(H, L, C, n) {
    const out = new Array(n).fill(0);
    for (let i = 0; i < n; i += 1) {
      const hl = H[i] - L[i];
      if (hl > 0) out[i] = ((C[i] - L[i]) - (H[i] - C[i])) / hl;
    }
    return out;
  }

  function adLine(H, L, C, V, n) {
    const c = clv(H, L, C, n);
    const out = new Array(n);
    let acc = 0;
    for (let i = 0; i < n; i += 1) { acc += c[i] * V[i]; out[i] = acc; }
    return out;
  }

  function momentum(C, n, p = 10) {
    const out = nan(n);
    for (let i = p; i < n; i += 1) out[i] = C[i] - C[i - p];
    return out;
  }

  // ── 이동평균 ──────────────────────────────────────────────
  function ma(type, closes, p) {
    if (type === 'ema') return ema(closes, p);
    if (type === 'wma') return wma(closes, p);
    return sma(closes, p);
  }

  // ── 가격 위 지표 (signal_strategies.py) ───────────────────
  const OVERLAYS = {
    bb(b) { // 볼린저밴드 20, 2σ
      const m = sma(b.C, 20);
      const sd = rollingStd(b.C, 20);
      return { lines: [
        { name: 'BB 상단', color: '#1D9BB0', values: m.map((x, i) => x + 2 * sd[i]) },
        { name: 'BB 중심', color: '#1D9BB0', values: m, style: 'dashed' },
        { name: 'BB 하단', color: '#1D9BB0', values: m.map((x, i) => x - 2 * sd[i]) },
      ] };
    },
    env(b) { // Envelope 20, ±5%
      const m = sma(b.C, 20);
      return { lines: [
        { name: 'Env 상단', color: '#B07A1D', values: m.map((x) => x * 1.05) },
        { name: 'Env 중심', color: '#B07A1D', values: m, style: 'dashed' },
        { name: 'Env 하단', color: '#B07A1D', values: m.map((x) => x * 0.95) },
      ] };
    },
    psar(b) { // Parabolic SAR 0.02, 0.2
      const { H, L, n } = b;
      const sar = nan(n);
      if (!n) return { lines: [] };
      let trend = 1;
      let ep = H[0];
      let af = 0.02;
      sar[0] = L[0];
      for (let i = 1; i < n; i += 1) {
        const ps = sar[i - 1];
        let ns = ps + af * (ep - ps);
        if (trend === 1) {
          ns = Math.min(ns, L[i - 1]);
          if (i >= 2) ns = Math.min(ns, L[i - 2]);
          if (L[i] < ns) { trend = -1; ns = ep; ep = L[i]; af = 0.02; } else if (H[i] > ep) { ep = H[i]; af = Math.min(af + 0.02, 0.2); }
        } else {
          ns = Math.max(ns, H[i - 1]);
          if (i >= 2) ns = Math.max(ns, H[i - 2]);
          if (H[i] > ns) { trend = 1; ns = ep; ep = H[i]; af = 0.02; } else if (L[i] < ep) { ep = L[i]; af = Math.min(af + 0.02, 0.2); }
        }
        sar[i] = ns;
      }
      return { lines: [{ name: 'SAR', color: '#5E6470', values: sar, dots: true }] };
    },
    /* 일목균형표 9, 26, 52 (daily_chart_indicators.py) — 선행스팬은 26봉 앞으로 민다.
       원본은 마지막 봉 뒤를 잘라내지만 여기서는 미래 26봉까지 남긴다 (값 길이 n + ahead, 앞 n 개는 원본과 같음).
       cloud: 선행스팬 A·B(lines 의 순번) 사이를 구간마다 A≥B 면 orange, 아니면 purple 로 채운다. */
    ichimoku(b) {
      const { H, L, C, n } = b;
      const mid = (i, p) => (highest(H, i - p + 1, i) + lowest(L, i - p + 1, i)) / 2;
      const tenkan = nan(n);
      const kijun = nan(n);
      const spanA = nan(n + 26);
      const spanB = nan(n + 26);
      const chikou = nan(n);
      for (let i = 0; i < n; i += 1) {
        if (i >= 8) tenkan[i] = mid(i, 9);
        if (i >= 25) kijun[i] = mid(i, 26);
        if (i >= 25) spanA[i + 26] = (tenkan[i] + kijun[i]) / 2;
        if (i >= 51) spanB[i + 26] = mid(i, 52);
        if (i >= 26) chikou[i - 26] = C[i];
      }
      return {
        lines: [
          { name: '전환선', color: '#e74c3c', values: tenkan },
          { name: '기준선', color: '#3498db', values: kijun },
          { name: '후행스팬', color: '#2ecc7199', values: chikou },
          { name: '선행스팬 A', color: '#e67e22b3', values: spanA },
          { name: '선행스팬 B', color: '#9b59b6b3', values: spanB },
        ],
        cloud: { a: 3, b: 4, up: '#e67e2230', down: '#9b59b630' },
        ahead: 26,
      };
    },
  };

  // ── 보조 차트 (daily_second_indicators.py) ────────────────
  const OB = ['#ef444480', '#22c55e80']; // 과매수/과매도 기준선 색
  const SUBS = {
    macd(b) {
      const line = sub2(ema(b.C, 12), ema(b.C, 26));
      const signal = ema(line, 9);
      return { lines: [{ name: 'MACD', color: '#3b82f6', values: line }, { name: 'Signal', color: '#ef4444', values: signal }],
        hist: { name: 'Hist', values: sub2(line, signal) }, zero: true };
    },
    ppo(b) {
      const e12 = ema(b.C, 12);
      const e26 = ema(b.C, 26);
      const line = e12.map((x, i) => (e26[i] > 0 ? ((x - e26[i]) / e26[i]) * 100 : NaN));
      const signal = ema(line, 9);
      return { lines: [{ name: 'PPO', color: '#3b82f6', values: line }, { name: 'Signal', color: '#ef4444', values: signal }],
        hist: { name: 'Hist', values: sub2(line, signal) }, zero: true };
    },
    trix(b) {
      const e3 = ema(ema(ema(b.C, 15), 15), 15);
      const t = nan(b.n);
      for (let i = 1; i < b.n; i += 1) if (isNum(e3[i]) && isNum(e3[i - 1]) && e3[i - 1] !== 0) t[i] = ((e3[i] - e3[i - 1]) / e3[i - 1]) * 100;
      return { lines: [{ name: 'TRIX', color: '#7c3aed', values: t }, { name: 'Signal', color: '#f59e0b', values: ema(t, 9) }], zero: true };
    },
    dmi(b) {
      const { H, L, C, n } = b;
      const pdm = new Array(n).fill(0);
      const mdm = new Array(n).fill(0);
      const tr = new Array(n).fill(0);
      for (let i = 1; i < n; i += 1) {
        const up = H[i] - H[i - 1];
        const dn = L[i - 1] - L[i];
        pdm[i] = up > dn && up > 0 ? up : 0;
        mdm[i] = dn > up && dn > 0 ? dn : 0;
        tr[i] = Math.max(H[i] - L[i], Math.abs(H[i] - C[i - 1]), Math.abs(L[i] - C[i - 1]));
      }
      const atr = wilder(tr, 14);
      const pdi = wilder(pdm, 14).map((x, i) => (x / (atr[i] > 0 ? atr[i] : 1)) * 100);
      const mdi = wilder(mdm, 14).map((x, i) => (x / (atr[i] > 0 ? atr[i] : 1)) * 100);
      const dx = pdi.map((x, i) => { const s = x + mdi[i]; return isNum(s) && s > 0 ? (Math.abs(x - mdi[i]) / s) * 100 : NaN; });
      const adx = wilder(dx, 14);
      const adxr = nan(n);
      for (let i = 14; i < n; i += 1) if (isNum(adx[i]) && isNum(adx[i - 14])) adxr[i] = (adx[i] + adx[i - 14]) / 2;
      return { lines: [{ name: '+DI', color: '#22c55e', values: pdi }, { name: '-DI', color: '#ef4444', values: mdi },
        { name: 'ADX', color: '#a855f7', values: adx }, { name: 'ADXR', color: '#f97316', values: adxr }], hlines: [[25, '#f59e0b80']] };
    },
    aroon(b) {
      const p = 25;
      const up = nan(b.n);
      const dn = nan(b.n);
      for (let i = p; i < b.n; i += 1) {
        let hi = i - p; let lo = i - p;
        for (let j = i - p; j <= i; j += 1) { if (b.H[j] > b.H[hi]) hi = j; if (b.L[j] < b.L[lo]) lo = j; }
        up[i] = ((hi - (i - p)) / p) * 100;
        dn[i] = ((lo - (i - p)) / p) * 100;
      }
      return { lines: [{ name: 'Up', color: '#22c55e', values: up }, { name: 'Down', color: '#ef4444', values: dn },
        { name: 'Osc', color: '#0ea5e9', values: sub2(up, dn) }], zero: true };
    },
    sonar(b) {
      const m = momentum(b.C, b.n, 10);
      return { lines: [{ name: 'Mom', color: '#94a3b880', values: m }, { name: 'SONAR', color: '#f59e0b', values: sma(m, 5) }], zero: true };
    },
    mass(b) {
      const hl = b.H.map((h, i) => h - b.L[i]);
      const e1 = ema(hl, 9);
      const e2 = ema(e1, 9);
      const ratio = e1.map((x, i) => (e2[i] > 0 ? x / e2[i] : NaN));
      const out = nan(b.n);
      for (let i = 24; i < b.n; i += 1) {
        let s = 0; let ok = true;
        for (let j = i - 24; j <= i; j += 1) { if (!isNum(ratio[j])) { ok = false; break; } s += ratio[j]; }
        if (ok) out[i] = s;
      }
      return { lines: [{ name: 'MI', color: '#d946ef', values: out }], hlines: [[27, OB[0]], [26.5, OB[1]]] };
    },
    rsi(b) { return { lines: [{ name: 'RSI', color: '#a855f7', values: rsi(b.C, b.n) }], hlines: [[70, OB[0]], [30, OB[1]]] }; },
    stof(b) {
      const [k, d] = stochastic(b.H, b.L, b.C, b.n, 14, 3);
      return { lines: [{ name: '%K', color: '#3b82f6', values: k }, { name: '%D', color: '#ef4444', values: d }], hlines: [[80, OB[0]], [20, OB[1]]] };
    },
    stos(b) {
      const [, fastD] = stochastic(b.H, b.L, b.C, b.n, 14, 3);
      return { lines: [{ name: 'Slow %K', color: '#3b82f6', values: fastD }, { name: 'Slow %D', color: '#ef4444', values: sma(fastD, 3) }], hlines: [[80, OB[0]], [20, OB[1]]] };
    },
    storsi(b) {
      const r = rsi(b.C, b.n);
      const k = nan(b.n);
      for (let i = 13; i < b.n; i += 1) {
        const w = r.slice(i - 13, i + 1).filter(isNum);
        if (w.length >= 2 && isNum(r[i])) {
          const mn = Math.min(...w); const mx = Math.max(...w);
          if (mx !== mn) k[i] = ((r[i] - mn) / (mx - mn)) * 100;
        }
      }
      return { lines: [{ name: '%K', color: '#3b82f6', values: k }, { name: '%D', color: '#ef4444', values: sma(k, 3) }], hlines: [[80, OB[0]], [20, OB[1]]] };
    },
    cci(b) {
      const tp = b.H.map((h, i) => (h + b.L[i] + b.C[i]) / 3);
      const out = nan(b.n);
      for (let i = 19; i < b.n; i += 1) {
        let m = 0;
        for (let j = i - 19; j <= i; j += 1) m += tp[j];
        m /= 20;
        let md = 0;
        for (let j = i - 19; j <= i; j += 1) md += Math.abs(tp[j] - m);
        md /= 20;
        out[i] = md === 0 ? 0 : (tp[i] - m) / (0.015 * md);
      }
      return { lines: [{ name: 'CCI', color: '#f59e0b', values: out }], hlines: [[100, OB[0]], [-100, OB[1]]], zero: true };
    },
    wr(b) {
      const out = nan(b.n);
      for (let i = 13; i < b.n; i += 1) {
        const hh = highest(b.H, i - 13, i); const ll = lowest(b.L, i - 13, i);
        if (hh !== ll) out[i] = ((hh - b.C[i]) / (hh - ll)) * -100;
      }
      return { lines: [{ name: '%R', color: '#e11d48', values: out }], hlines: [[-20, OB[0]], [-80, OB[1]]] };
    },
    mom(b) { return { lines: [{ name: 'Momentum', color: '#3b82f6', values: momentum(b.C, b.n, 10) }], zero: true }; },
    roc(b) {
      const out = nan(b.n);
      for (let i = 12; i < b.n; i += 1) if (b.C[i - 12] !== 0) out[i] = ((b.C[i] - b.C[i - 12]) / b.C[i - 12]) * 100;
      return { lines: [{ name: 'ROC', color: '#8b5cf6', values: out }], zero: true };
    },
    disp(b) {
      const m = sma(b.C, 20);
      return { lines: [{ name: '이격도', color: '#14b8a6', values: b.C.map((c, i) => (isNum(m[i]) && m[i] !== 0 ? (c / m[i]) * 100 : NaN)) }],
        hlines: [[105, OB[0]], [95, OB[1]]] };
    },
    psy(b) {
      const out = nan(b.n);
      for (let i = 12; i < b.n; i += 1) {
        let up = 0;
        for (let j = i - 11; j <= i; j += 1) if (b.C[j] > b.C[j - 1]) up += 1;
        out[i] = (up / 12) * 100;
      }
      return { lines: [{ name: '심리도', color: '#d946ef', values: out }], hlines: [[75, OB[0]], [25, OB[1]]] };
    },
    uo(b) {
      const { H, L, C, n } = b;
      const bp = new Array(n).fill(0);
      const tr = new Array(n).fill(0);
      for (let i = 1; i < n; i += 1) {
        bp[i] = C[i] - Math.min(L[i], C[i - 1]);
        tr[i] = Math.max(H[i], C[i - 1]) - Math.min(L[i], C[i - 1]);
      }
      const ratio = (i, p) => { let s = 0; let t = 0; for (let j = i - p + 1; j <= i; j += 1) { s += bp[j]; t += tr[j]; } return s / Math.max(t, 1e-10); };
      const out = nan(n);
      for (let i = 28; i < n; i += 1) out[i] = ((4 * ratio(i, 7) + 2 * ratio(i, 14) + ratio(i, 28)) / 7) * 100;
      return { lines: [{ name: 'UO', color: '#f43f5e', values: out }], hlines: [[70, OB[0]], [30, OB[1]]] };
    },
    elder(b) {
      const e = ema(b.C, 13);
      return { lines: [{ name: 'Bull', color: '#22c55e', values: sub2(b.H, e) }, { name: 'Bear', color: '#ef4444', values: sub2(b.L, e) }], zero: true };
    },
    obv(b) {
      const out = new Array(b.n).fill(0);
      for (let i = 1; i < b.n; i += 1) {
        out[i] = out[i - 1] + (b.C[i] > b.C[i - 1] ? b.V[i] : b.C[i] < b.C[i - 1] ? -b.V[i] : 0);
      }
      return { lines: [{ name: 'OBV', color: '#6366f1', values: out }] };
    },
    vr(b) {
      const out = nan(b.n);
      for (let i = 20; i < b.n; i += 1) {
        let up = 0; let dn = 0; let eq = 0;
        for (let j = i - 19; j <= i; j += 1) {
          if (b.C[j] > b.C[j - 1]) up += b.V[j]; else if (b.C[j] < b.C[j - 1]) dn += b.V[j]; else eq += b.V[j];
        }
        const d = dn + eq / 2;
        if (d > 0) out[i] = ((up + eq / 2) / d) * 100;
      }
      return { lines: [{ name: 'VR', color: '#f97316', values: out }], hlines: [[150, OB[0]], [70, OB[1]]] };
    },
    ad(b) { return { lines: [{ name: 'AD', color: '#06b6d4', values: adLine(b.H, b.L, b.C, b.V, b.n) }] }; },
    cmf(b) {
      const c = clv(b.H, b.L, b.C, b.n);
      const out = nan(b.n);
      for (let i = 19; i < b.n; i += 1) {
        let sv = 0; let tv = 0;
        for (let j = i - 19; j <= i; j += 1) { sv += c[j] * b.V[j]; tv += b.V[j]; }
        out[i] = tv > 0 ? sv / tv : 0;
      }
      return { lines: [{ name: 'CMF', color: '#10b981', values: out }], zero: true };
    },
    mfi(b) {
      const tp = b.H.map((h, i) => (h + b.L[i] + b.C[i]) / 3);
      const out = nan(b.n);
      for (let i = 14; i < b.n; i += 1) {
        let pos = 0; let neg = 0;
        for (let j = i - 13; j <= i; j += 1) {
          const mf = tp[j] * b.V[j];
          if (tp[j] > tp[j - 1]) pos += mf; else if (tp[j] < tp[j - 1]) neg += mf;
        }
        out[i] = neg === 0 ? 100 : 100 - 100 / (1 + pos / neg);
      }
      return { lines: [{ name: 'MFI', color: '#ec4899', values: out }], hlines: [[80, OB[0]], [20, OB[1]]] };
    },
    chosc(b) {
      const ad = adLine(b.H, b.L, b.C, b.V, b.n);
      return { lines: [{ name: 'CO', color: '#0ea5e9', values: sub2(ema(ad, 3), ema(ad, 10)) }], zero: true };
    },
    pvo(b) {
      const e12 = ema(b.V, 12);
      const e26 = ema(b.V, 26);
      const line = e12.map((x, i) => (e26[i] > 0 ? ((x - e26[i]) / e26[i]) * 100 : NaN));
      return { lines: [{ name: 'PVO', color: '#3b82f6', values: line }, { name: 'Signal', color: '#ef4444', values: ema(line, 9) }], zero: true };
    },
    pvi(b) { return { lines: [{ name: 'PVI', color: '#06b6d4', values: volumeIndex(b, (v, pv) => v > pv) }] }; },
    nvi(b) { return { lines: [{ name: 'NVI', color: '#14b8a6', values: volumeIndex(b, (v, pv) => v < pv) }] }; },
    force(b) {
      const raw = nan(b.n);
      for (let i = 1; i < b.n; i += 1) raw[i] = (b.C[i] - b.C[i - 1]) * b.V[i];
      return { lines: [{ name: 'FI', color: '#0ea5e9', values: ema(raw, 13) }], zero: true };
    },
    eom(b) {
      const raw = nan(b.n);
      for (let i = 1; i < b.n; i += 1) {
        const dm = (b.H[i] + b.L[i]) / 2 - (b.H[i - 1] + b.L[i - 1]) / 2;
        const br = b.H[i] - b.L[i];
        if (br > 0 && b.V[i] > 0) raw[i] = dm / (b.V[i] / br);
      }
      return { lines: [{ name: 'EOM', color: '#8b5cf6', values: sma(raw, 14) }], zero: true };
    },
    atr(b) {
      const tr = new Array(b.n).fill(0);
      if (b.n) tr[0] = b.H[0] - b.L[0];
      for (let i = 1; i < b.n; i += 1) tr[i] = Math.max(b.H[i] - b.L[i], Math.abs(b.H[i] - b.C[i - 1]), Math.abs(b.L[i] - b.C[i - 1]));
      return { lines: [{ name: 'ATR', color: '#f43f5e', values: wilder(tr, 14) }] };
    },
    chvol(b) {
      const e = ema(b.H.map((h, i) => h - b.L[i]), 10);
      const out = nan(b.n);
      for (let i = 10; i < b.n; i += 1) if (isNum(e[i]) && isNum(e[i - 10]) && e[i - 10] !== 0) out[i] = ((e[i] - e[i - 10]) / e[i - 10]) * 100;
      return { lines: [{ name: 'CV', color: '#f97316', values: out }], zero: true };
    },
  };

  function volumeIndex(b, cond) {
    const out = nan(b.n);
    if (!b.n) return out;
    out[0] = 1000;
    for (let i = 1; i < b.n; i += 1) {
      out[i] = cond(b.V[i], b.V[i - 1]) && b.C[i - 1] !== 0 ? out[i - 1] * (1 + (b.C[i] - b.C[i - 1]) / b.C[i - 1]) : out[i - 1];
    }
    return out;
  }

  window.Indicators = {
    ma,
    overlay: (id, bars) => (OVERLAYS[id] ? OVERLAYS[id](cols(bars)) : { lines: [] }),
    sub: (id, bars) => (SUBS[id] ? { hlines: [], zero: false, ...SUBS[id](cols(bars)) } : null),
    hasSub: (id) => !!SUBS[id],
  };
})();
