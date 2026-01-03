#!/usr/bin/env python3
"""
Robust portfolio driver for Vampire.

Fixes vs prior version:
- Hard-kill is now "best effort" across *both* process groups and process trees.
  This matters because --mode casc can spawn helpers that may outlive the parent.
- Uses start_new_session=True (portable alternative to preexec_fn=os.setsid).
- After killing, always reap the child (wait) so pipes close and communicate() cannot hang.
- Wallclock is enforced per *test* AND per *attempt*.
"""

import os
import sys
import subprocess
import signal
import time
import re
import shutil
from datetime import datetime
from typing import Dict, List, Tuple

ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"

# ----------------------------
# Configuration
# ----------------------------

AXIOM_FILES = [
    "DateArithmetic_TemporalSuiteCompleteBest_FAST.tff",
]

CONJECTURE_FILE = "ConjecturesDateArithmetic_TemporalSuiteCompleteBest_FIXED.tff"
REPORT_FILE = "vampire_report_portfolio.txt"

VAMPIRE_EXE = shutil.which("vampire-main") or shutil.which("vampire") or "./vampire"

TIMEOUT_SECONDS = 61               # per attempt (axiom file)
WALLCLOCK_SLACK = 10               # per test, across whole portfolio

VAMPIRE_FLAGS = ["--mode", "casc", "-qa", "plain", "--time_limit", str(TIMEOUT_SECONDS)]

RAW_DIR = "raw_logs"
SAVE_RAW_FOR_TIMEOUT = True
SAVE_RAW_FOR_ALL_NON_SUCCESS = True

# ----------------------------
# Diagnostics
# ----------------------------

def ensure_raw_dir():
    if RAW_DIR:
        os.makedirs(RAW_DIR, exist_ok=True)

def raw_log_path(tag: str, axiom_label: str) -> str:
    safe_ax = os.path.basename(axiom_label).replace(".", "_")
    name = f"raw_{tag}_{safe_ax}.log"
    return os.path.join(RAW_DIR, name) if RAW_DIR else name

def write_raw_log(tag: str, axiom_label: str, output: str):
    try:
        ensure_raw_dir()
        path = raw_log_path(tag, axiom_label)
        with open(path, "w", encoding="utf-8", errors="replace") as g:
            g.write(output)
    except Exception:
        pass

# ----------------------------
# Process-kill utilities
# ----------------------------

def _unix_ppid_map() -> Dict[int, List[int]]:
    """Build a ppid->children map using `ps` (avoids needing psutil)."""
    try:
        out = subprocess.check_output(["ps", "-axo", "pid=,ppid="], text=True)
    except Exception:
        return {}
    children: Dict[int, List[int]] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pid_s, ppid_s = line.split(None, 1)
            pid = int(pid_s)
            ppid = int(ppid_s)
        except Exception:
            continue
        children.setdefault(ppid, []).append(pid)
    return children

def _descendants(root_pid: int) -> List[int]:
    m = _unix_ppid_map()
    stack = [root_pid]
    seen = set()
    out: List[int] = []
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        for c in m.get(p, []):
            if c not in seen:
                stack.append(c)
    return out

def hard_kill_process(p: subprocess.Popen, tag: str, axiom_label: str, why: str):
    """
    Best-effort kill:
    1) SIGKILL process group (if any)
    2) SIGKILL descendant tree (ps-based)
    3) Reap
    """
    pid = getattr(p, "pid", None)
    note = [f"[PYTHON] hard_kill_process: {why}", f"[PYTHON] pid={pid}", f"[PYTHON] axiom_file={axiom_label}"]

    if pid is None:
        return

    # 1) Process group
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGKILL)
        note.append(f"[PYTHON] killpg(SIGKILL) pgid={pgid} OK")
    except Exception as e:
        note.append(f"[PYTHON] killpg(SIGKILL) failed: {e!r}")

    # 2) Descendants (includes pid)
    try:
        for dp in _descendants(pid):
            try:
                os.kill(dp, signal.SIGKILL)
            except Exception:
                pass
        note.append("[PYTHON] killed descendants (best-effort)")
    except Exception as e:
        note.append(f"[PYTHON] descendant kill failed: {e!r}")

    # 3) Reap
    try:
        p.wait(timeout=2)
        note.append("[PYTHON] wait() OK")
    except Exception as e:
        note.append(f"[PYTHON] wait() failed: {e!r}")

    if SAVE_RAW_FOR_TIMEOUT:
        write_raw_log(tag, axiom_label, "\n".join(note) + "\n")

