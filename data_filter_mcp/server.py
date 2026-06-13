from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Sequence

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .loaders.factory import load_document
from .models import ConvertFileResult, RegisterFilterResult, RunFilterResult
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
        workdirs: Sequence[str] | None = None,
    ) -> None:
        self._registry = FilterRegistry(
            filter_ttl_seconds=filter_ttl_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds,
            now_provider=now_provider,
        )
        self._workdirs: list[Path] = []
        if workdirs:
            for raw in workdirs:
                p = Path(raw)
                if not p.is_absolute():
                    raise ValueError(f"workdir must be an absolute path: {raw}")
                resolved = p.expanduser().resolve()
                if not resolved.is_dir():
                    raise ValueError(
                        f"workdir is not an existing directory: {resolved}"
                    )
                self._workdirs.append(resolved)

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

    def _resolve_allowed_file_path(self, file_path: str) -> Path:
        candidate = Path(file_path)
        if not candidate.is_absolute():
            raise ValueError(f"file_path must be an absolute path: {file_path}")

        resolved = candidate.expanduser().resolve()

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")
        if not resolved.is_file():
            raise ValueError(f"Path is not a file: {resolved}")

        if self._workdirs:
            if not any(
                resolved == wd or wd in resolved.parents for wd in self._workdirs
            ):
                raise ValueError(f"File path is outside allowed workdirs: {resolved}")

        return resolved

    def _resolve_destination_file_path(self, file_path: str) -> Path:
        candidate = Path(file_path)
        if not candidate.is_absolute():
            raise ValueError(
                f"destination_file_path must be an absolute path: {file_path}"
            )

        if not self._workdirs:
            raise ValueError(
                "convert_file requires at least one --workdir to be configured"
            )

        try:
            resolved = candidate.expanduser().resolve(strict=False)
        except OSError as exc:
            raise ValueError(f"Cannot resolve destination path: {file_path}") from exc

        if not any(resolved == wd or wd in resolved.parents for wd in self._workdirs):
            raise ValueError(f"Destination path is outside allowed workdirs: {resolved}")

        if resolved.exists() and resolved.is_dir():
            raise ValueError(f"Destination path is a directory: {resolved}")

        return resolved

    def _ensure_destination_parent_allowed(self, destination: Path) -> None:
        try:
            resolved_parent = destination.parent.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Cannot resolve destination parent directory: {destination.parent}"
            ) from exc

        if not any(
            resolved_parent == wd or wd in resolved_parent.parents
            for wd in self._workdirs
        ):
            raise ValueError(
                f"Destination parent is outside allowed workdirs: {resolved_parent}"
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

        resolved_path = self._resolve_allowed_file_path(file_path)

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

    def convert_file(
        self,
        filter_id: str,
        source_file_path: str,
        destination_file_path: str,
        file_type: Literal["json", "yaml", "txt"] | None = None,
        overwrite: bool = False,
    ) -> ConvertFileResult:
        try:
            entry = self._registry.get(filter_id)
        except (FilterNotFoundError, FilterExpiredError) as exc:
            raise ValueError(str(exc)) from exc

        resolved_source = self._resolve_allowed_file_path(source_file_path)
        resolved_destination = self._resolve_destination_file_path(destination_file_path)

        if resolved_source == resolved_destination:
            raise ValueError("source and destination paths must differ")

        will_overwrite = resolved_destination.exists()
        if will_overwrite and not overwrite:
            raise ValueError(
                "Destination file already exists (set overwrite=true to replace): "
                f"{resolved_destination}"
            )

        document, resolved_file_type = load_document(resolved_source, file_type)
        result = entry.function(document)
        if not isinstance(result, str):
            raise ValueError("filter_item(data) must return a string")

        encoded = result.encode("utf-8")
        resolved_destination.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_destination_parent_allowed(resolved_destination)
        resolved_destination.write_bytes(encoded)

        return ConvertFileResult(
            expires_at=_to_isoformat(entry.expires_at),
            filter_id=entry.filter_id,
            source_file_path=str(resolved_source),
            destination_file_path=str(resolved_destination),
            file_type=resolved_file_type,
            bytes_written=len(encoded),
            overwritten=will_overwrite,
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

        Preloaded standard-library modules (don't try to import them in your functions):
        - json, yaml, re
        - math, statistics, datetime, decimal
        - collections, itertools, functools, operator
        - textwrap, html, base64, hashlib, ipaddress, unicodedata, difflib

        Safety rules:
        - The code is validated against a restricted Python subset
        - Imports, network access, dynamic execution, and unsafe attribute access are rejected
        - Registered filters are stored in memory only and expire automatically after a server-side TTL

        Forbidden:
        - Using non-standard libraries or modules
        - Accessing the filesystem, network, or environment variables
        - Defining multiple top-level functions, classes, or module-level code
        - Using dynamic features like eval, exec, or __import__

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

    @mcp.tool()
    def convert_file(
        filter_id: Annotated[
            str,
            Field(description="Identifier previously returned by register_filter."),
        ],
        source_file_path: Annotated[
            str,
            Field(
                description=(
                    "Absolute path to the source file. Must be inside an allowed "
                    "--workdir if any are configured."
                )
            ),
        ],
        destination_file_path: Annotated[
            str,
            Field(
                description=(
                    "Absolute path to the destination file. Must be inside an "
                    "allowed --workdir. Missing parent directories are created "
                    "automatically."
                )
            ),
        ],
        file_type: Annotated[
            Literal["json", "yaml", "txt"] | None,
            Field(
                description=(
                    "Optional explicit file type override for the source file. "
                    "If omitted, detected from the source extension."
                )
            ),
        ] = None,
        overwrite: Annotated[
            bool,
            Field(
                description=(
                    "If false (default), fail when destination exists. If true, "
                    "overwrite the existing destination file."
                )
            ),
        ] = False,
    ) -> ConvertFileResult:
        """
        Apply a registered filter to a source file and save the text output.

        Use this tool after register_filter when you want to transform a local
        json, yaml, or txt file and persist the returned string as UTF-8 text.
        The destination path must be inside a configured --workdir; unlike
        run_filter, convert_file refuses to write when no --workdir is configured.

        Missing destination parent directories are created automatically. Existing
        destination files are rejected unless overwrite is true.

        Args:
            filter_id: Identifier returned earlier by register_filter.
            source_file_path: Absolute path to the source file to load.
            destination_file_path: Absolute path where result text is saved.
            file_type: Optional explicit source file type override.
            overwrite: Whether to replace an existing destination file.

        Returns:
            A structured object describing the written file and filter metadata.

        Raises:
            ValueError: If paths are invalid, workdir is missing, the filter is
                unknown or expired, destination exists without overwrite, or the
                filter returns a non-string result.
            FileNotFoundError: If the source file does not exist.
        """

        return active_service.convert_file(
            filter_id,
            source_file_path,
            destination_file_path,
            file_type,
            overwrite,
        )

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
    parser.add_argument(
        "--workdir",
        action="append",
        default=None,
        help=(
            "Absolute directory allowed for file reads. "
            "Repeat the flag to allow multiple directories. "
            "If omitted, no directory restrictions are applied."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    service = FilterService(
        filter_ttl_seconds=args.filter_ttl_seconds,
        cleanup_interval_seconds=args.cleanup_interval_seconds,
        workdirs=args.workdir,
    )
    service.start()
    try:
        create_mcp_server(service).run()
    finally:
        service.stop()


if __name__ == "__main__":
    main()
