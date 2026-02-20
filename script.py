#!/usr/bin/env python3
"""
rotxter - Robots.txt Endpoint Checker
Author: Pevinkumar A
Version: 1.0
"""

import argparse
import sys
import re
from urllib.parse import urlparse, urljoin
import threading
from queue import Queue
from datetime import datetime
import json

# ANSI color codes
class Colors:
    WHITE = '\033[97m'
    BOLD_WHITE = '\033[1;97m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    GRAY = '\033[90m'
    CYAN = '\033[96m'

# Thread-safe queue and shared variables
queue = Queue()
results = []
lock = threading.Lock()
total_endpoints = 0
completed = 0

def print_banner(no_color=False):
    """Display tool banner"""
    if no_color:
        banner = """
╔══════════════════════════════════════════╗
║              ROTXTER v1.0                ║
║     Robots.txt Endpoint Checker Tool     ║
╠══════════════════════════════════════════╣
║  Author: Pevinkumar A                    ║
║  Version: 1.0                            ║
╚══════════════════════════════════════════╝
        """
    else:
        banner = f"""
{Colors.CYAN}╔══════════════════════════════════════════╗
║{Colors.BOLD_WHITE}              ROTXTER v1.0                {Colors.CYAN}║
║{Colors.WHITE}     Robots.txt Endpoint Checker Tool     {Colors.CYAN}║
╠══════════════════════════════════════════╣
║{Colors.YELLOW}  Author: Pevinkumar A                    {Colors.CYAN}║
║{Colors.YELLOW}  Version: 1.0                            {Colors.CYAN}║
╚══════════════════════════════════════════╝{Colors.RESET}
        """
    print(banner)

def normalize_url(url):
    """Normalize URL by adding scheme if missing"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url.rstrip('/')

def fetch_robots_txt(base_url):
    """Fetch robots.txt content"""
    import urllib.request
    import urllib.error
    
    robots_url = urljoin(base_url + '/', 'robots.txt')
    
    try:
        req = urllib.request.Request(robots_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8', errors='ignore')
            return content, robots_url
    except Exception as e:
        return None, robots_url

def parse_robots_txt(content):
    """Parse robots.txt and extract endpoints"""
    endpoints = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.lower().startswith(('disallow:', 'allow:', 'sitemap:')):
            parts = line.split(':', 1)
            if len(parts) == 2:
                path = parts[1].strip()
                if path and not path.startswith('#'):
                    endpoints.append(path)
    
    return endpoints

def check_endpoint(base_url, endpoint):
    """Check endpoint and return status code and size"""
    import urllib.request
    import urllib.error
    
    full_url = urljoin(base_url, endpoint)
    
    try:
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read()
            return response.getcode(), len(content), full_url
    except urllib.error.HTTPError as e:
        return e.code, 0, full_url
    except Exception as e:
        return None, 0, full_url

def worker(base_url, no_color):
    """Worker thread function"""
    global completed
    
    while True:
        try:
            endpoint = queue.get(timeout=1)
        except:
            break
            
        status, size, full_url = check_endpoint(base_url, endpoint)
        
        with lock:
            results.append({
                'endpoint': endpoint,
                'full_url': full_url,
                'status': status,
                'size': size
            })
            completed += 1
            
            # Print progress
            if not no_color:
                if status == 200:
                    status_color = Colors.GREEN
                elif status and 300 <= status < 400:
                    status_color = Colors.YELLOW
                elif status and 400 <= status < 500:
                    status_color = Colors.RED
                elif status and 500 <= status:
                    status_color = Colors.RED
                else:
                    status_color = Colors.GRAY
                
                print(f"\r{Colors.GRAY}[{completed}/{total_endpoints}]{Colors.RESET} Checking: {endpoint[:50]:<50} {status_color}{status if status else 'ERR'}{Colors.RESET}", end='')
            else:
                print(f"\r[{completed}/{total_endpoints}] Checking: {endpoint[:50]:<50} {status if status else 'ERR'}", end='')
        
        queue.task_done()

def get_interesting_endpoints(results):
    """Identify interesting endpoints based on status and patterns"""
    interesting = []
    interesting_patterns = [
        r'admin', r'login', r'api', r'backup', r'config', r'db',
        r'wp-', r'.git', r'.env', r'secret', r'private', r'dev',
        r'test', r'staging', r'debug', r'console', r'dashboard'
    ]
    
    for result in results:
        # Check if status code is interesting (200, 403, 401)
        if result['status'] in [200, 403, 401, 500]:
            # Check if endpoint matches interesting patterns
            endpoint_lower = result['endpoint'].lower()
            if any(re.search(pattern, endpoint_lower) for pattern in interesting_patterns):
                result['interesting'] = True
                interesting.append(result)
            elif result['status'] == 200:
                result['interesting'] = True
                interesting.append(result)
    
    return interesting

def export_results(results, interesting, filename, format='txt'):
    """Export results to file"""
    try:
        with open(filename, 'w') as f:
            if format == 'json':
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total': len(results),
                    'interesting': len(interesting),
                    'results': results
                }, f, indent=2)
            else:  # txt format
                f.write("ROTXTER Scan Results\n")
                f.write("=" * 50 + "\n")
                f.write(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Endpoints: {len(results)}\n")
                f.write(f"Interesting Endpoints: {len(interesting)}\n\n")
                
                f.write("ALL ENDPOINTS:\n")
                f.write("-" * 30 + "\n")
                for r in results:
                    f.write(f"{r['full_url']} | Status: {r['status']} | Size: {r['size']}\n")
                
                if interesting:
                    f.write("\n\nINTERESTING ENDPOINTS:\n")
                    f.write("-" * 30 + "\n")
                    for r in interesting:
                        f.write(f"{r['full_url']} | Status: {r['status']} | Size: {r['size']}\n")
        
        return True
    except Exception as e:
        return False

def main():
    parser = argparse.ArgumentParser(
        description='ROTXTER - Robots.txt Endpoint Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rotxter.py google.com
  python rotxter.py -f urls.txt
  python rotxter.py google.com -t 20 -o results.txt
  python rotxter.py google.com --no-color
  python rotxter.py google.com --interesting-only
        """
    )
    
    parser.add_argument('target', nargs='?', help='Target URL (e.g., google.com)')
    parser.add_argument('-f', '--file', help='Input file containing URLs')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Number of threads (default: 10)')
    parser.add_argument('-o', '--output', help='Output file for results')
    parser.add_argument('--format', choices=['txt', 'json'], default='txt', help='Output format (default: txt)')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    parser.add_argument('--interesting-only', action='store_true', help='Show only interesting endpoints')
    parser.add_argument('-r', '--robots', help='Custom robots.txt file path')
    
    args = parser.parse_args()
    
    if not args.target and not args.file:
        parser.print_help()
        sys.exit(1)
    
    print_banner(args.no_color)
    
    urls_to_scan = []
    
    # Get targets from file or single target
    if args.file:
        try:
            with open(args.file, 'r') as f:
                urls_to_scan = [line.strip() for line in f if line.strip()]
            print(f"{Colors.GRAY}[*]{Colors.RESET} Loaded {len(urls_to_scan)} targets from {args.file}")
        except Exception as e:
            print(f"{Colors.RED}[!]{Colors.RESET} Error reading file: {e}")
            sys.exit(1)
    else:
        urls_to_scan = [args.target]
    
    all_results = {}
    
    # Process each target
    for target_url in urls_to_scan:
        global total_endpoints, completed, results, queue
        results = []
        completed = 0
        
        target_url = normalize_url(target_url)
        print(f"\n{Colors.BOLD_WHITE}[>]{Colors.RESET} Scanning: {Colors.CYAN}{target_url}{Colors.RESET}")
        
        # Get robots.txt
        if args.robots:
            try:
                with open(args.robots, 'r') as f:
                    robots_content = f.read()
                robots_url = args.robots
            except Exception as e:
                print(f"{Colors.RED}[!]{Colors.RESET} Error reading custom robots.txt: {e}")
                continue
        else:
            robots_content, robots_url = fetch_robots_txt(target_url)
        
        if not robots_content:
            print(f"{Colors.RED}[!]{Colors.RESET} Could not fetch robots.txt from {robots_url}")
            continue
        
        print(f"{Colors.GREEN}[+]{Colors.RESET} Found robots.txt at: {robots_url}")
        
        # Parse endpoints
        endpoints = parse_robots_txt(robots_content)
        
        if not endpoints:
            print(f"{Colors.YELLOW}[-]{Colors.RESET} No endpoints found in robots.txt")
            continue
        
        # Clean endpoints
        cleaned_endpoints = []
        for endpoint in endpoints:
            if endpoint.startswith('http'):
                # Absolute URL - extract path
                parsed = urlparse(endpoint)
                cleaned_endpoints.append(parsed.path or '/')
            else:
                cleaned_endpoints.append(endpoint)
        
        total_endpoints = len(cleaned_endpoints)
        print(f"{Colors.GREEN}[+]{Colors.RESET} Found {total_endpoints} endpoints to check\n")
        
        # Fill queue
        for endpoint in cleaned_endpoints:
            queue.put(endpoint)
        
        # Start threads
        threads = []
        for _ in range(min(args.threads, total_endpoints)):
            t = threading.Thread(target=worker, args=(target_url, args.no_color))
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Wait for completion
        queue.join()
        
        print("\n")  # New line after progress
        
        # Sort results by status code
        results.sort(key=lambda x: (x['status'] if x['status'] else 999, x['endpoint']))
        
        # Find interesting endpoints
        interesting = get_interesting_endpoints(results)
        
        # Display results
        if args.interesting_only:
            display_results = interesting
            print(f"{Colors.BOLD_WHITE}[*] Interesting Endpoints ({len(interesting)}):{Colors.RESET}")
        else:
            display_results = results
            print(f"{Colors.BOLD_WHITE}[*] All Endpoints ({len(results)}):{Colors.RESET}")
        
        print(f"{Colors.GRAY}{'='*60}{Colors.RESET}")
        
        for r in display_results:
            if args.no_color:
                status_str = str(r['status']) if r['status'] else 'ERR'
                print(f"{r['full_url']:<60} | {status_str:>4} | {r['size']:>6} bytes")
            else:
                if r['status'] == 200:
                    status_color = Colors.GREEN
                elif r['status'] and 300 <= r['status'] < 400:
                    status_color = Colors.YELLOW
                elif r['status'] and 400 <= r['status'] < 500:
                    status_color = Colors.RED
                elif r['status'] and 500 <= r['status']:
                    status_color = Colors.RED
                else:
                    status_color = Colors.GRAY
                
                status_str = str(r['status']) if r['status'] else 'ERR'
                print(f"{r['full_url']:<60} | {status_color}{status_str:>4}{Colors.RESET} | {Colors.WHITE}{r['size']:>6}{Colors.RESET} bytes")
        
        if interesting and not args.interesting_only:
            print(f"\n{Colors.BOLD_WHITE}[!] Interesting Findings ({len(interesting)}):{Colors.RESET}")
            print(f"{Colors.GRAY}{'='*60}{Colors.RESET}")
            for r in interesting:
                if args.no_color:
                    print(f"{r['full_url']} | {r['status']} | {r['size']} bytes")
                else:
                    print(f"{Colors.YELLOW}{r['full_url']}{Colors.RESET} | {status_color}{r['status']}{Colors.RESET} | {r['size']} bytes")
        
        all_results[target_url] = {
            'results': results,
            'interesting': interesting,
            'total': len(results),
            'interesting_count': len(interesting)
        }
        
        print(f"\n{Colors.GRAY}[*]{Colors.RESET} Scan completed for {target_url}")
    
    # Export results if requested
    if args.output:
        # Combine all results for export
        combined_results = []
        for url_data in all_results.values():
            combined_results.extend(url_data['results'])
        
        combined_interesting = []
        for url_data in all_results.values():
            combined_interesting.extend(url_data['interesting'])
        
        if export_results(combined_results, combined_interesting, args.output, args.format):
            print(f"\n{Colors.GREEN}[+]{Colors.RESET} Results exported to {args.output}")
        else:
            print(f"\n{Colors.RED}[!]{Colors.RESET} Failed to export results")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[!]{Colors.RESET} Scan interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}[!]{Colors.RESET} Unexpected error: {e}")
        sys.exit(1)
