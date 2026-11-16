"""variant.py NAME: one rule of the governor changed in this checkout (variants.json), to measure it in the fuzz before
it changes. For the CI checkout only: the file is not put back."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for rel, old, new in json.load(open(os.path.join(ROOT, "ci-checks", "variants.json")))[sys.argv[1]]:
    path = os.path.join(ROOT, rel)
    src = open(path).read()
    assert src.count(old) == 1, (sys.argv[1], old)
    open(path, "w").write(src.replace(old, new))
print("variant", sys.argv[1], "applied")
