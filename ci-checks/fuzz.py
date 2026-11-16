"""Fuzz with random but plausible games in the simulator (governor alone, as on the device: no "clipped" flag, the draw
known): places with a need of 9-36 W, capped or not, 1-9 % frame spread, hitches; between them loading screens (no
frames), fast menus, 30 fps videos. Per run the simulator's score, and per place of 120 s or more the last 60 s of it:
watts over the need, share of time starved. The worst are listed with their seed.
   python b03_fuzz_scenes.py [first seed] [number of runs] [--old]"""
import random, sys
from lib import sim, HGame, OLD, TAG, mk, seg_stats

S = sim.Scene
args = [a for a in sys.argv[1:] if not a.startswith("--")]
FIRST, RUNS = (int(args[0]) if args else 0), (int(args[1]) if len(args) > 1 else 60)


class FGame(HGame):
    """+ stretches without frames (loading): the frames of those stretches are not handed over."""
    def __init__(self, scenario, silent=(), **kw):
        super().__init__(scenario, **kw)
        self.silent = silent

    def take(self):
        frames, watts = super().take()
        return [f for f in frames if not any(a <= f[0] < b for a, b in self.silent)], watts


def make(seed):
    r = random.Random(seed)
    ceiling = r.choice([30, 30, 30, 25, 20, 17])
    cap = r.choice([None, None, 60.0, 60.0, 30.0, 40.0, 120.0])
    fills = r.random() < 0.3
    base = r.choice([28, 35, 45, 55, 62, 75, 100, 140]) if cap is None else cap * r.choice([0.8, 1.0, 1.15, 1.4, 2.0])
    jit = r.choice([0.01, 0.02, 0.02, 0.035, 0.035, 0.06, 0.09])
    hitch = r.choice([0.0, 0.0, 0.5, 3.0])
    places = []
    for k in range(r.randint(1, 4)):
        need, g, f = r.uniform(9, 36), r.uniform(0.7, 1.2), base * r.uniform(0.7, 1.3)
        curve = tuple((w, round(f * min(1.0, w / need) ** g, 2)) for w in range(8, 41, 2))
        name = f"fz-{seed}-{k}"
        sim.SCENES[name] = S(curve=curve, cap=cap, fills=fills, jitter=jit, hitch_per_min=hitch, cpu_pct=40)
        places.append(name)
    sim.SCENES[f"fz-{seed}-menu"] = S(curve=((8, base * 3.2), (30, base * 3.2)), cap=None if cap is None else cap * r.choice([1.0, 2.4]),
                                      free_w=9.0, jitter=0.02, cpu_pct=10)
    sim.SCENES[f"fz-{seed}-video"] = S(curve=((8, 300.0), (30, 300.0)), cap=30.0, free_w=6.0, jitter=0.01, cpu_pct=10)
    sim.SCENES[f"fz-{seed}-load"] = S(curve=((8, 300.0), (30, 300.0)), cap=60.0, free_w=12.0, jitter=0.01, cpu_pct=90)
    scen, silent, t, marks = [], [], 0.0, []
    while t < 1500:
        x = r.random()
        if x < 0.62:
            d, n = r.choice([20, 45, 90, 150, 240, 400]), r.choice(places)
            marks.append((t, t + d, n))
        elif x < 0.75:
            d, n = r.choice([3, 8, 20]), f"fz-{seed}-load"
            silent.append((t, t + d))
        elif x < 0.88:
            d, n = r.choice([5, 12, 40]), f"fz-{seed}-menu"
        else:
            d, n = r.choice([10, 30, 80]), f"fz-{seed}-video"
        scen.append((d, n, 1.0))
        t += d
    target = r.choice([None, None, None, 30, 40, 60, 60, 60, 90, 120]) if cap is None else r.choice([None, None, int(cap), int(cap), 60, 30])
    kw = dict(lag_s=r.choice([0.15, 0.15, 0.3, 0.6]), window_s=r.choice([None, None, 8.0]))
    return dict(scen=scen, silent=silent, marks=marks, target=target, ceiling=ceiling, kw=kw,
                desc=f"cap {cap} base {base:.0f} fps jitter {jit} hitch/min {hitch} fills {fills} ceiling {ceiling} target {target} {kw}")


def fair_line(game, scene):
    """The frame rate under which the limit costs frames, by Autotune's own rule (the new simulator's Game.line)."""
    best = game.best(scene, 1.0)
    return game.line(best)


def run_one(seed, trace=True):
    m = make(seed)
    game = FGame(m["scen"], silent=m["silent"], seed=seed, goal_fps=m["target"], ceiling=m["ceiling"], **m["kw"])
    if trace:
        game.trace = []
    g = mk(m["target"])
    sim.run(g, game)
    return m, game, g


if __name__ == "__main__":
    rows = []
    for seed in range(FIRST, FIRST + RUNS):
        try:
            m, game, g = run_one(seed)
        except Exception as e:                       # noqa: BLE001
            import traceback
            print(f"seed {seed}: EXCEPTION {e!r}\n{traceback.format_exc()[-1200:]}")
            continue
        sc = game.score()
        worst_over, worst_starved = (0.0, None), (0.0, None)
        for a, b, n in m["marks"]:
            if b - a < 120:
                continue
            rs = [r for r in game.trace if b - 60 <= r[0] < b]
            if not rs:
                continue
            dur = sum(r[3] for r in rs) / 1000.0
            over = sum(max(0.0, r[1] - r[4]) * r[3] for r in rs) / 1000.0 / dur
            scene = sim.SCENES[n]
            line = fair_line(game, scene)
            starved = sum(r[3] for r in rs if scene.shown(r[2], 1.0) < line) / 1000.0 / dur
            if over > worst_over[0]:
                worst_over = (over, (a, b, n))
            if starved > worst_starved[0]:
                worst_starved = (starved, (a, b, n))
        rows.append((seed, sc, worst_over, worst_starved, m["desc"]))
        print(f"{TAG} seed {seed:>4}: limit {sc.limit_w:5.1f} need {sc.need_w:5.1f} over {sc.over_w:4.1f} starved {sc.starved_pct:5.1f} % "
              f"longest {sc.longest_starved_s:6.1f} s lost {sc.lost_pct:4.1f} % chg/min {sc.changes_per_min:4.1f} | last 60 s of a place: "
              f"over {worst_over[0]:4.1f} W {worst_over[1]}, starved {100 * worst_starved[0]:3.0f} % {worst_starved[1]} | {m['desc']}", flush=True)
    n = len(rows)
    if n:
        print(f"\n{TAG} {n} runs: mean limit {sum(r[1].limit_w for r in rows) / n:.2f} W, need {sum(r[1].need_w for r in rows) / n:.2f} W, "
              f"over {sum(r[1].over_w for r in rows) / n:.2f} W, starved {sum(r[1].starved_pct for r in rows) / n:.2f} %, "
              f"lost {sum(r[1].lost_pct for r in rows) / n:.2f} %, longest starved: median "
              f"{sorted(r[1].longest_starved_s for r in rows)[n // 2]:.1f} s, worst {max(r[1].longest_starved_s for r in rows):.1f} s, "
              f"chg/min {sum(r[1].changes_per_min for r in rows) / n:.2f}")
