#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_z3 import find_exe,run_one
from lib.tptp_utils import strip_conjectures

ROOT=Path(__file__).resolve().parents[1]
TIERS=[
 ROOT/'theories'/'sound_tiers'/'T1_structural.tff',
 ROOT/'theories'/'sound_tiers'/'T2_core_no_accel.tff',
 ROOT/'theories'/'sound_tiers'/'T2_full_sound.tff',
 ROOT/'theories'/'sound_tiers'/'T3_validated_anchors.tff',
]
FALSE='tff(consistency_probe, conjecture, $false).'
REG_T1=[
 ('reg_feb1900', 'tff(reg_feb1900, conjecture, is_days_in_month(2,1900,28)).'),
 ('reg_weekday_2025_01_01', 'tff(reg_weekday_2025_01_01, conjecture, weekday(ymd(2025,1,1),wednesday)).'),
]
REG_T2=[
 ('reg_actual_fifth_thu_feb_2024', 'tff(reg_actual_fifth_thu_feb_2024, conjecture, nth_weekday_date(5,thursday,2,2024,ymd(2024,2,29))).'),
 ('reg_no_fifth_fri_feb_2025', 'tff(reg_no_fifth_fri_feb_2025, conjecture, ~ ?[D:$int]: nth_weekday_date(5,friday,2,2025,ymd(2025,2,D))).'),
 ('reg_last_mon_mar_2025', 'tff(reg_last_mon_mar_2025, conjecture, last_weekday_date(monday,3,2025,ymd(2025,3,31))).'),
 ('reg_date_1000', 'tff(reg_date_1000, conjecture, calc_date(1001,1,2024,ymd(2026,9,27))).'),
 ('reg_negative_time', 'tff(reg_negative_time, conjecture, normalize_time(0,0,-1,-1,22,59,-1)).'),
]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--exe'); ap.add_argument('--timeout',type=int,default=20)
    a=ap.parse_args(); exe=find_exe(a.exe)
    out=ROOT/'results'/'PRECHECK_Z3'; out.mkdir(parents=True,exist_ok=True)
    fatal=False; theorem_count=0
    print('[INFO] Z3 TPTP frontend:',exe)
    for idx,tp in enumerate(TIERS):
        th=strip_conjectures(tp.read_text())
        st,raw,sec=run_one(exe,th,FALSE,a.timeout,'none',out/'logs'/tp.stem/'consistency.log')
        print(f'[CONSISTENCY] {tp.name}: {st} ({sec:.3f}s)')
        if st in {'THEOREM','ERROR_CONTRADICTORY_AXIOMS'}:
            print('  [FAIL] $false is derivable or contradictory axioms reported'); fatal=True
        elif st=='INPUT_ERROR':
            print('  [FAIL] TPTP frontend input error; inspect log'); fatal=True
        regs=REG_T1 if idx==0 else REG_T1+REG_T2
        for name,c in regs:
            st,raw,sec=run_one(exe,th,c,a.timeout,'none',out/'logs'/tp.stem/f'{name}.log')
            print(f'[REGRESSION ] {tp.name}: {name}: {st} ({sec:.3f}s)')
            if st=='THEOREM': theorem_count+=1
            elif st=='COUNTERSAT':
                print('  [FAIL] expected-true regression is counter-satisfiable'); fatal=True
            elif st in {'INPUT_ERROR','ERROR_CONTRADICTORY_AXIOMS'}:
                print('  [FAIL] frontend/theory error; inspect log'); fatal=True
            else:
                print('  [WARN] regression not proved within preflight limit; not a consistency failure')
    # This catches the exact failure mode of the previous wrapper: instant UNKNOWN everywhere.
    if theorem_count==0:
        print('[FAIL] Z3 TPTP frontend proved zero regression cases; preflight is not meaningful.')
        fatal=True
    if fatal: raise SystemExit(2)
    print(f'[OK] Z3 TPTP preflight passed; proved regressions: {theorem_count}')
if __name__=='__main__':main()
