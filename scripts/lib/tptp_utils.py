from __future__ import annotations
from pathlib import Path
import re, hashlib, datetime
from typing import List, Tuple, Dict

FORMULA_START = re.compile(r'(?m)^\s*(tff|fof|cnf|thf)\s*\(')

def sha256_file(path: str|Path) -> str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def _find_formula_end(text: str, start: int) -> int:
    # start at beginning of tff/fof token. Scan parentheses, respecting single quotes and comments.
    i=text.find('(', start)
    if i<0: return -1
    depth=0; in_sq=False; line_comment=False; block_comment=False
    n=len(text)
    while i<n:
        c=text[i]; nxt=text[i+1] if i+1<n else ''
        if line_comment:
            if c=='\n': line_comment=False
            i+=1; continue
        if block_comment:
            if c=='*' and nxt=='/': block_comment=False; i+=2; continue
            i+=1; continue
        if not in_sq and c=='%': line_comment=True; i+=1; continue
        if not in_sq and c=='/' and nxt=='*': block_comment=True; i+=2; continue
        if c=="'":
            # TPTP single quoted atoms escape quote by backslash
            if i==0 or text[i-1] != '\\': in_sq=not in_sq
            i+=1; continue
        if not in_sq:
            if c=='(': depth+=1
            elif c==')':
                depth-=1
                if depth==0:
                    j=i+1
                    while j<n and text[j].isspace(): j+=1
                    if j<n and text[j]=='.': return j+1
                    return i+1
        i+=1
    return -1

def extract_formula_blocks(text: str) -> List[Tuple[str,str,str,int,int]]:
    out=[]; pos=0
    while True:
        m=FORMULA_START.search(text,pos)
        if not m: break
        start=m.start(); end=_find_formula_end(text,start)
        if end<0: break
        block=text[start:end]
        hm=re.match(r'\s*(tff|fof|cnf|thf)\s*\(\s*([^,\s]+)\s*,\s*([^,\s]+)', block, re.S)
        if hm: out.append((hm.group(2), hm.group(3), block, start, end))
        pos=end
    return out

def extract_conjectures(path: str|Path) -> List[Tuple[str,str]]:
    text=Path(path).read_text(encoding='utf-8',errors='replace')
    return [(name,block) for name,role,block,_,__ in extract_formula_blocks(text) if role.lower()=='conjecture']

def strip_conjectures(text: str) -> str:
    blocks=extract_formula_blocks(text)
    spans=[(s,e) for _,role,_,s,e in blocks if role.lower()=='conjecture']
    if not spans: return text
    parts=[]; last=0
    for s,e in spans:
        parts.append(text[last:s]); last=e
    parts.append(text[last:]); return ''.join(parts)

def remove_named_formulas(text: str, names: set[str]) -> tuple[str,list[str]]:
    blocks=extract_formula_blocks(text)
    spans=[]; removed=[]
    for name,role,block,s,e in blocks:
        if name in names:
            spans.append((s,e)); removed.append(name)
    if not spans: return text,removed
    parts=[]; last=0
    for s,e in spans:
        parts.append(text[last:s]); last=e
    parts.append(text[last:])
    return ''.join(parts),removed

def formula_by_name(text: str, name: str) -> str|None:
    for n,role,b,s,e in extract_formula_blocks(text):
        if n==name: return b
    return None

def seed_weekdays(conjecture: str) -> str:
    out=[]; seen=set()
    names=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    # first of month for nth weekday
    pat_n=r'nth_weekday_date\s*\(\s*\d+\s*,\s*\w+\s*,\s*(\d+)\s*,\s*(\d+)\s*,'
    for ms,ys in re.findall(pat_n,conjecture):
        Y,M,D=int(ys),int(ms),1
        try: wd=datetime.date(Y,M,D).weekday()
        except ValueError: continue
        key=(Y,M,D)
        if key not in seen:
            out.append(f'tff(seed_wk_{Y}_{M}_{D}, axiom, weekday(ymd({Y}, {M}, {D}), {names[wd]})).')
            seen.add(key)
    pat=r'weekday\s*\(\s*ymd\s*\(\s*(-?\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,'
    for ys,ms,ds in re.findall(pat,conjecture):
        Y,M,D=int(ys),int(ms),int(ds)
        try: wd=datetime.date(Y,M,D).weekday()
        except ValueError: continue
        key=(Y,M,D)
        if key not in seen:
            out.append(f'tff(seed_wk_{Y}_{M}_{D}, axiom, weekday(ymd({Y}, {M}, {D}), {names[wd]})).')
            seen.add(key)
    return '\n'.join(out)+('\n' if out else '')
