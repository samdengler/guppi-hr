"""The bridge's HTTP surface: the platform agent kit's AG-UI app around ConnectTurn."""

from __future__ import annotations

import os

from guppi_agent import create_app

from connect_bridge.store import DynamoSessionStore, MemorySessionStore
from connect_bridge.turn import ConnectTurn

_store = None


def store():
    """The session store, built once per process: DynamoDB when a table is configured."""
    global _store
    if _store is None:
        table_name = os.environ.get("SESSION_TABLE", "")
        if table_name:
            import boto3

            table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION")).Table(table_name)
            _store = DynamoSessionStore(table)
        else:
            _store = MemorySessionStore()
    return _store


def build_agent(token: str) -> ConnectTurn:
    return ConnectTurn(token, store())


app = create_app(build_agent)
