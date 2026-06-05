#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import matplotlib.pyplot as plt

def detect_caches():
    """Detects cache sizes (L1d, L2, L3) on macOS or Linux."""
    l1, l2, l3 = None, None, None
    
    # Try macOS sysctl
    try:
        out = subprocess.check_output(["sysctl", "-a"], stderr=subprocess.DEVNULL).decode('utf-8')
        
        # Look for perflevel0 (performance cores) sizes first (e.g. Apple Silicon)
        l1_match = re.search(r'hw\.perflevel0\.l1dcachesize:\s*(\d+)', out)
        l2_match = re.search(r'hw\.perflevel0\.l2cachesize:\s*(\d+)', out)
        
        if l1_match:
            l1 = int(l1_match.group(1))
        else:
            l1_gen = re.search(r'hw\.l1dcachesize:\s*(\d+)', out)
            if l1_gen:
                l1 = int(l1_gen.group(1))
                
        if l2_match:
            l2 = int(l2_match.group(1))
        else:
            l2_gen = re.search(r'hw\.l2cachesize:\s*(\d+)', out)
            if l2_gen:
                l2 = int(l2_gen.group(1))
                
        l3_gen = re.search(r'hw\.l3cachesize:\s*(\d+)', out)
        if l3_gen:
            l3 = int(l3_gen.group(1))
    except Exception:
        pass
        
    # Try Linux sysfs if macOS failed
    if l1 is None and l2 is None:
        try:
            for i in range(5):
                path = f"/sys/devices/system/cpu/cpu0/cache/index{i}/"
                if os.path.exists(path):
                    with open(os.path.join(path, "type"), "r") as f:
                        cache_type = f.read().strip()
                    with open(os.path.join(path, "level"), "r") as f:
                        level = int(f.read().strip())
                    with open(os.path.join(path, "size"), "r") as f:
                        size_str = f.read().strip().upper()
                        multiplier = 1024
                        if 'M' in size_str:
                            multiplier = 1024 * 1024
                        elif 'G' in size_str:
                            multiplier = 1024 * 1024 * 1024
                        size_val = int(re.sub(r'[^0-9]', '', size_str)) * multiplier
                    
                    if level == 1 and cache_type == "Data":
                        l1 = size_val
                    elif level == 2:
                        l2 = size_val
                    elif level == 3:
                        l3 = size_val
        except Exception:
            pass
            
    # Default fallbacks if detection fails completely
    if l1 is None:
        l1 = 32 * 1024
    if l2 is None:
        l2 = 512 * 1024
        
    return l1, l2, l3

