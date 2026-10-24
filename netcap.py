#!/usr/bin/env python3
"""Minimal pcap reader for the PCAPdroid pass (pure Python, no scapy, no adb).

From a per-app PCAPdroid capture it derives, per time window ("phase"): connections opened
(TCP SYN from the phone, or the first packet of a UDP flow to a port other than 53, i.e. QUIC),
the host names behind them (TLS ClientHello SNI, else a DNS answer seen earlier in the capture,
else the IP), DNS queries, bytes in and out (from the on-the-wire length, so a snaplen does not
matter) and the time to the first server packet with payload.

Encrypted contents stay encrypted: nothing here reads request paths or bodies. This is what
replaces the RISE API log for competitor apps (hosts, timing and bytes only).

Link types handled: Ethernet (1, also VLAN-tagged), raw IP (12, 101, 228, 229) and Linux SLL
(113). PCAPdroid writes raw IP unless its dump extensions add a fake Ethernet header.
"""
import struct

PCAP_MAGICS = {0xA1B2C3D4: ("<", 1e-6), 0xD4C3B2A1: (">", 1e-6), 0xA1B23C4D: ("<", 1e-9), 0x4D3CB2A1: (">", 1e-9)}
LINK_ETHERNET, LINK_SLL = 1, 113
LINK_RAW = {12, 101, 228, 229}
FLOW_FIELDS = ["seq", "phase", "t_rel_ms", "proto", "host", "dst_ip", "port", "sni", "first_response_ms",
               "bytes_out", "bytes_in", "pkts", "third_party"]


# ---------------------------------------------------------------- pcap

def read_pcap(data):
    """(linktype, [(ts_seconds, orig_len, captured_bytes)]). Raises ValueError on a non-pcap file."""
    if len(data) < 24:
        raise ValueError("not a pcap file (too short)")
    magic = struct.unpack("<I", data[:4])[0]
    if magic not in PCAP_MAGICS:
        magic_be = struct.unpack(">I", data[:4])[0]
        if magic_be == 0x0A0D0D0A:
            raise ValueError("pcapng is not supported; capture with pcapng_format off")
        raise ValueError("not a pcap file (bad magic)")
    endian, tick = PCAP_MAGICS[magic]
    linktype = struct.unpack(endian + "I", data[20:24])[0]
    pkts, off = [], 24
    while off + 16 <= len(data):
        sec, frac, incl, orig = struct.unpack(endian + "IIII", data[off:off + 16])
        off += 16
        if incl > len(data) - off:
            break  # truncated capture: keep what we have
        pkts.append((sec + frac * tick, orig, data[off:off + incl]))
        off += incl
    return linktype, pkts


def ip_payload(linktype, frame):
    """Strip the link-layer header; returns the IP packet bytes or None."""
    if linktype == LINK_ETHERNET:
        if len(frame) < 14:
            return None
        eth = struct.unpack("!H", frame[12:14])[0]
        off = 14
        while eth in (0x8100, 0x88A8) and len(frame) >= off + 4:
            eth = struct.unpack("!H", frame[off + 2:off + 4])[0]
            off += 4
        return frame[off:] if eth in (0x0800, 0x86DD) else None
    if linktype == LINK_SLL:
        if len(frame) < 16:
            return None
        eth = struct.unpack("!H", frame[14:16])[0]
        return frame[16:] if eth in (0x0800, 0x86DD) else None
    if linktype in LINK_RAW or linktype not in (LINK_ETHERNET, LINK_SLL):
        return frame
    return None


