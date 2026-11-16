"""Cloud-fuzz seeds again, wired, on the tree of the cwd's parent: every stretch of 10 s or more under the fair line, with
what the governor believed in its middle.   PYTHONPATH=. python stretches.py SEED...   (cwd: ci-checks)"""
import sys
sys.argv, a = [sys.argv[0]], sys.argv[1:]
import fuzz as fz
from lib import sim
for seed in (int(x) for x in a):
    m = fz.make(seed)
    game = fz.FGame(m["scen"], silent=m["silent"], seed=seed, goal_fps=m["target"], ceiling=m["ceiling"], **m["kw"])
    game.trace = []
    g = fz.mk(m["target"])
    states, tick = [], g.tick

    def tick2(frames, draw, tick=tick, g=g, game=game, states=states):
        tick(frames, draw)
        s = g.at.session
        st = s.gov
        goal = sim.governor.goal(st, s.cfg)
        states.append((game.t, st.ref, goal, st.limit, st.mode, st.scene_since, (st.lo, st.hi), s.last_action))

    g.tick = tick2
    sim.run(g, game)
    bounds, t = [], 0.0
    for d, n, k in m["scen"]:
        bounds.append((t, t + d, n)); t += d

    def scene_at(t, bounds=bounds):
        for x, y, n in bounds:
            if x <= t < y:
                return n

    runs, cur = [], None
    for r in game.trace:                       # (t, limit, watts, ms, need)
        n = scene_at(r[0])
        if n is None:
            continue
        sc = sim.SCENES[n]
        bad = sc.shown(r[2], 1.0) < fz.fair_line(game, sc)
        if bad and cur is not None and cur[2] == n:
            cur[1] = r[0]; cur[3].append(sc.shown(r[2], 1.0)); cur[4].append(r[1])
        else:
            if cur is not None and cur[1] - cur[0] >= 10:
                runs.append(cur)
            cur = [r[0], r[0], n, [sc.shown(r[2], 1.0)], [r[1]]] if bad else None
    if cur is not None and cur[1] - cur[0] >= 10:
        runs.append(cur)
    sc_ = game.score()
    print(f"seed {seed}: starved {sc_.starved_pct:.1f} % longest {sc_.longest_starved_s:.1f} s | {m['desc'][:95]}")
    for x, y, n, shown, lims in runs:
        sc = sim.SCENES[n]
        line, best = fz.fair_line(game, sc), game.best(sc, 1.0)
        mid = [s for s in states if x + (y - x) * 0.4 <= s[0] <= x + (y - x) * 0.6] or [s for s in states if x <= s[0] <= y]
        s0 = mid[len(mid) // 2] if mid else None
        got = sum(shown) / len(shown)
        visit = sum(1 for s in states if x <= s[0] <= y and s[5] is not None) / max(1, sum(1 for s in states if x <= s[0] <= y))
        kind = n.split("-")[-1]
        print(f"   {x:7.1f}-{y:7.1f} ({y - x:5.1f} s) {kind:5} at {sum(lims) / len(lims):4.1f} W: {got:5.1f} fps, line {line:5.1f} ({100 * (got / line - 1):+5.1f} %), "
              f"full {best:5.1f} | ref {'-' if s0 is None or s0[1] is None else round(s0[1], 1)} goal {'-' if s0 is None or s0[2] is None else round(s0[2], 1)} "
              f"mode {s0[4] if s0 else '-'} new scene {100 * visit:3.0f} % band {s0[6] if s0 else '-'} | {(s0[7] or '')[:60] if s0 else ''}")
