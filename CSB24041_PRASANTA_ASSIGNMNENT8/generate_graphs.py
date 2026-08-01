
import argparse
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = "graphs"


def load_and_average(path):
    """Returns dict: {num_clients: {metric: avg_value}}"""
    if not path or not os.path.exists(path):
        return {}

    buckets = defaultdict(lambda: defaultdict(list))
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                n = int(row["clients"])
            except (KeyError, ValueError):
                continue
            for metric in ("avg_delay_ms", "throughput_msgs_per_sec", "cpu_percent", "memory_mb"):
                if metric in row and row[metric] != "":
                    try:
                        buckets[n][metric].append(float(row[metric]))
                    except ValueError:
                        pass

    averaged = {}
    for n, metrics in buckets.items():
        averaged[n] = {m: sum(v) / len(v) for m, v in metrics.items() if v}
    return averaged


def plot_metric(before, after, metric, ylabel, title, filename):
    client_counts = sorted(set(list(before.keys()) + list(after.keys())))
    if not client_counts:
        print(f"Skipping {filename}: no data")
        return

    plt.figure(figsize=(7, 5))

    if before:
        y_before = [before.get(n, {}).get(metric) for n in client_counts]
        plt.plot(client_counts, y_before, marker="o", label="Before optimization", color="#c62828")

    if after:
        y_after = [after.get(n, {}).get(metric) for n in client_counts]
        plt.plot(client_counts, y_after, marker="s", label="After optimization", color="#2e7d32")

    plt.xlabel("Number of Concurrent Clients")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(client_counts)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", help="Path to Assignment 7 (pre-optimization) performance_results.csv")
    parser.add_argument("--after", required=True, help="Path to Assignment 8 (post-optimization) performance_results.csv")
    args = parser.parse_args()

    before = load_and_average(args.before)
    after = load_and_average(args.after)

    plot_metric(before, after, "avg_delay_ms", "Average Delay (ms)",
                "Message Delay vs Concurrent Clients", "delay_vs_clients.png")
    plot_metric(before, after, "throughput_msgs_per_sec", "Throughput (msg/sec)",
                "Throughput vs Concurrent Clients", "throughput_vs_clients.png")
    plot_metric(before, after, "cpu_percent", "CPU Usage (%)",
                "CPU Usage vs Concurrent Clients", "cpu_vs_clients.png")
    plot_metric(before, after, "memory_mb", "Memory Usage (MB)",
                "Memory Usage vs Concurrent Clients", "memory_vs_clients.png")


if __name__ == "__main__":
    main()
