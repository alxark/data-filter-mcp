# data-filter-mcp

Local MCP server that registers restricted Python filters and runs them against local `json`, `yaml`, and `txt` files.

## What it does

- `register_filter` accepts Python source code with exactly one top-level function: `def filter_item(data):`
- `run_filter` loads a local file, passes the loaded document into `filter_item(data)`, and returns the text from `result_text`
- Registered filters live only in memory and expire automatically based on server TTL settings

### What filter code may use

Filter bodies are AST-validated against a whitelist. In addition to a curated set of builtins (`len`, `sorted`, `max`, `min`, `range`, `enumerate`, `zip`, `sum`, `any`, `all`, conversions, etc.) and safe string/dict/list methods, filters may also use:

- **`lambda` expressions** — typically as `key=` arguments, e.g. `sorted(data, key=lambda item: item.get("score"))`. Lambda bodies are validated by the same rules as the rest of the filter.
- **`json`** — `json.loads`, `json.dumps`.
- **`yaml`** — `yaml.safe_load`, `yaml.safe_dump`. The unsafe `yaml.load` / `yaml.dump` are intentionally not exposed.
- **`re`** — `re.match`, `re.search`, `re.fullmatch`, `re.findall`, `re.sub`, `re.subn`, `re.compile`, `re.escape`, plus `Match` / `Pattern` methods (`group`, `groups`, `groupdict`, `start`, `end`, `span`).

Note: `re.compile` runs against patterns supplied by filter code, so a pathological pattern can stall the server (ReDoS). Treat filter source as trusted-but-restricted.

## Run with uvx

After publishing to PyPI, start the server with:

```bash
uvx data-filter-mcp --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
```

Show the available CLI flags with:

```bash
uvx data-filter-mcp --help
```

### Restricting file access with `--workdir`

By default the server can read any file on the local filesystem. Use one or
more `--workdir` flags to restrict file reads to specific directories:

```bash
uvx data-filter-mcp \
  --filter-ttl-seconds 3600 \
  --cleanup-interval-seconds 60 \
  --workdir /Users/me/project \
  --workdir /tmp/data
```

Rules:
- Each `--workdir` value must be an **absolute path** to an existing directory.
- `run_filter` will only accept files located inside the allowed directories.
- If no `--workdir` flags are provided, no restrictions are applied (backward compatible).

Example MCP client configuration:

```json
{
  "mcpServers": {
    "data-filter": {
      "command": "uvx",
      "args": [
        "data-filter-mcp",
        "--filter-ttl-seconds",
        "3600",
        "--cleanup-interval-seconds",
        "60",
        "--workdir",
        "/Users/me/project",
        "--workdir",
        "/tmp/data"
      ]
    }
  }
}
```

## Run locally

```bash
python server.py --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
python -m data_filter_mcp.server --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
.venv/bin/data-filter-mcp --filter-ttl-seconds 3600 --cleanup-interval-seconds 60
```
