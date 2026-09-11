#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_formula_blocks
ROOT=Path(__file__).resolve().parents[1]

def chk_file(p, expected_conj=None):
    text=p.read_text(encoding='utf-8',errors='replace')
    blocks=extract_formula_blocks(text)
    names=[n for n,_,_,_,__ in blocks]
    dups=sorted({n for n in names if names.count(n)>1})
    if dups: raise SystemExit(f'[FAIL] duplicate formula names in {p}: {dups[:10]}')
    if expected_conj is not None:
        c=sum(1 for _,r,_,_,__ in blocks if r.lower()=='conjecture')
        if c!=expected_conj: raise SystemExit(f'[FAIL] {p.name}: expected {expected_conj} conjectures, found {c}')
    return len(blocks)

# Validate the distributed files without rewriting them; this preserves the exact theory hashes used by raw runs.
for p in sorted((ROOT/'theories'/'sound_tiers').glob('*.tff')):
    print(f'[OK] {p.name}: {chk_file(p)} formulas')
for p in sorted((ROOT/'theories'/'ablation_variants').glob('*.tff')):
    chk_file(p)
print(f'[OK] ablation variants: {len(list((ROOT/"theories"/"ablation_variants").glob("*.tff")))}')
chk_file(ROOT/'conjectures'/'ground_200_corrected.tff',200)
chk_file(ROOT/'conjectures'/'structural_subset.tff',41)
chk_file(ROOT/'conjectures'/'extended_subset.tff',159)
chk_file(ROOT/'conjectures'/'quantified_T1.tff',6)
chk_file(ROOT/'conjectures'/'quantified_T2.tff',6)
for script in ('static_oracle_check.py','audit_anchor_overlap.py','verify_reported_results.py'):
    subprocess.run([sys.executable,str(ROOT/'scripts'/script)],check=True,cwd=ROOT)
print('[OK] suite validation passed')
