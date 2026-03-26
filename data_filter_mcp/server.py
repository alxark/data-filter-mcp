from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Sequence

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .loaders.factory import load_document
from .models import RegisterFilterResult, RunFilterResult
from .registry import FilterExpiredError, FilterNotFoundError, FilterRegistry
from .validator import POLICY_VERSION, FilterValidationError, compile_filter


def _to_isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class FilterService:
    def __init__(
        self,
        filter_ttl_seconds: int = 3600,
        cleanup_interval_seconds: float = 60.0,
        now_provider=None,
    ) -> None:
        self._registry = FilterRegistry(
            filter_ttl_seconds=filter_ttl_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
            now_provider=now_provider,
        )

    def start(self) -> None:
        self._registry.start_cleanup_thread()

    def stop(self) -> None:
        self._registry.stop_cleanup_thread()

    def register_filter(self, code: str) -> RegisterFilterResult:
        try:
            filter_fn = compile_filter(code)
        except FilterValidationError:
            raise

        entry = self._registry.register(
            source_code=code,
            function=filter_fn,
            policy_version=POLICY_VERSION,
        )
        return RegisterFilterResult(
            filter_id=entry.filter_id,
            expires_at=_to_isoformat(entry.expires_at),
            policy_version=entry.policy_version,
            ttl_seconds=self._registry.filter_ttl_seconds,
        )

    def run_filter(
        self,
        filter_id: str,
        file_path: str,
        file_type: Literal["json", "yaml", "txt"] | None = None,
    ) -> RunFilterResult:
        try:
            entry = self._registry.get(filter_id)
        except (FilterNotFoundError, FilterExpiredError) as exc:
            raise ValueError(str(exc)) from exc

        resolved_path = Path(file_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")
        if not resolved_path.is_file():
            raise ValueError(f"Path is not a file: {resolved_path}")

        document, resolved_file_type = load_document(resolved_path, file_type)
        result = entry.function(document)
        if not isinstance(result, str):
            raise ValueError("filter_item(data) must return a string")

        return RunFilterResult(
            expires_at=_to_isoformat(entry.expires_at),
            file_path=str(resolved_path),
            file_type=resolved_file_type,
            filter_id=entry.filter_id,
            result_text=result,
        )


def create_mcp_server(service: FilterService | None = None) -> FastMCP:
    active_service = service or FilterService()
    mcp = FastMCP("data-filter-mcp")

    @mcp.tool()
    def register_filter(
        code: Annotated[
            str,
            Field(
                description=(
                    "Python source code that defines exactly one top-level function "
                    "named filter_item(data). The function receives the loaded "
                    "document and must return a text result."
                )
            ),
        ],
    ) -> RegisterFilterResult:
        """
        Validate and register a restricted Python filter for later execution on a local file.

        Use this tool first when you want to run custom filtering or transformation logic
        against a local document. The submitted source code must define exactly one
        top-level function with this exact signature:

            def filter_item(data):

        The server loads the target file before execution and passes the loaded document
        into filter_item(data).

        Input document types:
        - JSON files -> parsed JSON value such as dict, list, string, number, boolean, or null
        - YAML files -> parsed YAML value such as dict, list, string, number, boolean, or null
        - TXT files -> list of text lines

        The function must return a text result (str). The returned text may contain any
        format you want, such as plain text, YAML, CSV-like text, or a custom report.

        Safety rules:
        - The code is validated against a restricted Python subset
        - Imports, file I/O, network access, dynamic execution, and unsafe attribute access are rejected
        - Registered filters are stored in memory only and expire automatically after a server-side TTL

        Args:
            code: Python source code that defines exactly one function named filter_item(data).

        Returns:
            A structured object containing the new filter identifier, expiration timestamp,
            TTL in seconds, and validation policy version.

        Raises:
            ValueError: If the code is invalid, unsafe, or does not match the required function signature.
        """

        return active_service.register_filter(code)

    @mcp.tool()
    def run_filter(
        filter_id: Annotated[
            str,
            Field(description="Identifier previously returned by register_filter."),
        ],
        file_path: Annotated[
            str,
            Field(
                description=(
                    "Path to the local file that should be loaded and passed into "
                    "filter_item(data)."
                )
            ),
        ],
        file_type: Annotated[
            Literal["json", "yaml", "txt"] | None,
            Field(
                description=(
                    "Optional explicit file type override. If omitted, the server "
                    "detects the type from the file extension."
                )
            ),
        ] = None,
    ) -> RunFilterResult:
        """
        Run a previously registered filter on a local file and return its text output.

        Use this tool after register_filter. The server resolves the registered filter,
        loads the file from the local filesystem, converts it into an in-memory document,
        calls filter_item(data), and returns the exact text produced by the filter.

        Supported file types:
        - json
        - yaml
        - txt

        If file_type is omitted, the server tries to detect the type from the file extension.

        File loading behavior:
        - json -> parsed JSON value
        - yaml -> parsed YAML value
        - txt -> list of lines

        Args:
            filter_id: Identifier returned earlier by register_filter.
            file_path: Path to the local file that should be loaded and passed into the filter.
            file_type: Optional explicit file type override. Use this when extension-based detection
                is missing or ambiguous.

        Returns:
            A structured object containing the filter identifier, resolved file path,
            effective file type, filter expiration time, and result_text.

        Raises:
            ValueError: If the filter does not exist, has expired, returns a non-string result,
                or the file type is unsupported.
            FileNotFoundError: If the file does not exist.
        """

        return active_service.run_filter(filter_id, file_path, file_type)

    return mcp


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local data filter MCP server")
    parser.add_argument(
        "--filter-ttl-seconds",
        type=int,
        default=3600,
        help="How long registered filters stay available in memory",
    )
    parser.add_argument(
        "--cleanup-interval-seconds",
        type=float,
        default=60.0,
        help="How often expired filters are swept from the registry",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    service = FilterService(
        filter_ttl_seconds=args.filter_ttl_seconds,
        cleanup_interval_seconds=args.cleanup_interval_seconds,
    )
    service.start()
    try:
        create_mcp_server(service).run()
    finally:
        service.stop()


if __name__ == "__main__":
    main()
