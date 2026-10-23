"""Build the multi-page execution plan (HTML) from the JSON files written by the
benchmark-execution-plan agent.

Usage: python3 execution-plan/tools/build_plan.py <data_dir> <out_dir>

<data_dir> holds meta.json, section-<LETTER>.json (one per section) and, optionally,
summary.json, optimized.json and preferred.json. See execution-plan/SCHEMA.md.
"""
import html
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 3:
    sys.exit("usage: build_plan.py <data_dir> <out_dir>")
SRC = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
with open(os.path.join(SRC, "meta.json"), encoding="utf-8") as _f:
    META = json.load(_f)
MODULE_PATH = META.get("module_path", "").rstrip("/")
MODULE_PKG = os.path.basename(MODULE_PATH) or "module"
PLAN_TITLE = META.get("title", "Change Plan")

ORDER = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
CATS = ["FE", "FE-Shared", "BE", "Product"]
CAT_LABEL = {"FE": "FE", "FE-Shared": "FE · shared", "BE": "BE", "Product": "Product"}
CAT_DESC = {
    "FE": "Front-end change inside %s only. Owned by the module's FE team." % (MODULE_PATH or "the module"),
    "FE-Shared": "Front-end change in a shared package or the app shell. Other modules depend on these, so they need wider review and testing.",
    "BE": "Backend, API, socket server, CDN or Remote Config value change. Needs the backend or platform team.",
    "Product": "Changes what the user sees or how a feature behaves. Needs a Product / UX decision before release. Until then the change ships behind a flag that keeps today's behaviour.",
}
RISKS = ["Low", "Medium", "High"]
RISK_DESC = {
    "Low": "Internal to one widget or function. No visible behaviour change. Easy to revert. Normal code review and a smoke test.",
    "Medium": "Changes loading order, timing, state flow or a visible detail inside this module. Needs a regression pass on the affected screen.",
    "High": "Touches a shared package used by other modules, navigation / back-stack, a live-data subscription model or the core state flow. Ships behind a feature flag and needs a full regression pass.",
}
EFFORT = {"S": "≤ 1 day", "M": "2–4 days", "L": "1 week +"}
RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}

DATE = META.get("date", "")
CODE_ROOTS = [r.rstrip("/") + "/" for r in {META.get("code_root", ""), os.path.expanduser(META.get("code_root", ""))} if r]


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def slug(letter):
    return "section-%s.html" % letter.lower()


# ---------- Dart highlighting ----------
KW = ("abstract as assert async await break case catch class const continue covariant default deferred do dynamic else enum "
      "export extends extension external factory false final finally for Function get if implements import in is late library "
      "mixin new null on operator part required rethrow return set show static super switch sync this throw true try typedef "
      "var void while with yield override").split()
TOKEN = re.compile(
    r"(?P<c>//[^\n]*|/\*.*?\*/)"
    r"|(?P<s>'''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\")"
    r"|(?P<k>@\w+|\b(?:%s)\b)"
    r"|(?P<n>\b\d+(?:\.\d+)?\b)" % "|".join(KW),
    re.S,
)


def hl(code):
    out, pos = [], 0
    for m in TOKEN.finditer(code):
        out.append(esc(code[pos:m.start()]))
        kind = m.lastgroup
        cls = {"c": "t-c", "s": "t-s", "k": "t-k", "n": "t-n"}[kind]
        out.append('<span class="%s">%s</span>' % (cls, esc(m.group(0))))
        pos = m.end()
    out.append(esc(code[pos:]))
    return "".join(out)


# ---------- load ----------
sections = []
for L in ORDER:
    p = os.path.join(SRC, "section-%s.json" % L)
    if not os.path.exists(p):
        continue
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    d["letter"] = L
    for c in d.get("changes", []):
        c["_sec"] = L
        c["_sectitle"] = d.get("title", "")
        c.setdefault("categories", ["FE"])
        c["categories"] = [x for x in c["categories"] if x in CATS] or ["FE"]
        if c.get("risk") not in RISKS:
            c["risk"] = "Medium"
        c.setdefault("files", [])
        c.setdefault("steps", [])
        c.setdefault("safety", [])
        c.setdefault("regression_checks", [])
        c.setdefault("depends_on", [])
    sections.append(d)

ALL = [c for s in sections for c in s["changes"]]
if not ALL:
    sys.exit("no section-*.json files with changes in %s" % SRC)

FOOTER = META.get("footer") or (
    "Prepared from a read-only review of %s%s and the benchmark %s%s. Expected results are estimates to be confirmed by "
    "re-measuring on the same device. Items tagged \"verify\" need device confirmation." % (
        MODULE_PATH or "the module", (" (branch %s)" % META["branch"]) if META.get("branch") else "",
        META.get("benchmark_source", "results"), (" measured on %s" % META["measured_on"]) if META.get("measured_on") else ""))
