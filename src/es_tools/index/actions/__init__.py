"""Index list actions (URI-bound and per-index)."""

from .alias import UpdateAliases
from .allocation import SetAllocation
from .apply_ilm import ApplyIlmPolicy
from .close import CloseIndices
from .cold2frozen import Cold2FrozenIndices
from .confirm_ilm import ConfirmIlmPhase
from .create import CreateIndices
from .data_stream import DeleteDataStreams, RolloverDataStreams
from .delete import DeleteIndices
from .forcemerge import ForceMerge
from .open import OpenIndices
from .promote_ilm import PromoteIlm
from .reindex import ReindexIndices
from .replicas import SetReplicas
from .rollover import RolloverIndices
from .settings import PutIndexSettings
from .shrink import ShrinkIndices

__all__ = [
    "ApplyIlmPolicy",
    "CloseIndices",
    "Cold2FrozenIndices",
    "ConfirmIlmPhase",
    "CreateIndices",
    "DeleteDataStreams",
    "DeleteIndices",
    "ForceMerge",
    "OpenIndices",
    "PromoteIlm",
    "PutIndexSettings",
    "ReindexIndices",
    "RolloverDataStreams",
    "RolloverIndices",
    "SetAllocation",
    "SetReplicas",
    "ShrinkIndices",
    "UpdateAliases",
]
