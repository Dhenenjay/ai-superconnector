# Connector stubs provide a standard interface but do not perform real OAuth/API calls yet.
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable


class Connector(Protocol):
    def backfill(self, user_id: int) -> Iterable[dict]:
        ...

    def send(self, payload: dict) -> dict:
        ...


@dataclass
class GmailConnector:
    def backfill(self, user_id: int):
        # dummy data
        yield {
            "provider": "gmail",
            "provider_type": "message",
            "provider_id": "demo-gmail-1",
            "title": "Welcome to Superconnector",
            "body": "This is a placeholder email for user %d" % user_id,
            "metadata_json": {"from": "noreply@example.com"},
        }

    def send(self, payload: dict) -> dict:
        return {"status": "queued", "provider": "gmail", "payload": payload}


@dataclass
class SlackConnector:
    def backfill(self, user_id: int):
        yield {
            "provider": "slack",
            "provider_type": "message",
            "provider_id": "demo-slack-1",
            "title": "General channel greeting",
            "body": "Hello user %d from #general" % user_id,
            "metadata_json": {"channel": "general"},
        }

    def send(self, payload: dict) -> dict:
        return {"status": "queued", "provider": "slack", "payload": payload}


@dataclass
class NotionConnector:
    def backfill(self, user_id: int):
        yield {
            "provider": "notion",
            "provider_type": "file",
            "provider_id": "demo-notion-1",
            "title": "Project Plan",
            "body": "Goals, milestones, and tasks",
            "metadata_json": {"database": "docs"},
        }

    def send(self, payload: dict) -> dict:
        return {"status": "queued", "provider": "notion", "payload": payload}