EXTRA_PAGES = [(f, t) for f, t, src in (
    ("roadmap.html", "Roadmap and rank impact", "roadmap.json"),
    ("summary.html", "Summary and 2–4 day plan", "summary.json"),
    ("optimized-plan.html", "Optimized FE plan", "optimized.json"),
    ("most-preferred-plan.html", "Most preferred plan", "preferred.json")) if os.path.exists(os.path.join(SRC, src))
    and (src != "roadmap.json" or os.path.exists(os.path.join(SRC, "rank.json")))]
BY_ID = {c["id"]: c for c in ALL}


def link(cid, with_title=False):
    c = BY_ID.get(cid)
    if not c:
        return esc(cid)
    t = (' — ' + esc(c["title"])) if with_title else ""
    return '<a href="%s#%s" title="%s">%s</a>%s' % (slug(c["_sec"]), esc(cid), esc(c["title"]), esc(cid), t)


def cat_tags(cats):
    return '<span class="tags">' + "".join('<span class="tag cat-%s">%s</span>' % (esc(c), esc(CAT_LABEL[c])) for c in cats) + "</span>"


def risk_html(r):
    return '<span class="risk %s">%s</span>' % (esc(r), esc(r))


def effort_html(e):
    return '<span class="effort">%s · %s</span>' % (esc(e), esc(EFFORT.get(e, "")))


def norm_path(p):
    p = (p or "").strip()
    for root in CODE_ROOTS:  # absolute paths under the analysed repository become repository-relative
        if p.startswith(root):
            p = p[len(root):]
            break
    m = re.match(r"^(?:~|/Users/[^/]+)/\.pub-cache/git/([a-z_]+)-[0-9a-f]+/(.*)$", p)
    if m:
        p = "%s: %s" % (m.group(1), m.group(2))
    m = re.match(r"^(?:~|/Users/[^/]+)/\.pub-cache/hosted/pub\.dev/([a-z_]+)-[0-9.+]+/(.*)$", p)
    if m:
        p = "%s: %s" % (m.group(1), m.group(2))
    p = re.sub(r"^([a-z_]+):\s*", r"\1: ", p)
    return p


def pkg_of(p):
    m = re.match(r"^packages/([^/]+)/", p)
    if m:
        return m.group(1)
    m = re.match(r"^apps/([^/]+)/", p)
    if m:
        return "apps/" + m.group(1)
    m = re.match(r"^([a-z_]+): ", p)
    if m:
        return m.group(1)
    return "other"


def counts(changes):
    r = {k: 0 for k in RISKS}
    c = {k: 0 for k in CATS}
    for x in changes:
        r[x["risk"]] += 1
        for k in x["categories"]:
            c[k] += 1
    return r, c


def split_bar(r):
    tot = sum(r.values()) or 1
    parts = "".join('<i class="%s" style="width:%.1f%%" title="%s: %d"></i>' % (cls, 100.0 * r[k] / tot, k, r[k])
                    for k, cls in (("Low", "low"), ("Medium", "med"), ("High", "high")) if r[k])
    return '<div class="split" aria-hidden="true">%s</div>' % parts


# ---------- page shell ----------
def nav(current):
    def a(href, label, n=None, letter=None):
        cls = ' class="current"' if href == current else ""
        l = '<span class="l">%s</span>' % esc(letter) if letter else ""
        nn = '<span class="n">%s</span>' % n if n is not None else ""
        return '<a href="%s"%s>%s<span>%s</span>%s</a>' % (href, cls, l, esc(label), nn)

    secs = "".join(a(slug(s["letter"]), s["title"], len(s["changes"]), s["letter"]) for s in sections)
    return (
        '<div class="navgroup">%s%s</div>' % (a("index.html", "Overview"), "".join(a(f, t) for f, t in EXTRA_PAGES))
        + '<div class="navgroup"><div class="label">Sections</div>%s</div>' % secs
        + '<div class="navgroup"><div class="label">Cross views</div>%s%s%s%s</div>'
        % (a("files.html", "File-wise changes"), a("teams.html", "Team-wise changes"),
           a("risk.html", "Risk and rollout"), a("full-report.html", "Full report (print)"))
    )


def page(fname, title, body, desc):
    n = nav(fname)
    doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="shell">
  <aside class="side" aria-label="Report navigation">
    <div class="brand">%(plan)s<small>%(pkg)s · %(date)s</small></div>
    %(nav)s
  </aside>
  <div>
    <div class="topnav">
      <div class="row">
        <div class="brand">%(plan)s</div>
        <details><summary>Menu</summary><div class="menu">%(nav)s</div></details>
      </div>
    </div>
    <main class="content">
