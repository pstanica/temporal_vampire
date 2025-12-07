# This code will probe every conjecture from the tff file, using the axioms from the Temporal Suite
# and check if they are refuted by Vampire

import os
import sys
import subprocess
import time
import re
import shutil
from datetime import datetime

# ==========================================
# CONFIGURATION  
# ==========================================
AXIOM_FILE = "DateArithmetic_TemporalSuiteCompleteBest.tff"
CONJECTURE_FILE = "ConjecturesDateArithmetic_TemporalSuiteCompleteBest.tff"
REPORT_FILE = "vampire_conjecture_report.txt"

VAMPIRE_CMD = shutil.which("vampire-main") or shutil.which("vampire") or "./vampire"
TIMEOUT_SECONDS = 60
VAMPIRE_FLAGS = ["--mode", "casc", "-qa", "plain", "--time_limit", str(TIMEOUT_SECONDS)]

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_base_axioms(filename):
    """Extracts axioms/rules from the TFF file, skipping conjectures."""
    print(f"[INFO] Loading axioms from {filename}...")
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[ERROR] Axiom file not found: {filename}")
        sys.exit(1)
    
    # Remove all conjectures from the axiom file
    # Match tff(..., conjecture, ...). blocks and remove them
    content = re.sub(r'tff\s*\([^,]+,\s*conjecture\s*,.*?\)\.', '', content, flags=re.DOTALL)
    
    # Add activation hints
    content += "\ntff(activate_quad_year, axiom, rule_fwd_4year).\n"
    content += "tff(activate_year_jump, axiom, rule_fwd_year).\n"
    
    lines = content.split('\n')
    print(f"[INFO] Loaded base axioms ({len(lines)} lines).")
    return content

def extract_conjectures(filename):
    """Extract conjecture blocks - keep them COMPLETELY INTACT."""
    print(f"[INFO] Loading conjectures from {filename}...")
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[ERROR] Conjecture file not found: {filename}")
        sys.exit(1)
    
    # Match complete tff(..., conjecture, ...). blocks
    # Keep the ENTIRE block intact, including all formatting
    pattern = r'(tff\s*\(\s*(\w+)\s*,\s*conjecture\s*,.*?\)\.)'
    
    conjectures = []
    for match in re.finditer(pattern, content, re.DOTALL):
        full_block = match.group(1)  # The entire tff(...). block
        tag = match.group(2)          # Just the tag name
        conjectures.append((tag, full_block))
    
    print(f"[INFO] Extracted {len(conjectures)} conjectures.")
    return conjectures

def run_single_conjecture(base_content, tag, conjecture_block, report_file):
    """Runs one conjecture against Vampire and logs the result."""
    
    # Simply append the complete conjecture block to the axioms
    full_content = base_content + "\n\n" + conjecture_block + "\n"
    temp_name = f"temp_{tag}.tff"
    
    start_time = time.time()
    
    try:
        # Write the temporary TFF file
        with open(temp_name, 'w') as f:
            f.write(full_content)
            
        # Run Vampire
        cmd = [VAMPIRE_CMD] + VAMPIRE_FLAGS + [temp_name]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=TIMEOUT_SECONDS + 5
        )
        
        end_time = time.time()
        elapsed_ms = int((end_time - start_time) * 1000)
        
        output = result.stdout + result.stderr
        
        # Extract SZS Status
        szs_match = re.search(r'SZS status\s+(\w+)', output)
        szs_status = szs_match.group(1) if szs_match else "Unknown"
        
        # Determine Success/Failure
        if szs_status in ["Theorem", "CounterSatisfiable", "Satisfiable"]:
            outcome = "SUCCESS"
        elif "Timeout" in szs_status or "Termination reason: Time limit" in output:
            outcome = "TIMEOUT"
            elapsed_ms = TIMEOUT_SECONDS * 1000
        else:
            outcome = "FAIL"
            
        # Log the result
        with open(report_file, 'a') as f:
            f.write(f"{tag:<30} | {elapsed_ms:>10} ms | {szs_status:<20} | {outcome}\n")
            
        print(f"  > {tag:<25} | {elapsed_ms:>6} ms | {outcome:<8} | {szs_status}")
        
        return outcome == "SUCCESS"
        
    except subprocess.TimeoutExpired:
        elapsed_ms = TIMEOUT_SECONDS * 1000
        with open(report_file, 'a') as f:
            f.write(f"{tag:<30} | {elapsed_ms:>10} ms | Canceled(Timeout) | TIMEOUT\n")
        print(f"  > {tag:<25} | {elapsed_ms:>6} ms | {'TIMEOUT':<8} | Canceled")
        return False
        
    except FileNotFoundError:
        print(f"\n[CRITICAL ERROR] Vampire executable not found at: {VAMPIRE_CMD}")
        sys.exit(1)
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        with open(report_file, 'a') as f:
            f.write(f"{tag:<30} | {elapsed_ms:>10} ms | PythonError | FAIL\n")
        print(f"  > {tag:<25} | {elapsed_ms:>6} ms | {'FAIL':<8} | PythonError: {e}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except:
                pass

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    
    if not shutil.which(VAMPIRE_CMD) and not os.path.exists(VAMPIRE_CMD):
        print(f"[CRITICAL ERROR] Vampire executable not found.")
        sys.exit(1)
    
    # Load Axioms
    base_logic = get_base_axioms(AXIOM_FILE)
    
    # Load Conjectures  
    conjectures = extract_conjectures(CONJECTURE_FILE)
    
    if not conjectures:
        print("[ERROR] No conjectures found.")
        sys.exit(1)
        
    # Prepare Report
    start_run = datetime.now()
    with open(REPORT_FILE, 'w') as f:
        f.write(f"# VAMPIRE CONJECTURE EXECUTION REPORT\n")
        f.write(f"# Generated: {start_run.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total Conjectures: {len(conjectures)}\n")
        f.write("#" * 70 + "\n")
        f.write(f"{'Conjecture Tag':<30} | {'Time':<10} | {'SZS Status':<20} | Result\n")
        f.write("-" * 70 + "\n")

    print("\n" + "="*70)
    print(f"RUNNING {len(conjectures)} CONJECTURES")
    print("="*70)
    
    # Run Tests
    success_count = 0
    
    for tag, conjecture_block in conjectures:
        if run_single_conjecture(base_logic, tag, conjecture_block, REPORT_FILE):
            success_count += 1
            
    end_run = datetime.now()
    duration = end_run - start_run

    # Final Summary
    summary = f"\n# SUMMARY: {success_count}/{len(conjectures)} passed ({duration})"
    
    with open(REPORT_FILE, 'a') as f:
        f.write("-" * 70 + "\n")
        f.write(summary)

    print("\n" + "="*70)
    print(summary)
    print("="*70)

if __name__ == "__main__":
    main()