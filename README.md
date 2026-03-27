# data-filter-mcp

Local MCP server that registers restricted Python filters and runs them against local `json`, `yaml`, and `txt` files.

## What it does

- `register_filter` accepts Python source code with exactly one top-level function: `def filter_item(data):`
- `run_filter` loads a local file, passes the loaded document into `filter_item(data)`, and returns the text from `result_text`
- Registered filters live only in memory and expire automatically based on server TTL settings

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
