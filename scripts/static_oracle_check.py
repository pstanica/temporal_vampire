#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re, datetime, calendar, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.tptp_utils import extract_formula_blocks

ROOT = Path(__file__).resolve().parents[1]
CFILE = ROOT / 'conjectures' / 'ground_200_corrected.tff'
TDIR = ROOT / 'theories' / 'sound_tiers'
DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
PRIMARY = ('calc_date','weekday','nth_weekday_date','last_weekday_date',
           'calc_datetime','normalize_time','is_days_in_month')

def split_args(s: str):
    out=[]; dep=0; st=0
    for i,ch in enumerate(s):
        if ch=='(': dep+=1
        elif ch==')': dep-=1
        elif ch==',' and dep==0:
            out.append(s[st:i].strip()); st=i+1
    out.append(s[st:].strip())
    return out

def calls(text: str, name: str):
    pat=name+'('; out=[]; i=0
    while True:
        j=text.find(pat,i)
        if j<0: break
        k=j+len(pat); dep=1; st=k
        while k<len(text) and dep:
            if text[k]=='(': dep+=1
            elif text[k]==')': dep-=1
            k+=1
        if dep: break
        out.append(text[st:k-1]); i=k
    return out

def is_var(t: str):
    return bool(re.fullmatch(r'[A-Z][A-Za-z0-9_]*', t.strip()))

def bind(env: dict[str, object], term: str, value: object, issues: list[str], where: str):
    term=term.strip()
    if is_var(term):
        if term in env and env[term] != value:
            issues.append(f'{where}: variable {term} forced to both {env[term]} and {value}')
        else:
            env[term]=value
        return True
    return False

def ev(e: str, env: dict[str, object]):
    e=e.strip()
    if re.fullmatch(r'-?\d+',e): return int(e)
    if is_var(e) and isinstance(env.get(e), int): return env[e]
    for fn,op in [('$sum',lambda a,b:a+b),('$difference',lambda a,b:a-b),('$product',lambda a,b:a*b)]:
        if e.startswith(fn+'(') and e.endswith(')'):
            a=split_args(e[len(fn)+1:-1])
            if len(a)==2:
                x,y=ev(a[0],env),ev(a[1],env)
                if isinstance(x,int) and isinstance(y,int): return op(x,y)
    if e.startswith('$uminus(') and e.endswith(')'):
        x=ev(e[8:-1],env)
        return -x if isinstance(x,int) else None
    return None

def dayval(e: str, env: dict[str, object]):
    e=e.strip()
    if e in DAYS: return e
    if is_var(e) and env.get(e) in DAYS: return env[e]
    return None

def parse_equalities(f: str, env: dict[str, object], issues: list[str], name: str):
    # Ground equalities in this benchmark are simple variable=integer/day-name constraints.
    for v,n in re.findall(r'\b([A-Z][A-Za-z0-9_]*)\s*=\s*(-?\d+)\b',f):
        bind(env,v,int(n),issues,name)
    for n,v in re.findall(r'(-?\d+)\s*=\s*\b([A-Z][A-Za-z0-9_]*)\b',f):
        bind(env,v,int(n),issues,name)
    dayalt='|'.join(DAYS)
    for v,d in re.findall(rf'\b([A-Z][A-Za-z0-9_]*)\s*=\s*({dayalt})\b',f):
        bind(env,v,d,issues,name)
    for d,v in re.findall(rf'\b({dayalt})\s*=\s*([A-Z][A-Za-z0-9_]*)\b',f):
        bind(env,v,d,issues,name)

def nth_py(y,m,w,n):
    if n < 1: return None
    first=datetime.date(y,m,1); target=DAYS.index(w)
    d=1+(target-first.weekday())%7+7*(n-1)
    return None if d>calendar.monthrange(y,m)[1] else datetime.date(y,m,d)

def last_py(y,m,w):
    d=calendar.monthrange(y,m)[1]; z=datetime.date(y,m,d); target=DAYS.index(w)
    return z-datetime.timedelta(days=(z.weekday()-target)%7)

def norm(sh,sm,ah,am):
    tm=sm+am; ch,em=divmod(tm,60); th=sh+ah+ch; dd,eh=divmod(th,24)
    return eh,em,dd

def calc_dt(vals):
    Y,M,D,H,Min,AD,AH,AM=vals; eh,em,dd=norm(H,Min,AH,AM)
    z=datetime.date(Y,M,1)+datetime.timedelta(days=D+AD+dd-1)
    return z.year,z.month,z.day,eh,em

def leap_before(y):
    z=y-1; return z//4-z//100+z//400

def span(y,n): return 365*n+leap_before(y+n)-leap_before(y)