def parse_ip(buf):
    """(src, dst, proto, payload, total_len) for IPv4/IPv6; None when malformed."""
    if not buf:
        return None
    ver = buf[0] >> 4
    if ver == 4:
        if len(buf) < 20:
            return None
        ihl = (buf[0] & 0x0F) * 4
        total = struct.unpack("!H", buf[2:4])[0]
        proto = buf[9]
        src, dst = _ip4(buf[12:16]), _ip4(buf[16:20])
        if ihl < 20 or len(buf) < ihl:
            return None
        return src, dst, proto, buf[ihl:max(ihl, min(total, len(buf)))], total
    if ver == 6:
        if len(buf) < 40:
            return None
        plen = struct.unpack("!H", buf[4:6])[0]
        nxt = buf[6]
        src, dst = _ip6(buf[8:24]), _ip6(buf[24:40])
        off = 40
        while nxt in (0, 43, 44, 60) and len(buf) >= off + 8:  # hop-by-hop, routing, fragment, dst opts
            if nxt == 44:
                nxt, ext_len = buf[off], 8
            else:
                nxt, ext_len = buf[off], (buf[off + 1] + 1) * 8
            off += ext_len
        return src, dst, nxt, buf[off:], 40 + plen
    return None


def _ip4(b):
    return ".".join(str(x) for x in b)


def _ip6(b):
    return ":".join(f"{struct.unpack('!H', b[i:i + 2])[0]:x}" for i in range(0, 16, 2))


def parse_tcp(p):
    """(sport, dport, flags, payload) or None."""
    if len(p) < 20:
        return None
    sport, dport = struct.unpack("!HH", p[:4])
    doff = (p[12] >> 4) * 4
    flags = p[13]
    if doff < 20 or len(p) < doff:
        return None
    return sport, dport, flags, p[doff:]


def parse_udp(p):
    if len(p) < 8:
        return None
    sport, dport = struct.unpack("!HH", p[:4])
    return sport, dport, p[8:]


# ---------------------------------------------------------------- TLS / DNS

def tls_sni(payload):
    """Server name from a TLS ClientHello, or None."""
    try:
        if len(payload) < 6 or payload[0] != 0x16 or payload[5] != 0x01:
            return None
        p = payload[5:]            # handshake
        hl = struct.unpack("!I", b"\x00" + p[1:4])[0]
        p = p[4:4 + hl]
        off = 2 + 32               # version + random
        sid = p[off]; off += 1 + sid
        cs = struct.unpack("!H", p[off:off + 2])[0]; off += 2 + cs
        cm = p[off]; off += 1 + cm
        if off + 2 > len(p):
            return None
        el = struct.unpack("!H", p[off:off + 2])[0]; off += 2
        end = min(len(p), off + el)
        while off + 4 <= end:
            et, ln = struct.unpack("!HH", p[off:off + 4]); off += 4
            if et == 0:
                q = p[off:off + ln]
                i = 2
                while i + 3 <= len(q):
                    nt, nl = q[i], struct.unpack("!H", q[i + 1:i + 3])[0]
                    if nt == 0:
                        return q[i + 3:i + 3 + nl].decode("ascii", "replace").lower()
                    i += 3 + nl
                return None
            off += ln
    except (IndexError, struct.error, ValueError):
        return None
    return None


def _dns_name(buf, off, depth=0):
    labels = []
    while off < len(buf):
        ln = buf[off]
        if ln == 0:
            return ".".join(labels), off + 1
        if ln & 0xC0 == 0xC0:
            ptr = struct.unpack("!H", buf[off:off + 2])[0] & 0x3FFF
            if depth > 10:
                return ".".join(labels), off + 2
            tail, _ = _dns_name(buf, ptr, depth + 1)
            return ".".join(labels + ([tail] if tail else [])), off + 2
        labels.append(buf[off + 1:off + 1 + ln].decode("ascii", "replace"))
        off += 1 + ln
    return ".".join(labels), off


