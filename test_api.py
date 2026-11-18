import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app


class TicketTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "test.db"
        self.client = self.enterContext(TestClient(create_app(self.db)))
        response = self.client.post("/api/tickets", json={
            "title": "VPN is unavailable", "description": "VPN disconnects after login.",
            "category": "Network", "priority": "High",
        })
        self.assertEqual(response.status_code, 201)
        self.ticket = response.json()
        self.path = f'/api/tickets/{self.ticket["id"]}'

    def test_lifecycle_and_activity(self):
        for version, status in enumerate(["In progress", "Resolved", "Open"], start=1):
            response = self.client.patch(self.path + "/status", json={"status": status, "version": version})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["version"], version + 1)
        response = self.client.post(self.path + "/notes", json={"body": "Verified access."})
        self.assertEqual(response.status_code, 201)
        detail = self.client.get(self.path).json()
        self.assertEqual(detail["status"], "Open")
        self.assertEqual([entry["body"] for entry in detail["activity"]], [
            "Verified access.", "Resolved → Open", "In progress → Resolved",
            "Open → In progress", "Ticket opened",
        ])

    def test_invalid_transition_does_not_write_activity(self):
        response = self.client.patch(self.path + "/status", json={"status": "Resolved", "version": 1})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.client.get(self.path).json()["activity"]), 1)

    def test_concurrent_edits_reject_one_update(self):
        def start_work(_):
            return self.client.patch(self.path + "/status", json={"status": "In progress", "version": 1})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(start_work, range(2)))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        self.assertEqual(len(self.client.get(self.path).json()["activity"]), 2)

    def test_validation_and_missing_ticket(self):
        self.assertEqual(self.client.post("/api/tickets", json={"title": "   "}).status_code, 422)
        self.assertEqual(self.client.get("/api/tickets/99999").status_code, 404)

    def test_persists_across_restart(self):
        with TestClient(create_app(self.db)) as restarted:
            self.assertEqual(restarted.get(self.path).json()["title"], self.ticket["title"])