def bind_ymd(term: str, tup, env, issues, where):
    if not term.strip().startswith('ymd('): return False
    aa=split_args(term.strip()[4:-1])
    if len(aa)!=3: return False
    changed=False
    for t,v in zip(aa,tup):
        if is_var(t) and t not in env: changed=True
        bind(env,t,v,issues,where)
        x=ev(t,env)
        if x is not None and x!=v: issues.append(f'{where}: expected date coordinate {v}, encoded {x}')
    return changed

def bind_dt(term: str, tup, env, issues, where):
    if not term.strip().startswith('dt('): return False
    aa=split_args(term.strip()[3:-1])
    if len(aa)!=5: return False
    changed=False
    for t,v in zip(aa,tup):
        if is_var(t) and t not in env: changed=True
        bind(env,t,v,issues,where)
        x=ev(t,env)
        if x is not None and x!=v: issues.append(f'{where}: expected datetime coordinate {v}, encoded {x}')
    return changed

def ymd_value(term: str, env):
    term=term.strip()
    if not term.startswith('ymd('): return None
    aa=split_args(term[4:-1])
    if len(aa)!=3:return None
    vv=[ev(x,env) for x in aa]
    return tuple(vv) if all(isinstance(x,int) for x in vv) else None

def audit_conjecture(name: str, f: str, issues: list[str]):
    env={}; parse_equalities(f,env,issues,name)
    recognized_atoms=set()
    # Propagate outputs until stable. This handles combinations such as calc_date(...,ymd(Y,M,D)) & weekday(ymd(Y,M,D),W).
    for _ in range(8):
        before=dict(env)
        for idx,inn in enumerate(calls(f,'calc_date')):
            a=split_args(inn)
            if len(a)!=4: continue
            D,M,Y=[ev(x,env) for x in a[:3]]
            if all(isinstance(x,int) for x in (D,M,Y)) and Y>=1 and 1<=M<=12:
                try: z=datetime.date(Y,M,1)+datetime.timedelta(days=D-1)
                except (ValueError,OverflowError): continue
                bind_ymd(a[3],(z.year,z.month,z.day),env,issues,f'{name}/calc_date[{idx}]')
                recognized_atoms.add(('calc_date',idx))
        for idx,inn in enumerate(calls(f,'is_days_in_month')):
            a=split_args(inn)
            if len(a)!=3:continue
            M,Y=ev(a[0],env),ev(a[1],env)
            if isinstance(M,int) and isinstance(Y,int) and Y>=1 and 1<=M<=12:
                ex=calendar.monthrange(Y,M)[1]
                bind(env,a[2],ex,issues,f'{name}/is_days_in_month[{idx}]')
                got=ev(a[2],env)
                if got is not None and got!=ex:issues.append(f'{name}: month length expected {ex}, encoded {got}')
                recognized_atoms.add(('is_days_in_month',idx))
        for idx,inn in enumerate(calls(f,'nth_weekday_date')):
            a=split_args(inn)
            if len(a)!=5:continue
            N,M,Y=ev(a[0],env),ev(a[2],env),ev(a[3],env); w=dayval(a[1],env)
            if all(isinstance(x,int) for x in (N,M,Y)) and w in DAYS and Y>=1 and 1<=M<=12:
                z=nth_py(Y,M,w,N)
                if z is None:
                    issues.append(f'{name}: asks for nonexistent {N} occurrence of {w} in {Y}-{M:02d}')
                else:
                    bind_ymd(a[4],(z.year,z.month,z.day),env,issues,f'{name}/nth_weekday_date[{idx}]')
                recognized_atoms.add(('nth_weekday_date',idx))
        for idx,inn in enumerate(calls(f,'last_weekday_date')):
            a=split_args(inn)
            if len(a)!=4:continue
            w=dayval(a[0],env); M,Y=ev(a[1],env),ev(a[2],env)
            if w in DAYS and isinstance(M,int) and isinstance(Y,int) and Y>=1 and 1<=M<=12:
                z=last_py(Y,M,w)
                bind_ymd(a[3],(z.year,z.month,z.day),env,issues,f'{name}/last_weekday_date[{idx}]')
                recognized_atoms.add(('last_weekday_date',idx))
        for idx,inn in enumerate(calls(f,'normalize_time')):
            a=split_args(inn)
            if len(a)!=7:continue
            vals=[ev(x,env) for x in a[:4]]
            if all(isinstance(x,int) for x in vals):
                ex=norm(*vals)
                for t,v in zip(a[4:],ex): bind(env,t,v,issues,f'{name}/normalize_time[{idx}]')
                recognized_atoms.add(('normalize_time',idx))
        for idx,inn in enumerate(calls(f,'calc_datetime')):
            a=split_args(inn)
            if len(a)!=9:continue
            vals=[ev(x,env) for x in a[:8]]
            if all(isinstance(x,int) for x in vals) and vals[0]>=1 and 1<=vals[1]<=12:
                try: ex=calc_dt(vals)
                except (ValueError,OverflowError):continue
                bind_dt(a[8],ex,env,issues,f'{name}/calc_datetime[{idx}]')
                recognized_atoms.add(('calc_datetime',idx))
        for idx,inn in enumerate(calls(f,'weekday')):
            a=split_args(inn)
            if len(a)!=2:continue
            rv=ymd_value(a[0],env)
            if rv and rv[0]>=1:
                try: ex=DAYS[datetime.date(*rv).weekday()]
                except ValueError: continue
                w=dayval(a[1],env)
                if w is not None and w!=ex:issues.append(f'{name}: weekday expected {ex}, encoded {w} at {rv}')
                bind(env,a[1],ex,issues,f'{name}/weekday[{idx}]')
                recognized_atoms.add(('weekday',idx))
        if env==before: break

    # Simple guard checks used by the benchmark.
    for idx,inn in enumerate(calls(f,'valid_day')):
        a=split_args(inn)
        if len(a)==1:
            d=ev(a[0],env)
            if isinstance(d,int) and not (1<=d<=31): issues.append(f'{name}: valid_day({d}) is false')

    expected_atoms=[]
    for p in PRIMARY:
        expected_atoms.extend((p,i) for i,_ in enumerate(calls(f,p)))
    missing=[x for x in expected_atoms if x not in recognized_atoms]
    if missing:
        issues.append(f'{name}: oracle could not evaluate semantic atom(s): {missing}')
        return False
    if not expected_atoms:
        issues.append(f'{name}: no supported calendar-semantic atom found')
        return False
    return True

