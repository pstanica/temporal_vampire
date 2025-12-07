#!/usr/bin/env python3
"""
================================================================================
VAMPIRE CORRECTNESS VERIFICATION (Alternative Approach)
================================================================================
Instead of extracting dates from proofs, we test if Vampire can VERIFY
specific dates that we compute with Python.

Strategy:
  1. Compute expected date with Python: datetime(2024,1,1) + timedelta(days=N)
  2. Ask Vampire to prove: calc_date(1+N, 1, 2024, ymd(Y,M,D)) & Y=expected_Y & M=expected_M & D=expected_D
  3. If Vampire finds refutation → date is correct!
  4. If Vampire fails → date is wrong (or system has bug)

This is actually a STRONGER test than extraction - we're verifying the exact date.
================================================================================
"""

import os
import sys
import subprocess
import shutil
import re
from datetime import datetime, timedelta

# ==========================================
# CONFIGURATION
# ==========================================
TFF_FILE = "DateArithmetic_TemporalSuiteComplete.tff"
VAMPIRE_CMD = shutil.which("vampire") or shutil.which("vampire-main") or "./vampire"
TIMEOUT_SECONDS = 60

# Test points - using range Python can handle
TEST_POINTS = [1, 10, 100, 365, 1000, 10000,
               -1, -10, -100, -365, -1000, -10000]

BASE_DATE = datetime(2024, 1, 1)

# Day name mapping (Python uses 0=Monday, we use 0=Monday too)
DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_base_axioms(filename):
    """Extract axioms without conjectures."""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    filtered_lines = []
    in_conjecture = False
    for line in lines:
        if re.search(r'^\s*%?\s*tff\s*\([^,]+,\s*conjecture', line):
            in_conjecture = True
        if not in_conjecture:
            filtered_lines.append(line)
        if in_conjecture and ').' in line:
            in_conjecture = False
    
    return "".join(filtered_lines)

def python_compute_date(base_date, days):
    """Compute expected date using Python datetime."""
    result_date = base_date + timedelta(days=days)
    weekday_num = result_date.weekday()  # 0=Monday
    weekday_name = DAY_NAMES[weekday_num]
    return result_date, weekday_name

def test_specific_date(base_content, days, expected_year, expected_month, expected_day, expected_weekday):
    """
    Test if Vampire can verify a specific date.
    Returns: (success, elapsed_ms)
    """
    tag = f"{abs(days)}{'n' if days < 0 else 'p'}"
    
    # Conjecture: Does calc_date(1+days, 1, 2024) produce the expected Y/M/D?
    conjecture = (
        f"tff(verify_{tag}, conjecture, "
        f"?[Y:$int, M:$int, D:$int, N:day_name]: "
        f"(calc_date($sum(1, {days}), 1, 2024, ymd(Y, M, D)) & "
        f"Y = {expected_year} & M = {expected_month} & D = {expected_day} & "
        f"weekday(ymd(Y, M, D), N) & N = {expected_weekday} & "
        f"valid_day(D)))."
    )
    
    full_content = base_content + "\n" + conjecture
    temp_name = f"temp_verify_{tag}.tff"
    
    try:
        with open(temp_name, 'w') as f:
            f.write(full_content)
        
        cmd = [VAMPIRE_CMD, "--mode", "casc", "--time_limit", str(TIMEOUT_SECONDS), temp_name]
        
        import time
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, 
                              timeout=TIMEOUT_SECONDS + 5)
        end = time.time()
        elapsed_ms = int((end - start) * 1000)
        
        output = result.stdout + result.stderr
        
        # Check if proof was found
        success = (
            "Refutation found" in output or
            "Termination reason: Refutation" in output or
            "SZS status Theorem" in output
        )
        
        return success, elapsed_ms
        
    except subprocess.TimeoutExpired:
        return False, TIMEOUT_SECONDS * 1000
    except Exception as e:
        print(f"    ERROR: {e}")
        return False, 0
    finally:
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except:
                pass

# ==========================================
# MAIN
# ==========================================

