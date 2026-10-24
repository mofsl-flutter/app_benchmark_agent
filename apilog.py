#!/usr/bin/env python3
"""Parse the API lines RISE writes to logcat into a per-call table (pure, no adb).

RISE's production build logs every API call as one JSON object with "type":"API", the request
start time (`ts`), `method`, `url`, `status`, `duration_ms`, `api_version` and, for CDN calls, a
`cdn` block with the cache state. Known quirks handled here: each call is logged twice, successful
calls also print an empty `{API Failed}` line, the base URL is doubled inside `url`, and logcat
splits payloads longer than ~4 KB over several lines.

Competitor apps log nothing of the kind, so parse_api_log() returns [] for them.

Only metadata is kept: query strings are dropped and id-like path segments masked, so the output
can live in the shared results folder (api_calls.csv). Response bodies are never present in the
production log and are not captured.
"""
import json
import re
from urllib.parse import urlsplit

LOGCAT_RE = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+(\S+?)\s*:\s?(.*)$")
API_MARK = re.compile(r'"type"\s*:\s*"API"')
URL_SCHEME = re.compile(r"https?://", re.I)
SIZE_RE = re.compile(r"(?i)\bsize\b[^0-9]{0,24}(\d+(?:\.\d+)?)\s*(kb|mb|b|bytes)?")
# RISE's text log line for a response, e.g.
#   {Trader API Service}  {Response 200, GET,https://host/path?q=1, Response Time: 216ms, Data Size: 4kb }
RESPONSE_LINE_RE = re.compile(r"Response\s+(\d{3}),\s*([A-Z]+),\s*(\S+?),\s*Response Time:\s*(\d+)\s*ms(?:,\s*Data Size:\s*(\d+(?:\.\d+)?)\s*(kb|mb|b|bytes)?)?", re.I)
ID_SEGMENT = (re.compile(r"^\d{3,}$"), re.compile(r"^[0-9a-fA-F-]{20,}$"),
              re.compile(r"^[A-Za-z]{0,4}\d{4,}[A-Za-z0-9]*$"))
CALL_FIELDS = ["seq", "ts", "logged_at", "t_rel_ms", "method", "host", "path", "status", "level",
               "duration_ms", "size_bytes", "cache", "api_version", "repeat_of"]


# ---------------------------------------------------------------- logcat lines

def parse_lines(text):
    """[(timestamp, pid, tid, level, tag, message)] for threadtime-format lines; others are skipped."""
    out = []
    for line in text.splitlines():
        m = LOGCAT_RE.match(line.rstrip("\r"))
        if m:
            out.append(m.groups())
    return out


def iter_json_objects(lines):
    """Yield (line_index, dict) for every API JSON object, joining objects logcat split over lines."""
    pending = None  # (start_index, pid, tag, buffer)
    for i, (_, pid, _, _, tag, msg) in enumerate(lines):
        if pending is not None:
            s_i, s_pid, s_tag, buf = pending
            if pid == s_pid and tag == s_tag:
                buf += msg
                obj = _try_json(buf)
                if obj is not None:
                    pending = None
                    if obj.get("type") == "API":
                        yield s_i, obj
                    continue
                if buf.count("{") <= buf.count("}") or len(buf) > 65536:
                    pending = None  # give up on this fragment
                else:
                    pending = (s_i, s_pid, s_tag, buf)
                    continue
            else:
                pending = None
        if not API_MARK.search(msg):
            continue
        start = msg.find("{")
        if start < 0:
            continue
        frag = msg[start:]
        obj = _try_json(frag)
        if obj is not None:
            if obj.get("type") == "API":
                yield i, obj
        elif frag.count("{") > frag.count("}"):
            pending = (i, pid, tag, frag)