%(body)s
      <footer class="foot">%(foot)s</footer>
    </main>
  </div>
</div>
<script src="assets/app.js"></script>
</body>
</html>
""" % {"title": esc(title), "desc": esc(desc), "nav": n, "body": body, "date": esc(DATE), "plan": esc(PLAN_TITLE), "pkg": esc(MODULE_PKG), "foot": esc(FOOTER)}
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
        f.write(doc)


def pagehead(eyebrow, title, lede, meta_html=""):
    return """      <header class="pagehead">
        <div class="headrow"><div class="eyebrow">%s</div><button class="theme-btn" type="button">Theme</button></div>
        <h1>%s</h1>
        <p class="lede">%s</p>
        %s
      </header>""" % (esc(eyebrow), esc(title), esc(lede), meta_html)


def filters_bar(noun, risk=True, cats=True):
    chips_c = ""
    if cats:
        chips_c = '<div class="chips" role="group" aria-label="Filter by team">' + \
            '<button class="chip" type="button" data-group="cat" data-value="all" aria-pressed="true">All teams</button>' + \
            "".join('<button class="chip" type="button" data-group="cat" data-value="%s" aria-pressed="false">%s</button>' % (c, esc(CAT_LABEL[c])) for c in CATS) + "</div>"
    chips_r = ""
    if risk:
        chips_r = '<div class="chips" role="group" aria-label="Filter by risk">' + \
            '<button class="chip" type="button" data-group="risk" data-value="all" aria-pressed="true">Any risk</button>' + \
            "".join('<button class="chip" type="button" data-group="risk" data-value="%s" aria-pressed="false">%s</button>' % (r, r) for r in RISKS) + "</div>"
    return ('<div class="filters" role="search"><input class="search" id="search" type="search" placeholder="Search…" aria-label="Search">'
            '%s%s<span class="count" id="count" data-noun="%s" aria-live="polite"></span></div>') % (chips_c, chips_r, esc(noun))


# ---------- change card ----------
def change_card(c):
    cats = " ".join(c["categories"])
    facts = [
        '<span>Teams %s</span>' % cat_tags(c["categories"]),
        '<span>Risk %s</span>' % risk_html(c["risk"]),
        '<span>Effort %s</span>' % effort_html(c.get("effort", "M")),
        '<span><span class="tag visible">%s</span></span>' % ("Visible to users" if c.get("user_visible") else "No visible change"),
    ]
    if c.get("verify"):
        facts.append('<span><span class="tag verify">verify on device</span></span>')
    if c.get("depends_on"):
        facts.append('<span class="idlinks">Depends on %s</span>' % " ".join(link(x) for x in c["depends_on"]))

    steps = "".join("<li>%s</li>" % esc(s) for s in c["steps"])
    files_rows = "".join(
        '<tr><td class="path">%s</td><td class="nowrap">%s</td><td>%s</td></tr>' % (esc(norm_path(f.get("path"))), esc(f.get("lines", "")), esc(f.get("change", "")))
        for f in c["files"])
    files_tbl = ('<div class="part"><h4>Files</h4><div class="card table-wrap"><table class="files-table"><thead><tr><th>File</th><th>Lines</th><th>What changes</th></tr></thead><tbody>%s</tbody></table></div></div>' % files_rows) if files_rows else ""

    code = ""
    b, a = c.get("before_code") or {}, c.get("after_code") or {}
    if b.get("code") or a.get("code"):
        boxes = ""
        if b.get("code"):
            loc = norm_path(b.get("path", "")) + ((":" + b["lines"]) if b.get("lines") else "")
            boxes += '<div class="codebox before"><div class="cap"><b>Current code</b><span class="loc">%s</span></div><pre><code>%s</code></pre></div>' % (esc(loc), hl(b["code"].rstrip()))
        if a.get("code"):
            boxes += '<div class="codebox after"><div class="cap"><b>Proposed change</b><span class="loc">sketch</span></div><pre><code>%s</code></pre></div>' % hl(a["code"].rstrip())
        code = '<div class="codepair">%s</div>' % boxes

    safety = "".join("<li>%s</li>" % esc(s) for s in c["safety"])
    checks = "".join("<li>%s</li>" % esc(s) for s in c["regression_checks"])
    callouts = ""
    if c.get("product_decision"):
        callouts += '<div class="callout prod"><h4>Product decision needed</h4><p>%s</p></div>' % esc(c["product_decision"])
    if c.get("be_request"):
        callouts += '<div class="callout be"><h4>Backend request</h4><p>%s</p></div>' % esc(c["be_request"])
    if callouts:
        callouts = '<div class="callouts%s">%s</div>' % (" two" if c.get("product_decision") and c.get("be_request") else "", callouts)

    return """<article class="card change" id="%(id)s" data-item data-cat="%(cats)s" data-risk="%(risk)s">
  <header>
    <div class="idrow"><span class="cid">%(id)s</span><h3>%(title)s</h3></div>
    <p class="summary">%(summary)s</p>
    <div class="facts">%(facts)s</div>
  </header>
  <div class="bodygrid">
    <div class="twocol">
      <div class="part"><h4>Today</h4><p>%(current)s</p></div>
      <div class="part"><h4>What to change</h4><ol>%(steps)s</ol></div>
    </div>
    %(files)s
    %(code)s
    <div class="twocol">
      <div class="part"><h4>How existing behaviour is kept</h4><ul>%(safety)s</ul></div>
      <div class="part"><h4>Regression checks</h4><ul>%(checks)s</ul></div>
    </div>
    <p class="riskbox"><b>Risk %(risk)s.</b> %(risk_reason)s</p>
    %(callouts)s
    <div class="callout after"><h4>After improvement</h4><p>%(after)s</p></div>
  </div>