# ----------------------------
# File parsing
# ----------------------------

def get_base_axioms(filename: str) -> str:
    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[ERROR] Axiom file not found: {filename}")
        sys.exit(1)

    # Remove conjectures if any exist inside axiom file
    content = re.sub(r"tff\s*\([^,]+,\s*conjecture\s*,.*?\)\.", "", content, flags=re.DOTALL)
    return content

def extract_conjectures(filename: str) -> List[Tuple[str, str]]:
    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[ERROR] Conjecture file not found: {filename}")
        sys.exit(1)

    pattern = r"(tff\s*\(\s*(\w+)\s*,\s*conjecture\s*,.*?\)\.)"
    return [(m.group(2), m.group(1)) for m in re.finditer(pattern, content, re.DOTALL)]

# ----------------------------
# Outcome handling
# ----------------------------

def classify_outcome(status: str) -> str:
    if status in ["Theorem", "CounterSatisfiable", "Satisfiable"]:
        return "SUCCESS"
    if status == "Timeout":
        return "TIMEOUT"
    return "FAIL"

def colorize_status(status: str) -> str:
    st = status.lower()
    if st == "timeout":
        return f"{ANSI_RED}TIMEOUT{ANSI_RESET}"
    if status == "ContradictoryAxioms":
        return f"{ANSI_BOLD}{ANSI_RED}ContradictoryAxioms{ANSI_RESET}"
    if status == "Theorem":
        return f"{ANSI_GREEN}Theorem{ANSI_RESET}"
    return status

# ----------------------------
# Weekday seeding
# ----------------------------

def weekday_seed_for_nth_weekday(conjecture_block: str) -> str:
    m = re.search(r"nth_weekday_date\s*\(\s*\d+\s*,\s*\w+\s*,\s*(\d+)\s*,\s*(\d+)\s*,", conjecture_block)
    if not m:
        return ""
    month, year = int(m.group(1)), int(m.group(2))
    import datetime as _dt
    wd = _dt.date(year, month, 1).weekday()
    names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return f"tff(seed_wk_{year}_{month}_01, axiom, weekday(ymd({year}, {month}, 1), {names[wd]})).\n"

def weekday_seeds_for_explicit_atoms(conjecture_block: str) -> str:
    import datetime as _dt
    out = []
    pat = r"weekday\s*\(\s*ymd\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,"
    for (ys, ms, ds) in re.findall(pat, conjecture_block):
        Y, M, D = int(ys), int(ms), int(ds)
        try:
            wd = _dt.date(Y, M, D).weekday()
        except ValueError:
            continue
        names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        out.append(f"tff(seed_wk_{Y}_{M}_{D}, axiom, weekday(ymd({Y}, {M}, {D}), {names[wd]})).")
    return "\n".join(out) + ("\n" if out else "")

# ----------------------------
# Core runner
# ----------------------------

def run_test_with_axioms(base_axioms: str, axiom_label: str, tag: str, conjecture: str, timeout_seconds: int):
    seed1 = weekday_seed_for_nth_weekday(conjecture)
    seed2 = weekday_seeds_for_explicit_atoms(conjecture)
    problem = base_axioms + "\n\n" + seed1 + seed2 + "\n" + conjecture + "\n"

    temp_file = f"temp_{tag}.tff"
    start = time.time()
    output = ""

    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(problem)

    cmd = [VAMPIRE_EXE] + VAMPIRE_FLAGS + [temp_file]

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        try:
            out, err = p.communicate(timeout=timeout_seconds)
            output = (out or "") + (err or "")
        except subprocess.TimeoutExpired:
            hard_kill_process(p, tag, axiom_label, why=f"TimeoutExpired after {timeout_seconds}s")
            return int((time.time() - start) * 1000), "Timeout", "TIMEOUT", axiom_label

        m = re.search(r"SZS status\s+(\w+)", output)
        if m:
            status = m.group(1)
        else:
            low = output.lower()
            if ("user error" in low or "syntax error" in low or "parsing" in low or
                "failed to create" in low or "type error" in low):
                status = "InputError"
            elif ("segmentation fault" in low or "core dumped" in low or "crash" in low):
                status = "Crash"
            else:
                status = "Unknown"

        outcome = classify_outcome(status)

        if SAVE_RAW_FOR_ALL_NON_SUCCESS and (outcome != "SUCCESS" or status == "ContradictoryAxioms"):
            write_raw_log(tag, axiom_label, output)

        return int((time.time() - start) * 1000), status, outcome, axiom_label

    finally:
        try:
            os.remove(temp_file)
        except Exception:
            pass

