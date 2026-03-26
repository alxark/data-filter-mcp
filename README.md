# data-filter-mcp

Local MCP server that registers restricted Python filters and runs them against local `json`, `yaml`, and `txt` files.

## What it does

- `register_filter` accepts Python source code with exactly one top-level function: `def filter_item(data):`
- `run_filter` loads a local file, passes the loaded document into `filter_item(data)`, and returns the text from `result_text`
- Registered filters live only in memory and expire automatically based on server TTL settings

## Run locally

```bash
python server.py --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
python -m data_filter_mcp.server --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
.venv/bin/data-filter-mcp --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
```