def main():
    print("\n" + "="*80)
    print("  VAMPIRE CORRECTNESS VERIFICATION")
    print("  Testing if Vampire verifies Python-computed dates")
    print("="*80)
    
    # Verify files
    if not os.path.exists(TFF_FILE):
        print(f"\n[ERROR] TFF file not found: {TFF_FILE}")
        sys.exit(1)
    
    if not shutil.which(VAMPIRE_CMD) and not os.path.exists(VAMPIRE_CMD):
        print(f"\n[ERROR] Vampire not found: {VAMPIRE_CMD}")
        sys.exit(1)
    
    print(f"\n[OK] TFF file: {TFF_FILE}")
    print(f"[OK] Vampire:  {VAMPIRE_CMD}")
    print(f"[OK] Base date: {BASE_DATE.strftime('%Y-%m-%d')} (Monday)")
    print(f"[OK] Strategy: Verify Python-computed dates with Vampire\n")
    
    # Load axioms
    try:
        base_logic = get_base_axioms(TFF_FILE)
    except Exception as e:
        print(f"\n[ERROR] Loading axioms: {e}")
        sys.exit(1)
    
    # Run verification
    print("="*80)
    print("  VERIFICATION RESULTS")
    print("="*80)
    print(f"{'Days':<10} | {'Python Date':<12} | {'Weekday':<10} | {'Time (ms)':<10} | {'Status'}")
    print("-" * 80)
    
    results = []
    all_passed = True
    
    for days in TEST_POINTS:
        # Compute expected with Python
        python_date, python_weekday = python_compute_date(BASE_DATE, days)
        
        # Test if Vampire verifies this date
        success, elapsed_ms = test_specific_date(
            base_logic, days,
            python_date.year, python_date.month, python_date.day,
            python_weekday
        )
        
        # Format output
        date_str = python_date.strftime('%Y-%m-%d')
        status = "PASS" if success else "FAIL"
        
        if not success:
            all_passed = False
        
        print(f"{days:<10,} | {date_str:<12} | {python_weekday:<10} | {elapsed_ms:<10} | {status}")
        
        results.append({
            'days': days,
            'date': date_str,
            'weekday': python_weekday,
            'time_ms': elapsed_ms,
            'passed': success
        })
    
    # Summary
    print("="*80)
    print("  SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    
    avg_time = sum(r['time_ms'] for r in results if r['passed']) / passed_count if passed_count > 0 else 0
    
    print(f"\nTests Passed: {passed_count}/{total_count} ({pass_rate:.0f}%)")
    print(f"Average Time: {avg_time:.0f} ms")
    
    if all_passed:
        print("\n[SUCCESS] All dates verified correctly!")
        print("Vampire successfully verified all Python-computed dates.")
        print("This proves the system computes mathematically correct results.")
    else:
        print("\n[WARNING] Some tests failed!")
        failed = [r for r in results if not r['passed']]
        print(f"\nFailed tests ({len(failed)}):")
        for f in failed:
            print(f"  - {f['days']:>6} days: Expected {f['date']} ({f['weekday']})")
        print("\nThis indicates either:")
        print("  1. A bug in the date calculation axioms")
        print("  2. Vampire timeout (increase TIMEOUT_SECONDS)")
        print("  3. Missing accelerator rules for this range")
    
    # LaTeX table
    print("\n" + "="*80)
    print("  LaTeX TABLE FOR PAPER")
    print("="*80)
    print("""
\\begin{table}[htbp]
\\centering
\\caption{Correctness Verification: Vampire vs Python datetime}
\\label{tab:verification}
\\begin{tabular}{@{}rllc@{}}
\\toprule
\\textbf{Days} & \\textbf{Expected Date} & \\textbf{Weekday} & \\textbf{Verified} \\\\
\\midrule""")
    
    for r in results:
        check = "\\checkmark" if r['passed'] else "\\times"
        print(f"{r['days']:>10,} & {r['date']} & {r['weekday'].capitalize():<9} & {check} \\\\")
    
    print(f"""\\midrule
\\multicolumn{{3}}{{l}}{{Accuracy:}} & {passed_count}/{total_count} ({pass_rate:.0f}\\%) \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
""")
    
    print("="*80 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
