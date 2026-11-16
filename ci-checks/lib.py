"""review2 helpers: load the simulator of the new build (gov) or the old one (review/old_tree) by --old."""
import importlib.util, logging, os, sys
sys.dont_write_bytecode = True
OLD = "--old" in sys.argv
ROOT = os.environ.get("GOV_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "OLD" if OLD else "NEW"
spec = importlib.util.spec_from_file_location("autotune_sim", os.path.join(ROOT, "tools", "autotune_sim.py"))
sim = importlib.util.module_from_spec(spec); sys.modules["autotune_sim"] = sim; spec.loader.exec_module(sim)
logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hostile  # noqa: E402
HGame = hostile.build(sim)


def mk(target=None):
    return sim.Today(target=target) if OLD else sim.Wired(target=target)


def seg_stats(game, t0, t1):
    """From game.trace rows (t, limit, watts, ms, need) between t0 and t1: mean limit, mean need, limit at the end,
    seconds starved (frame rate under line) is not here; changes of the limit a minute."""
    rows = [r for r in game.trace if t0 <= r[0] < t1]
    if not rows:
        return None
    dur = sum(r[3] for r in rows) / 1000.0
    lim = sum(r[1] * r[3] for r in rows) / 1000.0 / dur
    need = sum(r[4] * r[3] for r in rows) / 1000.0 / dur
    ch = sum(1 for a, b in zip(rows, rows[1:]) if a[1] != b[1])
    fps = len(rows) / dur
    return dict(limit=lim, need=need, end=rows[-1][1], chg=ch * 60.0 / dur, fps=fps, lo=min(r[1] for r in rows))
