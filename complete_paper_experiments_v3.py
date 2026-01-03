#!/usr/bin/env python3
"""complete_paper_experiments_v3.py

================================================================================
COMPLETE PAPER EXPERIMENT SUITE (v3)
Multi-theory scalability + portfolio category analysis (paper-ready)
================================================================================

This script produces paper-ready artifacts:
  • Multi-theory scalability measurements (forward/backward; basic vs weekday-coupled)
  • Portfolio report parsing (200-pass run) with per-category summaries and tier counts
  • PDF figures + LaTeX tables

Key robustness fixes vs v2:
  • Writes generated temporary .tff instances to /tmp using unique filenames to avoid
    macOS/NFS "Stale NFS file handle" failures.
  • Produces an additional consolidated scalability summary table (median/p90/max).

Usage:
  python3 complete_paper_experiments_v3.py

Expected inputs (in the working directory, unless you edit THEORY_FILES):
  - DateArithmetic_TemporalSuiteCompleteBest_FAST.tff
  - DateArithmetic_TemporalSuiteBest0_PORTFOLIO.tff
  - DateArithmetic_Best1_PORTFOLIO.tff
  - DateArithmetic_Completion_SAFE_HEAVY_PLUS_v3.tff
  - vampire_report_portfolio_200Pass.txt  (optional, for category analysis)

Outputs:
  paper_results_v3/
    experiment_results_v3.json
    latex_tables_v3.tex
    scalability_forward_multi.pdf
    scalability_backward_multi.pdf
    tier_distribution_by_category.pdf

================================================================================
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

# Optional plotting
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

# =============================================================================
# CONFIGURATION
# =============================================================================

# Theories to compare
THEORY_FILES: List[Tuple[str, str]] = [
    ("FAST",       "DateArithmetic_TemporalSuiteCompleteBest_FAST.tff"),
    ("Best0",      "DateArithmetic_TemporalSuiteBest0_PORTFOLIO.tff"),
    ("Best1",      "DateArithmetic_Best1_PORTFOLIO.tff"),
    ("SAFE_HEAVY", "DateArithmetic_Completion_SAFE_HEAVY_PLUS_v3.tff"),
]

# Run only a subset of labels if you want (e.g., {"FAST","Best0"})
RUN_LABELS: Optional[set] = None

# Timeouts
TIMEOUT_SECONDS = 120

# Scalability points (days)
FORWARD_POINTS  = [1, 10, 100, 365, 1000, 10000, 100000, 500000, 1000000]
BACKWARD_POINTS = [-1, -10, -100, -365, -1000, -10000, -100000, -500000, -1000000]

# Portfolio report (optional)
PORTFOLIO_REPORT = "vampire_report_portfolio_200Pass.txt"

# Output locations
OUTPUT_DIR   = "paper_results_v3"
LATEX_FILE   = os.path.join(OUTPUT_DIR, "latex_tables_v3.tex")
JSON_FILE    = os.path.join(OUTPUT_DIR, "experiment_results_v3.json")
FIG_SCAL_FWD = os.path.join(OUTPUT_DIR, "scalability_forward_multi.pdf")
FIG_SCAL_BWD = os.path.join(OUTPUT_DIR, "scalability_backward_multi.pdf")
FIG_TIER_BAR = os.path.join(OUTPUT_DIR, "tier_distribution_by_category.pdf")

# =============================================================================
# UTILITIES
# =============================================================================

def setup_output_directory() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"[OK] Output directory: {OUTPUT_DIR}/")


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def get_base_axioms(filename: str) -> str:
    """Extract all axioms etc. from a .tff, removing any conjectures present."""
    lines = read_file(filename).splitlines(True)
    filtered: List[str] = []
    in_conj = False
    for line in lines:
        # Conservative: if a conjecture block starts, omit until terminating ').'
        if re.search(r"^\s*tff\s*\([^,]+,\s*conjecture\b", line):
            in_conj = True
        if not in_conj:
            filtered.append(line)
        if in_conj and ")." in line:
            in_conj = False
    return "".join(filtered)


def detect_vampire() -> Optional[str]:
    """Return path to vampire binary if found, else None."""
    # Common names
    for cand in [
        os.environ.get("VAMPIRE"),
        shutil.which("vampire-main"),
        shutil.which("vampire"),
        shutil.which("vampire_z3_rel"),
    ]:
        if cand and os.path.exists(cand):
            return cand
    # If user has a local ./vampire
    if os.path.exists("./vampire"):
        return "./vampire"
    return None


def write_temp_tff(contents: str, prefix: str = "temp_", suffix: str = ".tff") -> str:
    """Write a temp file to /tmp to avoid NFS "stale handle" issues."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir="/tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


