"""MCP 도구 응답 줄이기 — KIS 조회 도구 전부와 batch_query 가 같이 쓴다.

KIS API 는 기간을 안 받는 것도 30일 치처럼 고정 길이로 돌려주고, 행마다 같은 키를 반복한다.
에이전트에게 "7일만 봐라" 고 지시해도 응답을 받는 순간 토큰은 이미 쓰이므로 서버에서 잘라서 보낸다.

    rows    목록에서 몇 줄만 남길지. 날짜 열이 있는 일자별 목록은 기본 최근 7줄,
            순위·잔고처럼 날짜가 없는 목록과 시작일을 받는 도구(사용자가 기간을 정함)는 기본 전부. 0 이면 전부.
    fields  남길 필드 이름. 목록의 행과 단일 객체 모두에 적용한다 (일자별 목록의 날짜 열은 늘 남긴다).
    표 형식  [{키: 값}, ...] 대신 {"cols": [...], "rows": [[...], ...]} — 키를 반복하지 않아 크기가 절반쯤 준다.
"""
from __future__ import annotations

import re
from typing import Any, Optional

SERIES_ROWS = 7

_DATE_KEY = re.compile(r"(date|dt|yymm|time)$")
_DATE_VAL = re.compile(r"^(19|20)\d{2}-?\d{2}(-?\d{2})?$")


class FieldError(ValueError):
    """fields 가 응답의 어떤 필드와도 맞지 않을 때."""


def _is_records(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(r, dict) for r in v)


def _is_flat(v: Any) -> bool:
    return isinstance(v, dict) and bool(v) and not any(isinstance(x, (dict, list)) for x in v.values())


def _empty(v: Any) -> bool:
    return v is None or v == ""


def date_key(records: list[dict]) -> Optional[str]:
    """일자별 목록이면 날짜 열 이름 (stck_bsop_date, data_dt, stac_yymm, date, time …)."""
    for k, v in records[0].items():
        if _DATE_KEY.search(k) and isinstance(v, str) and _DATE_VAL.match(v):
            return k
    return None


def _table(name: str, records: list[dict], rows: Optional[int], fields: list[str],
           series_default: bool) -> tuple[dict, Optional[str]]:
    dk = date_key(records)
    recs = records
    if fields:
        keep = [f for f in fields if f != dk]
        cols = ([dk] if dk else []) + keep
        recs = [{k: r[k] for k in cols if k in r} for r in records]
        if keep:  # 아직 값이 없는 행(장중의 오늘 투자자별 순매수 등)은 빼서 rows 를 실제 값으로 채운다
            recs = [r for r in recs if any(not _empty(r.get(k)) for k in keep)]

    total = len(recs)
    intraday = any(k.endswith("hour") for k in records[0])  # 분봉·체결처럼 하루 안의 목록은 기본으로 자르지 않는다
    limit = rows if rows is not None else (SERIES_ROWS if dk and series_default and not intraday else 0)
    note = None
    if limit and total > limit:
        ascending = bool(dk) and str(recs[0].get(dk, "")) < str(recs[-1].get(dk, ""))
        recs = recs[-limit:] if ascending else recs[:limit]
        note = f"{name}: {total}줄 중 {'최근' if dk else '앞'} {limit}줄 (rows 로 조절, 0 이면 전부)"

    cols: list[str] = []
    for r in recs:
        cols.extend(k for k, v in r.items() if k not in cols and not _empty(v))
    out: dict[str, Any] = {"cols": cols, "rows": [["" if _empty(r.get(k)) else r[k] for k in cols] for r in recs]}
    if note:
        out["total"] = total
    return out, note


def shape(data: Any, rows: Optional[int] = None, fields: Optional[list[str]] = None,
          series_default: bool = True) -> Any:
    """도구 응답(dict)의 목록은 표로 바꾸고 rows · fields 를 적용한다. 스칼라 값(rt_cd, msg1 …)은 그대로."""
    if not isinstance(data, dict):
        return data
    if rows is not None:
        rows = max(0, int(rows))
    fset = [f.strip() for f in (fields or []) if isinstance(f, str) and f.strip()]

    out: dict[str, Any] = {}
    notes: list[str] = []
    available: set[str] = set()
    matched = False
    for key, val in data.items():
        if _is_records(val):
            for r in val:
                available.update(r)
            matched = matched or any(f in r for r in val for f in fset)
            out[key], note = _table(key, val, rows, fset, series_default)
            if note:
                notes.append(note)
        elif fset and _is_flat(val):
            available.update(val)
            picked = {k: v for k, v in val.items() if k in fset}
            if picked:
                matched = True
                out[key] = picked
        else:
            out[key] = val
    if fset and not matched and available:
        raise FieldError("fields 와 맞는 필드가 없습니다. 이 도구의 필드: " + ", ".join(sorted(available)))
    if notes:
        out["_note"] = " / ".join(notes)
    return out


def merge(results: dict[str, dict], names: dict[str, str]) -> dict:
    """종목별 shape 결과를 섹션마다 표 하나로 합친다. 맨 앞에 code · name 열을 붙인다."""
    per_section: dict[str, list[dict]] = {}
    truncated = False
    for code, data in results.items():
        for key, val in data.items():
            if key == "_note":
                truncated = True
                continue
            if isinstance(val, dict) and "cols" in val and "rows" in val:
                recs = [dict(zip(val["cols"], row)) for row in val["rows"]]
            elif _is_flat(val):
                recs = [val]
            else:
                continue  # rt_cd · msg1 같은 스칼라는 버린다
            lead = {"code": code, "name": names.get(code, "")}
            per_section.setdefault(key, []).extend({**lead, **r} for r in recs)

    out: dict[str, Any] = {}
    for key, recs in per_section.items():
        cols: list[str] = []
        for r in recs:
            cols.extend(k for k, v in r.items() if k not in cols and (k in ("code", "name") or not _empty(v)))
        out[key] = {"cols": cols, "rows": [["" if _empty(r.get(k)) else r[k] for k in cols] for r in recs]}
    if truncated:
        out["_note"] = "종목마다 일부 줄만 담았습니다 (rows 로 조절, 0 이면 전부)"
    return out
