#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import csv,io,zipfile,hashlib,collections,sys,re
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_formula_blocks
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'raw_results'
THEORY_DIRS=[ROOT/'theories'/'sound_tiers',ROOT/'theories'/'ablation_variants']

def sha(p):
    h=hashlib.sha256();
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
THEORIES={p.name:p for d in THEORY_DIRS for p in d.glob('*.tff')}
HASHES={n:sha(p) for n,p in THEORIES.items()}

def rows(zname):
    p=RAW/zname
    if not p.exists():raise SystemExit(f'[FAIL] missing raw archive {zname}')
    with zipfile.ZipFile(p) as z:
        names=[n for n in z.namelist() if n.endswith('/results.csv') and not n.startswith('__MACOSX')]
        if len(names)!=1:raise SystemExit(f'[FAIL] {zname}: expected one results.csv, found {names}')
        rr=list(csv.DictReader(io.StringIO(z.read(names[0]).decode('utf-8'))))
    for r in rr:
        tn=r.get('theory_name','')
        if tn not in HASHES:raise SystemExit(f'[FAIL] {zname}: unknown theory_name {tn}')
        if r.get('theory_sha256')!=HASHES[tn]:
            raise SystemExit(f'[FAIL] {zname}: hash mismatch for {tn}: raw={r.get("theory_sha256")} current={HASHES[tn]}')
        if r.get('status') not in {'THEOREM','UNKNOWN','TIMEOUT'}:
            raise SystemExit(f'[FAIL] {zname}: nonclean status {r.get("status")} on {r.get("conjecture")}')
    return rr

def theorem_counts(rr):
    out={}
    for th in sorted({r['theory_name'] for r in rr}):
        xs=[r for r in rr if r['theory_name']==th]
        out[th]=sum(r['status']=='THEOREM' for r in xs)
    return out

def expect_counts(zname,expected):
    rr=rows(zname); got=theorem_counts(rr)
    if got!=expected:raise SystemExit(f'[FAIL] {zname}: theorem counts {got}, expected {expected}')
    print(f'[OK] {zname}: {got}')
    return rr

v=expect_counts('E2V_full.zip',{'T2_core_no_accel.tff':126,'T2_full_sound.tff':161,'T3_validated_anchors.tff':165})
z=expect_counts('E2Z_full.zip',{'T2_core_no_accel.tff':138,'T2_full_sound.tff':73,'T3_validated_anchors.tff':77})

# Structural/extended split used for the controlled Tier-3 discussion.
struct_text=(ROOT/'conjectures'/'structural_subset.tff').read_text()
struct={n for n,r,_,_,__ in extract_formula_blocks(struct_text) if r.lower()=='conjecture'}
if len(struct)!=41:raise SystemExit(f'[FAIL] expected 41 structural names, found {len(struct)}')
for label,rr,exp in [
    ('Vampire',v,{'T2_core_no_accel.tff':(41,85),'T2_full_sound.tff':(41,120),'T3_validated_anchors.tff':(41,124)}),
    ('Z3',z,{'T2_core_no_accel.tff':(41,97),'T2_full_sound.tff':(41,32),'T3_validated_anchors.tff':(36,41)})]:
    got={}
    for th in exp:
        proofs=[r for r in rr if r['theory_name']==th and r['status']=='THEOREM']
        s=sum(r['conjecture'] in struct for r in proofs); got[th]=(s,len(proofs)-s)
    if got!=exp:raise SystemExit(f'[FAIL] {label} structural/extended counts {got}, expected {exp}')
    print(f'[OK] {label} structural/extended theorem counts: {got}')

expect_counts('E4V_add1.zip',{
 'T2_core_no_accel.tff':130,'ADD1__1y.tff':161,'ADD1__4y.tff':150,'ADD1__10y.tff':147,
 'ADD1__100y.tff':140,'ADD1__400y.tff':140,'ADD1__month_hopper.tff':133,'ADD1__weekday400.tff':124})
for zn,th,c in [
 ('E4Z_add1_1y.zip','ADD1__1y.tff',111),('E4Z_add1_4y.zip','ADD1__4y.tff',90),
 ('E4Z_add1_10y.zip','ADD1__10y.tff',86),('E4Z_add1_100y.zip','ADD1__100y.tff',91),
 ('E4Z_add1_400y.zip','ADD1__400y.tff',79)]:
 expect_counts(zn,{'T2_core_no_accel.tff':138,th:c})
for zn,loo,full,red in [
 ('E5V_loo_1y.zip','LOO__1y.tff',165,159),('E5V_loo_4y.zip','LOO__4y.tff',160,156),
 ('E5V_loo_10y.zip','LOO__10y.tff',158,160),('E5V_loo_100y.zip','LOO__100y.tff',157,156),
 ('E5V_loo_400y.zip','LOO__400y.tff',160,159),('E5V_loo_month_hopper.zip','LOO__month_hopper.tff',160,158),
 ('E5V_loo_weekday400.zip','LOO__weekday400.tff',161,159)]:
 expect_counts(zn,{'T2_full_sound.tff':full,loo:red})
expect_counts('E6V_quantified_T1.zip',{'T1_structural.tff':6,'T2_core_no_accel.tff':5,'T2_full_sound.tff':5,'T3_validated_anchors.tff':6})
expect_counts('E6Z_quantified_T1.zip',{'T1_structural.tff':6,'T2_core_no_accel.tff':5,'T2_full_sound.tff':4,'T3_validated_anchors.tff':4})
print('[OK] every retained raw result row refers to the exact distributed theory SHA-256')
print('[OK] all theorem-count tables used in the audited manuscript reproduce from retained CSV data')