</article>""" % {
        "id": esc(c["id"]), "cats": esc(cats), "risk": esc(c["risk"]), "title": esc(c.get("title")),
        "summary": esc(c.get("summary")), "facts": "".join(facts), "current": esc(c.get("current")),
        "steps": steps, "files": files_tbl, "code": code, "safety": safety, "checks": checks,
        "risk_reason": esc(c.get("risk_reason")), "callouts": callouts, "after": esc(c.get("after_improvement")),
    }


def measured_table(s, with_area=False):
    rows = s.get("measured") or []
    if not rows:
        return ""
    body = "".join("<tr>%s<td>%s</td><td>%s</td><td><b>%s</b></td></tr>" % (
        ('<td class="nowrap"><a href="%s">%s · %s</a></td>' % (slug(s["letter"]), s["letter"], esc(s["title"])) if with_area else ""),
        esc(r.get("metric")), esc(r.get("current")), esc(r.get("expected"))) for r in rows)
    head = "<tr>%s<th>Metric</th><th>Today</th><th>After improvement</th></tr>" % ("<th>Section</th>" if with_area else "")
    return '<div class="card table-wrap"><table><thead>%s</thead><tbody>%s</tbody></table></div>' % (head, body)


def summary_table(changes, show_section=False):
    rows = "".join("<tr>%s<td class=\"nowrap\">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        ('<td class="nowrap">%s</td>' % esc(c["_sec"]) if show_section else ""),
        link(c["id"]), esc(c.get("title")), cat_tags(c["categories"]), risk_html(c["risk"]),
        effort_html(c.get("effort", "M")), "Yes" if c.get("user_visible") else '<span class="muted">No</span>') for c in changes)
    head = "<tr>%s<th>ID</th><th>Change</th><th>Teams</th><th>Risk</th><th>Effort</th><th>Visible</th></tr>" % ("<th>Sec</th>" if show_section else "")
    return '<div class="card table-wrap"><table><thead>%s</thead><tbody>%s</tbody></table></div>' % (head, rows)


# ---------- build ----------
os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
shutil.copy(os.path.join(HERE, "assets", "style.css"), os.path.join(OUT, "assets", "style.css"))
shutil.copy(os.path.join(HERE, "assets", "app.js"), os.path.join(OUT, "assets", "app.js"))

R, C = counts(ALL)
visible = sum(1 for c in ALL if c.get("user_visible"))

# Section pages
for i, s in enumerate(sections):
    L = s["letter"]
    r, cc = counts(s["changes"])
    meta = '<div class="meta"><span><b>%d</b> changes</span><span><b>%d</b> low · <b>%d</b> medium · <b>%d</b> high risk</span><span>%s</span></div>' % (
        len(s["changes"]), r["Low"], r["Medium"], r["High"],
        " · ".join("%s <b>%d</b>" % (CAT_LABEL[k], cc[k]) for k in CATS if cc[k]))
    body = pagehead("Section %s" % L, s["title"], s.get("intro", ""), meta)
    if s.get("measured"):
        body += '<section class="block"><div class="bh"><h2>Today vs after improvement</h2></div>%s</section>' % measured_table(s)
    body += '<section class="block"><div class="bh"><h2>Changes in this section</h2><p>Select an ID to jump to the full detail.</p></div>%s</section>' % summary_table(s["changes"])
    body += '<section class="block"><div class="bh"><h2>Change details</h2></div>%s<div class="changes">%s</div><div class="card empty" id="empty">No changes match this filter.</div></section>' % (
        filters_bar("changes"), "".join(change_card(c) for c in s["changes"]))
    prev_s = sections[i - 1] if i > 0 else None
    next_s = sections[i + 1] if i + 1 < len(sections) else None
    pager = '<nav class="pager">'
    pager += ('<a class="card prev" href="%s"><span class="k">← Previous</span><span class="t">%s · %s</span></a>' % (slug(prev_s["letter"]), prev_s["letter"], esc(prev_s["title"]))) if prev_s else '<a class="card prev" href="index.html"><span class="k">← Back</span><span class="t">Overview</span></a>'
    pager += ('<a class="card next" href="%s"><span class="k">Next →</span><span class="t">%s · %s</span></a>' % (slug(next_s["letter"]), next_s["letter"], esc(next_s["title"]))) if next_s else '<a class="card next" href="files.html"><span class="k">Next →</span><span class="t">File-wise changes</span></a>'
    pager += "</nav>"
    body += pager
    page(slug(L), "%s · %s" % (L, s["title"]), body, s.get("intro", ""))

# Index
_m = [("Date", DATE), ("Module", " · ".join(x for x in (MODULE_PATH, META.get("code_stats", "")) if x)),
      ("Branch reviewed", META.get("branch", "")), ("Measured on", META.get("measured_on", "")), ("Benchmark", META.get("benchmark_source", ""))]
meta = '<div class="meta">%s</div>' % "".join('<span><b>%s</b> %s</span>' % (esc(k), esc(v)) for k, v in _m if v)
body = pagehead(" · ".join(x for x in (META.get("app", ""), META.get("subject", "")) if x), PLAN_TITLE,
                "A detailed, file-by-file plan to make the %s faster, lighter and more reliable without changing what it does today. " % (META.get("subject") or "screen").lower() + 
                "Every change lists the files and lines, the current code, the proposed code, which teams are involved, its risk to existing functionality, "
                "how existing behaviour is kept, what QA must re-test, and the expected result.", meta)
body += """<section class="block"><div class="tiles">
  <div class="card tile"><div class="k">Changes planned</div><div class="v">%d</div><div class="s">Across %d sections and %d files</div></div>
  <div class="card tile"><div class="k">Risk to existing functionality</div><div class="v">%d <span class="muted" style="font-size:15px;font-weight:500">low</span></div><div class="s">%d medium · %d high</div>%s</div>
  <div class="card tile"><div class="k">Teams involved</div><div class="v">%d <span class="muted" style="font-size:15px;font-weight:500">FE</span></div><div class="s">%d FE shared · %d BE · %d Product</div></div>
  <div class="card tile"><div class="k">No visible change</div><div class="v">%d</div><div class="s">%d are visible to users and need a Product decision or flag</div></div>
