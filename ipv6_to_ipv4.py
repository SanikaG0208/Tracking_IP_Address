"""
ipv6_to_ipv4.py
---------------
Takes many IPv6 addresses and tries to find the IPv4 address of each device.

IMPORTANT: An IPv4 cannot be calculated from a normal IPv6 address.
This script tries every method that can actually work, in this order:

  1. Inventory  - your own CSV (ipv6,ipv4), e.g. exported from DHCP/router/firewall
  2. Embedded   - IPv4 hidden inside the IPv6 (mapped, 6to4, NAT64, Teredo, ISATAP)
  3. Neighbor   - match by MAC address using ARP / NDP tables (same local network only)
  4. DNS        - reverse lookup (PTR) of IPv6, then A record of the hostname

Usage (any of these):
  python ipv6_to_ipv4.py                          -> uses IPV6_LIST below
  python ipv6_to_ipv4.py ipv6_list.txt            -> one IPv6 per line in the file
  python ipv6_to_ipv4.py ipv6_list.txt inv.csv    -> also uses an inventory CSV

Output: printed on screen and saved to results.csv

Only use this on networks you administer or with people's consent.
"""

import csv
import ipaddress
import re
import socket
import subprocess
import sys

# =====================  SETTINGS (edit these)  =====================

# Paste your IPv6 addresses here if you don't want to use a file.
IPV6_LIST = [
    "::ffff:203.0.113.5",        # IPv4-mapped
    "2002:cb00:7105::1",         # 6to4
    "64:ff9b::cb00:7105",        # NAT64
    "2401:4900:1234:5678::1",    # normal address (needs inventory/DNS/neighbor)
    "fe80::1a2b:3cff:fe4d:5e6f", # link-local (EUI-64, MAC based)
]

INPUT_FILE = None        # e.g. "ipv6_list.txt"  (overrides IPV6_LIST if set)
INVENTORY_FILE = None    # e.g. "inventory.csv"  with columns: ipv6,ipv4
OUTPUT_FILE = "results.csv"
DNS_TIMEOUT_SECONDS = 3

# ===================================================================

MAC_RE = re.compile(r"(?:[0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}")


# ---------- Method 1: Inventory ----------
def load_inventory(path):
    inventory = {}
    if not path:
        return inventory
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    key = ipaddress.IPv6Address(row["ipv6"].strip()).compressed
                    inventory[key] = row["ipv4"].strip()
                except (ValueError, KeyError, AttributeError):
                    continue
    except OSError as e:
        print(f"[warning] could not read inventory file '{path}': {e}")
    return inventory


# ---------- Method 2: IPv4 embedded inside the IPv6 ----------
def from_embedded(addr):
    n = int(addr)

    if addr.ipv4_mapped:  # ::ffff:a.b.c.d
        return str(addr.ipv4_mapped), "ipv4-mapped"

    if addr.sixtofour:  # 2002:aabb:ccdd::/48
        return str(addr.sixtofour), "6to4"

    if addr.teredo:  # 2001:0::/32 -> (server, client)
        return str(addr.teredo[1]), "teredo (client)"

    if addr in ipaddress.IPv6Network("64:ff9b::/96"):  # NAT64
        return str(ipaddress.IPv4Address(n & 0xFFFFFFFF)), "nat64"

    # ISATAP: interface id = 0000:5efe:a.b.c.d or 0200:5efe:a.b.c.d
    if ((n >> 32) & 0xFFFFFFFF) in (0x00005EFE, 0x02005EFE):
        return str(ipaddress.IPv4Address(n & 0xFFFFFFFF)), "isatap"

    # IPv4-compatible (deprecated): ::a.b.c.d
    if 1 < n < 2 ** 32:
        return str(ipaddress.IPv4Address(n)), "ipv4-compatible"

    return None


# ---------- Method 3: Neighbor tables (ARP for IPv4, NDP for IPv6) ----------
def normalize_mac(mac):
    parts = re.split(r"[:-]", mac.strip().lower())
    return ":".join(p.zfill(2) for p in parts)


def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, shell=False
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def get_neighbor_output():
    """Collect raw ARP/NDP output for Windows, Linux and macOS."""
    outputs = []
    if sys.platform.startswith("win"):
        outputs.append(run_command(["arp", "-a"]))
        outputs.append(run_command(["netsh", "interface", "ipv6", "show", "neighbors"]))
    elif sys.platform == "darwin":
        outputs.append(run_command(["arp", "-an"]))
        outputs.append(run_command(["ndp", "-an"]))
    else:  # Linux
        outputs.append(run_command(["ip", "neigh", "show"]))
    return "\n".join(outputs)


