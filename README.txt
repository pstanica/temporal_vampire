================================================================================
FIRST-ORDER TEMPORAL ARITHMETIC WITH STRATIFIED AXIOMATIZATION
================================================================================
Implementation Repository

Authors: Adam Pease, Pantelimon Stanica
Naval Postgraduate School, CS & Math

This repository contains the complete TPTP implementation and experimental 
framework for the paper "First-Order Temporal Arithmetic with Stratified 
Axiomatization".

================================================================================
REPOSITORY CONTENTS
================================================================================

AXIOM FILES (TPTP Format - .tff files):
---------------------------------------
These files contain the stratified axiomatization of Gregorian calendar 
arithmetic in First-Order Logic.

1. DateArithmetic_TemporalSuiteBest0_PORTFOLIO.tff
   - Tier 1: Structural axioms only
   - Contains: leap year rules, month lengths, Zeller's congruence
   - Used for: queries solvable with pure calendar semantics
   
2. DateArithmetic_Best1_PORTFOLIO.tff
   - Tier 2: Structural + Normalization axioms
   - Contains: recursive date/time normalization predicates
   - Used for: queries requiring arithmetic offset computation
   
3. DateArithmetic_Completion_SAFE_HEAVY_PLUS_v3.tff
   - Tier 3: Structural + Normalization + Semantic anchors
   - Contains: ground facts that bound proof depth
   - Used for: backward queries and complex scheduling constraints
   
4. DateArithmetic_FAST_fragment.tff (optional)
   - FAST fragment: Gapped accelerator axioms only
   - Contains: century/decade/quad-year jump axioms
   - Used for: demonstrating offset-independent behavior
   - Note: Intentionally incomplete (unsatisfiable for arbitrary queries)

CONJECTURE FILES:
----------------
5. temporal_conjectures_200.tff
   - Complete benchmark suite: 200 temporal reasoning queries
   - Categories: date arithmetic, leap years, weekdays, scheduling, 
                 normalization, scalability tests
   
PYTHON SCRIPTS:
--------------
6. run_hybrid_hardkill_safeheavy_v3.py
   - Primary experimental script
   - Runs the three-tier portfolio strategy
   - For each conjecture, attempts proof with Best0, Best1, SAFE_HEAVY in order
   - First success wins (timeout: 61s per tier)
   
7. complete_paper_experiments_v3.py
   - Comprehensive analysis script
   - Generates all tables, figures, and statistics for the paper
   - Requires output from run_hybrid_hardkill_safeheavy_v3.py

================================================================================
SYSTEM REQUIREMENTS
================================================================================

