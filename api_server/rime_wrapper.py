"""Utility classes for working with librime via ctypes.

This module provides a very small subset of the librime C API that is enough
for building a HTTP service which converts Pinyin strings to Chinese text using
an existing Rime schema (for example the Wanxiang schema that lives in this
repository).

The binding is intentionally lightweight so that we do not depend on any
third-party Python packages.  Users are expected to provide a librime shared
library (``libRimeCore.so`` on Linux, ``librime.dylib`` on macOS or the
corresponding DLL on Windows) which is discoverable either through the standard
library search path or via the ``LIBRIME_PATH`` environment variable.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import threading
from dataclasses import dataclass
from typing import Optional


class RimeError(RuntimeError):
    """Generic error raised when librime reports a failure."""


class RimeInitializationError(RimeError):
    """Raised when librime cannot be initialised."""


class RimeConversionError(RimeError):
    """Raised when a conversion request fails."""


class _RimeTraits(ctypes.Structure):
    _fields_ = [
        ("data_size", ctypes.c_size_t),
        ("shared_data_dir", ctypes.c_char_p),
        ("user_data_dir", ctypes.c_char_p),
        ("distribution_name", ctypes.c_char_p),
        ("distribution_code_name", ctypes.c_char_p),
        ("distribution_version", ctypes.c_char_p),
        ("app_name", ctypes.c_char_p),
        ("modules", ctypes.c_char_p),
    ]


class _RimeCommit(ctypes.Structure):
    _fields_ = [
        ("data_size", ctypes.c_size_t),
        ("text", ctypes.c_char_p),
    ]


@dataclass
class RimeConfig:
    """Settings used when initialising :class:`RimeEngine`."""

    shared_data_dir: str
    user_data_dir: str
    schema_id: str = "wanxiang"
    distribution_name: str = "wanxiang"
    distribution_code_name: str = "wanxiang"
    distribution_version: str = "dev"
    app_name: str = "wanxiang-api"
    librime_path: Optional[str] = None


class RimeEngine:
    """Thin wrapper around the subset of librime that we need."""

    def __init__(self, config: RimeConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._load_library()
        self._configure_functions()
        self._session_id: Optional[int] = None
        self._initialise()

    # ------------------------------------------------------------------
    # Library/bootstrap helpers
    # ------------------------------------------------------------------
    def _load_library(self) -> None:
        library_path = self._config.librime_path or os.getenv("LIBRIME_PATH")
        if library_path:
            self._lib = ctypes.CDLL(library_path)
            return

        guessed = ctypes.util.find_library("rime")
        if not guessed:
            raise RimeInitializationError(
                "Unable to locate librime. Set LIBRIME_PATH to the shared library "
                "or provide 'librime_path' in RimeConfig."
            )
        self._lib = ctypes.CDLL(guessed)

    def _configure_functions(self) -> None:
        lib = self._lib
        # Setup/teardown
        lib.RimeSetup.argtypes = [ctypes.POINTER(_RimeTraits)]
        lib.RimeSetup.restype = None

        lib.RimeInitialize.argtypes = [ctypes.POINTER(_RimeTraits)]
        lib.RimeInitialize.restype = None

        lib.RimeFinalize.argtypes = []
        lib.RimeFinalize.restype = None

        lib.RimeStartMaintenance.argtypes = [ctypes.c_bool]
        lib.RimeStartMaintenance.restype = ctypes.c_bool

        lib.RimeJoinMaintenanceThread.argtypes = []
        lib.RimeJoinMaintenanceThread.restype = None

        lib.RimeCreateSession.argtypes = []
        lib.RimeCreateSession.restype = ctypes.c_ulonglong

        lib.RimeDestroySession.argtypes = [ctypes.c_ulonglong]
        lib.RimeDestroySession.restype = ctypes.c_bool

        lib.RimeSelectSchema.argtypes = [ctypes.c_ulonglong, ctypes.c_char_p]
        lib.RimeSelectSchema.restype = ctypes.c_bool

        lib.RimeCleanupStaleSessions.argtypes = []
        lib.RimeCleanupStaleSessions.restype = None

        lib.RimeCleanupAllSessions.argtypes = []
        lib.RimeCleanupAllSessions.restype = None

        lib.RimeDeployWorkspace.argtypes = []
        lib.RimeDeployWorkspace.restype = None

        lib.RimeClearComposition.argtypes = [ctypes.c_ulonglong]
        lib.RimeClearComposition.restype = None

        lib.RimeSimulateKeySequence.argtypes = [ctypes.c_ulonglong, ctypes.c_char_p]
        lib.RimeSimulateKeySequence.restype = ctypes.c_bool

        lib.RimeCommitComposition.argtypes = [ctypes.c_ulonglong]
        lib.RimeCommitComposition.restype = ctypes.c_bool

        lib.RimeGetCommit.argtypes = [ctypes.c_ulonglong, ctypes.POINTER(_RimeCommit)]
        lib.RimeGetCommit.restype = ctypes.c_bool

        lib.RimeFreeCommit.argtypes = [ctypes.POINTER(_RimeCommit)]
        lib.RimeFreeCommit.restype = None

    def _initialise(self) -> None:
        cfg = self._config
        traits = _RimeTraits()
        traits.data_size = ctypes.sizeof(_RimeTraits)
        traits.shared_data_dir = os.fsencode(cfg.shared_data_dir)
        traits.user_data_dir = os.fsencode(cfg.user_data_dir)
        traits.distribution_name = cfg.distribution_name.encode()
        traits.distribution_code_name = cfg.distribution_code_name.encode()
        traits.distribution_version = cfg.distribution_version.encode()
        traits.app_name = cfg.app_name.encode()
        traits.modules = None

        self._lib.RimeSetup(ctypes.byref(traits))
        self._lib.RimeInitialize(ctypes.byref(traits))
        if not self._lib.RimeStartMaintenance(False):
            raise RimeInitializationError("Failed to start librime maintenance thread")
        self._lib.RimeJoinMaintenanceThread()
        self._lib.RimeDeployWorkspace()

        session_id = self._lib.RimeCreateSession()
        if not session_id:
            raise RimeInitializationError("Failed to create librime session")
        schema_id = self._config.schema_id.encode()
        if not self._lib.RimeSelectSchema(session_id, schema_id):
            self._lib.RimeDestroySession(session_id)
            raise RimeInitializationError(
                f"Unable to select schema '{self._config.schema_id}'. "
                "Make sure the schema exists in the shared data directory."
            )
        self._session_id = session_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def convert(self, pinyin: str) -> str:
        """Convert a Pinyin string into Chinese text.

        The implementation is intentionally simple: we feed the key sequence to
        librime, force a commit of the current composition and then return the
        committed text.  Errors from librime are surfaced as
        :class:`RimeConversionError`.
        """

        if self._session_id is None:
            raise RimeConversionError("Rime session is not available")

        sequence = f"{pinyin}<Return>"
        with self._lock:
            if not self._lib.RimeSimulateKeySequence(self._session_id, sequence.encode("utf-8")):
                raise RimeConversionError("Failed to simulate key sequence")

            if not self._lib.RimeCommitComposition(self._session_id):
                raise RimeConversionError("Failed to commit composition")

            commit = _RimeCommit()
            commit.data_size = ctypes.sizeof(_RimeCommit)
            if not self._lib.RimeGetCommit(self._session_id, ctypes.byref(commit)):
                self._lib.RimeClearComposition(self._session_id)
                raise RimeConversionError("Unable to obtain commit result")

            try:
                text = commit.text.decode("utf-8") if commit.text else ""
            finally:
                self._lib.RimeFreeCommit(ctypes.byref(commit))
                self._lib.RimeClearComposition(self._session_id)

            if not text:
                raise RimeConversionError("librime returned an empty commit")
            return text

    def close(self) -> None:
        with self._lock:
            if self._session_id is not None:
                self._lib.RimeDestroySession(self._session_id)
                self._session_id = None
            self._lib.RimeCleanupAllSessions()
            self._lib.RimeFinalize()

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------
    def __enter__(self) -> "RimeEngine":  # pragma: no cover - convenience wrapper
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience wrapper
        self.close()


__all__ = [
    "RimeConfig",
    "RimeConversionError",
    "RimeEngine",
    "RimeInitializationError",
    "RimeError",
]
