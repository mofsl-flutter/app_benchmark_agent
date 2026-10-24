# Executed inside build_plan.py after plan_pages.py (shares its namespace: page, pagehead, link, esc,
# risk_html, BY_ID, DATE, MODULE_PATH, SRC, _load, _ids, _ul). Renders roadmap.html, the management
# page, from roadmap.json + rank.json (written by rank_impact.py plan). Skipped when either is missing.
# This is the only page that shows ranks and other apps: the engineering pages compare today with after.

import datetime as _dt

ROAD = _load("roadmap.json")
RANK = _load("rank.json")
IMPACT = _load("impact.json")
if ROAD and RANK:
    T = RANK.get("target", "RISE")
    goal = RANK.get("goal") or {}
    today = RANK.get("today") or {}
    rec_key = RANK.get("recommended")
    rec = RANK.get(rec_key) if rec_key else None
    lev_title = {lv["id"]: lv.get("title", lv["id"]) for lv in (IMPACT or {}).get("levers", [])}
    pct = lambda f: "–" if f is None else "%d %%" % round(100 * f)  # noqa: E731

    def num(v):
        return "–" if v is None else ("%.1f" % v if isinstance(v, float) else str(v))

    def sr(score, rank):
        return "%s (#%s)" % (num(score), rank if rank is not None else "–")

    def goal_words():
        parts = []
        if goal.get("technical_rank"):
            parts.append("technical top %d" % goal["technical_rank"])
        if goal.get("user_rank"):
            parts.append("user feel top %d" % goal["user_rank"] if goal["user_rank"] > 1 else "user feel #1")
        return " and ".join(parts) or "the goal"

    partial = RANK.get("partial", 0.75)
    if not RANK.get("reachable"):
        ev = RANK.get("everything") or {}
        verdict = ("%s is technical %s and user feel %s today. Even with every lever in this plan it reaches only technical "
                   "%s and user feel %s, short of %s. More levers, or a closer look at the targets, are needed." % (
                       T, sr(today.get("technical"), today.get("technical_rank")), sr(today.get("user"), today.get("user_rank")),
                       sr(ev.get("technical"), ev.get("technical_rank")), sr(ev.get("user"), ev.get("user_rank")), goal_words()))
    else:
        verdict = ("%s is technical %s and user feel %s today. The recommended set of %d levers (about %d engineer-days) reaches "
                   "technical %s and user feel %s, which meets %s. %s" % (
                       T, sr(today.get("technical"), today.get("technical_rank")), sr(today.get("user"), today.get("user_rank")),
                       len(rec["levers"]), rec["days"], sr(rec.get("technical"), rec.get("technical_rank")),
                       sr(rec.get("user"), rec.get("user_rank")), goal_words(),
                       ("It still meets the goal if every lever delivers only %s of its improvement." % pct(partial)) if rec_key == "robust"
                       else ("It meets the goal only if every lever lands in full; no set in this plan survives %s delivery." % pct(partial))))

    body = pagehead("Management roadmap", ROAD.get("title", "Roadmap"), verdict,
                    '<div class="meta"><span><b>Date</b> %s</span><span><b>Goal</b> %s</span><span><b>Team</b> %s</span></div>' % (
                        esc(DATE), esc(ROAD.get("goal_text") or goal_words()), esc(ROAD.get("team", "to confirm"))))

    def m(v):
        return "–" if v is None else ("%+.1f pts" % v)

    body += """<section class="block"><div class="tiles">
  <div class="card tile"><div class="k">Today</div><div class="v">#%s · #%s</div><div class="s">technical · user feel</div></div>
  <div class="card tile"><div class="k">After the recommended set</div><div class="v">#%s · #%s</div><div class="s">technical · user feel</div></div>
  <div class="card tile"><div class="k">Margin at the goal line</div><div class="v" style="font-size:22px">%s · %s</div><div class="s">points ahead of the first app outside it</div></div>
  <div class="card tile"><div class="k">Work</div><div class="v">%s</div><div class="s">engineer-days, estimated from change sizes</div></div>
</div></section>""" % (today.get("technical_rank"), today.get("user_rank"),
                       (rec or {}).get("technical_rank", "–"), (rec or {}).get("user_rank", "–"),
                       m((rec or {}).get("margin_technical")), m((rec or {}).get("margin_user")), (rec or {}).get("days", "–"))

    # 1. scope
    sc = '<div class="twocol"><div class="card pad"><h3>In scope</h3>%s</div><div class="card pad"><h3>Out of scope</h3>%s</div></div>' % (
        _ul(ROAD.get("scope_in")), _ul(ROAD.get("scope_out")))
    body += '<section class="block"><div class="bh"><h2>1. Scope</h2><p>%s</p></div>%s</section>' % (
        esc(ROAD.get("scope_intro", "What this plan covers and what counts as done: a re-run of the same benchmark on the same phone.")), sc)

    # 2. impact by phase
    rows = ""
    for ph in RANK.get("phases", []):
        rows += '<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s · %s</td><td>%s</td></tr>' % (
            esc(ph["title"]), esc(", ".join(lev_title.get(i, i) for i in ph["levers"])),
            esc(sr(ph.get("technical"), ph.get("technical_rank"))), esc(sr(ph.get("user"), ph.get("user_rank"))),
            esc(m(ph.get("margin_technical"))), esc(m(ph.get("margin_user"))), "Yes" if ph.get("meets") else "Not yet")
    body += ('<section class="block"><div class="bh"><h2>2. Impact after each phase</h2><p>Scores if every lever up to that phase lands at its '
             'target, using the dashboard\'s own scoring. Levers are cumulative. Ranks are confirmed only by the re-test at each gate.</p></div>'
             '<div class="card table-wrap"><table><thead><tr><th>After</th><th>Levers done</th><th>Technical</th><th>User feel</th>'
             '<th>Margin (tech · user)</th><th>Goal met</th></tr></thead><tbody>'
             '<tr><td><b>Today</b></td><td>—</td><td>%s</td><td>%s</td><td>—</td><td>—</td></tr>%s</tbody></table></div></section>') % (
        esc(sr(today.get("technical"), today.get("technical_rank"))), esc(sr(today.get("user"), today.get("user_rank"))), rows)

    # 3. levers: impact and complexity
    rows = ""
    for lv in sorted(RANK.get("levers", []), key=lambda x: (not x["in_recommended"], not x.get("needed"), -(x["gain_technical"] + x["gain_user"]))):
        if lv["in_recommended"]:
            role = "Needed" if lv.get("needed") else "Margin"
            w = lv.get("without") or {}
            drop = "Technical #%s, user #%s" % (w.get("technical_rank"), w.get("user_rank"))
        else:
            role = "Extra"
            p = lv.get("plus") or {}
            drop = "Adding it: technical #%s, user #%s" % (p.get("technical_rank"), p.get("user_rank"))
        rows += ('<tr><td><b>%s</b><br><span class="muted">%s</span></td><td class="idlinks">%s</td><td>%+.1f · %+.1f</td><td>%s</td>'
                 '<td>%s</td><td class="nowrap">%s</td><td>%s</td><td>%s</td><td class="nowrap"><b>%s</b></td></tr>') % (
            esc(lv["title"]), esc(" ".join([next((x.get("basis", "") for x in (IMPACT or {}).get("levers", []) if x["id"] == lv["id"]), "")] + lv.get("notes", []))),
            _ids(lv["changes"]), lv["gain_technical"], lv["gain_user"], esc(drop), esc(pct(lv.get("break_even")) if lv["in_recommended"] else "—"),
            "%d day%s" % (lv["days"], "" if lv["days"] == 1 else "s"), risk_html(lv["risk"]), esc(lv["chance"]), role)
    body += ('<section class="block"><div class="bh"><h2>3. Levers: impact and complexity</h2><p><b>Needed</b>: dropping it from the '
             'recommended set misses the goal. <b>Margin</b>: in the set for safety. <b>Extra</b>: not in the set. <b>Break-even</b>: the '
             'smallest share of its improvement that still meets the goal with the others in full. Gain alone = points on each scorecard '
             'if only that lever lands.</p></div><div class="card table-wrap"><table><thead><tr><th>Lever and basis</th><th>Changes</th>'
             '<th>Gain alone (tech · user)</th><th>If dropped</th><th>Break-even</th><th>Effort</th><th>Risk</th><th>Chance</th>'
             '<th>Role</th></tr></thead><tbody>%s</tbody></table></div></section>') % rows

    # 4. options
    rows = ""
    for key, label in (("minimum", "Fewest levers"), ("robust", "Recommended: survives partial delivery"), ("everything", "Every lever")):
        s = RANK.get(key)
        if not s:
            rows += '<tr><td><b>%s</b></td><td colspan="5" class="muted">No set in this plan qualifies.</td></tr>' % esc(label)
            continue
        ap = s.get("at_partial")
        rows += '<tr><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>' % (
            esc(label), esc(", ".join(lev_title.get(i, i) for i in s["levers"])), esc(sr(s.get("technical"), s.get("technical_rank"))),
            esc(sr(s.get("user"), s.get("user_rank"))),
            esc("#%s · #%s" % (ap["technical_rank"], ap["user_rank"])) if ap else "—", s["days"])
    body += ('<section class="block"><div class="bh"><h2>4. Options compared</h2><p>%d lever sets scored (%s search). "At %s" is the result '
             'when every lever in the set delivers only that share of its improvement.</p></div><div class="card table-wrap"><table><thead>'
             '<tr><th>Option</th><th>Levers</th><th>Technical</th><th>User feel</th><th>At %s (tech · user)</th><th>Engineer-days</th></tr>'
             '</thead><tbody>%s</tbody></table></div></section>') % (RANK.get("sets_scored", 0), esc(RANK.get("method", "")), pct(partial), pct(partial), rows)

    # 5. timeline
    phs = [p for p in ROAD.get("phases", []) if p.get("start") and p.get("end")]
    if phs:
        d0 = min(_dt.date.fromisoformat(p["start"]) for p in phs)
        ends = [_dt.date.fromisoformat(p["end"]) for p in phs] + [_dt.date.fromisoformat(p["gate"]["date"]) for p in phs if (p.get("gate") or {}).get("date")]
        d1 = max(ends)
        span = max(1, (d1 - d0).days)
        x = lambda d: 100.0 * ((_dt.date.fromisoformat(d) - d0).days) / span  # noqa: E731
        bars = ""
        for p in phs:
            g = p.get("gate") or {}
            left, right = x(p["start"]), x(p["end"])
            gate = ('<span title="Gate %s: %s" style="position:absolute;left:calc(%.2f%% - 6px);top:3px;width:12px;height:12px;transform:rotate(45deg);'
                    'background:var(--accent)"></span>' % (esc(g.get("date")), esc(g.get("pass")), x(g["date"]))) if g.get("date") else ""
            bars += ('<div style="display:grid;grid-template-columns:minmax(120px,30%%) 1fr;gap:12px;align-items:center;padding:6px 0;border-top:1px solid var(--border)">'
                     '<div><b>%s</b><div class="muted" style="font-size:12.5px">%s to %s%s</div></div>'
                     '<div style="position:relative;height:18px"><span style="position:absolute;left:%.2f%%;width:%.2f%%;top:2px;height:14px;border-radius:7px;'
                     'background:var(--accent-soft);border:1px solid var(--accent)"></span>%s</div></div>') % (
                esc(p["title"]), esc(p["start"]), esc(p["end"]), (" · gate %s" % esc(g["date"])) if g.get("date") else "",
                left, max(0.8, right - left), gate)
        gates = "".join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (esc(p["title"]), esc((p.get("gate") or {}).get("date", "")),
                                                                         esc((p.get("gate") or {}).get("pass", ""))) for p in phs)
        body += ('<section class="block"><div class="bh"><h2>5. Timeline and gates</h2><p>%s Dates are estimates from change sizes; the team '
                 'confirms them. Each gate re-measures %s on the same phone (the verifier agent) before the next phase starts.</p></div>'
                 '<div class="card pad">%s</div><div class="card table-wrap" style="margin-top:12px"><table><thead><tr><th>Phase</th><th>Gate</th>'
                 '<th>Pass mark</th></tr></thead><tbody>%s</tbody></table></div></section>') % (
            esc("From %s to %s." % (d0.isoformat(), d1.isoformat())), esc(T), bars, gates)

    # 6. risks, 7. open questions
    rows = "".join('<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (esc(r.get("risk")), esc(r.get("effect")), esc(r.get("fallback")))
                   for r in ROAD.get("risks", []))
    if rows:
        body += ('<section class="block"><div class="bh"><h2>6. Risks and fallbacks</h2></div><div class="card table-wrap"><table><thead>'
                 '<tr><th>Risk</th><th>Effect</th><th>Fallback</th></tr></thead><tbody>%s</tbody></table></div></section>') % rows
    if ROAD.get("open_questions"):
        body += '<section class="block"><div class="bh"><h2>7. Open questions</h2></div><div class="card pad">%s</div></section>' % _ul(ROAD["open_questions"])

    body += ('<section class="block"><div class="callout"><h4>How these numbers are made</h4><p>Scores use the module dashboard\'s scoring '
             '(technical: weights.json; user feel: ux_rubric.json) on the benchmark in %s. Each lever sets %s\'s measurements to the '
             '"after" values in impact.json, which are estimates until re-measured. The scorecards are relative: other apps\' updates move them.</p></div></section>') % (
        esc(RANK.get("source", "the benchmark")), esc(T))
    page("roadmap.html", ROAD.get("title", "Roadmap"), body, "Management roadmap: scope, rank impact, complexity, timeline and risks.")