issues=[]; fully_checked=[]
blocks=extract_formula_blocks(CFILE.read_text(encoding='utf-8',errors='replace'))
conjs=[(n,b) for n,r,b,_,__ in blocks if r.lower()=='conjecture']
if len(conjs)!=200: issues.append(f'expected 200 conjectures, found {len(conjs)}')
for name,f in conjs:
    if audit_conjecture(name,f,issues): fully_checked.append(name)

# Sound theory files must not contain known legacy fragments; independently check every closed T3 anchor.
for p in sorted(TDIR.glob('*.tff')):
    t=p.read_text(encoding='utf-8',errors='replace')
    forbidden=['last_weekday_via_4th','nth_weekday_range','cache_scale_fwd_1m','rule_fwd_century']
    for x in forbidden:
        if x in t: issues.append(f'{p.name}: forbidden legacy fragment {x}')
    for n,r,b,_,__ in extract_formula_blocks(t):
        if r.lower()!='axiom':continue
        for inn in calls(b,'year_span_days'):
            a=split_args(inn)
            if len(a)==3:
                env={}; y,nn,dd=[ev(x,env) for x in a]
                if all(isinstance(x,int) for x in (y,nn,dd)) and y>0 and nn>0 and dd!=span(y,nn):
                    issues.append(f'{p.name}/{n}: year_span_days should be {span(y,nn)}, encoded {dd}')
        for inn in calls(b,'weekday'):
            a=split_args(inn)
            if len(a)==2:
                env={}; rv=ymd_value(a[0],env); w=dayval(a[1],env)
                if rv and w in DAYS and rv[0]>0:
                    try: ex=DAYS[datetime.date(*rv).weekday()]
                    except ValueError: continue
                    if w!=ex:issues.append(f'{p.name}/{n}: false weekday anchor; expected {ex}, encoded {w}')
        for inn in calls(b,'is_days_in_month'):
            a=split_args(inn)
            if len(a)==3:
                env={}; M,Y,L=[ev(x,env) for x in a]
                if all(isinstance(x,int) for x in (M,Y,L)) and Y>0 and 1<=M<=12:
                    ex=calendar.monthrange(Y,M)[1]
                    if L!=ex:issues.append(f'{p.name}/{n}: false month-length anchor; expected {ex}, encoded {L}')

print(f'[INFO] conjectures: {len(conjs)}')
print(f'[INFO] fully oracle-checked conjectures: {len(fully_checked)}')
if issues:
    print('[FAIL] static semantic audit found issues:')
    for x in issues: print(' -',x)
    raise SystemExit(2)
if len(fully_checked)!=200:
    raise SystemExit(f'[FAIL] expected 200 fully checked conjectures, found {len(fully_checked)}')
print('[OK] all 200 main conjectures agree with independent proleptic-Gregorian arithmetic')
print('[OK] closed Tier-3 weekday, month-length, and year-span anchors passed independent checks')
