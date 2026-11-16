"""Hostile scenes for tools/autotune_sim.py, defined outside the worktree. build(sim) returns a Game subclass of the given
simulator module (the branch's, or the old tree's in review/old_tree), so the same scenes run on the new governor and on
the build it replaces. What is added to the simulator's Game (all optional):
  workfn(t)      a factor on the scene's work over time (bursts, drift, staircase, noise that hangs together in time)
  vsync_hz       frame times rounded up to whole refresh periods (double-buffered vsync: 60 / 30 / 20 fps)
  bimodal        frame times alternate short / long around their mean (uneven pacing, as generated frames can have)
  runs           the game's own hitches come as runs of `run_len` frames `run_x` times as long, `runs` a minute
  window_s       the chip may draw limit + 2 W (PL2) while its average over this window (PL1's) is under the limit
  lag_s          how fast the chip follows a new limit (the simulator has 0.15 s)
Extra score: deep_s, seconds with less than 80 % of the frames the full limit would give."""
import math


def build(sim):
    class HGame(sim.Game):
        def __init__(self, scenario, workfn=None, vsync_hz=None, bimodal=None, runs=0.0, run_len=8, run_x=1.5,
                     window_s=None, lag_s=None, **kw):
            super().__init__(scenario, **kw)
            self.workfn, self.vsync_hz, self.bimodal = workfn, vsync_hz, bimodal
            self.runs, self.run_len, self.run_x, self._run_left = runs, run_len, run_x, 0
            self.window_s, self.lag_s = window_s, lag_s if lag_s is not None else sim.LAG_S
            self._avg = float(self.ceiling)            # the chip's own average of its draw (PL1's window)
            self._n, self.deep_s, self._carry = 0, 0.0, 0.0

        def place(self, t):
            scene, work = super().place(t)
            if self.workfn:
                work = round(work * self.workfn(t), 3)
            return scene, work

        def advance(self, until):
            rng = self.rng
            while self.t < until:
                scene, work = self.place(self.t)
                ms = 1000.0 / scene.rate(self.watts, work) * math.exp(rng.gauss(0.0, scene.jitter))
                if scene.cap:
                    ms = max(ms, 1000.0 / scene.cap + rng.gauss(0.0, sim.PRESENT_MS))
                if scene.hitch_per_min and rng.random() < scene.hitch_per_min / 60.0 * ms / 1000.0:
                    ms += rng.uniform(40.0, 190.0)
                if self.runs and self._run_left == 0 and rng.random() < self.runs / 60.0 * ms / 1000.0:
                    self._run_left = self.run_len
                if self._run_left:
                    self._run_left -= 1
                    ms *= self.run_x
                if self.bimodal:
                    self._n += 1
                    ms *= (1.0 + self.bimodal) if self._n % 2 else (1.0 - self.bimodal)
                if self.vsync_hz:
                    period = 1000.0 / self.vsync_hz
                    ms = max(1, math.ceil((ms - 0.3) / period)) * period
                dt = ms / 1000.0
                if scene.fills or not scene.cap or scene.rate(self.watts, work) < scene.cap:
                    draw = self.watts
                else:
                    draw = min(self.watts, scene.free_w if scene.free_w is not None else self._watts_for_cap(scene, work))
                best, need = self.best(scene, work), self.need(scene, work)
                now = scene.shown(self.watts, work)
                cost = max(0.0, 1.0 - now / best)
                a = self._acc
                a["limit"] += self.limit * dt
                a["draw"] += draw * dt
                a["need"] += need * dt
                a["over"] += max(0.0, self.limit - need) * dt
                a["lost"] += cost * dt
                a["frames"] += 1
                if "slow" in a:
                    a["slow"] += ms > 1100.0 / best
                # the design's own line (for a game without a target: 5 % or 2 fps, whichever is more), as in sim.Game.advance;
                # best * 0.95 alone counted a 24 fps game as starved at a limit the design allows (fuzz seed 208, 2026-11-16)
                if now < (self.line(best) if hasattr(self, "line") else best * (1 - sim.TOLERANCE) - sim.SLACK_FPS):
                    a["starved"] += dt
                    self._run += dt
                    self._longest = max(self._longest, self._run)
                else:
                    self._run = 0.0
                if now < 0.8 * best:
                    self.deep_s += dt
                self._joules += draw * dt
                self.t += dt
                self._frames.append((self.t, ms))
                if self.trace is not None:
                    self.trace.append((round(self.t, 3), self.limit, round(self.watts, 2), round(ms, 2), need))
                allowed = self.limit
                if self.window_s:
                    self._avg += (draw - self._avg) * (1.0 - math.exp(-dt / self.window_s))
                    if self._avg < self.limit:
                        allowed = min(self.limit + 2.0, self.ceiling + 2.0)
                self.watts += (allowed - self.watts) * (1.0 - math.exp(-dt / self.lag_s))

    return HGame


