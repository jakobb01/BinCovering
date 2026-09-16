"""
Parallel runner for True Uniform DNF experiments.
Runs multiple experiments with different N values in parallel using all available CPU cores.
Supports both SWAPS and PERMUTATIONS modes.
"""
"""
# Default: Run n=10k, 20k, 30k, ... 100k using all CPU cores (swaps mode)
python3 custom_code/main_TrueUniform_Parallel.py

# Custom range
python3 custom_code/main_TrueUniform_Parallel.py --start 10000 --end 50000 --step 10000

# Specific N values
python3 custom_code/main_TrueUniform_Parallel.py -n 10000 25000 50000 75000 100000

# Limit workers (e.g., use only 4 cores)
python3 custom_code/main_TrueUniform_Parallel.py -w 4

# With custom swap step
python3 custom_code/main_TrueUniform_Parallel.py -s 10

# Use PERMUTATIONS mode instead of swaps
python3 custom_code/main_TrueUniform_Parallel.py --mode permutation

# Permutations with custom number
python3 custom_code/main_TrueUniform_Parallel.py --mode permutation --num-permutations 5000
"""


import sys
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse

# Add path for imports

from main_TrueUniform_DNF import run_true_uniform_dnf_experiment
from main_TrueUniform_Permutation_DNF import run_true_uniform_permutation_experiment


def run_swap_experiment_wrapper(args):
    """
    Wrapper function to run a single SWAP experiment.
    Args is a tuple of (num_items, swap_step, max_swaps, data_path)
    """
    num_items, swap_step, max_swaps, data_path = args
    print(f"\n[PID {os.getpid()}] Starting SWAP experiment with n={num_items}")
    try:
        csv_path = run_true_uniform_dnf_experiment(
            num_items=num_items,
            swap_step=swap_step,
            max_swaps=max_swaps,
            data_path=data_path
        )
        print(f"\n[PID {os.getpid()}] Completed SWAP experiment with n={num_items}")
        return (num_items, csv_path, None)
    except Exception as e:
        print(f"\n[PID {os.getpid()}] Error in SWAP experiment with n={num_items}: {e}")
        return (num_items, None, str(e))


def run_permutation_experiment_wrapper(args):
    """
    Wrapper function to run a single PERMUTATION experiment.
    Args is a tuple of (num_items, num_permutations, data_path)
    """
    num_items, num_permutations, data_path = args
    print(f"\n[PID {os.getpid()}] Starting PERMUTATION experiment with n={num_items}")
    try:
        csv_path = run_true_uniform_permutation_experiment(
            num_items=num_items,
            num_permutations=num_permutations,
            data_path=data_path
        )
        print(f"\n[PID {os.getpid()}] Completed PERMUTATION experiment with n={num_items}")
        return (num_items, csv_path, None)
    except Exception as e:
        print(f"\n[PID {os.getpid()}] Error in PERMUTATION experiment with n={num_items}: {e}")
        return (num_items, None, str(e))