def dns_message(payload):
    """(is_response, [query names], {ip: name}) with CNAME chains resolved to the queried name."""
    try:
        if len(payload) < 12:
            return None
        flags, qd, an = struct.unpack("!HHH", payload[2:8])
        off, qnames = 12, []
        for _ in range(qd):
            name, off = _dns_name(payload, off)
            off += 4
            qnames.append(name.lower())
        cname = {}
        addrs = []
        for _ in range(an):
            name, off = _dns_name(payload, off)
            rtype, _, _, rdlen = struct.unpack("!HHIH", payload[off:off + 10]); off += 10
            rdata = payload[off:off + rdlen]
            if rtype == 1 and rdlen == 4:
                addrs.append((name.lower(), _ip4(rdata)))
            elif rtype == 28 and rdlen == 16:
                addrs.append((name.lower(), _ip6(rdata)))
            elif rtype == 5:
                target, _ = _dns_name(payload, off)
                cname[target.lower()] = name.lower()
            off += rdlen
        ips = {}
        for name, ip in addrs:
            seen = 0
            while name in cname and seen < 10:
                name = cname[name]; seen += 1
            ips[ip] = name
        return bool(flags & 0x8000), qnames, ips
    except (IndexError, struct.error):
        return None


# ---------------------------------------------------------------- analysis

def third_party(hosts, own_domains):
    own = [d.lower().lstrip(".") for d in (own_domains or []) if d]
    out = set()
    for h in hosts:
        h = (h or "").lower()
        if not h or h.replace(".", "").isdigit() or ":" in h:
            out.add(h or "?")  # bare IPs (no SNI, no DNS answer) count as unknown third parties
            continue
        if not any(h == d or h.endswith("." + d) for d in own):
            out.add(h)
    return sorted(out)