def load_neighbor_table():
    """Returns (ipv6 -> mac, mac -> list of ipv4)."""
    v6_to_mac = {}
    mac_to_v4 = {}

    for line in get_neighbor_output().splitlines():
        mac_match = MAC_RE.search(line)
        if not mac_match:
            continue
        mac = normalize_mac(mac_match.group(0))

        ip_obj = None
        for token in re.split(r"[\s()]+", line):
            token = token.split("%")[0]  # remove scope id like fe80::1%12
            try:
                ip_obj = ipaddress.ip_address(token)
                break
            except ValueError:
                continue
        if ip_obj is None or ip_obj.is_multicast:
            continue

        if ip_obj.version == 6:
            v6_to_mac[ip_obj.compressed] = mac
        else:
            mac_to_v4.setdefault(mac, [])
            if str(ip_obj) not in mac_to_v4[mac]:
                mac_to_v4[mac].append(str(ip_obj))

    return v6_to_mac, mac_to_v4


def eui64_to_mac(addr):
    """If the address was built from a MAC (EUI-64), recover that MAC."""
    b = addr.packed[8:]
    if b[3] == 0xFF and b[4] == 0xFE:
        mac = bytes([b[0] ^ 0x02, b[1], b[2], b[5], b[6], b[7]])
        return ":".join(f"{x:02x}" for x in mac)
    return None


def from_neighbors(addr, v6_to_mac, mac_to_v4):
    mac = v6_to_mac.get(addr.compressed) or eui64_to_mac(addr)
    if mac and mac in mac_to_v4:
        return ", ".join(mac_to_v4[mac]), f"neighbor table (mac {mac})"
    return None


# ---------- Method 4: DNS ----------
def from_dns(ipv6_text):
    try:
        hostname = socket.gethostbyaddr(ipv6_text)[0]
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ips = sorted({i[4][0] for i in infos})
        if ips:
            return ", ".join(ips), f"dns ({hostname})"
    except (socket.herror, socket.gaierror, OSError):
        pass
    return None


# ---------- Resolver ----------
def resolve(ipv6_text, v6_to_mac, mac_to_v4, inventory):
    try:
        addr = ipaddress.IPv6Address(ipv6_text.strip().split("%")[0])
    except ValueError:
        return "invalid IPv6", "-"

    if addr.is_unspecified or addr.is_loopback:
        return "not applicable", "loopback/unspecified address"
    if addr.is_multicast:
        return "not applicable", "multicast address"

    if addr.compressed in inventory:
        return inventory[addr.compressed], "inventory"

    for finder in (
        lambda: from_embedded(addr),
        lambda: from_neighbors(addr, v6_to_mac, mac_to_v4),
        lambda: from_dns(addr.compressed),
    ):
        result = finder()
        if result:
            return result

    return "not found", "no IPv4 can be derived"


# ---------- Input helpers ----------
def read_ipv6_list(path):
    addresses = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                addresses.append(line)
    return addresses


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    inventory_file = sys.argv[2] if len(sys.argv) > 2 else INVENTORY_FILE

    if input_file:
        try:
            addresses = read_ipv6_list(input_file)
        except OSError as e:
            print(f"Could not read '{input_file}': {e}")
            sys.exit(1)
    else:
        addresses = IPV6_LIST

    if not addresses:
        print("No IPv6 addresses to process.")
        sys.exit(1)

    socket.setdefaulttimeout(DNS_TIMEOUT_SECONDS)
    inventory = load_inventory(inventory_file)
    v6_to_mac, mac_to_v4 = load_neighbor_table()

    found = 0
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["ipv6", "ipv4", "method"])

        for ipv6 in addresses:
            ipv4, method = resolve(ipv6, v6_to_mac, mac_to_v4, inventory)
            if re.match(r"^\d+\.\d+\.\d+\.\d+", ipv4):
                found += 1
            print(f"{ipv6:42} -> {ipv4:20} [{method}]")
            writer.writerow([ipv6, ipv4, method])

    print(f"\nDone. IPv4 found for {found} of {len(addresses)} addresses.")
    print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()