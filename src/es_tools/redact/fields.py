"""Hot-index field redaction via update_by_query.

This is a real mutating action. dry_run is ActionRun's job — execute()
always issues the ES call. execute() loops until matching hits are 0
(or fails). It waits on each task itself so leftover documents cannot
journal COMPLETED.
"""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.checkpoint.events import Progress
from es_tools.debug import begin_end
from es_tools.exceptions import ESToolActionError
from es_tools.wait.task import Task

MAX_UNCHANGED = 10


def _require_fields(fields: list[str]) -> list[str]:
    """Reject empty lists and empty/dotted-empty field names."""
    if not fields:
        raise ValueError("fields must be a non-empty list")
    cleaned: list[str] = []
    for field in fields:
        if not field or any(part == "" for part in field.split(".")):
            raise ValueError("fields must be non-empty dotted names")
        cleaned.append(field)
    return cleaned


def count_hits(client: Any, index: str, query: dict[str, Any]) -> int:
    """Return the number of documents matching ``query`` on ``index``.

    Args:
        client: Elasticsearch client.
        index: Index name.
        query: Query DSL.

    Returns:
        Hit count. Zero is only returned for a well-formed empty total.

    Raises:
        ESToolActionError: Response is not a mapping or lacks ``hits.total``.
    """
    raw = client.search(
        index=index,
        query=query,
        size=0,
        track_total_hits=True,
        ignore_unavailable=True,
    )
    body: Any = raw if isinstance(raw, dict) else None
    if body is None:
        maybe = getattr(raw, "body", None)
        if isinstance(maybe, dict):
            body = maybe
    if body is None and hasattr(raw, "get"):
        body = raw
    if not isinstance(body, dict):
        raise ESToolActionError("search response is not a mapping")
    hits = body.get("hits")
    if not isinstance(hits, dict):
        raise ESToolActionError("search response missing hits")
    total = hits.get("total")
    if isinstance(total, dict):
        if "value" not in total:
            raise ESToolActionError("search hits.total missing value")
        return int(total.get("value") or 0)
    if total is None:
        raise ESToolActionError("search hits.total missing")
    try:
        return int(total)
    except (TypeError, ValueError) as exc:
        raise ESToolActionError("search hits.total is not a count") from exc


def build_script(message: str, fields: list[str]) -> dict[str, Any]:
    """Return a Painless script that sets each existing field to ``message``.

    Args:
        message: Replacement string (e.g. ``REDACTED``).
        fields: Dotted field names.

    Returns:
        Elasticsearch ``script`` body.

    Raises:
        ValueError: Empty message or fields.
    """
    if not message:
        raise ValueError("message must be non-empty")
    fields = _require_fields(fields)
    lines: list[str] = []
    for field in fields:
        path = field.split(".")
        condition = "?.".join(["ctx._source", *path]) + " != null"
        assignment = f"ctx._source.{field} = params.replacement;"
        lines.append(f"if ({condition}) {{\n  {assignment}\n}}")
    return {
        "source": "\n".join(lines),
        "lang": "painless",
        "params": {"replacement": message},
    }


def _task_id(raw: Any) -> str | None:
    if hasattr(raw, "get"):
        task = raw.get("task")
        if task:
            return str(task)
    body = getattr(raw, "body", None)
    if isinstance(body, dict) and body.get("task"):
        return str(body["task"])
    return None


class RedactFields:
    """Overwrite matching fields until the query has zero hits.

    Each pass starts ``update_by_query`` and waits on the task. Execute
    fails (workbook does not COMPLETED) when the hit count is unchanged
    for ``MAX_UNCHANGED + 1`` consecutive iterations (11 with the
    default of 10), matching pii-tool's ``times_unchanged > 10``.

    Args:
        query: Query DSL identifying documents to change.
        fields: Dotted field names to overwrite.
        message: Replacement value.

    Raises:
        ValueError: Empty query, fields, or message.
    """

    name = "redact_fields"
    mode: Mode = "per_item"
    wait_type: str | None = None
    task_action = "update_by_query"

    def __init__(
        self,
        query: dict[str, Any],
        fields: list[str],
        message: str = "REDACTED",
    ) -> None:
        if not query:
            raise ValueError("query must be a non-empty mapping")
        if not message:
            raise ValueError("message must be non-empty")
        self.query = dict(query)
        self.fields = _require_fields(fields)
        self.message = message

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Redact ``names[0]`` until matching hits are 0.

        Args:
            client: Elasticsearch client.
            names: One-item unit (index name).
            **opts: Optional ``event_bus`` (EventBus). When present,
                publishes ``Progress`` before each ``update_by_query``.

        Returns:
            ExecuteResult. ``ok`` is False if the task id is missing or
            hits remain after stagnant iterations.
        """
        bus = opts.get("event_bus")
        index = names[0]
        hits = count_hits(client, index, self.query)
        if hits == 0:
            return ExecuteResult(ok=True, names=names)
        last_raw: Any = None
        last_task: str | None = None
        unchanged = 0
        last_hits = -1
        iteration = 0
        script = build_script(self.message, self.fields)
        while hits > 0:
            if hits == last_hits:
                unchanged += 1
            else:
                unchanged = 0
            if unchanged > MAX_UNCHANGED:
                return ExecuteResult(
                    ok=False,
                    names=names,
                    raw=last_raw,
                    task_id=last_task,
                    error=(
                        f"{hits} hits remain after {unchanged} unchanged iterations"
                    ),
                )
            iteration += 1
            if bus is not None:
                bus.publish(
                    Progress(
                        job_id=str(opts.get("job_id") or ""),
                        step_name=self.name,
                        index=index,
                        iteration=iteration,
                        hits=hits,
                    )
                )
            last_hits = hits
            last_raw = client.update_by_query(
                index=index,
                script=script,
                query=self.query,
                wait_for_completion=False,
                expand_wildcards=["open", "hidden"],
                refresh=True,
            )
            last_task = _task_id(last_raw)
            if not last_task:
                return ExecuteResult(
                    ok=False,
                    names=names,
                    raw=last_raw,
                    task_id=None,
                    error="update_by_query did not return a task id",
                )
            Task(client, action="update_by_query", task_id=last_task).wait()
            hits = count_hits(client, index, self.query)
        return ExecuteResult(ok=True, names=names, raw=last_raw, task_id=last_task)
