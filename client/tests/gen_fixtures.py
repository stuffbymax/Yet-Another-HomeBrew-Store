#!/usr/bin/env python3
"""python gen_fixtures.py SEED_HEX OUTDIR  - writes signed catalogs used by test_core.c"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../server"))
import signing
seed, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
rows = ["1\tAlpha\t1.0\tps4\t1234\t" + "a" * 64 + "\tpkg", "2\tBeta\t2.0\tps4\t999\t" + "b" * 64 + "\tzip"]
w = lambda n, s: open(os.path.join(out, n), "w").write(s)
w("good_ps4.tsv", signing.sign_catalog(seed, "ps4", rows))
w("old_ps4.tsv", signing.sign_catalog(seed, "ps4", rows, now=1_000_000))
w("unsigned_ps4.tsv", "#ts\t1\n#plat\tps4\n" + "\n".join(rows) + "\n")
other, _ = signing.generate()
w("otherkey_ps4.tsv", signing.sign_catalog(other, "ps4", rows))
