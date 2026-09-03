"""Bounded SQLite historian support for the OPC UA server."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from asyncua import ua
from asyncua.common.sql_injection import validate_table_name
from asyncua.common.utils import Buffer
from asyncua.server.history_sql import HistorySQLite
from asyncua.ua.ua_binary import variant_from_binary, variant_to_binary


class BulkHistorySQLite(HistorySQLite):
    """Asyncua historian with explicit timestamps and transactional bulk inserts."""

    def __init__(self, path: str | Path, max_history_data_response_size: int = 10_000) -> None:
        super().__init__(str(path), max_history_data_response_size)

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._db_file)

    async def save_node_values(
        self,
        node_id: ua.NodeId,
        values: Iterable[ua.DataValue],
        *,
        commit: bool = True,
    ) -> None:
        table = self._get_table_name(node_id)
        validate_table_name(table)
        rows = [
            (
                self._encode(value.ServerTimestamp),
                self._encode(value.SourceTimestamp),
                value.StatusCode.value,
                str(value.Value.Value),
                value.Value.VariantType.name,
                sqlite3.Binary(variant_to_binary(value.Value)),
            )
            for value in values
        ]
        if rows:
            await self._db.executemany(
                f'INSERT INTO "{table}" VALUES (NULL, ?, ?, ?, ?, ?, ?)',
                rows,
            )
            if commit:
                await self._db.commit()

    async def commit_pending(self) -> None:
        await self._db.commit()

    async def read_node_history(
        self,
        node_id: ua.NodeId,
        start: datetime | None,
        end: datetime | None,
        nb_values: int,
    ) -> tuple[list[ua.DataValue], datetime | None]:
        table = self._get_table_name(node_id)
        start_time, end_time, order, limit = self._get_bounds(start, end, nb_values)
        validate_table_name(table)
        results: list[ua.DataValue] = []
        async with self._db.execute(
            f'SELECT * FROM "{table}" WHERE "SourceTimestamp" BETWEEN ? AND ? '
            f'ORDER BY "_Id" {order} LIMIT ?',
            (start_time, end_time, limit),
        ) as cursor:
            async for row in cursor:
                results.append(
                    ua.DataValue(
                        variant_from_binary(Buffer(row[6])),
                        ServerTimestamp=self._decode(row[1]),
                        SourceTimestamp=self._decode(row[2]),
                        StatusCode_=ua.StatusCode(row[3]),
                    )
                )
        continuation = (
            results[self.max_history_data_response_size].SourceTimestamp
            if len(results) > self.max_history_data_response_size
            else None
        )
        return results[: self.max_history_data_response_size], continuation

    @staticmethod
    def _encode(value: datetime | None) -> str | None:
        return None if value is None else value.astimezone(UTC).replace(tzinfo=None).isoformat(" ")

    @staticmethod
    def _decode(value: str | None) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)
