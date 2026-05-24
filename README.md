created by : latent

---

# lat-finder

Fast async subdomain discovery tool with adaptive throttling, HTTP probing, and live progress.

```
  _       _     ___ _           _
 | |     | |   |  _(_)_ __   __| | ___ _ __
 | |     | |   | |_| | '_ \ / _` |/ _ \ '__|
 | |___  | |___|  _| | | | | (_| |  __/ |
 |_____| |_____|_| |_|_| |_|\__,_|\___|_|
```

## Features

- **Adaptive throttling** — automatically scales threads up/down based on DNS error rate
- **Live progress bar** — real-time req/s, ETA, thread count, found count
- **HTTP probe** — checks HTTP/HTTPS status codes and page titles on discovered subdomains
- **Multi-wordlist** — merge, dedup, shuffle, and regex-filter any number of lists
- **Wildcard filtering** — detects and removes false positives
- **Output formats** — `text`, `json`, `csv`

## Install

```bash
pip install lat-finder
```

Or from source:

```bash
git clone https://github.com/LaxenTgit/lat-finder
cd lat-finder
pip install -e .
```

**Requirements:** Python 3.11+

## Usage

```bash
# Basic
lat-finder example.com

# Custom wordlist + HTTP probe
lat-finder example.com -w /path/to/big.txt --http-probe

# Merge two lists, shuffle, filter
lat-finder example.com -w default -w /path/to/extra.txt --shuffle --filter "^dev"

# JSON output
lat-finder example.com -f json -o results.json

# Max threads, custom resolvers
lat-finder example.com -t 150 -r 8.8.8.8,9.9.9.9,1.1.1.1
```

## Options

```
positional:
  domain              Target domain

wordlist:
  -w, --wordlist      Wordlist path or built-in (repeatable)
  --shuffle           Randomize wordlist order
  --no-dedup          Keep duplicate entries
  --filter REGEX      Only test words matching regex

scan:
  -t, --threads       Concurrent threads (default: 50)
  --timeout           DNS timeout in seconds (default: 3.0)
  -r, --resolvers     Comma-separated resolvers
  --no-adaptive       Disable adaptive throttling
  --no-wildcard       Skip wildcard detection
  --http-probe        Probe found subdomains over HTTP/HTTPS

output:
  -o, --output        Write results to file
  -f, --format        text | json | csv (default: text)
```

## Legal

Only use on domains you own or have explicit permission to test.

## License

MIT
