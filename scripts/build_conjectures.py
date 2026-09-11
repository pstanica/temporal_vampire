#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re, json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_formula_blocks

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'conjectures'/'source_benchmark_raw.tff'
OUT=ROOT/'conjectures'/'ground_200_corrected.tff'
STRUCT=ROOT/'conjectures'/'structural_subset.tff'
EXT=ROOT/'conjectures'/'extended_subset.tff'
MAP=ROOT/'conjectures'/'correction_manifest.json'

text=SRC.read_text(encoding='utf-8',errors='replace')
blocks=extract_formula_blocks(text)
byname={name:(block,s,e) for name,role,block,s,e in blocks if role.lower()=='conjecture'}

# Correct independently checked Gregorian expected results while preserving each input day index.
expected={
 'test_scale_fwd_5k':(2037,9,9),
 'test_scale_fwd_50k':(2160,11,23),
 'test_scale_back_10k':(1996,8,15),
 'test_scale_back_50k':(1887,2,8),
 'test_scale_back_100k':(1750,3,18),
 'test_accel_back_century':(1924,1,1),
 'test_accel_back_decade':(2013,12,30),
 'test_sub_1':(2023,12,21),
 'test_sub_3':(1996,8,15),
 'test_mix_m_long_back':(2023,12,28),
 'test_mix_m_short_back':(2024,3,30),
 'test_quad_fwd_leap_1':(2028,1,1),
 'test_quad_fwd_leap_2':(2032,1,1),
 'test_quad_back_norm_1':(2025,1,1),
 'test_quad_back_norm_2':(2026,1,1),
 'test_quad_back_norm_3':(2027,1,1),
 'test_decade_fwd_2':(2034,1,1),
 'test_decade_mix_1':(2044,12,31),
 'test_decade_mix_2':(2074,12,30),
 'test_decade_mix_4':(2115,12,30),
}

replacements={}
changes=[]
for name,(y,m,d) in expected.items():
    block=byname[name][0]
    new=re.sub(r'\bY\s*=\s*-?\d+',f'Y={y}',block)
    new=re.sub(r'\bM\s*=\s*-?\d+',f'M={m}',new)
    new=re.sub(r'\bD\s*=\s*-?\d+',f'D={d}',new)
    replacements[name]=new
    changes.append({'test':name,'kind':'Gregorian expected-date correction','new_expected':[y,m,d]})

# A formerly duplicated/misnamed last-Monday query is made into the intended 4th-Monday query.
old='test_sch_last_mon_mar'
newblock='tff(test_sch_4th_mon_mar, conjecture, ?[D:$int]: (nth_weekday_date(4, monday, 3, 2025, ymd(2025, 3, D)) & D=24 & valid_day(D))).'
replacements[old]=newblock
changes.append({'test':old,'renamed_to':'test_sch_4th_mon_mar','kind':'scheduler semantic correction'})

# Negative time normalization: -1h -1m from 00:00 has day delta -1, not 0.
old='test_sub_10'
block=byname[old][0]
new=block.replace('H, M, 0)', 'H, M, -1)')
replacements[old]=new
changes.append({'test':old,'kind':'time normalization day-delta correction','new_day_delta':-1})

# Clean misleading IDs without changing their formulas.
renames={
 'test_comb_sch_5th_feb_fail':'test_comb_sch_4th_fri_feb_end',
 'test_wk_old_bce':'test_wk_year1',
 'test_wk_far_future':'test_wk_2030_dec31',
}
for old,newname in renames.items():
    block=byname[old][0]
    replacements[old]=re.sub(r'(^\s*tff\s*\()'+re.escape(old),r'\1'+newname,block,count=1)
    changes.append({'test':old,'renamed_to':newname,'kind':'misleading identifier cleanup'})

# Apply replacements by source spans from right to left.
spans=[]
for name,new in replacements.items():
    _,s,e=byname[name]
    spans.append((s,e,new))
for s,e,new in sorted(spans,reverse=True):
    text=text[:s]+new+text[e:]

OUT.write_text(text,encoding='utf-8')

# Split into a T1-only structural subset and the remaining T2-level subset.
blocks2=extract_formula_blocks(text)
struct=[]; ext=[]
for name,role,block,s,e in blocks2:
    if role.lower()!='conjecture': continue
    lower=block.lower()
    if any(sym in lower for sym in ('calc_date(', 'calc_datetime(', 'normalize_time(', 'nth_weekday_date(', 'last_weekday_date(')):
        ext.append(block)
    else:
        struct.append(block)
STRUCT.write_text('% T1 structural subset extracted from ground_200_corrected.tff\n\n'+'\n\n'.join(struct)+'\n')
EXT.write_text('% T2/T3 extended-vocabulary subset extracted from ground_200_corrected.tff\n\n'+'\n\n'.join(ext)+'\n')

manifest={
 'source':'source_benchmark_raw.tff',
 'corrected_file':'ground_200_corrected.tff',
 'total_conjectures':sum(1 for _,r,_,_,__ in blocks2 if r.lower()=='conjecture'),
 'structural_subset_count':len(struct),
 'extended_subset_count':len(ext),
 'changes':changes,
}
MAP.write_text(json.dumps(manifest,indent=2)+'\n')
print('[OK] wrote',OUT)
print(f'[OK] total=200 structural={len(struct)} extended={len(ext)} changes={len(changes)}')
