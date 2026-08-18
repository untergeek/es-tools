"""Consolidated exception classes for es_tools.

All exceptions use ESTool prefix to prevent naming conflicts across submodules.
"""


class ESToolException(Exception):
    """Base exception for all es_tools errors."""


# Client exceptions
class ESToolConfigurationError(ESToolException):
    """Configuration validation or setup error."""


class ESToolConnectionError(ESToolException):
    """Error connecting to Elasticsearch."""


class ESToolNotMaster(ESToolConnectionError):
    """Error: connected to non-master node when master_only is True."""


class ESToolVersionError(ESToolException):
    """Error with Elasticsearch version."""


class ESToolSchemaValidationError(ESToolException):
    """Error validating configuration schema."""


class ESToolBuilderException(ESToolException):
    """Base exception for Builder errors."""


# Docker exceptions
class ESToolDockerException(ESToolException):
    """Base exception for Docker operations."""


class ESToolContainerError(ESToolDockerException):
    """Error with Docker container."""


class ESToolContainerNotFound(ESToolDockerException):
    """Container not found."""


class ESToolContainerRunningError(ESToolDockerException):
    """Container running error."""


# List actions
class ESToolActionError(ESToolException):
    """List action failed."""


# Reindex exceptions
class ESToolReindexException(ESToolException):
    """Base exception for reindex operations."""


class ESToolTaskNotFoundError(ESToolReindexException):
    """Task not found in Elasticsearch."""


class ESToolReindexError(ESToolReindexException):
    """Error during reindex operation."""


class ESToolTaskTimeoutError(ESToolReindexException):
    """Timeout waiting for task to complete."""


# Redact exceptions
class ESToolRedactException(ESToolException):
    """Base exception for redaction operations."""


class ESToolFatalError(ESToolRedactException):
    """Fatal error that should not be retried."""


class ESToolMissingIndex(ESToolRedactException):
    """Index not found."""


class ESToolRedactionError(ESToolRedactException):
    """Error during redaction."""


# Snapshot exceptions
class ESToolSnapshotException(ESToolException):
    """Base exception for snapshot operations."""


class ESToolRestoreError(ESToolSnapshotException):
    """Error during restore operation."""


class ESToolRepositoryError(ESToolSnapshotException):
    """Error related to snapshot repository."""


# Checkpoint exceptions
class ESToolCheckpointException(ESToolException):
    """Base exception for checkpoint tracking operations."""


class ESToolClientError(ESToolCheckpointException):
    """Error related to Elasticsearch client operations."""


class ESToolMissingDocument(ESToolCheckpointException):
    """Document not found in tracking index."""


# Wait exceptions
class ESToolWaitException(ESToolException):
    """Base exception for wait operations."""


class ESToolWaitFatal(ESToolWaitException):
    """Fatal error that should not be retried."""


class ESToolWaitTimeout(ESToolWaitException):
    """Timeout waiting for operation to complete."""


class ESToolExceptionCount(ESToolWaitException):
    """Too many exceptions raised."""


class ESToolIlmWaitError(ESToolWaitException):
    """Error during ILM phase/step wait."""
