# IPv6 to IPv4 lookup

Requires Python 3. Uses only the Python standard library.

Run in a terminal:

    python ipv6_to_ipv4.py

Or supply an address list and optional inventory:

    python ipv6_to_ipv4.py ipv6_list.txt
    python ipv6_to_ipv4.py ipv6_list.txt inventory.csv

Results are written to results.csv in the terminal's current directory.

A normal IPv6 address cannot be converted directly into an IPv4 address. Inventory, embedded addresses, neighbor tables, and DNS can provide possible associations. DNS and embedded results do not necessarily identify the same device. The configured socket timeout may not bound system DNS lookups.

The example files use documentation addresses. Replace them with your own authorized inputs.

On this computer, run run.cmd from the terminal to use the bundled Python runtime. You can also use: run.cmd ipv6_list.txt inventory.csv. This launcher depends on the Codex runtime path on this computer.

## Local website
Run start_website.cmd, keep the terminal open, then open http://127.0.0.1:8765 in your browser. Paste or upload up to 500 addresses, optionally upload inventory CSV, and click Find IPv4 matches. Download CSV exports the displayed results. Ctrl+C stops the server. No extra Python packages required.