def format_bytes(size_bytes):
    """Formats bytes to human-readable strings (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes // 1024} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        val = size_bytes / (1024 * 1024)
        return f"{int(val)} MB" if val.is_integer() else f"{val:.1f} MB"
    else:
        val = size_bytes / (1024 * 1024 * 1024)
        return f"{int(val)} GB" if val.is_integer() else f"{val:.1f} GB"

def parse_output(text):
    """Parses benchmark output to extract sizes and latencies."""
    sizes = []
    latencies = []
    
    # Matches lines like: N=4096 bytes  0.0349121 ns/elem  sum=1024000
    pattern = re.compile(r'N=(\d+)\s+bytes\s+([\d\.]+)\s+ns/elem')
    
    for line in text.strip().split('\n'):
        match = pattern.search(line)
        if match:
            sizes.append(int(match.group(1)))
            latencies.append(float(match.group(2)))
            
    return sizes, latencies

def plot_data(sizes, latencies, output_image="cache_cliff.png"):
    """Generates and saves the Cache Cliff plot."""
    if not sizes or not latencies:
        print("Error: No valid benchmark data found in the input!", file=sys.stderr)
        return

    # Ensure parent directory exists, or fall back to current directory
    dir_name = os.path.dirname(output_image)
    if dir_name and not os.path.exists(dir_name):
        print(f"Warning: Directory '{dir_name}' does not exist. Saving to '{os.path.basename(output_image)}' in current directory instead.")
        output_image = os.path.basename(output_image)
        
    # Get system cache details
    l1, l2, l3 = detect_caches()
    
    # Create the figure
    plt.figure(figsize=(10, 6), dpi=150)
    plt.grid(True, which="both", ls="-", alpha=0.2, color="gray")
    
    # Plot benchmark data
    plt.plot(sizes, latencies, marker='o', color='#1f77b4', linewidth=2.5, markersize=7, label="Measured Latency")
    
    # Set log scale on x-axis
    plt.xscale('log', base=2)
    plt.xticks(sizes, [format_bytes(s) for s in sizes], rotation=45, ha='right')
    
    max_latency = max(latencies) * 1.15
    min_latency = min(latencies) * 0.85
    plt.ylim(min_latency, max_latency)
    
    # Shading regions
    # L1 Range: [0, L1]
    plt.axvspan(min(sizes), l1, color='#2ca02c', alpha=0.1, label="L1 Cache Region")
    plt.axvline(x=l1, color='#2ca02c', linestyle='--', linewidth=1.5, alpha=0.7)
    plt.text(l1 * 0.7, max_latency * 0.9, f"L1d Limit\n({format_bytes(l1)})", 
             color='#1e6b1e', fontsize=9, fontweight='bold', ha='right')
    
    # L2 Range: [L1, L2]
    if l2:
        plt.axvspan(l1, l2, color='#bcbd22', alpha=0.08, label="L2 Cache Region")
        plt.axvline(x=l2, color='#bcbd22', linestyle='--', linewidth=1.5, alpha=0.7)
        plt.text(l2 * 0.7, max_latency * 0.9, f"L2 Limit\n({format_bytes(l2)})", 
                 color='#7b7d15', fontsize=9, fontweight='bold', ha='right')
        
        # DRAM/L3 Region
        if l3:
            plt.axvspan(l2, l3, color='#9467bd', alpha=0.08, label="L3 Cache Region")
            plt.axvline(x=l3, color='#9467bd', linestyle='--', linewidth=1.5, alpha=0.7)
            plt.text(l3 * 0.7, max_latency * 0.9, f"L3 Limit\n({format_bytes(l3)})", 
                     color='#5c3d7a', fontsize=9, fontweight='bold', ha='right')
            
            plt.axvspan(l3, max(sizes), color='#d62728', alpha=0.08, label="DRAM Region")
            plt.text(max(sizes) * 0.8, max_latency * 0.9, "DRAM", 
                     color='#941b1c', fontsize=9, fontweight='bold', ha='right')
        else:
            plt.axvspan(l2, max(sizes), color='#d62728', alpha=0.08, label="DRAM Region")
            plt.text(max(sizes) * 0.8, max_latency * 0.9, "DRAM", 
                     color='#941b1c', fontsize=9, fontweight='bold', ha='right')
    else:
        plt.axvspan(l1, max(sizes), color='#d62728', alpha=0.08, label="DRAM Region")
        plt.text(max(sizes) * 0.8, max_latency * 0.9, "DRAM", 
                 color='#941b1c', fontsize=9, fontweight='bold', ha='right')

    plt.title("Memory Latency vs. Working Set Size (The Cache Cliff)", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Working Set Size (Bytes)", fontsize=11, fontweight='semibold', labelpad=10)
    plt.ylabel("Latency (ns / element)", fontsize=11, fontweight='semibold', labelpad=10)
    
    plt.legend(loc="upper left", framealpha=0.9, facecolor='white', edgecolor='none')
    plt.tight_layout()
    
    plt.savefig(output_image, dpi=300)
    print(f"Plot saved successfully to {output_image}")
    
    try:
        plt.show()
    except Exception:
        pass

def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ('-', '--help', '-h'):
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                raw_text = f.read()
        except Exception as e:
            print(f"Error reading file {filename}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h'):
            print("Usage: python3 plot_cache_cliff.py [input_file.txt]")
            print("Reads from stdin if no file is provided.")
            sys.exit(0)
        # Read from stdin
        raw_text = sys.stdin.read()

    sizes, latencies = parse_output(raw_text)
    
    # Print out summary table to console
    print("\nParsed Benchmark Data:")
    print(f"{'Size (Bytes)':<15} | {'Latency (ns/elem)':<20}")
    print("-" * 38)
    for s, l in zip(sizes, latencies):
        print(f"{format_bytes(s):<15} | {l:<20.4f}")
    print()
    
    plot_data(sizes, latencies)

if __name__ == "__main__":
    main()