class OU:
    """Load that hangs together in time: exp of an Ornstein-Uhlenbeck walk (sigma of the logarithm, time constant s),
    sampled on a 50 ms grid so the same seed gives the same load to every governor."""
    def __init__(self, sigma, tau, seed, seconds=3600.0, step=0.05):
        import random
        r, x, self.step, self.v = random.Random(seed), 0.0, step, []
        k = math.exp(-step / tau)
        s = sigma * math.sqrt(1 - k * k)
        for _ in range(int(seconds / step) + 2):
            x = x * k + r.gauss(0.0, s)
            self.v.append(math.exp(x))

    def __call__(self, t):
        return self.v[min(len(self.v) - 1, int(t / self.step))]


def scenes(sim, seed):
    """name -> (scenario, target for target mode, kwargs for HGame)."""
    S = sim.Scene
    sim.SCENES.setdefault("slow-20", S(curve=((8, 11.0), (12, 16.0), (16, 19.5), (20, 22.0), (30, 24.0)), jitter=0.03, cpu_pct=60))
    sim.SCENES.setdefault("fast-240", S(curve=((8, 150.0), (12, 215.0), (14, 245.0), (30, 300.0)), cap=240.0, jitter=0.05, cpu_pct=30))
    sim.SCENES.setdefault("noisy-uncapped", S(curve=((8, 16.4), (10, 23.2), (12, 30.6), (15, 38.7), (18, 44.5), (30, 48.5)),
                                              jitter=0.09, cpu_pct=35, gpu_bound=True))
    play = [(600, "enshrouded-play", 1.20)]
    ou = OU(0.06, 1.5, seed)
    return {
        "load noise 6 %, 1.5 s (60 cap)": (play, 60, dict(workfn=lambda t: 0.94 * ou(t))),
        "dips -20 % for 0.6 s every 12 s": (play, 60, dict(workfn=lambda t: 0.80 if (t % 12.0) < 0.6 else 1.0)),
        "need swings every 2.5 s": (play, 60, dict(workfn=lambda t: 1.0 if int(t / 2.5) % 2 else 0.88)),
        "need swings every 10 s": (play, 60, dict(workfn=lambda t: 1.0 if int(t / 10.0) % 2 else 0.88)),
        "staircase need, 20 s a step": (play, 60, dict(workfn=lambda t: 1.0 - 0.02 * min(int(t / 20) % 20, 20 - int(t / 20) % 20))),
        "slow drift of the need (5 min)": (play, 60, dict(workfn=lambda t: 0.93 + 0.08 * math.sin(2 * math.pi * t / 300.0))),
        "hitch runs, 6 a minute": (play, 60, dict(runs=6.0)),
        "hitch runs, 30 a minute": (play, 60, dict(runs=30.0)),
        "uncapped, scene +-15 % every 30 s": ([(600, "enshrouded-altar", 1.0)], None,
                                             dict(workfn=lambda t: 1.0 if int(t / 30.0) % 2 else 0.87)),
        "uncapped, 9 % frame noise": ([(600, "noisy-uncapped", 1.0)], None, {}),
        "20 fps game, uncapped": ([(600, "slow-20", 1.0)], None, {}),
        "240 fps cap, light": ([(600, "fast-240", 1.0)], 240, {}),
        "vsync 60 Hz (60/30/20)": (play, 60, dict(vsync_hz=60.0)),
        "uneven pacing +-30 %": (play, 60, dict(bimodal=0.30)),
        "chip follows in 1.5 s": (sim.SCENARIOS["cap-need-moves"][:4], 60, dict(lag_s=1.5)),
        "PL1 window 8 s, PL2 +2": (sim.SCENARIOS["cap-need-moves"][:4], 60, dict(window_s=8.0)),
        "PL1 window, parked emulator": ([(600, "mcla", 1.0)], 30, dict(window_s=8.0)),
        "PL1 window, uncapped": ([(600, "enshrouded-altar", 1.0)], None, dict(window_s=8.0)),
    }
