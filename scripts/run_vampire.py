#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,csv,json,os,re,shutil,signal,subprocess,sys,time,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_conjectures,strip_conjectures,seed_weekdays,sha256_file
REV='2026-08-29-portable-final'

def find_exe(arg):
    c=[]
    if arg: c.append(arg)
    if os.environ.get('VAMPIRE_EXE'): c.append(os.environ['VAMPIRE_EXE'])
    for n in ('vampire-main','vampire'):
        w=shutil.which(n)
        if w: c.append(w)
    for x in c:
        if x and Path(x).exists() and os.access(x,os.X_OK): return str(Path(x).resolve())
    raise SystemExit('[ERROR] cannot find Vampire. Set --exe or VAMPIRE_EXE.')

def kill_group(p):
    try: os.killpg(os.getpgid(p.pid),signal.SIGKILL)
    except Exception:
        try:p.kill()
        except Exception:pass
    try:p.wait(timeout=2)
    except Exception:pass

def classify(out, timed):
    if timed:return 'TIMEOUT','Timeout'
    m=re.search(r'SZS status\s+(\w+)',out)
    s=m.group(1) if m else 'Unknown'
    if s=='Theorem': return 'THEOREM',s
    if s=='CounterSatisfiable': return 'COUNTERSAT',s
    if s=='Satisfiable': return 'SAT',s
    if s=='ContradictoryAxioms': return 'ERROR_CONTRADICTORY_AXIOMS',s
    low=out.lower()
    if any(x in low for x in ['syntax error','user error','parsing','type error']):return 'INPUT_ERROR',s
    return 'UNKNOWN',s

def run_one(exe, theory_text, conj, timeout, seed_mode, logpath):
    seed=seed_weekdays(conj) if seed_mode=='python-weekday' else ''
    problem=theory_text.rstrip()+'\n\n'+seed+conj+'\n'
    with tempfile.NamedTemporaryFile('w',suffix='.tff',delete=False,encoding='utf-8') as f:
        f.write(problem); tmp=f.name
    cmd=[exe,'--mode','casc','-qa','plain','--time_limit',str(timeout),tmp]
    t=time.perf_counter(); timed=False
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        try: out,err=p.communicate(timeout=timeout+2)
        except subprocess.TimeoutExpired:
            timed=True; kill_group(p); out,err='','PYTHON_WALLCLOCK_TIMEOUT'
    finally:
        try:Path(tmp).unlink()
        except Exception:pass
    elapsed=time.perf_counter()-t; raw=(out or '')+(err or '')
    status,szs=classify(raw,timed)
    if status not in ('THEOREM',):
        logpath.parent.mkdir(parents=True,exist_ok=True); logpath.write_text(raw,encoding='utf-8',errors='replace')
    return status,szs,elapsed

def main():
    ap=argparse.ArgumentParser(description='Run Vampire independently on sound theory tiers; no hidden seeding by default.')
    ap.add_argument('--exe'); ap.add_argument('--theories',nargs='+',required=True); ap.add_argument('--conjectures',required=True)
    ap.add_argument('--timeout',type=int,default=60); ap.add_argument('--seed-mode',choices=['none','python-weekday'],default='none')
    ap.add_argument('--limit',type=int); ap.add_argument('--outdir',required=True)
    ap.add_argument('--continue-on-contradiction',action='store_true',help='Do not use for paper runs; default is fail-fast.')
    a=ap.parse_args(); exe=find_exe(a.exe); outdir=Path(a.outdir); outdir.mkdir(parents=True,exist_ok=True)
    conjs=extract_conjectures(a.conjectures); conjs=conjs[:a.limit] if a.limit else conjs
    print(f'[INFO] runner revision: {REV}\n[INFO] executable: {exe}\n[INFO] conjectures: {len(conjs)} seed={a.seed_mode}')
    fields=['prover','executable','theory','theory_name','theory_sha256','conjecture','status','raw_status','seconds','timeout_s','seed_mode']
    csvpath=outdir/'results.csv'
    with open(csvpath,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); f.flush()
        for tp in map(Path,a.theories):
            theory=strip_conjectures(tp.read_text(encoding='utf-8',errors='replace')); thash=sha256_file(tp)
            print(f'\n== {tp.name} | {len(conjs)} conjectures | seed={a.seed_mode} ==')
            for i,(name,conj) in enumerate(conjs,1):
                log=outdir/'logs'/tp.stem/f'{name}.log'
                st,szs,sec=run_one(exe,theory,conj,a.timeout,a.seed_mode,log)
                print(f'[{i:03d}/{len(conjs):03d}] {name:<42} {st:<28} {sec:8.3f}s',flush=True)
                row={'prover':'Vampire','executable':exe,'theory':str(tp),'theory_name':tp.name,'theory_sha256':thash,'conjecture':name,'status':st,'raw_status':szs,'seconds':f'{sec:.6f}','timeout_s':a.timeout,'seed_mode':a.seed_mode}
                w.writerow(row); f.flush()
                if st=='ERROR_CONTRADICTORY_AXIOMS' and not a.continue_on_contradiction:
                    print(f'\n[FATAL] ContradictoryAxioms detected in {tp.name} on {name}.')
                    print(f'[FATAL] Partial results preserved at {csvpath}. Stop and inspect the log: {log}')
                    raise SystemExit(2)
    (outdir/'run_metadata.json').write_text(json.dumps({'runner_revision':REV,'executable':exe,'conjecture_file':a.conjectures,'seed_mode':a.seed_mode,'timeout_s':a.timeout,'theories':a.theories},indent=2)+'\n')
    print(f'\n[OK] wrote {csvpath}')
if __name__=='__main__':main()
