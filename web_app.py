"""Local browser interface for the IPv6 lookup tool. Standard library only."""
import csv
import io
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ipv6_to_ipv4 as resolver

ROOT = Path(__file__).resolve().parent


def lookup(data):
    addresses = data.get('addresses', [])
    if not isinstance(addresses, list) or len(addresses) > 500 or not all(isinstance(a, str) and len(a) <= 200 for a in addresses):
        raise ValueError('Provide up to 500 IPv6 addresses per batch.')
    inventory = {}
    raw_inventory = data.get('inventory', '')
    if not isinstance(raw_inventory, str):
        raise ValueError('Inventory must be CSV text.')
    if raw_inventory.strip():
        reader = csv.DictReader(io.StringIO(raw_inventory.lstrip('\ufeff')))
        if not reader.fieldnames or not {'ipv6', 'ipv4'}.issubset(reader.fieldnames):
            raise ValueError('Inventory CSV needs columns named ipv6 and ipv4.')
        for number, row in enumerate(reader, 2):
            try:
                v6 = str(ipaddress.IPv6Address(row['ipv6'].strip()))
                v4 = str(ipaddress.IPv4Address(row['ipv4'].strip()))
                inventory[v6] = v4
            except (ValueError, AttributeError, KeyError):
                raise ValueError(f'Invalid inventory address on CSV row {number}.')
    use_neighbors = data.get('neighbors') is True
    use_dns = data.get('dns') is True
    v6_mac, mac_v4 = resolver.load_neighbor_table() if use_neighbors else ({}, {})
    results = []
    for raw in addresses:
        raw = raw.strip()
        if not raw or raw.startswith('#'):
            continue
        row = dict(ipv6=raw, ipv4='', method='None', status='Not found', explanation='No supported match. An ordinary IPv6 address does not encode an IPv4 address.')
        try:
            addr = ipaddress.IPv6Address(raw)
        except ValueError:
            row.update(status='Invalid input', explanation='Enter a valid IPv6 address.')
            results.append(row)
            continue
        if addr.is_multicast or addr.is_loopback or addr.is_unspecified:
            row.update(status='Not applicable', explanation='Multicast, loopback and unspecified addresses do not identify a remote device.')
        elif addr.scope_id:
            row.update(status='Needs inventory', explanation='Scoped addresses require interface-aware matching; automatic lookup is skipped to avoid mixing interfaces.')
            if str(addr) in inventory:
                row.update(ipv4=inventory[str(addr)], method='Inventory', status='Match', explanation='Association supplied in your inventory CSV.')
        elif str(addr) in inventory:
            row.update(ipv4=inventory[str(addr)], method='Inventory', status='Match', explanation='Association supplied in your inventory CSV.')
        else:
            match = resolver.from_embedded(addr)
            if match:
                row.update(ipv4=match[0], method=match[1], status='Candidate', explanation='Extracted from an IPv6 address format. May identify a translator, tunnel endpoint or NAT address; it does not prove the device has this IPv4 address.')
            elif use_neighbors and (match := resolver.from_neighbors(addr, v6_mac, mac_v4)):
                row.update(ipv4=match[0], method=match[1], status='Candidate', explanation='Local neighbor-cache MAC association. May be stale or ambiguous across interfaces; verify in your inventory.')
            elif use_dns and not addr.is_link_local and (match := resolver.from_dns(str(addr))):
                row.update(ipv4=match[0], method=match[1], status='Candidate', explanation='IPv6 PTR hostname has these A records. DNS association does not establish the same device.')
        results.append(row)
    return results


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        else:
            self.send(404, b'Not found', 'text/plain')

    def do_POST(self):
        if self.path != '/api/lookup':
            return self.send(404, b'Not found', 'text/plain')
        if self.headers.get('Host') != '127.0.0.1:8765' or self.headers.get('Origin') not in (None, 'http://127.0.0.1:8765'):
            return self.send(403, b'Local requests only', 'text/plain')
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 1000000 or self.headers.get_content_type() != 'application/json':
                raise ValueError('Use JSON input smaller than 1 MB.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected an input object.')
            result = {'results': lookup(data)}
            self.send(200, json.dumps(result).encode(), 'application/json')
        except (ValueError, TypeError) as exc:
            self.send(400, json.dumps({'error': str(exc)}).encode(), 'application/json')
        except Exception:
            self.send(500, b'{"error":"Lookup failed. Check the server terminal for details."}', 'application/json')
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    print('IPv6 Address Explorer: http://127.0.0.1:8765', flush=True)
    print('Keep this terminal open. Press Ctrl+C to stop.', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