@dataclass
class VampireResult:
    elapsed_ms: int
    success: bool
    szs: str
    raw_out: str


def run_vampire(vampire_bin: str, base_content: str, days: int, mode: str) -> VampireResult:
    """Run Vampire on a generated conjecture under the given base theory content."""
    tag = f"{abs(days)}{'n' if days < 0 else 'p'}"

    if mode == "basic":
        conjecture = (
            f"tff(exp_b_{tag}, conjecture, "
            f"?[Y:$int, M:$int, D:$int]: "
            f"(calc_date($sum(1, {days}), 1, 2024, ymd(Y, M, D)) & valid_day(D)))."
        )
    elif mode == "weekday":
        conjecture = (
            f"tff(exp_w_{tag}, conjecture, "
            f"?[Y:$int, M:$int, D:$int, N:day_name]: "
            f"(calc_date($sum(1, {days}), 1, 2024, ymd(Y, M, D)) & "
            f"weekday(ymd(Y, M, D), N) & valid_day(D)))."
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    full_content = base_content + "\n" + conjecture + "\n"
    tmp_path = write_temp_tff(full_content, prefix=f"temp_{tag}_{mode}_")

    cmd = [vampire_bin, "--mode", "casc", "--time_limit", str(TIMEOUT_SECONDS), tmp_path]

    start = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS + 10)
        end = time.time()
        elapsed_ms = int((end - start) * 1000)

        out = (p.stdout or "") + "\n" + (p.stderr or "")
        success = (
            "SZS status Theorem" in out
            or "Refutation found" in out
            or "Termination reason: Refutation" in out
        )
        m = re.search(r"SZS status (\w+)", out)
        szs = m.group(1) if m else ("Theorem" if success else "Unknown")

        return VampireResult(elapsed_ms=elapsed_ms, success=success, szs=szs, raw_out=out)

    except subprocess.TimeoutExpired:
        return VampireResult(elapsed_ms=TIMEOUT_SECONDS * 1000, success=False, szs="Timeout", raw_out="")

    finally:
        safe_unlink(tmp_path)


def run_scalability(vampire_bin: str, theory_label: str, tff_file: str, points: Iterable[int]) -> List[Dict]:
    base_logic = get_base_axioms(tff_file)
    results: List[Dict] = []

    for d in points:
        years = round(abs(d) / 365.25, 1)

        r_basic = run_vampire(vampire_bin, base_logic, d, "basic")
        r_week  = run_vampire(vampire_bin, base_logic, d, "weekday")

        results.append({
            "theory": theory_label,
            "days": d,
            "years": years,
            "basic_ms": r_basic.elapsed_ms if r_basic.success else None,
            "weekday_ms": r_week.elapsed_ms if r_week.success else None,
            "basic_success": bool(r_basic.success),
            "weekday_success": bool(r_week.success),
            "basic_szs": r_basic.szs,
            "weekday_szs": r_week.szs,
        })

        status = "OK" if (r_basic.success and r_week.success) else "FAIL"
        print(
            f"  [{theory_label:<9}] {d:>12,} days | "
            f"basic={r_basic.elapsed_ms:>6} ms | wk={r_week.elapsed_ms:>6} ms | {status}"
        )

    return results


