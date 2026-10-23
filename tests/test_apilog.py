"""Unit tests for apilog.py (RISE logcat API lines). Run: python3 -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import apilog as A  # noqa: E402

P = "10-23 13:34:21"
BASE = "https://api.example-broker.com"
LOG = "\n".join([
    # call 1, logged twice (same ts), base URL doubled
    f'{P}.100 14986 15030 I flutter : {{"ts":"2026-10-23 13:34:21.050","level":"SUCCESS","type":"API","method":"POST",'
    f'"url":"{BASE}{BASE}/TradingApiV2/api/Init","status":200,"duration_ms":252,"api_version":"4.0","cdn":{{"cache":"MISS"}}}}',
    f'{P}.100 14986 15030 I flutter : {{API Failed}}',
    f'{P}.101 14986 15030 I flutter : Response for /TradingApiV2/api/Init size: 1.5 KB',
    f'{P}.101 14986 15030 I flutter : {{"ts":"2026-10-23 13:34:21.050","level":"SUCCESS","type":"API","method":"POST",'
    f'"url":"{BASE}{BASE}/TradingApiV2/api/Init","status":200,"duration_ms":252,"api_version":"4.0","cdn":{{"cache":"MISS"}}}}',
    # unrelated noise from another process
    f'{P}.102 21481 21481 W PackageConfigPersister: App-specific configuration not found',
    # call 2 with a query string carrying a client code and an id-like path segment
    f'{P}.400 14986 15030 I flutter : {{"ts":"2026-10-23 13:34:21.300","level":"SUCCESS","type":"API","method":"GET",'
    f'"url":"{BASE}/portfolio/api/holdings/ABC12345/summary?clientcode=ABC12345&token=secret","status":200,"duration_ms":120}}',
    # call 3 split over two logcat lines; same endpoint as call 2 -> repeat
    f'{P}.600 14986 15030 I flutter : {{"ts":"2026-10-23 13:34:21.500","level":"SUCCESS","type":"API","method":"GET",',
    f'{P}.600 14986 15030 I flutter : "url":"{BASE}/portfolio/api/holdings/ABC12345/summary","status":200,"duration_ms":80,"cdn":{{"cache":"HIT"}}}}',
    # a non-API JSON object (UAT-style body dump) must be ignored
    f'{P}.700 14986 15030 I flutter : {{"type":"BODY","data":{{"x":1}}}}',
    # call 4: an error
    f'{P}.900 14986 15030 E flutter : {{"ts":"2026-10-23 13:34:21.900","level":"ERROR","type":"API","method":"GET",'
    f'"url":"{BASE}/cmsapi/v2/api/Explore/Home","status":500,"duration_ms":1000}}',
])


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.calls = A.parse_api_log(LOG)

    def test_count_after_dedupe(self):
        self.assertEqual(len(self.calls), 4)
        self.assertEqual([c["seq"] for c in self.calls], [1, 2, 3, 4])

    def test_doubled_base_url_and_query_stripped(self):
        c = self.calls[0]
        self.assertEqual(c["host"], "api.example-broker.com")
        self.assertEqual(c["path"], "/TradingApiV2/api/Init")
        c2 = self.calls[1]
        self.assertEqual(c2["path"], "/portfolio/api/holdings/{id}/summary")
        for c in self.calls:
            for v in c.values():
                self.assertNotIn("secret", str(v))
                self.assertNotIn("ABC12345", str(v))
                self.assertNotIn("?", str(v))

    def test_fields(self):
        c = self.calls[0]
        self.assertEqual((c["method"], c["status"], c["duration_ms"], c["cache"], c["api_version"]),
                         ("POST", 200, 252, "MISS", "4.0"))
        self.assertEqual(c["size_bytes"], 1536)
        self.assertEqual(c["t_rel_ms"], 0)
        self.assertEqual(self.calls[1]["t_rel_ms"], 250)
        self.assertIsNone(self.calls[1]["size_bytes"])

    def test_split_json_and_repeat(self):
        c3 = self.calls[2]
        self.assertEqual(c3["duration_ms"], 80)
        self.assertEqual(c3["cache"], "HIT")
        self.assertEqual(c3["repeat_of"], 2)
        self.assertEqual(self.calls[1]["repeat_of"], "")

    def test_summary(self):
        s = A.summarize(self.calls)
        self.assertEqual((s["calls"], s["endpoints"], s["repeats"], s["errors"]), (4, 3, 1, 1))
        self.assertEqual(s["total_ms"], 252 + 120 + 80 + 1000)
        self.assertEqual(s["wall_ms"], 850 + 1000)
        self.assertEqual(s["longest"], "GET /cmsapi/v2/api/Explore/Home")
        self.assertEqual((s["cache_hits"], s["cache_total"]), (1, 2))
        note = A.summary_note(self.calls)
        self.assertTrue(note.startswith("api: 4 calls, 3 endpoints, 1 repeats, 1 errors, net 1.85 s"), note)
        self.assertIn("longest GET /cmsapi/v2/api/Explore/Home 1000 ms", note)
        self.assertIn("cache 1/2 HIT", note)

    def test_rows(self):
        rows = A.to_rows(self.calls, "open", 3)
        self.assertEqual(len(rows), 4)
        self.assertEqual((rows[0]["phase"], rows[0]["run"], rows[0]["seq"]), ("open", 3, 1))
        self.assertEqual(rows[1]["size_bytes"], "")

    def test_empty_for_competitor_log(self):
        self.assertEqual(A.parse_api_log("10-23 13:34:21.100 1 1 I foo : hello\nnot a logcat line"), [])
        self.assertEqual(A.summary_note([]), "")


class HelperTests(unittest.TestCase):
    def test_sanitize_path(self):
        self.assertEqual(A.sanitize_path("/a/123456/b/3fa85f64-5717-4562-b3fc-2c963f66afa6/c?x=1"), "/a/{id}/b/{id}/c")
        self.assertEqual(A.sanitize_path("/v2/api/Explore/Home"), "/v2/api/Explore/Home")
        self.assertEqual(A.sanitize_path("/user/MO12345678/x"), "/user/{id}/x")
        self.assertEqual(A.sanitize_path(""), "/")

    def test_normalise_url(self):
        self.assertEqual(A.normalise_url("https://a.b/x/https://a.b/y?q=1"), ("a.b", "/y"))
        self.assertEqual(A.normalise_url("/relative/path?z=1"), ("", "/relative/path"))


if __name__ == "__main__":
    unittest.main()


class RealLineTests(unittest.TestCase):
    """One real PLogger line from a RISE 6.2.09 launch on 2026-10-23 (client_id redacted)."""
    REAL = ('10-23 20:44:57.574  4795  5150 I PLogger : {"ts":"2026-10-23T20:44:55.857","level":"SUCCESS","type":"API",'
            '"method":"POST","url":"https://tradingapi.mofsl.nethttps://tradingapi.mofsl.net/TradingApiV2/api/Init",'
            '"status":200,"duration_ms":1250,"api_version":"4.0","platform":"Android","os_version":"16",'
            '"app_version":"6.2.09_6220","client_id":"00000000-0000-4000-8000-000000000000",'
            '"cdn":{"cache":"MISS","edge_ms":6,"origin_ms":18}}\n'
            '10-23 20:44:57.729  4795  4795 I PLogger : {23-10-2026 20:44:57.107 PM}  {API Failed}  {The new error }  '
            '{23 October 2026 08:44:57.530 PM}  {INFO}\n')

    REAL2 = ('10-23 21:11:25.702 20906 23064 I PLogger : {"ts":"2026-10-23T21:11:25.421","level":"SUCCESS","type":"API","method":"GET",'
             '"url":"https://api.riseapp.inhttps://api.riseapp.in/wms/v2/api/Search/History/Recent","status":200,"duration_ms":216,"api_version":"1.0"}\n'
             + "10-23 21:11:25.710 20906 20906 I Noise : filler\n" * 12 +
             '10-23 21:11:25.786 20906 20906 I PLogger : {23-10-2026 21:11:25.637 PM}  {Trader API Service}  {Response 200, GET,'
             'https://api.riseapp.in/wms/v2/api/Search/History/Recent, Response Time: 216ms, Data Size: 4kb }  {23 October 2026 09:11:25.686 PM}  {INFO}\n'
             '10-23 21:11:28.136 20906 23064 I PLogger : {"ts":"2026-10-23T21:11:27.988","level":"SUCCESS","type":"API","method":"GET",'
             '"url":"https://api.riseapp.inhttps://api.riseapp.in/wms/v2/api/Search/History/Recent","status":200,"duration_ms":140,"api_version":"1.0"}\n'
             '10-23 21:11:28.627 20906 23064 I PLogger : {"ts":"2026-10-23T21:11:28.214","level":"SUCCESS","type":"API","method":"GET",'
             '"url":"https://api.riseapp.inhttps://api.riseapp.in/wms/v2/api/Search?query=RELIANCE","status":200,"duration_ms":407,"api_version":"1.0"}\n'
             '10-23 21:11:28.700 20906 20906 I PLogger : {23-10-2026 21:11:28.630 PM}  {Trader API Service}  {Response 200, GET,'
             'https://api.riseapp.in/wms/v2/api/Search?query=RELIANCE, Response Time: 407ms, Data Size: 14kb }  {23 October 2026 09:11:28.690 PM}  {INFO}\n')

    def test_real_response_lines_pair_by_path_and_time(self):
        calls = A.parse_api_log(self.REAL2)
        self.assertEqual([(c["path"], c["duration_ms"], c["size_bytes"], c["repeat_of"]) for c in calls],
                         [("/wms/v2/api/Search/History/Recent", 216, 4096, ""),
                          ("/wms/v2/api/Search/History/Recent", 140, None, 1),
                          ("/wms/v2/api/Search", 407, 14336, "")])
        self.assertTrue(all("RELIANCE" not in str(v) for c in calls for v in c.values()))

    def test_real_line(self):
        calls = A.parse_api_log(self.REAL)
        self.assertEqual(len(calls), 1)
        c = calls[0]
        self.assertEqual((c["method"], c["host"], c["path"], c["status"], c["duration_ms"], c["cache"]),
                         ("POST", "tradingapi.mofsl.net", "/TradingApiV2/api/Init", 200, 1250, "MISS"))
        self.assertEqual(c["t_rel_ms"], 0)
        for v in c.values():
            self.assertNotIn("00000000-0000", str(v))  # client_id is never copied out
        self.assertEqual(A.summary_note(calls), "api: 1 calls, 1 endpoints, 0 repeats, net 1.25 s, "
                                                "longest POST /TradingApiV2/api/Init 1250 ms, cache 0/1 HIT")