</div></section>""" % (
    len(ALL), len(sections), len({norm_path(f.get("path")) for c in ALL for f in c["files"]}),
    R["Low"], R["Medium"], R["High"], split_bar(R), C["FE"], C["FE-Shared"], C["BE"], C["Product"],
    len(ALL) - visible, visible)

rows = "".join("".join(
    "<tr><td class=\"nowrap\"><a href=\"%s\">%s · %s</a></td><td>%s</td><td>%s</td><td><b>%s</b></td></tr>" % (
        slug(s["letter"]), s["letter"], esc(s["title"]), esc(r.get("metric")), esc(r.get("current")), esc(r.get("expected")))
    for r in s.get("measured") or []) for s in sections)
body += '<section class="block"><div class="bh"><h2>Today vs after improvement</h2><p>Today\'s values were measured on the device. The after-improvement values are the targets these changes are designed to reach; re-measure after each release to confirm.</p></div><div class="card table-wrap"><table><thead><tr><th>Section</th><th>Metric</th><th>Today</th><th>After improvement</th></tr></thead><tbody>%s</tbody></table></div></section>' % rows

cards = ""
for s in sections:
    r, cc = counts(s["changes"])
    cards += '<a class="card seccard" href="%s"><div class="top"><span class="letter">%s</span><span class="t">%s</span></div><p class="d">%s</p><div class="stats"><span>%d changes</span><span>%d low · %d med · %d high</span></div>%s</a>' % (
        slug(s["letter"]), s["letter"], esc(s["title"]), esc(s.get("intro", "")), len(s["changes"]), r["Low"], r["Medium"], r["High"], split_bar(r))
body += '<section class="block"><div class="bh"><h2>Sections</h2><p>Each section page has a measured summary, a change table, and a full card per change with current and proposed code.</p></div><div class="secgrid">%s</div></section>' % cards

safe_first = [c for c in ALL if c["risk"] == "Low" and not c.get("user_visible")]
body += '<section class="block"><div class="bh"><h2>Safe first changes</h2><p>Low-risk changes with no visible behaviour change. They can go out first, in small pull requests, without a Product decision.</p></div>%s</section>' % summary_table(safe_first, show_section=True)

legend_c = "".join('<div><span>%s</span><span>%s</span></div>' % (cat_tags([k]), esc(CAT_DESC[k])) for k in CATS)
legend_r = "".join('<div><span>%s</span><span>%s</span></div>' % (risk_html(k), esc(RISK_DESC[k])) for k in RISKS)
legend_e = "".join('<div><span class="effort"><b>%s</b></span><span>%s of work for one FE developer, including tests.</span></div>' % (k, v) for k, v in EFFORT.items())
body += """<section class="block"><div class="bh"><h2>How to read this plan</h2></div>
<div class="card pad" style="display:grid;gap:22px">
  <div><h4 style="margin-bottom:10px">Teams</h4><div class="legend-list">%s</div></div>
  <div><h4 style="margin-bottom:10px">Risk to existing functionality</h4><div class="legend-list">%s</div></div>
  <div><h4 style="margin-bottom:10px">Effort</h4><div class="legend-list">%s</div></div>
