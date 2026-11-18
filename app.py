import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

ROOT = Path(__file__).resolve().parent
Status = Literal["Open", "In progress", "Resolved"]
Category = Literal["Network", "Access", "Hardware", "Software"]
Priority = Literal["Low", "Normal", "High"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
TRANSITIONS = {"Open": {"In progress"}, "In progress": {"Resolved"}, "Resolved": {"Open"}}


class TicketInput(BaseModel):
    title: Title
    description: Note
    category: Category
    priority: Priority


class StatusUpdate(BaseModel):
    status: Status
    version: int


class Comment(BaseModel):
    body: Note


def create_app(db_path=None):
    database = db_path or os.getenv("RELAYDESK_DB", "relaydesk.db")

    @contextmanager
    def connection():
        db = sqlite3.connect(database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_ticket(db, ticket):
        result = db.execute(
            "INSERT INTO tickets(title,description,category,priority) VALUES(?,?,?,?)",
            (ticket.title, ticket.description, ticket.category, ticket.priority),
        )
        db.execute("INSERT INTO activity(ticket_id,body) VALUES(?,?)", (result.lastrowid, "Ticket opened"))
        return result.lastrowid

    def get_ticket(db, ticket_id):
        row = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Ticket not found")
        return dict(row)

    @asynccontextmanager
    async def lifespan(_):
        with connection() as db:
            db.executescript((ROOT / "schema.sql").read_text())
            db.execute("BEGIN IMMEDIATE")
            if os.getenv("RELAYDESK_SEED", "1") == "1" and not db.execute("SELECT 1 FROM tickets LIMIT 1").fetchone():
                examples = [
                    ("Wi-Fi disconnects in the training room", "Several laptops lose connectivity during afternoon sessions.", "Network", "High"),
                    ("New starter needs shared drive access", "Confirm group membership with the team lead before granting access.", "Access", "Normal"),
                    ("External monitor flickers at desk 14", "Issue occurs when connected through the docking station.", "Hardware", "Low"),
                ]
                for title, description, category, priority in examples:
                    add_ticket(db, TicketInput(title=title, description=description, category=category, priority=priority))
        yield

    api = FastAPI(title="RelayDesk API", lifespan=lifespan)

    @api.get("/api/health")
    def health():
        with connection() as db:
            db.execute("SELECT id FROM tickets LIMIT 1").fetchone()
        return {"status": "ok"}

    @api.get("/api/tickets")
    def list_tickets():
        with connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM tickets ORDER BY id DESC")]

    @api.post("/api/tickets", status_code=201)
    def create_ticket(ticket: TicketInput):
        with connection() as db:
            return get_ticket(db, add_ticket(db, ticket))

    @api.get("/api/tickets/{ticket_id}")
    def detail(ticket_id: int):
        with connection() as db:
            ticket = get_ticket(db, ticket_id)
            ticket["activity"] = [dict(row) for row in db.execute(
                "SELECT * FROM activity WHERE ticket_id=? ORDER BY id DESC", (ticket_id,)
            )]
            return ticket

    @api.patch("/api/tickets/{ticket_id}/status")
    def update_status(ticket_id: int, update: StatusUpdate):
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            ticket = get_ticket(db, ticket_id)
            if ticket["version"] != update.version:
                raise HTTPException(409, "Ticket changed. Close the details, reopen them, and try again.")
            if update.status not in TRANSITIONS[ticket["status"]]:
                raise HTTPException(409, "That status transition is unavailable")
            db.execute(
                "UPDATE tickets SET status=?, version=version+1 WHERE id=?", (update.status, ticket_id)
            )
            db.execute(
                "INSERT INTO activity(ticket_id,body) VALUES(?,?)",
                (ticket_id, f'{ticket["status"]} → {update.status}'),
            )
            return get_ticket(db, ticket_id)

    @api.post("/api/tickets/{ticket_id}/notes", status_code=201)
    def add_note(ticket_id: int, comment: Comment):
        with connection() as db:
            get_ticket(db, ticket_id)
            db.execute("INSERT INTO activity(ticket_id,body) VALUES(?,?)", (ticket_id, comment.body))
        return {"saved": True}

    api.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="frontend")
    return api


app = create_app()
