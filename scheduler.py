"""Configurable, failure-isolated Telegram financial report scheduler."""

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Mapping

from report import DEFAULT_REPORT_TIMEZONE, REPORT_BUILDERS, ReportDataError, report_now


WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}


def _enabled(value: str | None) -> bool:
    return (value or "false").strip().lower() in {"1", "true", "yes", "on"}


def _time(value: str, setting: str) -> tuple[int, int]:
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (TypeError, ValueError):
        pass
    raise ValueError(f"{setting} harus berformat HH:MM")


@dataclass(frozen=True)
class ReportScheduleConfig:
    daily_enabled: bool
    daily_time: tuple[int, int]
    weekly_enabled: bool
    weekly_day: int
    weekly_time: tuple[int, int]
    monthly_enabled: bool
    monthly_day: int
    monthly_time: tuple[int, int]
    timezone: str
    chat_ids: tuple[int, ...]
    state_file: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ, allowed_chat_ids: tuple[int, ...] = ()) -> "ReportScheduleConfig":
        configured_ids = tuple(int(value.strip()) for value in env.get("REPORT_TELEGRAM_CHAT_IDS", "").split(",") if value.strip())
        chat_ids = (
            tuple(chat_id for chat_id in configured_ids if chat_id in allowed_chat_ids)
            if configured_ids
            else allowed_chat_ids
        )
        weekly_day = env.get("WEEKLY_REPORT_DAY", "monday").lower()
        if weekly_day not in WEEKDAYS:
            raise ValueError("WEEKLY_REPORT_DAY harus nama hari bahasa Inggris")
        monthly_day = int(env.get("MONTHLY_REPORT_DAY", "1"))
        if not 1 <= monthly_day <= 31:
            raise ValueError("MONTHLY_REPORT_DAY harus antara 1 dan 31")
        return cls(
            daily_enabled=_enabled(env.get("DAILY_REPORT_ENABLED")),
            daily_time=_time(env.get("DAILY_REPORT_TIME", "21:00"), "DAILY_REPORT_TIME"),
            weekly_enabled=_enabled(env.get("WEEKLY_REPORT_ENABLED")),
            weekly_day=WEEKDAYS[weekly_day],
            weekly_time=_time(env.get("WEEKLY_REPORT_TIME", "09:00"), "WEEKLY_REPORT_TIME"),
            monthly_enabled=_enabled(env.get("MONTHLY_REPORT_ENABLED")),
            monthly_day=monthly_day,
            monthly_time=_time(env.get("MONTHLY_REPORT_TIME", "09:00"), "MONTHLY_REPORT_TIME"),
            timezone=env.get("REPORT_TIMEZONE", DEFAULT_REPORT_TIMEZONE),
            chat_ids=chat_ids,
            state_file=Path(env.get("REPORT_SCHEDULER_STATE_FILE", "/app/data/report_scheduler_state.json")),
        )


class FinancialReportScheduler:
    def __init__(self, config: ReportScheduleConfig, send: Callable[[int, str], Awaitable[None]]):
        self.config, self.send = config, send
        self._sent = self._load_state()

    def _load_state(self) -> set[str]:
        try:
            return set(json.loads(self.config.state_file.read_text()))
        except (OSError, ValueError, TypeError):
            return set()

    def _save_state(self) -> None:
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.state_file.write_text(json.dumps(sorted(self._sent)))

    def due_reports(self, now: datetime) -> list[str]:
        clock = (now.hour, now.minute)
        due = []
        if self.config.daily_enabled and clock == self.config.daily_time:
            due.append("daily")
        if self.config.weekly_enabled and now.weekday() == self.config.weekly_day and clock == self.config.weekly_time:
            due.append("weekly")
        if self.config.monthly_enabled and now.day == self.config.monthly_day and clock == self.config.monthly_time:
            due.append("monthly")
        return due

    async def tick(self, now: datetime | None = None) -> None:
        now = now or report_now(self.config.timezone)
        for report_type in self.due_reports(now):
            key = f"{report_type}:{now.date().isoformat()}"
            if key in self._sent or not self.config.chat_ids:
                continue
            try:
                message = await asyncio.to_thread(REPORT_BUILDERS[report_type], now)
                for chat_id in self.config.chat_ids:
                    await self.send(chat_id, message)
                self._sent.add(key)
                self._save_state()
            except (ReportDataError, OSError, ValueError) as error:
                print(f"[REPORT] {report_type} skipped: {error}")
            except Exception as error:
                print(f"[REPORT] {report_type} failed: {error!r}")

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as error:
                print(f"[REPORT] scheduler tick failed: {error!r}")
            await asyncio.sleep(30)
