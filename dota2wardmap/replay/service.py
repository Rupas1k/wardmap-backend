"""Compatibility imports for the replay service's former public surface."""

from .download import decompress_replay_archive, get_match_data, get_replay
from .parser import download_and_parse_replay, parser_process
from .persistence import persist_parsed_replay
from .worker_service import run_replay_worker

_decompress_replay_archive = decompress_replay_archive

__all__ = [
    "_decompress_replay_archive",
    "download_and_parse_replay",
    "get_match_data",
    "get_replay",
    "parser_process",
    "persist_parsed_replay",
    "run_replay_worker",
]
