"""Mutation check: each rule in mutants.json is broken in turn in this checkout, the backend tests run, and a mutant
counts as caught when a test fails that passes on the unchanged tree. The file is put back after each.
   python ci-checks/mutate.py SHARD OF"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = ["tests/test_governor.py", "tests/test_backend.py", "tests/test_autotune_sim.py", "tests/test_governor_sim.py",
         "tests/test_modules.py", "tests/test_diaglog.py", "tests/test_hardware_findings.py"]


def failing(first_only=False):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *(["-x"] if first_only else []), *TESTS],
                       cwd=ROOT, capture_output=True,
                       text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=600)
    out = r.stdout + r.stderr
    fails = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))
    if not fails and r.returncode not in (0, 1):
        fails.add("COLLECTION-ERROR: " + out.strip().splitlines()[-1][:120])
    return fails


def main():
    shard, of = int(sys.argv[1]), int(sys.argv[2])
    mutants = json.load(open(os.path.join(ROOT, "ci-checks", "mutants.json")))
    only = os.path.join(ROOT, "ci-checks", "only.json")          # a list of names: the rest of a run that was cut short
    if os.path.exists(only) and json.load(open(only)):
        mutants = [m for m in mutants if m[0] in json.load(open(only))]
    base = failing()
    print(f"shard {shard}/{of}: {len(base)} tests fail on the unchanged tree: {sorted(base)}", flush=True)
    survived = 0
    for i, (name, rel, what, old, new) in enumerate(mutants):
        if i % of != shard:
            continue
        path = os.path.join(ROOT, rel)
        src = open(path).read()
        if src.count(old) != 1:
            print(f"NOMATCH  {name:<28} the search text is in the file {src.count(old)} times", flush=True)
            continue
        open(path, "w").write(src.replace(old, new))
        try:
            new_fails = sorted(failing(first_only=not base) - base)   # (a clean tree: the first failing test is enough)
        except subprocess.TimeoutExpired:
            new_fails = ["TIMEOUT (the tests did not end in 600 s)"]
        finally:
            open(path, "w").write(src)
        survived += not new_fails
        print(("caught   " if new_fails else "SURVIVED ") + f"{name:<28} {what}"
              + (f"   [{len(new_fails)}: {new_fails[0].split('::')[-1][:70]}]" if new_fails else ""), flush=True)
    print(f"shard {shard}/{of}: {survived} survived", flush=True)


if __name__ == "__main__":
    main()
