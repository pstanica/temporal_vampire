#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,csv,json,os,re,shutil,signal,subprocess,sys,time,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_conjectures,strip_conjectures,seed_weekdays,sha256_file
REV='2026-08-26-sound-v3-z3tptp-filearg'

def find_exe(arg):
    cands=[arg,os.environ.get('Z3_TPTP_EXE'),shutil.which('z3_tptp'),shutil.which('z3_tptp5')]
    for x in cands:
        if x and Path(x).exists() and os.access(x,os.X_OK):
            return str(Path(x).resolve())
    raise SystemExit(
        '[ERROR] cannot find the Z3 TPTP frontend.\n'
        'Do NOT pass the ordinary z3 executable.\n'
        'Set --exe /full/path/to/z3_tptp5 or export Z3_TPTP_EXE=/full/path/to/z3_tptp5.\n'
        'See README.md and Z3_TPTP_SETUP_MACOS.txt.'
    )

def kill_group(p):
    try: os.killpg(os.getpgid(p.pid),signal.SIGKILL)
    except Exception:
        try: p.kill()
        except Exception: pass
    try: p.wait(timeout=2)
    except Exception: pass

def parse_status(raw,timed,returncode):
    if timed:
        return 'TIMEOUT','python_wallclock_timeout'
    low=raw.lower()
    # Prefer TPTP SZS statuses emitted by the TPTP frontend.
    m=re.search(r'\bszs\s+status\s+([a-z][a-z0-9_]*)',low,re.I)
    if m:
        s=m.group(1).lower()
        if s in {'theorem','unsatisfiable','contradictoryaxioms'}:
            # ContradictoryAxioms is never an acceptable theorem result in this suite.
            if s=='contradictoryaxioms': return 'ERROR_CONTRADICTORY_AXIOMS',s
            return 'THEOREM',s
        if s in {'countersatisfiable','satisfiable'}: return 'COUNTERSAT',s
        if s in {'timeout','resourceout'}: return 'TIMEOUT',s
        if s in {'gaveup','unknown','incomplete'}: return 'UNKNOWN',s
        if s in {'inputerror','syntaxerror','typeerror'}: return 'INPUT_ERROR',s
    # Conservative fallback for frontend versions that print bare SMT-style status.
    lines=[ln.strip().lower() for ln in raw.splitlines() if ln.strip()]
    if any(ln=='unsat' for ln in lines): return 'THEOREM','unsat'
    if any(ln=='sat' for ln in lines): return 'COUNTERSAT','sat'
    if any(ln=='unknown' for ln in lines): return 'UNKNOWN','unknown'
    parse_markers=('parse error','syntax error','type error','error:','unsupported')
    if returncode not in (0,None) or any(x in low for x in parse_markers):
        return 'INPUT_ERROR',f'exit_{returncode}'
    return 'UNKNOWN','no_conclusive_status'

def run_one(exe,theory,conj,timeout,seed_mode,log):
    seed=seed_weekdays(conj) if seed_mode=='python-weekday' else ''
    with tempfile.NamedTemporaryFile('w',suffix='.p',delete=False,encoding='utf-8') as f:
        f.write(theory.rstrip()+'\n\n'+seed+conj+'\n'); tmp=f.name
    # z3_tptp/z3_tptp5 requires -file:<path>; positional file arguments are rejected.
    # Use the frontend's native timeout and retain a slightly larger Python wall-clock guard.
    cmd=[exe,f'-t:{timeout}',f'-file:{tmp}']
    t=time.perf_counter(); timed=False; rc=None
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        try:
            o,e=p.communicate(timeout=timeout+2)
            rc=p.returncode
        except subprocess.TimeoutExpired:
            timed=True; kill_group(p); o,e='','PYTHON_WALLCLOCK_TIMEOUT'; rc=p.returncode
    finally:
        try: Path(tmp).unlink()
        except Exception: pass
    raw=(o or '')+(e or ''); sec=time.perf_counter()-t
    st,rs=parse_status(raw,timed,rc)
    if st!='THEOREM':
        log.parent.mkdir(parents=True,exist_ok=True)
        log.write_text('COMMAND: '+repr(cmd)+'\nRETURN_CODE: '+repr(rc)+'\n\n'+raw,encoding='utf-8',errors='replace')
    return st,rs,sec

def main():
    ap=argparse.ArgumentParser(description='Run the dedicated Z3 TPTP frontend independently. Never use the ordinary z3 binary here.')
    ap.add_argument('--exe');ap.add_argument('--theories',nargs='+',required=True);ap.add_argument('--conjectures',required=True)
    ap.add_argument('--timeout',type=int,default=60);ap.add_argument('--seed-mode',choices=['none','python-weekday'],default='none');ap.add_argument('--limit',type=int);ap.add_argument('--outdir',required=True)
    a=ap.parse_args();exe=find_exe(a.exe);od=Path(a.outdir);od.mkdir(parents=True,exist_ok=True);cs=extract_conjectures(a.conjectures);cs=cs[:a.limit] if a.limit else cs
    print(f'[INFO] runner revision: {REV}\n[INFO] TPTP frontend: {exe}\n[INFO] conjectures: {len(cs)} seed={a.seed_mode}')
    rows=[]
    for tp in map(Path,a.theories):
        theory=strip_conjectures(tp.read_text(encoding='utf-8',errors='replace'));h=sha256_file(tp);print(f'\n== {tp.name} | {len(cs)} conjectures | seed={a.seed_mode} ==')
        for i,(n,c) in enumerate(cs,1):
            st,rs,sec=run_one(exe,theory,c,a.timeout,a.seed_mode,od/'logs'/tp.stem/f'{n}.log');print(f'[{i:03d}/{len(cs):03d}] {n:<42} {st:<28} {sec:8.3f}s',flush=True)
            rows.append({'prover':'Z3-TPTP','executable':exe,'theory':str(tp),'theory_name':tp.name,'theory_sha256':h,'conjecture':n,'status':st,'raw_status':rs,'seconds':f'{sec:.6f}','timeout_s':a.timeout,'seed_mode':a.seed_mode})
            if st=='ERROR_CONTRADICTORY_AXIOMS':
                print('[FATAL] contradictory axioms detected; stopping immediately.',file=sys.stderr)
                break
        if rows and rows[-1]['status']=='ERROR_CONTRADICTORY_AXIOMS': break
    if rows:
        with open(od/'results.csv','w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (od/'run_metadata.json').write_text(json.dumps({'runner_revision':REV,'tptp_frontend':exe,'conjecture_file':a.conjectures,'seed_mode':a.seed_mode,'timeout_s':a.timeout,'theories':a.theories},indent=2)+'\n')
    print(f'\n[OK] wrote {od/"results.csv"}')
if __name__=='__main__':main()
