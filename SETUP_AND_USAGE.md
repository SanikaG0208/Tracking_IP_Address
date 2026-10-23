# IPv6 Address Explorer: setup and usage

This local Python app looks for possible IPv4 associations for IPv6 addresses.
A normal IPv6 address cannot be directly converted to IPv4. Inventory matches
come from your supplied data; embedded, neighbor and DNS matches are candidates
that you should verify.

## Requirements

- Python 3.10 or newer (Python 3.12 is suitable).
- A browser for the website interface.
- Git only if cloning or pushing the project.
- No pip packages, API keys or database are required.

## Get the project from GitHub

Open PowerShell in the folder where you want the project:

```powershell
git clone --branch ipv6-ipv4-lookup https://github.com/SanikaG0208/Tracking_IP_Address.git
cd Tracking_IP_Address
python --version
```

If Windows does not recognize `python`, try `py -3` in its place. If neither
works, install Python 3.10 or newer and enable its PATH option, then reopen
PowerShell.

## Start the website

From the project folder:

```powershell
python web_app.py
```

Open http://127.0.0.1:8765 in your browser. Keep PowerShell open while using
the app. Press Ctrl+C in PowerShell to stop it.

On Sanika's existing computer, ` .\start_website.cmd ` also starts the app
using the bundled Codex Python runtime. That launcher contains a computer-specific
path; on another computer use `python web_app.py` instead.

Opening index.html directly does not start the backend. Start web_app.py first.

## Use the website

1. Paste IPv6 addresses, one per line, or upload a text file such as ipv6_list.txt.
2. Optionally upload an inventory CSV with exactly these column names:

   ```csv
   ipv6,ipv4
   2001:db8::1,192.0.2.1
   ```

3. Optionally enable neighbor-table matching or DNS lookup. Neighbor matching
   depends on entries available on the computer's local network; DNS depends
   on the network's PTR and A records and may be slow.
4. Click **Find IPv4 matches**. The website accepts up to 500 addresses per batch.
5. Read the status, method and explanation for each result.
6. Click **Download CSV** to export the displayed results.

`Match` means your inventory supplied the association. `Candidate` needs
verification. `Not found` is expected when no supported association exists.
The supplied address files are examples; replace them with your own authorized
inputs. This tool does not determine a device's physical location.

## Use the command line

```powershell
python ipv6_to_ipv4.py ipv6_list.txt inventory.csv
```

Without inventory:

```powershell
python ipv6_to_ipv4.py ipv6_list.txt
```

Without arguments, the script uses the example list inside ipv6_to_ipv4.py.
The CLI tries inventory, embedded addresses, local neighbor tables and DNS.
It prints results and writes results.csv in the current terminal directory,
overwriting any previous results.csv there. Unlike the website, CLI output
has only ipv6, ipv4 and method columns and no separate candidate status.

On Sanika's existing computer, you can also use:

```powershell
.\run.cmd ipv6_list.txt inventory.csv
```

## Project files

- web_app.py: local HTTP server and website lookup endpoint.
- index.html: browser interface.
- ipv6_to_ipv4.py: lookup logic and command-line entry point.
- ipv6_list.txt: sample input, one address per line.
- inventory.csv: sample supplied IPv6/IPv4 association.
- start_website.cmd and run.cmd: launchers tied to the existing Codex runtime.
- README.md: original quick reference.
- SETUP_AND_USAGE.md: this guide.

## Save changes to GitHub

From your cloned repository on the ipv6-ipv4-lookup branch:

```powershell
git status
git add web_app.py index.html ipv6_to_ipv4.py README.md SETUP_AND_USAGE.md start_website.cmd run.cmd .gitignore
git commit -m "Update IPv6 address lookup tool"
git push origin ipv6-ipv4-lookup
```

Stage edited sample input files separately if you intend to publish them.
Keep private network inventories and lookup results out of GitHub. The included
.gitignore excludes generated results.csv, Python caches and local environments.

## Troubleshooting

- **Address already in use:** stop the previous app with Ctrl+C and start it again.
- **Browser cannot connect:** check that web_app.py is running, then use the exact
  URL http://127.0.0.1:8765.
- **Local requests only:** use that exact URL rather than localhost or a LAN IP.
- **No match:** add a known association to inventory.csv or check DNS/local
  neighbor availability. Ordinary IPv6 addresses do not encode an IPv4 address.
- **Launcher path missing:** run the Python commands above with your own Python.

The server listens only on this computer. GitHub stores the code; GitHub Pages
cannot run this Python backend.