</div></section>""" % (legend_c, legend_r, legend_e)

body += """<section class="block"><div class="bh"><h2>Rules for not breaking existing functionality</h2></div>
<div class="card pad"><ul class="part" style="padding-left:20px;display:grid;gap:6px">
<li>One change per pull request, in the order of the risk waves on the <a href="risk.html">Risk and rollout</a> page.</li>
<li>Anything a user could notice ships behind a Remote Config flag whose default keeps today's behaviour. Product turns it on after sign-off.</li>
<li>Shared-package changes (FE · shared) are additive: new methods or parameters with today's defaults. No existing public API is removed or renamed in the same release.</li>
<li>Data, routes, analytics events and DI registrations stay the same unless the change says otherwise.</li>
<li>Every change lists its regression checks. QA runs them plus the screen's smoke test%s.</li>""" % ((" (%s)" % esc(META["smoke_test"])) if META.get("smoke_test") else "") + """
<li>Re-measure on the same device after each wave and compare with the table above.</li>
</ul></div></section>"""
page("index.html", PLAN_TITLE, body, "Detailed file-wise change plan.")

# Files page
files = {}
for c in ALL:
    for f in c["files"]:
        p = norm_path(f.get("path"))
        if not p:
            continue
        files.setdefault(p, []).append((c, f))
by_pkg = {}
for p, lst in files.items():
    by_pkg.setdefault(pkg_of(p), {})[p] = lst


def pkg_sort(k):
    return (0 if k == MODULE_PKG else 1 if not k.startswith("apps/") else 2, k)


body = pagehead("Cross view", "File-wise changes",
                "Every file that the plan touches, grouped by package, with what changes in that file and which change it belongs to. Use this to plan pull requests and code ownership.",
                '<div class="meta"><span><b>%d</b> files</span><span><b>%d</b> packages</span></div>' % (len(files), len(by_pkg)))
body += '<section class="block">' + filters_bar("file changes")
fi = 0
for pk in sorted(by_pkg, key=pkg_sort):
    pfiles = by_pkg[pk]
    pkey = "pkg%d" % fi
    fi += 1
    shared = pk != MODULE_PKG
    rows = ""
    for p in sorted(pfiles):
        lst = sorted(pfiles[p], key=lambda cf: (ORDER.index(cf[0]["_sec"]), int(re.sub(r"\D", "", cf[0]["id"]) or 0)))
        hi = max((cf[0]["risk"] for cf in lst), key=lambda r: RISK_RANK[r])
        fkey = "f%d" % fi
        fi += 1
        rows += '<tr class="grouprow" data-group-rows="%s"><td colspan="5" class="path">%s <span class="muted">· %d change%s · highest risk %s</span></td></tr>' % (
            fkey, esc(p), len(lst), "" if len(lst) == 1 else "s", esc(hi))
        for c, f in lst:
            rows += '<tr data-item data-in="%s %s" data-cat="%s" data-risk="%s"><td class="nowrap idlinks">%s</td><td><b>%s</b><br><span class="muted">%s</span></td><td class="nowrap">%s</td><td>%s</td><td>%s</td></tr>' % (
                pkey, fkey, esc(" ".join(c["categories"])), esc(c["risk"]), link(c["id"]), esc(c.get("title")),
                esc(f.get("change", "")), esc(f.get("lines", "")), risk_html(c["risk"]), cat_tags(c["categories"]))
    body += '<div data-group-rows="%s" style="margin-top:22px"><h3 style="margin-bottom:10px">%s %s</h3><div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change and what happens in this file</th><th>Lines</th><th>Risk</th><th>Teams</th></tr></thead><tbody>%s</tbody></table></div></div>' % (
        pkey, esc(pk), '<span class="tag cat-FE-Shared" style="vertical-align:middle">shared package</span>' if shared else '<span class="tag cat-FE" style="vertical-align:middle">this module</span>', rows)
body += '<div class="card empty" id="empty">No files match this filter.</div></section>'
page("files.html", "File-wise changes", body, "Every file touched by the change plan.")

# Teams page
body = pagehead("Cross view", "Team-wise changes",
                "What each team needs to do: decisions for Product, requests for the backend team, work inside the module, and work in shared packages.",
                '<div class="meta">%s</div>' % "".join('<span><b>%d</b> %s</span>' % (C[k], esc(CAT_LABEL[k])) for k in CATS))
prod = [c for c in ALL if "Product" in c["categories"] or c.get("product_decision")]
be = [c for c in ALL if "BE" in c["categories"] or c.get("be_request")]
fe = [c for c in ALL if "FE" in c["categories"]]
fes = [c for c in ALL if "FE-Shared" in c["categories"]]


def qa_table(lst, field, head):
    rows = "".join('<tr><td class="nowrap">%s</td><td><b>%s</b><br><span class="muted">%s · %s</span></td><td>%s</td><td>%s</td></tr>' % (
        link(c["id"]), esc(c.get("title")), esc(c["_sec"]), esc(c["_sectitle"]), esc(c.get(field) or "—"), risk_html(c["risk"])) for c in lst)
    return '<div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change</th><th>%s</th><th>Risk</th></tr></thead><tbody>%s</tbody></table></div>' % (esc(head), rows)


body += '<section class="block" id="product"><div class="bh"><h2>Product decisions (%d)</h2><p>%s Each question below should be answered before the flag is turned on.</p></div>%s</section>' % (len(prod), esc(CAT_DESC["Product"]), qa_table(prod, "product_decision", "Decision needed"))
body += '<section class="block" id="be"><div class="bh"><h2>Backend requests (%d)</h2><p>%s</p></div>%s</section>' % (len(be), esc(CAT_DESC["BE"]), qa_table(be, "be_request", "Request"))


def fe_table(lst):
    rows = "".join('<tr><td class="nowrap">%s</td><td><b>%s</b><br><span class="muted">%s</span></td><td class="path">%s</td><td>%s</td><td>%s</td></tr>' % (
        link(c["id"]), esc(c.get("title")), esc(c.get("summary")),
        "<br>".join(esc(norm_path(f.get("path"))) for f in c["files"][:6]) + ("<br>…" if len(c["files"]) > 6 else ""),
        risk_html(c["risk"]), effort_html(c.get("effort", "M"))) for c in lst)
    return '<div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change</th><th>Files</th><th>Risk</th><th>Effort</th></tr></thead><tbody>%s</tbody></table></div>' % rows


body += '<section class="block" id="fe"><div class="bh"><h2>FE · this module (%d)</h2><p>%s</p></div>%s</section>' % (len(fe), esc(CAT_DESC["FE"]), fe_table(fe))
body += '<section class="block" id="fe-shared"><div class="bh"><h2>FE · shared packages (%d)</h2><p>%s</p></div>%s</section>' % (len(fes), esc(CAT_DESC["FE-Shared"]), fe_table(fes))
page("teams.html", "Team-wise changes", body, "Product, backend and FE work in the change plan.")

# Risk page
body = pagehead("Cross view", "Risk and rollout",
                "How the changes are sequenced so that existing functionality keeps working: risk by effort, the high-risk list, the flags, release waves and the regression checklist.", "")
cells = ""
for r in RISKS:
    cells += '<div class="h" style="align-self:center">%s</div>' % risk_html(r)
    for e in ("S", "M", "L"):
        lst = [c for c in ALL if c["risk"] == r and c.get("effort", "M") == e]
        cells += '<div class="cell"><span class="num">%d</span>%s</div>' % (len(lst), " ".join(link(c["id"]) for c in lst))
body += '<section class="block"><div class="bh"><h2>Risk by effort</h2><p>Start top-left (low risk, small effort) and move down and right.</p></div><div class="card pad"><div class="matrix"><div></div><div class="h">S · ≤ 1 day</div><div class="h">M · 2–4 days</div><div class="h">L · 1 week +</div>%s</div></div></section>' % cells

high = [c for c in ALL if c["risk"] == "High"]
rows = "".join('<tr><td class="nowrap">%s</td><td><b>%s</b><br>%s</td><td>%s</td><td><ul style="padding-left:18px">%s</ul></td></tr>' % (
    link(c["id"]), esc(c.get("title")), cat_tags(c["categories"]), esc(c.get("risk_reason")),
    "".join("<li>%s</li>" % esc(s) for s in c["safety"])) for c in high)
body += '<section class="block"><div class="bh"><h2>High-risk changes (%d)</h2><p>Each of these ships behind a flag, gets a full regression pass, and is released on its own.</p></div><div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change</th><th>Why it is high risk</th><th>How it is kept safe</th></tr></thead><tbody>%s</tbody></table></div></section>' % (len(high), rows)

flagged = []
for c in ALL:
    lines = [s for s in c["safety"] if re.search(r"flag|remote config", s, re.I)]
    if lines:
        flagged.append((c, lines[0]))
rows = "".join('<tr><td class="nowrap">%s</td><td><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (link(c["id"]), esc(c.get("title")), esc(l), risk_html(c["risk"])) for c, l in flagged)
body += '<section class="block"><div class="bh"><h2>Feature flags (%d)</h2><p>Changes that ship behind a Remote Config flag. The default value keeps today\'s behaviour.</p></div><div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change</th><th>Flag</th><th>Risk</th></tr></thead><tbody>%s</tbody></table></div></section>' % (len(flagged), rows)

waves = [
    ("Wave 1 · Low risk", "Internal fixes with no visible change. Normal review plus the screen's smoke test.", [c for c in ALL if c["risk"] == "Low"]),
    ("Wave 2 · Medium risk", "Loading-order, state-flow and visible-detail changes inside the module. Regression pass on each affected tab; visible ones behind flags.", [c for c in ALL if c["risk"] == "Medium"]),
    ("Wave 3 · High risk", "Shared packages, subscription model, navigation and cubit restructuring. One per release, behind flags, full regression pass.", [c for c in ALL if c["risk"] == "High"]),
]
wv = "".join('<div class="card pad" style="margin-top:12px"><h3>%s <span class="muted" style="font-weight:500;font-size:14px">· %d changes</span></h3><p class="muted" style="margin:6px 0 10px">%s</p><div class="idlinks">%s</div></div>' % (
    esc(t), len(l), esc(d), " ".join(link(c["id"]) for c in l)) for t, d, l in waves)
body += '<section class="block"><div class="bh"><h2>Release waves</h2><p>Within a wave, follow the "Depends on" links on each change.</p></div>%s</section>' % wv

reg = ""
for s in sections:
    seen, items = set(), []
    for c in s["changes"]:
        for r in c["regression_checks"]:
            k = r.strip().lower()
            if k not in seen:
                seen.add(k)
                items.append((r, c["id"]))
    if items:
        reg += '<div class="card pad" style="margin-top:12px"><h3>%s · %s</h3><ul style="padding-left:20px;margin-top:8px;display:grid;gap:4px;font-size:14px">%s</ul></div>' % (
            s["letter"], esc(s["title"]), "".join('<li>%s <span class="idlinks">%s</span></li>' % (esc(r), link(i)) for r, i in items))
body += '<section class="block"><div class="bh"><h2>Regression checklist</h2><p>All regression checks from the change cards, grouped by section and de-duplicated. QA can use this as the test plan for each wave.</p></div>%s</section>' % reg
page("risk.html", "Risk and rollout", body, "Risk matrix, flags, release waves and regression checklist.")

# Full report
body = pagehead("All sections", "Full report",
                "Every section and change on one page, for printing or saving as PDF. For day-to-day use, the section pages are easier to navigate.", "")
for s in sections:
    body += '<section class="block" id="sec-%s"><div class="bh"><h2>%s · %s</h2><p>%s</p></div>%s<div class="changes" style="margin-top:14px">%s</div></section>' % (
        s["letter"], s["letter"], esc(s["title"]), esc(s.get("intro", "")), measured_table(s),
        "".join(change_card(c).replace(' id="%s"' % c["id"], ' id="full-%s"' % c["id"], 1) for c in s["changes"]))
page("full-report.html", "Full report", body, "All changes in the change plan on one page.")

exec(open(os.path.join(HERE, "plan_pages.py"), encoding="utf-8").read())
exec(open(os.path.join(HERE, "roadmap_page.py"), encoding="utf-8").read())
print("built %d sections, %d changes, %d files -> %s" % (len(sections), len(ALL), len(files), OUT))