Required Software:
- Python 3.7 or higher
- Vampire theorem prover (https://vprover.github.io/)
  - Tested with Vampire 4.5+
  - Must be in system PATH or specify path in scripts
  
Python Libraries:
- Standard library only (no external dependencies for basic runs)
- Optional: matplotlib, pandas (for complete_paper_experiments_v3.py)

Operating System:
- Linux/Unix (recommended)
- macOS (compatible)
- Windows (with minor path adjustments)

================================================================================
QUICK START GUIDE
================================================================================

STEP 1: Run the Three-Tier Portfolio Experiment
-----------------------------------------------
This is the main experiment that validates the stratified axiomatization.

Command:
  python3 run_hybrid_hardkill_safeheavy_v3.py

What it does:
  - Loads all 200 conjectures from temporal_conjectures_200.tff
  - For each conjecture, attempts proof with:
    1. Best0 (structural axioms only)
    2. Best1 (adds normalization axioms) 
    3. SAFE_HEAVY (adds semantic anchors)
  - Stops at first success or after all three timeout
  - Timeout: 61 seconds per tier (183s maximum per conjecture)

Output:
  - Console: Real-time progress for each conjecture
  - File: vampire_report_portfolio_200Pass.txt
    * Contains: test name, time, status, winning tier
    * Format: tab-separated for easy parsing
  - Directory: raw_logs/ (detailed Vampire output for each attempt)

Expected runtime:
  - Complete suite: ~30-60 minutes (depends on hardware)
  - Most queries solve quickly; a few use full timeout before SAFE_HEAVY
  
Expected results:
  - 200/200 conjectures proved (100% success rate)
  - Distribution across tiers:
    * Best0: ~148 conjectures (structural queries, simple arithmetic)
    * Best1: ~24 conjectures (normalization-heavy queries)
    * SAFE_HEAVY: ~28 conjectures (backward arithmetic, complex scheduling)


STEP 2: Generate Paper Statistics and Figures
---------------------------------------------
This script analyzes the portfolio results and generates all experimental 
data reported in the paper.

Command:
  python3 complete_paper_experiments_v3.py

What it does:
  - Parses vampire_report_portfolio_200Pass.txt
  - Computes per-category statistics (median, P90, max times)
  - Generates tier distribution analysis
  - Creates scalability plots (if matplotlib installed)
  - Produces tables in LaTeX format

Input required:
  - vampire_report_portfolio_200Pass.txt (from Step 1)
  
Output:
  - Console: Summary statistics and LaTeX table code
  - Files (if applicable):
    * scalability_forward_multi.pdf
    * scalability_backward_multi.pdf
    * tier_distribution_by_category.pdf
    * latex_tables_v3.tex (all tables in paper-ready format)

Expected results:
  - Matches Table 2 (exhaustive results) in paper
  - Matches Table 3 (tier distribution) in paper
  - Matches Table 4 (scalability summary) in paper


STEP 3 (Optional): FAST Fragment Experiments
--------------------------------------------

To replicate the offset-independent behavior experiments (Section 10):

Command:
  python3 run_fast_fragment_experiments.py
  
What it does:
  - Tests DateArithmetic_FAST_fragment.tff on scalability queries
  - Compares FAST vs. Best0/Best1/SAFE_HEAVY across offset magnitudes
  - Demonstrates bounded proof depth (337-352ms constant time)

Note: The FAST fragment is intentionally incomplete and will fail on 
arbitrary temporal queries. It only succeeds on queries whose normalization 
paths are covered by the gapped accelerator axioms.

================================================================================
UNDERSTANDING THE RESULTS
================================================================================

Portfolio Strategy Success Patterns:
------------------------------------
Best0 Success:
  - Query types: weekday lookups, leap year tests, simple date properties
  - Why successful: Only structural reasoning needed
  - Example: "Is 2024 a leap year?" -> 24ms

Best1 Success:
  - Query types: forward date arithmetic, time normalization
  - Why successful: Normalization axioms enable offset computation
  - Example: "1000 days after Jan 1, 2024?" -> 1,847ms
  
SAFE_HEAVY Success:
  - Query types: backward arithmetic, complex scheduling, large offsets
  - Why successful: Semantic anchors collapse deep traversals
  - Example: "1461 days before March 1, 2028?" -> 396ms
  - Note: Typically timeout at Best0 and Best1 first (~120s total)

FAST Fragment Behavior:
  - Constant time (337-352ms) across 6 orders of magnitude
  - Only works for queries within gapped axiom coverage
  - Demonstrates proof-theoretic principle, not practical solver

================================================================================
FILE ORGANIZATION RECOMMENDATIONS
================================================================================

Recommended directory structure:

temporal-arithmetic/
├── README.txt (this file)
├── axioms/
│   ├── DateArithmetic_TemporalSuiteBest0_PORTFOLIO.tff
│   ├── DateArithmetic_Best1_PORTFOLIO.tff
│   ├── DateArithmetic_Completion_SAFE_HEAVY_PLUS_v3.tff
│   └── DateArithmetic_FAST_fragment.tff
├── conjectures/
│   └── temporal_conjectures_200.tff
├── scripts/
│   ├── run_hybrid_hardkill_safeheavy_v3.py
│   └── complete_paper_experiments_v3.py
├── results/
│   ├── vampire_report_portfolio_200Pass.txt
│   └── raw_logs/
└── figures/
    ├── scalability_forward_multi.pdf
    ├── scalability_backward_multi.pdf
    └── tier_distribution_by_category.pdf

================================================================================
TROUBLESHOOTING
================================================================================

Issue: "Vampire not found"
Solution: Install Vampire and add to PATH, or edit scripts to specify full path
  Example: VAMPIRE_PATH = "/usr/local/bin/vampire"

Issue: Script hangs on a conjecture
Solution: Some queries use full 61s timeout - this is expected behavior
  The hardkill mechanism ensures cleanup after timeout

Issue: Different timings than paper
Solution: Timings vary by hardware; tier distribution should match
  Vampire 4.5+ recommended; earlier versions may behave differently

Issue: FAST fragment fails on most queries
Solution: This is expected! FAST is intentionally incomplete
  Only use FAST for scalability experiments on covered queries

Issue: Python dependencies missing
Solution: For basic runs, only standard library needed
  For plots: pip install matplotlib pandas numpy

================================================================================
REPRODUCING PAPER RESULTS
================================================================================

To exactly reproduce the experimental results reported in the paper:

1. Run portfolio experiment:
   python3 run_hybrid_hardkill_safeheavy_v3.py
   
2. Verify 200/200 success rate in vampire_report_portfolio_200Pass.txt

3. Generate statistics:
   python3 complete_paper_experiments_v3.py
   
4. Compare output to paper tables:
   - Table 2 (tab:exhaustive_200): Per-category mean and range
   - Table 3 (tab:category_tiers): Tier distribution
   - Table 4 (tab:scalability_summary): Offset-independent behavior

Expected variance:
- Absolute timings: +/-20% (hardware dependent)
- Tier distribution: Exact match expected
- Success rate: 200/200 (100%) required

================================================================================
CITATION
================================================================================

If you use this implementation in your research, please cite (and update, after publication):

@article{PS2025temporal,
  title={First-Order Temporal Arithmetic with Stratified Axiomatization},
  author={Pease, Adam and St{\u{a}}nic{\u{a}}, Pantelimon},
  journal={[Journal Name]},
  year={2026},
  note={Naval Postgraduate School}
}

================================================================================
CONTACT
================================================================================

For questions, issues, or contributions:

Adam Pease
Department of Computer Science
Naval Postgraduate School
adam.pease@nps.edu

Pantelimon Stanica
Department of Applied Mathematics  
Naval Postgraduate School
pstanica@nps.edu

Repositories: 
https://github.com/pstanica/temporal_arithmetic, https://github.com/ontologyportal/sumo/tree/master/tests
Paper: [ArXiv/DOI link when available]

================================================================================
ACKNOWLEDGMENTS
================================================================================

This work was supported by NSWC/DoD.

We thank the Vampire development team for their excellent theorem prover.

================================================================================
VERSION HISTORY
================================================================================

v1.1 (January 2026)
- Initial release
- Complete implementation of stratified axiomatization
- 200 benchmark conjectures
- Three-tier portfolio strategy
- FAST fragment demonstrator

================================================================================
