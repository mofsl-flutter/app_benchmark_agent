"""Unit tests for netcap.py with pcaps built in the test. Run: python3 -m unittest discover tests"""
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import netcap as N  # noqa: E402

PHONE, API, CDN, DNS = "10.215.173.2", "93.184.216.34", "151.101.1.1", "8.8.8.8"
T0 = 1_700_000_000.0


def ip4(src, dst, proto, payload):
    total = 20 + len(payload)
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 0, 0, 64, proto, 0,
                      bytes(int(x) for x in src.split(".")), bytes(int(x) for x in dst.split(".")))
    return hdr + payload


def tcp(sport, dport, flags, payload=b""):
    return struct.pack("!HHIIBBHHH", sport, dport, 0, 0, 5 << 4, flags, 65535, 0, 0) + payload


def udp(sport, dport, payload):
    return struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload


def client_hello(host):
    sni_name = struct.pack("!BH", 0, len(host)) + host.encode()
    sni_list = struct.pack("!H", len(sni_name)) + sni_name
    ext = struct.pack("!HH", 0, len(sni_list)) + sni_list
    body = b"\x03\x03" + b"\x00" * 32 + b"\x00" + struct.pack("!H", 2) + b"\x13\x01" + b"\x01\x00" \
        + struct.pack("!H", len(ext)) + ext
    hs = b"\x01" + struct.pack("!I", len(body))[1:] + body
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def dns_name(n):
    return b"".join(bytes([len(l)]) + l.encode() for l in n.split(".")) + b"\x00"


def dns_response(qname, cname_to, ip):
    q = dns_name(qname) + struct.pack("!HH", 1, 1)
    ans = dns_name(qname) + struct.pack("!HHIH", 5, 1, 60, len(dns_name(cname_to))) + dns_name(cname_to)
    ans += dns_name(cname_to) + struct.pack("!HHIH", 1, 1, 60, 4) + bytes(int(x) for x in ip.split("."))
    return struct.pack("!HHHHHH", 1, 0x8180, 1, 2, 0, 0) + q + ans


def dns_query(qname):
    return struct.pack("!HHHHHH", 1, 0x0100, 1, 0, 0, 0) + dns_name(qname) + struct.pack("!HH", 1, 1)


def pcap(linktype, pkts, snaplen=None):
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, linktype)
    for ts, ippkt in pkts:
        frame = (b"\x00" * 12 + b"\x08\x00" + ippkt) if linktype == 1 else ippkt
        incl = frame if snaplen is None else frame[:snaplen]
        out += struct.pack("<IIII", int(ts), int(round((ts - int(ts)) * 1e6)), len(incl), len(frame)) + incl
    return out


def sample_packets():
    return [
        (T0 + 0.10, ip4(PHONE, DNS, 17, udp(5000, 53, dns_query("cdn.example.net")))),
        (T0 + 0.12, ip4(DNS, PHONE, 17, udp(53, 5000, dns_response("cdn.example.net", "edge.fastly.net", CDN)))),
        (T0 + 0.20, ip4(PHONE, API, 6, tcp(40000, 443, 0x02))),                       # SYN
        (T0 + 0.22, ip4(API, PHONE, 6, tcp(443, 40000, 0x12))),                       # SYN-ACK
        (T0 + 0.25, ip4(PHONE, API, 6, tcp(40000, 443, 0x18, client_hello("api.example.com")))),
        (T0 + 0.33, ip4(API, PHONE, 6, tcp(443, 40000, 0x18, b"\x16\x03\x03" + b"x" * 500))),  # first server payload
        (T0 + 0.40, ip4(PHONE, CDN, 17, udp(50000, 443, b"\xc0" + b"q" * 1200))),     # QUIC
        (T0 + 0.45, ip4(CDN, PHONE, 17, udp(443, 50000, b"\xc0" + b"r" * 1200))),
        (T0 + 12.0, ip4(PHONE, API, 6, tcp(40001, 443, 0x02))),                       # SYN outside the window
    ]


class NetcapTests(unittest.TestCase):
    def check(self, linktype, snaplen=None):
        data = pcap(linktype, sample_packets(), snaplen)
        res = N.analyse(data, {"open": (T0, T0 + 10)}, own_domains=["example.com"])
        o = res["open"]
        self.assertEqual(o["connections"], 2)
        self.assertEqual(o["hosts"], ["api.example.com", "cdn.example.net"])
        self.assertEqual(o["third_party"], ["cdn.example.net"])
        self.assertEqual(o["dns_queries"], 1)
        api = next(f for f in o["flows"] if f["host"] == "api.example.com")
        self.assertEqual(api["first_response_ms"], 130)  # SYN at 0.20 s -> first server payload at 0.33 s
        self.assertEqual(api["proto"], "tcp")
        self.assertEqual(api["third_party"], "no")
        self.assertEqual(api["t_rel_ms"], 200)
        quic = next(f for f in o["flows"] if f["host"] == "cdn.example.net")
        self.assertEqual(quic["proto"], "quic")
        self.assertEqual(quic["third_party"], "yes")
        self.assertEqual(quic["bytes_in"], 20 + 8 + 1201)   # from the wire length even when snaplen cuts
        self.assertEqual(res["other"]["connections"], 1)
        dns_in = 20 + 8 + len(dns_response("cdn.example.net", "edge.fastly.net", CDN))
        self.assertEqual(o["win_bytes_in"], o["bytes_in"] + dns_in)  # the DNS answer is in the window but in no flow
        self.assertEqual(o["win_pkts"], 8)
        self.assertEqual(res["other"]["win_pkts"], 1)
        self.assertEqual(o["median_first_response_ms"], 130)
        rows = N.to_rows(res, 2, phases=["open"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["run"], 2)
        self.assertIn("2 hosts: api.example.com, cdn.example.net", N.hosts_note(o))

    def test_raw_ip(self):
        self.check(12)

    def test_ethernet(self):
        self.check(1)

    def test_snaplen(self):
        self.check(12, snaplen=200)  # cuts the 500-byte TLS and 1200-byte QUIC payloads, not DNS / ClientHello

    def test_sni_parser(self):
        self.assertEqual(N.tls_sni(client_hello("x.example.org")), "x.example.org")
        self.assertIsNone(N.tls_sni(b"\x17\x03\x03\x00\x05hello"))
        self.assertIsNone(N.tls_sni(b"\x16\x03\x01\x00"))

    def test_dns_parser(self):
        is_resp, qn, ips = N.dns_message(dns_response("a.example.net", "b.cdn.net", "1.2.3.4"))
        self.assertTrue(is_resp)
        self.assertEqual(qn, ["a.example.net"])
        self.assertEqual(ips, {"1.2.3.4": "a.example.net"})

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            N.read_pcap(b"nope")
        truncated = pcap(12, sample_packets())[:-30]
        N.analyse(truncated, {"open": (T0, T0 + 10)})  # must not raise
        junk = pcap(12, [(T0, b"\x45\x00")])
        self.assertEqual(N.analyse(junk, {"open": (T0, T0 + 10)})["open"]["connections"], 0)

    def test_third_party(self):
        self.assertEqual(N.third_party(["api.groww.in", "cdn.groww.in", "x.appsflyer.com", "1.2.3.4"], ["groww.in"]),
                         ["1.2.3.4", "x.appsflyer.com"])


if __name__ == "__main__":
    unittest.main()
