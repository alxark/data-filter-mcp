from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel, Field

LoadedDocument = Any
FilterCallable = Callable[[LoadedDocument], str]


class RegisterFilterResult(BaseModel):
    filter_id: str = Field(
        description="Unique filter identifier to pass into run_filter."
    )
    expires_at: str = Field(
        description="UTC timestamp in ISO 8601 format when the filter expires."
    )
    ttl_seconds: int = Field(
        description="Server-side lifetime of the registered filter in seconds."
    )
    policy_version: str = Field(
        description="Validation policy version used for the submitted filter code."
    )


class RunFilterResult(BaseModel):
    filter_id: str = Field(
        description="Identifier of the registered filter that produced this result."
    )
    file_path: str = Field(
        description="Resolved absolute path of the processed local file."
    )
    file_type: str = Field(
        description="Effective loader type used for the file. One of: json, yaml, txt."
    )
    expires_at: str = Field(
        description="UTC timestamp in ISO 8601 format when this filter expires."
    )
    result_text: str = Field(description="Exact text returned by filter_item(data).")


class ConvertFileResult(BaseModel):
    filter_id: str = Field(
        description="Identifier of the registered filter that produced this file."
    )
    source_file_path: str = Field(
        description="Resolved absolute path of the processed source file."
    )
    destination_file_path: str = Field(
        description="Resolved absolute path where the result text was written."
    )
    file_type: str = Field(
        description="Effective loader type used for the source file. One of: json, yaml, txt."
    )
    expires_at: str = Field(
        description="UTC timestamp in ISO 8601 format when this filter expires."
    )
    bytes_written: int = Field(
        description="Number of UTF-8 bytes written to the destination file."
    )
    overwritten: bool = Field(
        description="Whether an existing destination file was replaced."
    )


@dataclass(slots=True)
class RegisteredFilter:
    filter_id: str
    function: FilterCallable
    source_code: str
    created_at: datetime
    expires_at: datetime
    policy_version: str

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
