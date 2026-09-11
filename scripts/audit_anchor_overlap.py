#!/usr/bin/env python3
from pathlib import Path
import re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_formula_blocks
ROOT=Path(__file__).resolve().parents[1]
T3=ROOT/'theories'/'sound_tiers'/'T3_validated_anchors.tff'
STRUCT=ROOT/'conjectures'/'structural_subset.tff'
EXT=ROOT/'conjectures'/'extended_subset.tff'
DAYS={'monday','tuesday','wednesday','thursday','friday','saturday','sunday'}

def eq_int(body,var):
    m=re.search(rf'\b{re.escape(var)}\s*=\s*(-?\d+)\b',body)
    if m:return int(m.group(1))
    m=re.search(rf'(-?\d+)\s*=\s*\b{re.escape(var)}\b',body)
    return int(m.group(1)) if m else None

def eq_day(body,var):
    alt='|'.join(sorted(DAYS))
    m=re.search(rf'\b{re.escape(var)}\s*=\s*({alt})\b',body)
    if m:return m.group(1)
    m=re.search(rf'\b({alt})\s*=\s*{re.escape(var)}\b',body)
    return m.group(1) if m else None

anchors=set()
for n,r,b,_,__ in extract_formula_blocks(T3.read_text()):
    if r.lower()!='axiom' or not n.startswith('anchor_'):continue
    m=re.search(r'weekday\(ymd\((\d+),(\d+),(\d+)\),(\w+)\)',b)
    if m:anchors.add(('weekday',int(m.group(1)),int(m.group(2)),int(m.group(3)),m.group(4)));continue
    m=re.search(r'is_days_in_month\((\d+),(\d+),(\d+)\)',b)
    if m:anchors.add(('month_length',int(m.group(2)),int(m.group(1)),int(m.group(3))));continue
    m=re.search(r'year_span_days\((\d+),(\d+),(\d+)\)',b)
    if m:anchors.add(('year_span',int(m.group(1)),int(m.group(2)),int(m.group(3))));continue

def target_facts(path):
    out=[]
    for n,r,b,_,__ in extract_formula_blocks(path.read_text()):
        if r.lower()!='conjecture':continue
        for m in re.finditer(r'weekday\(ymd\((\d+),\s*(\d+),\s*(\d+)\),\s*([A-Za-z][A-Za-z0-9_]*)\)',b):
            y,mo,d,w=m.groups(); wv=w if w in DAYS else eq_day(b,w)
            if wv: out.append((n,('weekday',int(y),int(mo),int(d),wv)))
        for m in re.finditer(r'is_days_in_month\((\d+),\s*(\d+),\s*([A-Za-z][A-Za-z0-9_]*|-?\d+)\)',b):
            mo,y,L=m.groups(); lv=int(L) if re.fullmatch(r'-?\d+',L) else eq_int(b,L)
            if lv is not None:out.append((n,('month_length',int(y),int(mo),lv)))
    return out

struct_hits=[(n,f) for n,f in target_facts(STRUCT) if f in anchors]
ext_hits=[(n,f) for n,f in target_facts(EXT) if f in anchors]
print(f'[INFO] Tier-3 anchor/structural-target direct coincidences: {len(struct_hits)}')
for n,f in struct_hits: print(f' - {n}: {f}')
print(f'[INFO] Tier-3 anchor/extended-target direct coincidences: {len(ext_hits)}')
for n,f in ext_hits: print(f' - {n}: {f}')
if len(struct_hits)!=12: raise SystemExit(f'[FAIL] expected 12 disclosed structural coincidences, found {len(struct_hits)}')
if ext_hits: raise SystemExit('[FAIL] Tier-3 anchors directly coincide with extended benchmark targets')
print('[OK] disclosed overlap is confined to 12 structural targets; extended subset has zero direct anchor coincidences')
