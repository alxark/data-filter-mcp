# data-filter-mcp

Local MCP server that registers restricted Python filters and runs them against local `json`, `yaml`, and `txt` files.

## What it does

- `register_filter` accepts Python source code with exactly one top-level function: `def filter_item(data):`
- `run_filter` loads a local file, passes the loaded document into `filter_item(data)`, and returns the text from `result_text`
- `convert_file` loads a local file, passes it into `filter_item(data)`, and writes the returned text to another local file
- Registered filters live only in memory and expire automatically based on server TTL settings

### What filter code may use

Filter bodies are AST-validated against a whitelist. In addition to a curated set of builtins (`len`, `sorted`, `max`, `min`, `range`, `enumerate`, `zip`, `sum`, `any`, `all`, conversions, etc.) and safe string/dict/list methods, filters may also use a curated set of standard-library modules. Modules are exposed by their canonical names (`math`, `datetime`, `hashlib`, etc.). Filesystem, process, network, and unsafe serialization modules (`os`, `pathlib`, `shutil`, `subprocess`, `socket`, `urllib`, `pickle`, etc.) are intentionally not available.

- **`lambda` expressions** — typically as `key=` arguments, e.g. `sorted(data, key=lambda item: item.get("score"))`. Lambda bodies are validated by the same rules as the rest of the filter.
- **`json`** — `json.loads`, `json.dumps`.
- **`yaml`** — `yaml.safe_load`, `yaml.safe_dump`. The unsafe `yaml.load` / `yaml.dump` are intentionally not exposed.
- **`re`** — `re.match`, `re.search`, `re.fullmatch`, `re.findall`, `re.sub`, `re.subn`, `re.compile`, `re.escape`, plus `Match` / `Pattern` methods (`group`, `groups`, `groupdict`, `start`, `end`, `span`).
- **`math`** — numeric helpers such as `math.ceil`, `math.floor`, `math.sqrt`, `math.log`, `math.exp`, `math.pow`, `math.factorial`, `math.gcd`, `math.lcm`, `math.isfinite`, `math.isclose`.
- **`statistics`** — aggregates such as `statistics.mean`, `statistics.median`, `statistics.stdev`, `statistics.variance`, `statistics.quantiles`.
- **`datetime`** — `datetime.datetime.fromisoformat`, `datetime.datetime.now`, `datetime.timedelta`, `datetime.timezone.utc`, and instance methods such as `isoformat`, `strftime`, `timestamp`, `weekday`, `total_seconds`. General instance attribute reads such as `dt.year` and `dt.month` are not supported by the current policy.
- **`decimal`** — `decimal.Decimal(...)`, `quantize`, `normalize`, `to_eng_string`, `to_integral_value`.
- **`collections`** — `collections.Counter`, `collections.defaultdict`, `collections.OrderedDict`, `collections.deque`, plus methods such as `most_common`, `elements`, `popleft`, `appendleft`, `rotate`.
- **`itertools`** — `chain`, `chain.from_iterable`, `islice`, `takewhile`, `dropwhile`, `groupby`, `starmap`, `accumulate`, `combinations`, `permutations`, `product`, `filterfalse`.
- **`functools`** — `reduce`, `partial`, `cmp_to_key`, `wraps`. Caching decorators such as `lru_cache` and `cache` are intentionally not exposed because they can retain process-local state across filter calls.
- **`operator`** — `itemgetter`, `methodcaller`, and arithmetic/comparison helpers such as `add`, `mul`, `lt`, `eq`, `gt`. `attrgetter` is intentionally not exposed.
- **`textwrap`** — `fill`, `wrap`, `shorten`, `indent`, `dedent`.
- **`html`** — `html.escape`, `html.unescape`.
- **`base64`** — `b64encode`, `b64decode`, `urlsafe_b64encode`, `urlsafe_b64decode`, `b32encode`, `b32decode`, `b16encode`, `b16decode`.
- **`hashlib`** — `hashlib.sha256`, `hashlib.sha1`, `hashlib.md5`, `hashlib.blake2b`, `hashlib.new`, plus hash object methods such as `hexdigest`, `digest`, `update`.
- **`ipaddress`** — `ip_address`, `ip_network`, `ip_interface`, `IPv4Network`, `IPv6Network`, plus methods such as `supernet`, `subnets`, `hosts`, `overlaps`, `subnet_of`, `supernet_of`. General instance attribute reads such as `addr.is_private` and `addr.compressed` are not supported by the current policy.
- **`unicodedata`** — `category`, `name`, `lookup`, `numeric`, `digit`, `decimal`, `bidirectional`, `combining`, `mirrored`.
- **`difflib`** — `get_close_matches`, `ndiff`, `unified_diff`, `context_diff`, `SequenceMatcher`.

Note: `re.compile` runs against patterns supplied by filter code, so a pathological pattern can stall the server (ReDoS). Some helpers such as `difflib.SequenceMatcher` can also be CPU-heavy on large inputs. Treat filter source as trusted-but-restricted.

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
- `convert_file` always requires at least one `--workdir` because it writes to disk.
- `convert_file` requires the destination path to be inside an allowed workdir.
- `convert_file` creates missing destination parent directories automatically.
- `convert_file` refuses to replace an existing destination file unless `overwrite` is `true`.

### Writing transformed files with `convert_file`

Use `convert_file` when the filtered output should be persisted instead of returned
inline to the model. The tool accepts:

- `filter_id` — an identifier returned by `register_filter`
- `source_file_path` — absolute path to the json/yaml/txt file to load
- `destination_file_path` — absolute path where the returned text should be saved
- `file_type` — optional source file type override (`json`, `yaml`, or `txt`)
- `overwrite` — optional boolean, default `false`

Example flow:

```python
def filter_item(data):
    return "\n".join(data["items"])
```

Then call `convert_file` with a source such as `/tmp/data/items.json` and a
destination such as `/tmp/data/out/items.txt`. The result is written as UTF-8
text. The returned metadata includes the resolved source and destination paths,
the effective source file type, `bytes_written`, and whether an existing file was
overwritten.

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