def run_parallel_experiments(n_values, mode='swap', swap_step=1, max_swaps=None, 
                             num_permutations=None, data_path="./data/", num_workers=None):
    """
    Run multiple experiments in parallel.
    
    Args:
        n_values: list of num_items values to run
        mode: 'swap' or 'permutation'
        swap_step: step size for swaps (default 1) - only for swap mode
        max_swaps: max swaps per experiment (default = 16*num_items) - only for swap mode
        num_permutations: number of permutations (default = 10*num_items) - only for permutation mode
        data_path: path to store data files
        num_workers: number of parallel workers (default = CPU count)
    
    Returns:
        dict: results mapping n -> csv_path or error
    """
    if num_workers is None:
        num_workers = multiprocessing.cpu_count()
    
    mode_str = "SWAPS" if mode == 'swap' else "PERMUTATIONS"
    
    print(f"\n{'='*70}")
    print(f"PARALLEL TRUE UNIFORM DNF EXPERIMENTS ({mode_str})")
    print(f"{'='*70}")
    print(f"CPU cores available: {multiprocessing.cpu_count()}")
    print(f"Workers to use: {num_workers}")
    print(f"Experiments to run: {len(n_values)}")
    print(f"N values: {n_values}")
    print(f"Mode: {mode_str}")
    if mode == 'swap':
        print(f"Swap step: {swap_step}, Max swaps: {max_swaps if max_swaps else '16*N'}")
    else:
        print(f"Num permutations: {num_permutations if num_permutations else '10*N'}")
    print(f"{'='*70}\n")
    
    # Prepare arguments for each experiment
    if mode == 'swap':
        experiment_args = [
            (n, swap_step, max_swaps, data_path) for n in n_values
        ]
        wrapper_func = run_swap_experiment_wrapper
    else:
        experiment_args = [
            (n, num_permutations, data_path) for n in n_values
        ]
        wrapper_func = run_permutation_experiment_wrapper
    
    results = {}
    
    # Use ProcessPoolExecutor to run experiments in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        future_to_n = {
            executor.submit(wrapper_func, args): args[0] 
            for args in experiment_args
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_n):
            n = future_to_n[future]
            try:
                num_items, csv_path, error = future.result()
                if error:
                    results[num_items] = {'status': 'error', 'error': error}
                else:
                    results[num_items] = {'status': 'success', 'csv_path': csv_path}
            except Exception as e:
                results[n] = {'status': 'error', 'error': str(e)}
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"SUMMARY ({mode_str})")
    print(f"{'='*70}")
    
    successful = 0
    failed = 0
    for n in sorted(results.keys()):
        result = results[n]
        if result['status'] == 'success':
            print(f"  n={n:>6}: SUCCESS -> {result['csv_path']}")
            successful += 1
        else:
            print(f"  n={n:>6}: FAILED  -> {result['error']}")
            failed += 1
    
    print(f"\nTotal: {successful} successful, {failed} failed")
    print(f"{'='*70}\n")
    
    return results


def main():
    """Main entry point for parallel experiment runner."""
    parser = argparse.ArgumentParser(
        description='Run multiple True Uniform DNF experiments in parallel (swaps or permutations)'
    )
    parser.add_argument(
        '--start', '-a',
        type=int,
        default=10000,
        help='Starting N value (default: 10000)'
    )
    parser.add_argument(
        '--end', '-b',
        type=int,
        default=100000,
        help='Ending N value (default: 100000)'
    )
    parser.add_argument(
        '--step', '-t',
        type=int,
        default=10000,
        help='Step between N values (default: 10000)'
    )
    parser.add_argument(
        '-n', '--n-values',
        type=int,
        nargs='+',
        default=None,
        help='Specific N values to run (overrides start/end/step)'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['swap', 'permutation'],
        default='swap',
        help='Experiment mode: swap or permutation (default: swap)'
    )
    parser.add_argument(
        '-s', '--swap-step',
        type=int,
        default=1,
        help='Step size for number of swaps - swap mode only (default: 1)'
    )
    parser.add_argument(
        '-m', '--max-swaps',
        type=int,
        default=None,
        help='Maximum number of swaps per experiment - swap mode only (default: 16 * num-items)'
    )
    parser.add_argument(
        '--num-permutations',
        type=int,
        default=None,
        help='Number of permutations per experiment - permutation mode only (default: 10 * num-items)'
    )
    parser.add_argument(
        '-p', '--path',
        type=str,
        default='./data/',
        help='Path to store data files (default: ./data/)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=None,
        help='Number of parallel workers (default: number of CPU cores)'
    )
    
    args = parser.parse_args()
    
    # Determine N values to run
    if args.n_values:
        n_values = args.n_values
    else:
        n_values = list(range(args.start, args.end + 1, args.step))
    
    if not n_values:
        print("Error: No N values to run")
        sys.exit(1)
    
    # Run parallel experiments
    results = run_parallel_experiments(
        n_values=n_values,
        mode=args.mode,
        swap_step=args.swap_step,
        max_swaps=args.max_swaps,
        num_permutations=args.num_permutations,
        data_path=args.path,
        num_workers=args.workers
    )
    
    # Exit with error code if any failed
    if any(r['status'] == 'error' for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