def analyse(data, windows, own_domains=None):
    """{phase: {connections, hosts, third_party, dns_queries, bytes_out, bytes_in, flows: [flow dicts]}}.

    windows: {phase: (t_start, t_end)} in pcap time (device epoch seconds). A flow belongs to the
    phase whose window holds its first packet. Flows outside every window are kept under "other".
    """
    linktype, pkts = read_pcap(data)
    flows, order = {}, []
    dns_map, dns_queries = {}, []
    win_bytes = {ph: [0, 0, 0] for ph in list(windows) + ["other"]}  # [in, out, pkts] by packet time, any flow
    for ts, orig, frame in pkts:
        ip = parse_ip(ip_payload(linktype, frame) or b"")
        if not ip:
            continue
        src, dst, proto, payload, total = ip
        wire = total or orig  # IP length: the same for every link type, intact under a snaplen
        if proto == 6:
            t = parse_tcp(payload)
            if not t:
                continue
            sport, dport, flags, body = t
            proto_name = "tcp"
        elif proto == 17:
            u = parse_udp(payload)
            if not u:
                continue
            sport, dport, body = u
            flags = 0
            proto_name = "udp"
            if sport == 53 or dport == 53:
                wb = win_bytes[_phase_of(ts, windows)]
                wb[2] += 1
                wb[0 if sport == 53 else 1] += wire  # answers come from port 53
                d = dns_message(body)
                if d:
                    is_resp, qn, ips = d
                    if is_resp:
                        dns_map.update(ips)
                    else:
                        dns_queries.append((ts, qn[0] if qn else ""))
                continue
        else:
            continue
        # direction: the phone is the side that opens the flow (first packet seen)
        key_fwd = (proto_name, src, sport, dst, dport)
        key_rev = (proto_name, dst, dport, src, sport)
        if key_fwd in flows:
            f, outbound = flows[key_fwd], True
        elif key_rev in flows:
            f, outbound = flows[key_rev], False
        else:
            syn = proto_name == "tcp" and (flags & 0x02) and not (flags & 0x10)
            f = {"proto": proto_name if proto_name == "tcp" else ("quic" if dport == 443 else "udp"),
                 "dst_ip": dst, "port": dport, "ts_first": ts, "ts_first_response": None, "sni": "",
                 "bytes_out": 0, "bytes_in": 0, "pkts": 0, "opened": bool(syn or proto_name == "udp")}
            flows[key_fwd] = f
            order.append(f)
            outbound = True
        f["pkts"] += 1
        wb = win_bytes[_phase_of(ts, windows)]
        wb[2] += 1
        if outbound:
            f["bytes_out"] += wire
            wb[1] += wire
            if body and not f["sni"]:
                f["sni"] = tls_sni(body) or ""
        else:
            f["bytes_in"] += wire
            wb[0] += wire
            if body and f["ts_first_response"] is None:
                f["ts_first_response"] = ts
    result = {ph: _empty() for ph in list(windows) + ["other"]}
    seq = 0
    for f in order:
        host = f["sni"] or dns_map.get(f["dst_ip"]) or f["dst_ip"]
        phase = _phase_of(f["ts_first"], windows)
        a = windows.get(phase, (f["ts_first"], None))[0] if phase != "other" else f["ts_first"]
        seq += 1
        row = {"seq": seq, "phase": phase, "t_rel_ms": int(round((f["ts_first"] - a) * 1000)), "proto": f["proto"],
               "host": host, "dst_ip": f["dst_ip"], "port": f["port"], "sni": f["sni"],
               "first_response_ms": (int(round((f["ts_first_response"] - f["ts_first"]) * 1000))
                                     if f["ts_first_response"] is not None else None),
               "bytes_out": f["bytes_out"], "bytes_in": f["bytes_in"], "pkts": f["pkts"],
               "third_party": "", "opened": f["opened"]}
        r = result[phase]
        r["flows"].append(row)
        if f["opened"]:
            r["connections"] += 1
        r["hosts"].add(host)
        r["bytes_out"] += f["bytes_out"]
        r["bytes_in"] += f["bytes_in"]
    for ph, (a, b) in windows.items():
        result[ph]["dns_queries"] = sum(1 for ts, _ in dns_queries if a is not None and a <= ts <= (b if b is not None else float("inf")))
    for ph, r in result.items():
        r["win_bytes_in"], r["win_bytes_out"], r["win_pkts"] = win_bytes[ph]
        tp = set(third_party(r["hosts"], own_domains)) if own_domains else set()
        r["third_party"] = sorted(tp)
        for row in r["flows"]:
            row["third_party"] = "yes" if (row["host"] in tp) else ("" if not own_domains else "no")
        r["hosts"] = sorted(r["hosts"])
        frs = [x["first_response_ms"] for x in r["flows"] if x["first_response_ms"] is not None]
        r["median_first_response_ms"] = sorted(frs)[len(frs) // 2] if frs else None
    return result


def _phase_of(ts, windows):
    return next((ph for ph, (a, b) in windows.items()
                 if a is not None and a <= ts <= (b if b is not None else float("inf"))), "other")


def _empty():
    return {"connections": 0, "hosts": set(), "third_party": [], "dns_queries": 0, "bytes_out": 0, "bytes_in": 0,
            "win_bytes_in": 0, "win_bytes_out": 0, "win_pkts": 0, "flows": [], "median_first_response_ms": None}


def to_rows(result, run, phases=None):
    """Rows for net_calls.csv (benchlib.NET_COLUMNS minus the meta columns benchlib fills)."""
    rows = []
    for ph, r in result.items():
        if phases is not None and ph not in phases:
            continue
        for f in r["flows"]:
            row = {k: ("" if f.get(k) is None else f.get(k)) for k in FLOW_FIELDS}
            row["run"] = run
            rows.append(row)
    return rows


def hosts_note(r, top=8):
    hosts = r["hosts"]
    shown = ", ".join(hosts[:top]) + (f" +{len(hosts) - top} more" if len(hosts) > top else "")
    med = r["median_first_response_ms"]
    kb = (r["win_bytes_in"] + r["win_bytes_out"]) / 1024
    return (f"{len(hosts)} hosts: {shown}; DNS {r['dns_queries']}; "
            f"median first-response {med if med is not None else '?'} ms; {kb:.0f} KB in the window")