def _try_json(text):
    end = text.rfind("}")
    if end < 0:
        return None
    try:
        obj = json.loads(text[: end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


# ---------------------------------------------------------------- urls

def normalise_url(url):
    """(host, path) from a RISE url, taking the last scheme when the base URL is doubled; no query."""
    url = str(url or "")
    starts = [m.start() for m in URL_SCHEME.finditer(url)]
    if starts:
        url = url[starts[-1]:]
        parts = urlsplit(url)
        host, path = parts.hostname or "", parts.path or "/"
    else:
        host, path = "", url.split("?", 1)[0].split("#", 1)[0] or "/"
    return host.lower(), sanitize_path(path)


def sanitize_path(path):
    """Mask path segments that look like ids or client codes with {id}; never keep a query string."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    segs = path.split("/")
    out = []
    for s in segs:
        if s and any(p.match(s) for p in ID_SEGMENT):
            out.append("{id}")
        else:
            out.append(s)
    return "/".join(out) or "/"


# ---------------------------------------------------------------- calls

def _ts_ms(ts):
    """Milliseconds since midnight from the 'HH:MM:SS.mmm' tail of a ts string; None if unparsable."""
    m = re.search(r"(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?\s*$", str(ts or ""))
    if not m:
        return None
    h, mi, s, frac = m.groups()
    ms = int((frac or "0").ljust(3, "0")[:3])
    return ((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + ms


def _size_bytes(num, unit):
    v = float(num)
    unit = (unit or "b").lower()
    if unit == "kb":
        v *= 1024
    elif unit == "mb":
        v *= 1024 * 1024
    return int(round(v))


def response_lines(lines):
    """[(line_index, status, method, host, path, duration_ms, size_bytes|None)] from RISE's text response lines."""
    out = []
    for i, (_, _, _, _, _, msg) in enumerate(lines):
        m = RESPONSE_LINE_RE.search(msg)
        if not m:
            continue
        host, path = normalise_url(m.group(3))
        size = _size_bytes(m.group(5), m.group(6)) if m.group(5) else None
        out.append((i, int(m.group(1)), m.group(2).upper(), host, path, int(m.group(4)), size))
    return out


def attach_sizes(calls, lines, window=5):
    """Fill size_bytes. First from RISE's text response line with the same method, path and response time
    (exact pairing); else from a nearby line (same pid) that mentions a size and the call's path tail."""
    used = set()
    resp = response_lines(lines)
    for c in calls:
        for k, (i, status, method, host, path, dur, size) in enumerate(resp):
            if k in used or method != c["method"] or path != c["path"] or dur != c["duration_ms"]:
                continue
            if host and c["host"] and host != c["host"]:
                continue
            used.add(k)
            if size is not None:
                c["size_bytes"] = size
            break
    if resp:
        return calls  # structured response lines exist: never guess from neighbouring lines
    for c in calls:
        i = c.get("_line")
        if i is None:
            continue
        pid = lines[i][1]
        tail = c["path"].rstrip("/").rsplit("/", 1)[-1]
        for j in range(max(0, i - window), min(len(lines), i + window + 1)):
            if j == i or lines[j][1] != pid:
                continue
            msg = lines[j][5]
            if API_MARK.search(msg):
                continue
            if tail and tail not in msg and tail.replace("{id}", "") not in msg:
                continue
            m = SIZE_RE.search(msg)
            if m:
                c["size_bytes"] = _size_bytes(m.group(1), m.group(2))
                break
    return calls


def dedupe(calls):
    seen, out = set(), []
    for c in calls:
        key = (c["ts"], c["method"], c["host"], c["path"], c["status"])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def mark_repeats(calls):
    first = {}
    for c in calls:
        key = (c["method"], c["host"], c["path"])
        if key in first:
            c["repeat_of"] = first[key]
        else:
            first[key] = c["seq"]
            c["repeat_of"] = ""
    return calls


def parse_api_log(text):
    """logcat -v threadtime text -> [call dict], ordered by request start, deduped, sanitized."""
    lines = parse_lines(text)
    calls = []
    for i, obj in iter_json_objects(lines):
        host, path = normalise_url(obj.get("url", ""))
        cdn = obj.get("cdn") if isinstance(obj.get("cdn"), dict) else {}
        dur = obj.get("duration_ms")
        try:
            dur = int(round(float(dur))) if dur not in (None, "") else None
        except (TypeError, ValueError):
            dur = None
        calls.append({
            "ts": str(obj.get("ts", "")), "logged_at": lines[i][0], "method": str(obj.get("method", "")).upper(),
            "host": host, "path": path, "status": obj.get("status", ""), "level": obj.get("level", ""),
            "duration_ms": dur, "size_bytes": None, "cache": str(cdn.get("cache", "") or ""),
            "api_version": str(obj.get("api_version", "") or ""), "_line": i,
        })
    calls = dedupe(calls)
    attach_sizes(calls, lines)
    calls.sort(key=lambda c: (_ts_ms(c["ts"]) if _ts_ms(c["ts"]) is not None else -1, c["_line"]))
    t0 = next((_ts_ms(c["ts"]) for c in calls if _ts_ms(c["ts"]) is not None), None)
    for n, c in enumerate(calls, 1):
        c["seq"] = n
        t = _ts_ms(c["ts"])
        c["t_rel_ms"] = (t - t0) if (t is not None and t0 is not None) else None
        c.pop("_line", None)
    return mark_repeats(calls)


# ---------------------------------------------------------------- summaries

def summarize(calls):
    """Counts and timings over one phase: calls, endpoints, repeats, total_ms, wall_ms, longest, cache."""
    calls = list(calls)
    durs = [c["duration_ms"] for c in calls if c.get("duration_ms") is not None]
    ends = [c["t_rel_ms"] + c["duration_ms"] for c in calls
            if c.get("t_rel_ms") is not None and c.get("duration_ms") is not None]
    longest = max((c for c in calls if c.get("duration_ms") is not None), key=lambda c: c["duration_ms"], default=None)
    cache = [c["cache"].upper() for c in calls if c.get("cache")]
    sizes = [c["size_bytes"] for c in calls if c.get("size_bytes")]
    return {
        "calls": len(calls),
        "endpoints": len({(c["method"], c["host"], c["path"]) for c in calls}),
        "repeats": sum(1 for c in calls if c.get("repeat_of")),
        "errors": sum(1 for c in calls if str(c.get("status", "")).isdigit() and int(c["status"]) >= 400),
        "total_ms": sum(durs),
        "wall_ms": max(ends) if ends else None,
        "longest_ms": longest["duration_ms"] if longest else None,
        "longest": f"{longest['method']} {longest['path']}" if longest else "",
        "cache_hits": sum(1 for c in cache if c == "HIT"),
        "cache_total": len(cache),
        "bytes": sum(sizes) if sizes else None,
    }


def summary_note(calls):
    s = summarize(calls)
    if not s["calls"]:
        return ""
    parts = [f"api: {s['calls']} calls, {s['endpoints']} endpoints, {s['repeats']} repeats"]
    if s["errors"]:
        parts.append(f"{s['errors']} errors")
    if s["wall_ms"] is not None:
        parts.append(f"net {s['wall_ms'] / 1000:.2f} s")
    if s["longest"]:
        parts.append(f"longest {s['longest']} {s['longest_ms']} ms")
    if s["cache_total"]:
        parts.append(f"cache {s['cache_hits']}/{s['cache_total']} HIT")
    if s["bytes"]:
        parts.append(f"{s['bytes'] / 1024:.0f} KB")
    return ", ".join(parts)


def to_rows(calls, phase, run):
    """Rows for api_calls.csv (benchlib.CALL_COLUMNS minus the meta columns benchlib fills)."""
    rows = []
    for c in calls:
        r = {k: ("" if c.get(k) is None else c.get(k)) for k in CALL_FIELDS}
        r["phase"], r["run"] = phase, run
        rows.append(r)
    return rows
