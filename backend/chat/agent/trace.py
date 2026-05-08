"""Transcript persistence for agent runs."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class TranscriptWriter:
    """Write agent events to a JSONL transcript file."""

    def __init__(self, transcript_dir: str, chat_id: str, message_id: str):
        self._dir = Path(transcript_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{chat_id}_{message_id}.jsonl"
        self._open = False

    def open(self) -> None:
        if self._open:
            return
        self._file = self._path.open("a", encoding="utf-8")
        self._open = True

    def write_event(self, event_type: str, data: dict) -> None:
        if not self._open:
            self.open()
        line = json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, "data": data},
            ensure_ascii=False,
            default=str,
        )
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._open:
            try:
                self._file.close()
            except Exception:
                logger.exception("Failed to close transcript file")
            finally:
                self._open = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