# =============================================================================
# PORTFOLIO PARSING + CATEGORY SUMMARY
# =============================================================================

def parse_portfolio_report(path: str) -> List[Dict]:
    """Parse lines: test_name |  123 ms | Theorem | SUCCESS | file1:...; file2:..."""
    if not os.path.exists(path):
        return []

    rows: List[Dict] = []
    for line in read_file(path).splitlines():
        if not line.startswith("test_"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        test = parts[0]
        m = re.search(r"(\d+)\s*ms", parts[1])
        if not m:
            continue
        time_ms = int(m.group(1))
        trace = parts[4]

        # Winner is typically the last mentioned .tff in the trace.
        files = re.findall(r"([A-Za-z0-9_]+\.tff)", trace)
        win = files[-1] if files else None
        tier = {
            "DateArithmetic_TemporalSuiteBest0_PORTFOLIO.tff": "Best0",
            "DateArithmetic_Best1_PORTFOLIO.tff": "Best1",
            "DateArithmetic_Completion_SAFE_HEAVY_PLUS_v3.tff": "SAFE_HEAVY",
        }.get(win, win or "UNKNOWN")

        rows.append({
            "test": test,
            "time_ms": time_ms,
            "win_file": win,
            "tier": tier,
            "trace": trace,
        })

    return rows


def classify_test(name: str) -> str:
    """Lightweight taxonomy based on test naming conventions."""
    # Keep this intentionally conservative; it should match your suite naming.
    if name.startswith("test_time_") or name.endswith("_time") or "time_" in name:
        return "Time normalization"
    if name.startswith("test_wk_") or "_wk_" in name or name.startswith("test_week"):
        return "Weekday"
    if name.startswith("test_sch_") or "_sch_" in name or "nth_" in name:
        return "Scheduling (nth weekday)"
    if name.startswith("test_accel_") or "accel" in name:
        return "Accelerators"
    if name.startswith("test_scale_"):
        return "Scalability microbench"
    if name.startswith("test_sub_") or ("back" in name and "wk" not in name and "comb" not in name):
        return "Backward arithmetic"
    if name.startswith("test_comb_") or name.startswith("test_comb"):
        return "Combined queries"
    if name.startswith("test_cent_") or name in {"test_1900", "test_2000", "test_1600"}:
        return "Century/leap edge"
    return "Core arithmetic"


def percentile(values: List[int], p: float) -> float:
    s = sorted(values)
    if not s:
        return float("nan")
    k = int(math.ceil(p * len(s))) - 1
    k = max(0, min(k, len(s) - 1))
    return float(s[k])


def summarize_by_category(rows: List[Dict]) -> List[Dict]:
    by_cat: Dict[str, List[Dict]] = {}
    for r in rows:
        cat = classify_test(r["test"])
        by_cat.setdefault(cat, []).append(r)

    summaries: List[Dict] = []
    for cat, lst in sorted(by_cat.items(), key=lambda kv: kv[0]):
        times = [x["time_ms"] for x in lst]
        tiers = [x["tier"] for x in lst]
        summaries.append({
            "category": cat,
            "n": len(lst),
            "median_ms": float(statistics.median(times)),
            "p90_ms": percentile(times, 0.90),
            "max_ms": float(max(times)),
            "best0": tiers.count("Best0"),
            "best1": tiers.count("Best1"),
            "safe_heavy": tiers.count("SAFE_HEAVY"),
        })

    return summaries


# =============================================================================
# SCALABILITY SUMMARY TABLE
# =============================================================================

def summarize_scalability(scalability_results: List[Dict]) -> List[Dict]:
    """Consolidated summary: theory × direction × mode -> n, success%, median, p90, max."""
    groups: Dict[Tuple[str, str, str], List[int]] = {}
    succ_counts: Dict[Tuple[str, str, str], int] = {}
    total_counts: Dict[Tuple[str, str, str], int] = {}

    for r in scalability_results:
        theory = r["theory"]
        direction = "forward" if r["days"] > 0 else "backward"

        for mode, key_ms, key_succ in [
            ("basic", "basic_ms", "basic_success"),
            ("weekday", "weekday_ms", "weekday_success"),
        ]:
            k = (theory, direction, mode)
            total_counts[k] = total_counts.get(k, 0) + 1
            if r.get(key_succ):
                succ_counts[k] = succ_counts.get(k, 0) + 1
            if r.get(key_ms) is not None:
                groups.setdefault(k, []).append(int(r[key_ms]))

    out: List[Dict] = []
    for (theory, direction, mode), times in sorted(groups.items()):
        total = total_counts[(theory, direction, mode)]
        succ = succ_counts.get((theory, direction, mode), 0)
        out.append({
            "theory": theory,
            "direction": direction,
            "mode": mode,
            "n": total,
            "success": succ,
            "success_pct": 100.0 * succ / max(1, total),
            "median_ms": float(statistics.median(times)) if times else float("nan"),
            "p90_ms": percentile(times, 0.90) if times else float("nan"),
            "max_ms": float(max(times)) if times else float("nan"),
        })

    return out


# =============================================================================
# OUTPUT: LaTeX + PLOTS
# =============================================================================

def generate_latex(category_summary: List[Dict], scal_summary: List[Dict]) -> None:
    with open(LATEX_FILE, "w", encoding="utf-8") as f:
        f.write("% ============================================================\n")
        f.write("% AUTO-GENERATED TABLES (v3)\n")
        f.write(f"% Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("% ============================================================\n\n")

        if category_summary:
            f.write("\\begin{table}[htbp]\n\\centering\n")
            f.write("\\caption{Per-category performance and winning tier distribution (portfolio run).}\n")
            f.write("\\label{tab:category_tiers}\n")
            f.write("\\begin{tabular}{@{}lrrrrrrr@{}}\n\\toprule\n")
            f.write("Category & $n$ & Median (ms) & P90 (ms) & Max (ms) & Best0 & Best1 & SAFE\\_HEAVY \\\\\n\\midrule\n")
            for r in category_summary:
                f.write(
                    f"{r['category']} & {r['n']} & {r['median_ms']:.0f} & {r['p90_ms']:.0f} & {r['max_ms']:.0f} "
                    f"& {r['best0']} & {r['best1']} & {r['safe_heavy']} \\\\\n"
                )
            f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n\n")

        if scal_summary:
            f.write("\\begin{table}[htbp]\n\\centering\n")
            f.write("\\caption{Consolidated scalability summary across theories (median/P90/max; milliseconds).}\n")
            f.write("\\label{tab:scalability_summary}\n")
            f.write("\\begin{tabular}{@{}lllrcrrr@{}}\n\\toprule\n")
            f.write("Theory & Direction & Mode & $n$ & Success & Median & P90 & Max \\\\\n\\midrule\n")
            for r in scal_summary:
                f.write(
                    f"{r['theory']} & {r['direction']} & {r['mode']} & {r['n']} & "
                    f"{r['success']}/{r['n']} ({r['success_pct']:.0f}\\%) & "
                    f"{r['median_ms']:.0f} & {r['p90_ms']:.0f} & {r['max_ms']:.0f} \\\\\n"
                )
            f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n\n")

    print(f"[OK] LaTeX written: {LATEX_FILE}")


def plot_scalability_multi(results: List[Dict], direction: str) -> None:
    if not HAS_MATPLOTLIB:
        return

    figpath = FIG_SCAL_FWD if direction == "fwd" else FIG_SCAL_BWD
    plt.figure(figsize=(10, 6))

    theories = sorted(set(r["theory"] for r in results))
    for theory in theories:
        rs = [r for r in results if r["theory"] == theory]

        xs = [abs(r["days"]) for r in rs if r.get("basic_ms") is not None]
        ys = [r["basic_ms"] for r in rs if r.get("basic_ms") is not None]
        if xs and ys:
            plt.plot(xs, ys, marker="o", linewidth=2, label=f"{theory} (basic)")

        xs2 = [abs(r["days"]) for r in rs if r.get("weekday_ms") is not None]
        ys2 = [r["weekday_ms"] for r in rs if r.get("weekday_ms") is not None]
        if xs2 and ys2:
            plt.plot(xs2, ys2, marker="s", linestyle="--", linewidth=2, label=f"{theory} (+weekday)")

    plt.xscale("log")
    plt.xlabel("Absolute offset (days, log scale)")
    plt.ylabel("Time (ms)")
    plt.title(("Forward" if direction == "fwd" else "Backward") + " scalability comparison")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(figpath, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Plot saved: {figpath}")


def plot_tier_distribution(category_summary: List[Dict]) -> None:
    if not HAS_MATPLOTLIB or not category_summary:
        return

    cats = [r["category"] for r in category_summary]
    best0 = [r["best0"] for r in category_summary]
    best1 = [r["best1"] for r in category_summary]
    sh = [r["safe_heavy"] for r in category_summary]

    x = range(len(cats))
    plt.figure(figsize=(12, 6))
    plt.bar(x, best0, label="Best0")
    plt.bar(x, best1, bottom=best0, label="Best1")
    bottom2 = [a + b for a, b in zip(best0, best1)]
    plt.bar(x, sh, bottom=bottom2, label="SAFE_HEAVY")
    plt.xticks(list(x), cats, rotation=30, ha="right")
    plt.ylabel("Solved count")
    plt.title("Winning tier distribution by category (portfolio run)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_TIER_BAR, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] Plot saved: {FIG_TIER_BAR}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    print("\n" + "=" * 88)
    print("  COMPLETE PAPER EXPERIMENT SUITE (v3)")
    print("  Multi-theory scalability + portfolio category analysis")
    print("=" * 88)

    setup_output_directory()

    # (B) Portfolio parsing
    portfolio_rows = parse_portfolio_report(PORTFOLIO_REPORT)
    category_summary = summarize_by_category(portfolio_rows) if portfolio_rows else []
    if portfolio_rows:
        print(f"[OK] Parsed portfolio report: {len(portfolio_rows)} tests")
    else:
        print("[NOTE] No portfolio report found (skipping category summary)")

    # (A) Scalability
    vampire_bin = detect_vampire()
    scalability_results: List[Dict] = []

    if vampire_bin:
        print(f"[OK] Vampire detected: {vampire_bin}")
        for label, tff in THEORY_FILES:
            if RUN_LABELS and label not in RUN_LABELS:
                continue
            if not os.path.exists(tff):
                print(f"[WARN] Theory file missing: {tff} (skipping {label})")
                continue

            print("\n" + "-" * 88)
            print(f"SCALABILITY: {label}  ({tff})")
            print("-" * 88)

            scalability_results += run_scalability(vampire_bin, label, tff, FORWARD_POINTS)
            scalability_results += run_scalability(vampire_bin, label, tff, BACKWARD_POINTS)

    else:
        print("[NOTE] Vampire not detected; skipping scalability runs.")

    scal_summary = summarize_scalability(scalability_results) if scalability_results else []

    out = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "vampire_cmd": vampire_bin,
            "timeout_seconds": TIMEOUT_SECONDS,
        },
        "category_summary": category_summary,
        "portfolio_rows": portfolio_rows,
        "scalability_results": scalability_results,
        "scalability_summary": scal_summary,
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[OK] JSON written: {JSON_FILE}")

    generate_latex(category_summary, scal_summary)

    if HAS_MATPLOTLIB:
        if scalability_results:
            plot_scalability_multi([r for r in scalability_results if r["days"] > 0], "fwd")
            plot_scalability_multi([r for r in scalability_results if r["days"] < 0], "bwd")
        plot_tier_distribution(category_summary)
    else:
        print("[NOTE] matplotlib not available; skipping figures.")

    print("\n[OK] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
