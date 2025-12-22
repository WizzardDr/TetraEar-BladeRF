"""
Final Verification Script
Runs all tests and generates a comprehensive report.
"""

import subprocess
import sys
import os
from datetime import datetime

def run_test(name, command, description):
    """Run a test and return result."""
    print(f"\n{'='*70}")
    print(f"Running: {name}")
    print(f"Description: {description}")
    print(f"Command: {command}")
    print('='*70)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        
        success = result.returncode == 0
        
        print("\nOutput:")
        print(result.stdout)
        
        if result.stderr and not success:
            print("\nErrors:")
            print(result.stderr)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\nResult: {status}")
        
        return {
            'name': name,
            'description': description,
            'success': success,
            'output': result.stdout,
            'error': result.stderr
        }
        
    except subprocess.TimeoutExpired:
        print("\n❌ TIMEOUT")
        return {
            'name': name,
            'description': description,
            'success': False,
            'output': '',
            'error': 'Test timed out after 60 seconds'
        }
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return {
            'name': name,
            'description': description,
            'success': False,
            'output': '',
            'error': str(e)
        }


def generate_report(results):
    """Generate a comprehensive test report."""
    report_lines = []
    report_lines.append("="*70)
    report_lines.append("TETRA DECODER - FINAL VERIFICATION REPORT")
    report_lines.append("="*70)
    report_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # Summary
    total = len(results)
    passed = sum(1 for r in results if r['success'])
    failed = total - passed
    
    report_lines.append("SUMMARY")
    report_lines.append("-"*70)
    report_lines.append(f"Total Tests: {total}")
    report_lines.append(f"Passed: {passed}")
    report_lines.append(f"Failed: {failed}")
    report_lines.append(f"Success Rate: {(passed/total*100):.1f}%")
    report_lines.append("")
    
    # Detailed Results
    report_lines.append("DETAILED RESULTS")
    report_lines.append("-"*70)
    
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        report_lines.append(f"\n{i}. {result['name']} - {status}")
        report_lines.append(f"   Description: {result['description']}")
        
        if not result['success'] and result['error']:
            report_lines.append(f"   Error: {result['error'][:200]}")
    
    report_lines.append("")
    report_lines.append("="*70)
    
    # Final verdict
    if passed == total:
        report_lines.append("✅ ALL TESTS PASSED - DECODER IS FULLY FUNCTIONAL")
    else:
        report_lines.append(f"⚠️  {failed} TEST(S) FAILED - REVIEW REQUIRED")
    
    report_lines.append("="*70)
    
    report = "\n".join(report_lines)
    
    # Print to console
    print("\n\n")
    print(report)
    
    # Save to file
    with open("TEST_REPORT.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("\nReport saved to: TEST_REPORT.txt")
    
    return passed == total


def main():
    """Run all verification tests."""
    print("\n" + "#"*70)
    print("# TETRA DECODER - FINAL VERIFICATION")
    print("#"*70)
    
    tests = [
        {
            'name': 'SDS & Voice Unit Tests',
            'command': 'python test_sds_voice.py',
            'description': 'Tests SDS fragmentation, voice decoding, and message parsing'
        },
        {
            'name': 'Codec Verification',
            'command': 'python verify_codec.py',
            'description': 'Verifies ACELP codec installation and functionality'
        },
        {
            'name': 'Live Demo',
            'command': 'python demo_live.py',
            'description': 'Demonstrates live message reconstruction and voice processing'
        }
    ]
    
    results = []
    
    for test in tests:
        result = run_test(test['name'], test['command'], test['description'])
        results.append(result)
    
    # Generate final report
    success = generate_report(results)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
