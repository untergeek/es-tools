"""es_tools package.

Unified Elasticsearch tools package consolidating Elasticsearch utility modules
into a single, publishable Python package with a hierarchical submodule layout.

Modules:
    - es_tools.client: Core ES client builder with schema validation
    - es_tools.wait: Wait utilities for ES tasks and API calls
    - es_tools.checkpoint: Progress tracking for ES operations
    - es_tools.snapshot: Snapshot and repository operations
    - es_tools.redact: ILM helpers and hot-index field redaction
    - es_tools.reindex: Reindex task monitoring
    - es_tools.index: Index list actions
    - es_tools.select: Pattern, alias, query, and data-stream name selectors
    - es_tools.docker: Docker test infrastructure
    - es_tools.utils: Common utilities and configuration

Example:
    >>> from es_tools.client import create_client
    >>> from es_tools.wait import Health
    >>> from es_tools.checkpoint import Job
"""

from datetime import UTC, datetime

from .checkpoint import Job, Step, Workbook
from .client import (
    VERSION_MAX,
    VERSION_MIN,
    ClientConfig,
    ConfigParser,
    ElasticsearchConfig,
    ESToolConfigurationError,
    ESToolConnectionError,
    ESToolSchemaValidationError,
    OtherSettings,
    check_es_version,
    create_client,
    get_version,
    validate_config,
    verify_ssl_paths,
    verify_url_schema,
)
from .docker import ElasticsearchDocker
from .reindex import ReindexMonitor, ReindexTask
from .snapshot import SnapshotTool
from .wait import (
    Exists,
    Health,
    IlmPhase,
    IlmStep,
    Relocate,
    Restore,
    Snapshot,
    Task,
)

FIRST_YEAR = 2022

def get_copyright_years() -> str:
    now = datetime.now(UTC)
    if now.year == FIRST_YEAR:
        return f"{FIRST_YEAR}"
    return f"{FIRST_YEAR}-{now.year}"

__version__ = "0.1.0a1"
__author__ = "Aaron Mildenstein"
__copyright__ = f"{get_copyright_years()}, {__author__}"
__license__ = "Apache 2.0"
__status__ = "Development"
__description__ = "Unified Elasticsearch tools package"
__url__ = "https://github.com/untergeek/es-tools"
__email__ = "aaron@mildensteins.com"
__maintainer__ = "Aaron Mildenstein"
__maintainer_email__ = f"{__email__}"
__keywords__ = [
    "elasticsearch",
    "es",
    "client",
    "tools",
    "wait",
    "checkpoint",
    "snapshot",
    "redact",
    "reindex",
    "index",
    "docker",
]
__classifiers__ = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
]

__all__ = [
    # Client
    "create_client",
    "ConfigParser",
    "validate_config",
    "verify_url_schema",
    "verify_ssl_paths",
    "VERSION_MAX",
    "VERSION_MIN",
    "check_es_version",
    "get_version",
    "ESToolConfigurationError",
    "ESToolConnectionError",
    "ESToolSchemaValidationError",
    "ClientConfig",
    "OtherSettings",
    "ElasticsearchConfig",
    # Wait
    "Exists",
    "Health",
    "IlmPhase",
    "IlmStep",
    "Relocate",
    "Restore",
    "Snapshot",
    "Task",
    # Checkpoint
    "Workbook",
    "Job",
    "Step",
    # Snapshot
    "SnapshotTool",
    # Reindex
    "ReindexTask",
    "ReindexMonitor",
    # Docker
    "ElasticsearchDocker",
    # Package metadata
    "__version__",
    "__author__",
    "__copyright__",
    "__license__",
    "__status__",
    "__description__",
    "__url__",
]