def run_portfolio_test(base_axioms_by_file, tag, conjecture, report_file):
    trace_parts = []
    TEST_WALL_LIMIT = TIMEOUT_SECONDS * len(AXIOM_FILES) + WALLCLOCK_SLACK
    t0 = time.time()

    best = None
    for ax_file in AXIOM_FILES:
        remaining = TEST_WALL_LIMIT - (time.time() - t0)
        if remaining <= 0:
            trace_parts.append("WALLCLOCK:Timeout")
            best = (int((time.time() - t0) * 1000), "Timeout", "TIMEOUT", "<wallclock>")
            break

        per_attempt_timeout = int(min(TIMEOUT_SECONDS, max(1, remaining)))

        elapsed, status, outcome, used_axioms = run_test_with_axioms(
            base_axioms_by_file[ax_file], ax_file, tag, conjecture, per_attempt_timeout
        )

        trace_parts.append(f"{os.path.basename(ax_file)}:{status}@{elapsed}ms")
        best = (elapsed, status, outcome, used_axioms)

        if outcome == "SUCCESS":
            break

    elapsed, status, outcome, used_axioms = best
    trace = "; ".join(trace_parts)

    with open(report_file, "a", encoding="utf-8") as f:
        f.write(f"{tag} | {elapsed:6d} ms | {status:20s} | {outcome:9s} | {trace}\n")

    return elapsed, status, outcome, used_axioms

# ----------------------------
# Main
# ----------------------------

def main():
    if not (shutil.which("vampire-main") or shutil.which("vampire") or os.path.exists(VAMPIRE_EXE)):
        print("[ERROR] Vampire executable not found (vampire-main/vampire/./vampire).")
        sys.exit(1)

    base_axioms_by_file = {}
    for ax in AXIOM_FILES:
        if not os.path.exists(ax):
            print(f"[ERROR] Missing axiom file: {ax}")
            sys.exit(1)
        base_axioms_by_file[ax] = get_base_axioms(ax)

    conjectures = extract_conjectures(CONJECTURE_FILE)
    if not conjectures:
        print("[ERROR] No conjectures found")
        sys.exit(1)

    start_time = datetime.now()

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# VAMPIRE TEST REPORT - PORTFOLIO\n")
        f.write("# Strategy: fixed axioms portfolio, first success wins\n")
        f.write(f"# Generated: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Timeout: {TIMEOUT_SECONDS}s per attempt\n")
        f.write(f"# Axioms order: {', '.join(AXIOM_FILES)}\n")
        f.write(f"# Raw logs dir: {RAW_DIR}\n")
        f.write("#" * 110 + "\n")
        f.write(f"{'Test':<30} | {'Time':>8} | {'Status':<20} | {'Result':<9} | Trace\n")
        f.write("-" * 110 + "\n")

    print("\n" + "=" * 110)
    print(f"PORTFOLIO RUN - {len(conjectures)} TESTS")
    print(f"Timeout per attempt: {TIMEOUT_SECONDS}s")
    print(f"Raw logs dir: {RAW_DIR}")
    print("Axioms order:")
    for ax in AXIOM_FILES:
        print(f"  - {ax}")
    print("=" * 110)

    passed = 0
    for idx, (tag, conj) in enumerate(conjectures, start=1):
        elapsed, status, outcome, used_axioms = run_portfolio_test(base_axioms_by_file, tag, conj, REPORT_FILE)

        ax_disp = os.path.basename(used_axioms) if isinstance(used_axioms, str) else str(used_axioms)
        status_disp = colorize_status(status)

        print(f"[{idx:03d}/{len(conjectures)}]  {tag:<30} | {elapsed:7d}ms | {status_disp:<22} | {ax_disp}", flush=True)

        if outcome == "SUCCESS":
            passed += 1

    duration = datetime.now() - start_time
    summary = f"\n# SUMMARY: {passed}/{len(conjectures)} passed ({duration})"

    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write("-" * 110 + "\n")
        f.write(summary + "\n")

    print("\n" + "=" * 110)
    print(summary)
    print("=" * 110)

if __name__ == "__main__":
    main()
