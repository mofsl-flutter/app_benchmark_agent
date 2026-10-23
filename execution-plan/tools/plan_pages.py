# Executed inside build_plan.py (shares its namespace: page, pagehead, link, esc, hl, BY_ID, ALL,
# R, C, RISKS, CATS, risk_html, cat_tags, effort_html, split_bar, norm_path, MODULE_PATH, DATE, SRC).
# Renders summary.html, optimized-plan.html and most-preferred-plan.html from JSON. Each page is
# skipped when its JSON file is missing.


def _load(name):
    p = os.path.join(SRC, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _ids(lst):
    return " ".join(link(i) for i in (lst or []) if i)


def _ul(items, style="padding-left:20px;display:grid;gap:6px;font-size:14px"):
    return '<ul style="%s">%s</ul>' % (style, "".join("<li>%s</li>" % esc(x) for x in items or []))


def _known(ids):
    return [BY_ID[i] for i in ids or [] if i in BY_ID]


MOD_PREFIX = (MODULE_PATH + "/") if MODULE_PATH else ""


# ---------------- summary.html ----------------
SUM = _load("summary.json")
if SUM:
    pkg = SUM.get("package") or {}
    pk_ids = []
    for grp in pkg.get("plan", []):
        for row in grp.get("rows", []):
            for i in row.get("ids", []):
                if i not in pk_ids:
                    pk_ids.append(i)
    pk = _known(pk_ids)
    pk_r = {k: sum(1 for c in pk if c["risk"] == k) for k in RISKS}

    body = pagehead("Summary", SUM.get("title", "Summary"),
                    SUM.get("intro", "The whole change plan on one page: the main problems, what the full plan delivers, and the major changes that can be completed in 2–4 days without changing existing behaviour."),
                    '<div class="meta"><span><b>Date</b> %s</span><span><b>Module</b> %s</span><span><b>Detail</b> every ID links to its full change card</span></div>' % (esc(DATE), esc(MODULE_PATH)))
    body += """<section class="block"><div class="tiles">
  <div class="card tile"><div class="k">Changes in the full plan</div><div class="v">%d</div><div class="s">%d low · %d medium · %d high risk</div>%s</div>
  <div class="card tile"><div class="k">Teams</div><div class="v">%d <span class="muted" style="font-size:15px;font-weight:500">FE</span></div><div class="s">%d FE shared · %d BE · %d Product</div></div>
  <div class="card tile"><div class="k">%s</div><div class="v">%d</div><div class="s">%d low · %d medium · %d high risk</div></div>
  <div class="card tile"><div class="k">Package files</div><div class="v">%d</div><div class="s">files touched by the package</div></div>
</div></section>""" % (len(ALL), R["Low"], R["Medium"], R["High"], split_bar(R), C["FE"], C["FE-Shared"], C["BE"], C["Product"],
                       esc(pkg.get("tile", "2–4 day package")), len(pk), pk_r["Low"], pk_r["Medium"], pk_r["High"],
                       len({norm_path(f.get("path")) for c in pk for f in c["files"]}))

    rows = "".join('<tr><td><b>%s</b><br><span class="muted">%s</span></td><td>%s</td><td class="idlinks">%s</td></tr>' % (
        esc(p.get("title")), esc(p.get("cause")), esc(p.get("effect")), _ids(p.get("ids"))) for p in SUM.get("problems", []))
    body += '<section class="block"><div class="bh"><h2>1. Main problems found</h2><p>The problems behind most of the slowness, heaviness and instability, in order of impact.</p></div><div class="card table-wrap"><table><thead><tr><th>Problem and cause</th><th>Effect today</th><th>Fixed by</th></tr></thead><tbody>%s</tbody></table></div></section>' % rows

    rows = "".join('<tr><td>%s</td><td>%s</td><td><b>%s</b></td></tr>' % (esc(o.get("area")), esc(o.get("today")), esc(o.get("after"))) for o in SUM.get("outcome", []))
    body += '<section class="block"><div class="bh"><h2>2. What the full plan delivers</h2><p>Measured today, and the target after all %d changes. Re-measure on the same device to confirm.</p></div><div class="card table-wrap"><table><thead><tr><th>Area</th><th>Today</th><th>After full plan</th></tr></thead><tbody>%s</tbody></table></div></section>' % (len(ALL), rows)

    if pkg:
        plan_html = ""
        for grp in pkg.get("plan", []):
            trs = ""
            for row in grp.get("rows", []):
                items = "".join('<div style="margin:2px 0">%s %s <span class="muted">· %s · %s</span></div>' % (
                    link(c["id"]), esc(c["title"]), esc(c["risk"]), esc(c.get("effort", ""))) for c in _known(row.get("ids")))
                trs += '<tr><td class="nowrap"><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (esc(row.get("when")), items, esc(row.get("what")))
            plan_html += '<h3 style="margin:22px 0 10px">%s</h3><div class="card table-wrap"><table><thead><tr><th>When</th><th>Changes</th><th>What gets done</th></tr></thead><tbody>%s</tbody></table></div>' % (esc(grp.get("owner")), trs)
        eff = "".join('<tr><td class="nowrap">%s</td><td>%s</td><td><b>%s</b></td></tr>' % (esc(e.get("area")), esc(e.get("today")), esc(e.get("after"))) for e in pkg.get("effect", []))
        effect = ('<h3 style="margin:26px 0 10px">Expected effect of the package</h3><div class="card table-wrap"><table><thead><tr><th>Area</th><th>Today</th><th>After the package (estimate)</th></tr></thead><tbody>%s</tbody></table></div>' % eff) if eff else ""
        needs = ""
        if pkg.get("needs_product") or pkg.get("needs_be"):
            needs = '<h3 style="margin:26px 0 10px">What the package needs from other teams</h3><div class="callouts two">%s%s</div>' % (
                ('<div class="callout prod"><h4>Product</h4><p>%s</p></div>' % esc(pkg["needs_product"])) if pkg.get("needs_product") else "",
                ('<div class="callout be"><h4>BE / Platform</h4><p>%s</p></div>' % esc(pkg["needs_be"])) if pkg.get("needs_be") else "")
        later = _known(pkg.get("later"))
        later_html = ""
        if later:
            later_html = '<h3 style="margin:26px 0 10px">Bigger changes for the following sprints</h3><div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change</th><th>Risk</th><th>Effort</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(
                '<tr><td class="nowrap">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (link(c["id"]), esc(c["title"]), risk_html(c["risk"]), effort_html(c.get("effort", "M"))) for c in later)
        body += '<section class="block"><div class="bh"><h2>3. %s</h2><p>%s</p></div>%s%s%s%s</section>' % (
            esc(pkg.get("title", "Major changes possible in 2–4 days")),
            esc(pkg.get("intro", "A package of %d changes. Every item is small or the short end of medium, low or medium risk, and needs no bigger change first." % len(pk))),
            plan_html, effect, needs, later_html)
    page("summary.html", SUM.get("title", "Summary"), body, "One-page summary of the change plan.")


# ---------------- optimized-plan.html ----------------
OPT = _load("optimized.json")
if OPT:
    def _rel(p):
        p = norm_path(p)
        return p[len(MOD_PREFIX):] if MOD_PREFIX and p.startswith(MOD_PREFIX) else p

    def item_files(it):
        if it.get("files"):
            return [(f.get("path"), f.get("lines", "")) for f in it["files"]]
        out, seen = [], set()
        for c in _known(it.get("ids")):
            for f in c["files"]:
                p = norm_path(f.get("path"))
                if MOD_PREFIX and not p.startswith(MOD_PREFIX):
                    continue
                if p.endswith("pubspec.yaml"):
                    continue
                r = _rel(p)
                if r not in seen:
                    seen.add(r)
                    out.append((r, f.get("lines", "")))
        return out

    def item_code(it):
        known = _known(it.get("ids"))
        last = known[-1] if known else {}
        b, bloc = it.get("before"), ""
        if not b:
            bc = last.get("before_code") or {}
            b = bc.get("code")
            bloc = _rel(bc.get("path", "")) + ((":" + bc["lines"]) if bc.get("lines") else "")
        a = it.get("after") or (last.get("after_code") or {}).get("code")
        boxes = ""
        if b:
            boxes += '<div class="codebox before"><div class="cap"><b>Current code</b><span class="loc">%s</span></div><pre><code>%s</code></pre></div>' % (esc(bloc), hl(b.rstrip()))
        if a:
            boxes += '<div class="codebox after"><div class="cap"><b>Change</b><span class="loc">sketch</span></div><pre><code>%s</code></pre></div>' % hl(a.rstrip())
        return '<div class="codepair">%s</div>' % boxes if boxes else ""

    items = OPT.get("items", [])
    all_files = sorted({f for it in items for f, _ in item_files(it)})
    title = OPT.get("title", "Optimized FE Plan")
    body = pagehead("FE only · %s" % (MODULE_PATH or "module"), title, OPT.get("intro", ""),
                    '<div class="meta"><span><b>%d</b> changes</span><span><b>%d</b> files</span>%s</div>' % (
                        len(items), len(all_files), ('<span>%s</span>' % esc(OPT["meta_note"])) if OPT.get("meta_note") else ""))
    rows = "".join('<tr><td class="nowrap"><a href="#m%d"><b>%d</b></a></td><td><b>%s</b><br><span class="muted">%s</span></td><td>%s</td><td>%s</td><td class="idlinks">%s</td></tr>' % (
        it["n"], it["n"], esc(it.get("title")), esc(it.get("area")), esc(it.get("effect")), risk_html(it.get("risk", "Medium")), _ids(it.get("ids"))) for it in items)
    body += '<section class="block"><div class="bh"><h2>The %d changes</h2><p>Ordered by impact. The detail IDs link to the full change cards.</p></div><div class="card table-wrap"><table><thead><tr><th>#</th><th>Change</th><th>Expected effect</th><th>Risk</th><th>Detail</th></tr></thead><tbody>%s</tbody></table></div></section>' % (len(items), rows)

    if OPT.get("achieve"):
        rows = "".join("<tr><td>%s</td><td>%s</td><td><b>%s</b></td><td class=\"nowrap\">%s</td></tr>" % (
            esc(r.get("metric")), esc(r.get("today")), esc(r.get("after")), esc(r.get("items"))) for r in OPT["achieve"])
        body += '<section class="block" id="achieve"><div class="bh"><h2>What this plan achieves</h2><p>Estimates from the code; confirm by re-measuring on the same device after each pull request.</p></div><div class="card table-wrap"><table><thead><tr><th>Metric</th><th>Today</th><th>After the optimized plan</th><th>Items</th></tr></thead><tbody>%s</tbody></table></div>' % rows
        if OPT.get("notice"):
            body += '<h3 style="margin:22px 0 10px">What users will notice</h3><div class="card pad">%s</div>' % _ul(OPT["notice"])
        if OPT.get("one_line"):
            body += '<div class="callout after" style="margin-top:12px"><h4>In one line</h4><p>%s</p></div>' % esc(OPT["one_line"])
        body += "</section>"

    if OPT.get("schedule"):
        sh = ""
        for grp in OPT["schedule"]:
            trs = "".join('<tr><td class="nowrap"><b>%s</b></td><td class="nowrap">%s</td><td>%s</td></tr>' % (
                esc(r.get("when")), " ".join('<a href="#m%s">%s</a>' % (x.strip(), x.strip()) if x.strip().isdigit() else esc(x) for x in str(r.get("items", "")).split(",")),
                esc(r.get("work"))) for r in grp.get("rows", []))
            sh += '<h3 style="margin:18px 0 10px">%s</h3><div class="card table-wrap"><table><thead><tr><th>When</th><th>Items</th><th>Work</th></tr></thead><tbody>%s</tbody></table></div>' % (esc(grp.get("who")), trs)
        body += '<section class="block"><div class="bh"><h2>Plan</h2><p>%s</p></div>%s</section>' % (esc(OPT.get("schedule_intro", "")), sh)

    cards = ""
    for it in items:
        known = _known(it.get("ids"))
        first = known[0] if known else {}
        frows = "".join('<tr><td class="path">%s</td><td class="nowrap">%s</td></tr>' % (esc(f), esc(l)) for f, l in item_files(it))
        cards += """<article class="card change" id="m%(n)d">
  <header>
    <div class="idrow"><span class="cid">#%(n)d</span><h3>%(title)s</h3></div>
    <div class="facts"><span>%(area)s</span><span>Risk %(risk)s</span><span class="idlinks">Detail %(ids)s</span></div>
  </header>
  <div class="bodygrid">
    <div class="twocol">
      <div class="part"><h4>Problem today</h4><p>%(why)s</p></div>
      <div class="part"><h4>Change</h4><p>%(change)s</p></div>
    </div>
    <div class="part"><h4>Files</h4><div class="card table-wrap"><table><thead><tr><th>File</th><th>Lines</th></tr></thead><tbody>%(frows)s</tbody></table></div></div>
    %(code)s
    <div class="twocol">
      <div class="part"><h4>Why it is safe</h4><p>%(risk_why)s</p></div>
      <div class="part"><h4>Test after the change</h4><ul>%(tests)s</ul></div>
    </div>
    <div class="callout after"><h4>Expected effect</h4><p>%(effect)s</p></div>
  </div>
</article>""" % {"n": it["n"], "title": esc(it.get("title")), "area": esc(it.get("area")), "risk": risk_html(it.get("risk", "Medium")),
                 "ids": _ids(it.get("ids")), "why": esc(it.get("why") or first.get("current", "")), "change": esc(it.get("change") or first.get("summary", "")),
                 "frows": frows, "code": item_code(it), "risk_why": esc(it.get("risk_why") or first.get("risk_reason", "")),
                 "tests": "".join("<li>%s</li>" % esc(t) for t in (it.get("test") or first.get("regression_checks", []))), "effect": esc(it.get("effect"))}
    body += '<section class="block"><div class="bh"><h2>Change details</h2></div><div class="changes">%s</div></section>' % cards
    body += '<section class="block"><div class="bh"><h2>All files touched (%d)</h2></div><div class="card pad">%s</div></section>' % (
        len(all_files), _ul(all_files, "padding-left:20px;display:grid;gap:3px;font-family:JetBrains Mono,ui-monospace,monospace;font-size:12.5px;grid-template-columns:minmax(0,1fr);overflow-wrap:anywhere"))
    if OPT.get("not_fixed"):
        rows = "".join('<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td class="idlinks">%s</td></tr>' % (
            esc(r.get("what")), esc(r.get("where")), esc(r.get("why")), _ids(r.get("ids"))) for r in OPT["not_fixed"])
        body += '<section class="block" id="not-fixed"><div class="bh"><h2>What this plan does not fix</h2><p>These gaps stay after the optimized plan. Each needs a bigger change, a shared-package change, backend work or a Product decision.</p></div><div class="card table-wrap"><table><thead><tr><th>Not fixed</th><th>Where it stands after this plan</th><th>Why it needs more</th><th>Main-plan changes</th></tr></thead><tbody>%s</tbody></table></div></section>' % rows
    page("optimized-plan.html", title, body, "Optimized FE-only change plan.")


# ---------------- most-preferred-plan.html ----------------
PREF = _load("preferred.json")
if PREF:
    CONTRIB_W = {"Largest": "100%", "Large": "66%", "Medium": "36%", "Small": "18%"}

    def contrib(level):
        level = level if level in CONTRIB_W else "Medium"
        return ('<span style="display:inline-flex;align-items:center;gap:8px;white-space:nowrap">'
                '<span style="display:inline-block;width:56px;height:6px;border-radius:3px;background:var(--surface-3);overflow:hidden">'
                '<span style="display:block;height:100%%;width:%s;background:var(--accent)"></span></span><b style="font-size:12.5px">%s</b></span>') % (CONTRIB_W[level], esc(level))

    def fe_tags(c):
        return cat_tags([k for k in c["categories"] if k in ("FE", "FE-Shared")] or ["FE"])

    factors = PREF.get("factors", [])
    plan_ids = []
    for f in factors:
        for i in f.get("ids", []):
            if i not in plan_ids:
                plan_ids.append(i)
    for ph in PREF.get("phases", []):
        for i in ph.get("ids", []):
            if i not in plan_ids:
                plan_ids.append(i)
    plan = _known(plan_ids)
    pr = {k: sum(1 for c in plan if c["risk"] == k) for k in RISKS}
    nfiles = len({norm_path(x.get("path")) for c in plan for x in c["files"]})
    title = PREF.get("title", "Most Preferred Plan")

    body = pagehead("Recommended", title, PREF.get("intro",
                    "For each factor that makes the screen feel slow, this plan names the causes that contribute the most and picks only the changes that remove them. Smaller wins from the full plan are left for later."),
                    '<div class="meta"><span><b>%d</b> changes</span><span><b>%d</b> low · <b>%d</b> medium · <b>%d</b> high risk</span><span><b>%d</b> files</span></div>' % (
                        len(plan), pr["Low"], pr["Medium"], pr["High"], nfiles))
    if PREF.get("problem_intro") or PREF.get("problem_points"):
        body += '<section class="block" id="problem"><div class="bh"><h2>Problem statement</h2></div><div class="card pad" style="display:grid;gap:10px;font-size:14.5px"><p>%s</p>%s<p>%s</p></div></section>' % (
            esc(PREF.get("problem_intro", "")), _ul(PREF.get("problem_points"), "padding-left:20px;display:grid;gap:4px"), esc(PREF.get("problem_outro", "")))

    rows = "".join('<tr><td><a href="#f-%s"><b>%s</b></a></td><td>%s</td><td><b>%s</b></td><td class="idlinks">%s</td></tr>' % (
        esc(f.get("key")), esc(f.get("title")), esc(f.get("today")), esc(f.get("after")), _ids(f.get("ids"))) for f in factors)
    body += '<section class="block"><div class="bh"><h2>What this plan covers</h2><p>Every factor gets its biggest causes fixed. Today\'s values come from the benchmark; the after values are estimates from the code, to confirm by re-measuring.</p></div><div class="card table-wrap"><table><thead><tr><th>Factor</th><th>Today</th><th>After this plan</th><th>Changes</th></tr></thead><tbody>%s</tbody></table></div>' % rows
    shared_n = sum(1 for c in plan if "FE-Shared" in c["categories"])
    body += """<div class="tiles" style="margin-top:14px">
  <div class="card tile"><div class="k">Changes</div><div class="v">%d</div><div class="s">of %d in the full plan; only the biggest contributors</div></div>
  <div class="card tile"><div class="k">Risk</div><div class="v">%d <span class="muted" style="font-size:15px;font-weight:500">low</span></div><div class="s">%d medium · %d high (high-risk ones behind a switch)</div></div>
  <div class="card tile"><div class="k">Scope</div><div class="v">FE <span class="muted" style="font-size:15px;font-weight:500">only</span></div><div class="s">%d in the module · %d also touch shared code</div></div>
  <div class="card tile"><div class="k">Phases</div><div class="v">%d</div><div class="s">each released and measured on its own</div></div>
</div></section>""" % (len(plan), len(ALL), pr["Low"], pr["Medium"], pr["High"], len(plan) - shared_n, shared_n, len(PREF.get("phases", [])))

    for n, f in enumerate(factors, 1):
        crow = "".join('<tr><td class="nowrap">%s</td><td>%s</td><td class="idlinks nowrap">%s</td></tr>' % (
            contrib(c.get("level")), esc(c.get("text")), _ids(c.get("ids"))) for c in f.get("causes", []))
        chg = "".join('<tr><td class="nowrap">%s</td><td><b>%s</b><br><span class="muted">%s</span></td><td>%s</td><td>%s</td></tr>' % (
            link(c["id"]), esc(c["title"]), esc(c.get("after_improvement", "")), fe_tags(c), risk_html(c["risk"])) for c in _known(f.get("ids")))
        prob = ('<div class="callout prod" style="margin-bottom:12px"><h4>Problem statement</h4><p>%s</p></div>' % esc(f["problem"])) if f.get("problem") else ""
        body += """<section class="block" id="f-%(key)s"><div class="bh"><h2>%(n)d. %(title)s</h2></div>
%(prob)s
<div class="card table-wrap"><table><thead><tr><th>Today</th><th>After this plan</th></tr></thead><tbody><tr><td>%(today)s</td><td><b>%(after)s</b></td></tr></tbody></table></div>
<h3 style="margin:18px 0 10px">What contributes most</h3>
<div class="card table-wrap"><table><thead><tr><th>Contribution</th><th>Cause</th><th>Fixed by</th></tr></thead><tbody>%(crow)s</tbody></table></div>
<h3 style="margin:18px 0 10px">Changes in this plan</h3>
<div class="card table-wrap"><table><thead><tr><th>ID</th><th>Change and effect</th><th>Teams</th><th>Risk</th></tr></thead><tbody>%(chg)s</tbody></table></div>
<div class="twocol" style="margin-top:14px">
  <div class="callout after"><h4>What it covers</h4>%(cov)s</div>
  <div class="callout"><h4>Left for later</h4>%(nott)s</div>
</div></section>""" % {"key": esc(f.get("key")), "n": n, "title": esc(f.get("title")), "prob": prob, "today": esc(f.get("today")), "after": esc(f.get("after")),
                       "crow": crow, "chg": chg, "cov": _ul(f.get("covers"), "padding-left:18px;display:grid;gap:4px"),
                       "nott": _ul(f.get("not") or ["Nothing major"], "padding-left:18px;display:grid;gap:4px")}

    ph = ""
    for p in PREF.get("phases", []):
        lst = _known(p.get("ids"))
        r = {k: sum(1 for c in lst if c["risk"] == k) for k in RISKS}
        ph += '<div class="card pad" style="margin-top:12px"><h3>%s <span class="muted" style="font-weight:500;font-size:14px">· %d changes · %d low / %d medium / %d high</span></h3><p class="muted" style="margin:6px 0 10px">%s</p><div class="idlinks">%s</div></div>' % (
            esc(p.get("title")), len(lst), r["Low"], r["Medium"], r["High"], esc(p.get("desc")), " ".join(link(c["id"]) for c in lst))
    if ph:
        found = PREF.get("foundation")
        body += '<section class="block" id="phases"><div class="bh"><h2>Order of work</h2><p>Each phase can be released on its own and measured before the next starts.%s</p></div>%s</section>' % (
            (" %s comes first because the flagged changes use it." % link(found)) if found else "", ph)
    page("most-preferred-plan.html", title, body, "Most preferred plan: the biggest contributors per factor and the changes that remove them.")
