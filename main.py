from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo import DESCENDING, MongoClient

app = FastAPI(title="Notes")
uri = "mongodb+srv://viharika807_db_user:XrhmPYnoYwSkhz0R@cluster0.rsofzur.mongodb.net/"
client = MongoClient(uri)
notes_collection = client.notes_app.notes

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

NOTE_COLORS = ("amber", "sage", "sky", "rose", "lavender")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_note(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "content": doc.get("content", ""),
        "color": doc.get("color", "amber"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def parse_object_id(note_id: str) -> ObjectId | None:
    try:
        return ObjectId(note_id)
    except (InvalidId, TypeError):
        return None


def render(
    request: Request,
    name: str,
    status_code: int = 200,
    **context: Any,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
async def list_notes(
    request: Request,
    q: str = Query(default=""),
    message: str = Query(default=""),
):
    query: dict[str, Any] = {}
    search = q.strip()
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"content": {"$regex": search, "$options": "i"}},
        ]

    notes = [
        serialize_note(doc)
        for doc in notes_collection.find(query).sort("updated_at", DESCENDING)
    ]
    return render(
        request,
        "index.html",
        notes=notes,
        q=search,
        message=message,
    )


@app.get("/notes/new", response_class=HTMLResponse)
async def new_note_form(request: Request):
    return render(
        request,
        "note_form.html",
        note=None,
        colors=NOTE_COLORS,
        error="",
    )


@app.post("/notes")
async def create_note(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    color: str = Form("amber"),
):
    title = title.strip()
    content = content.strip()
    if color not in NOTE_COLORS:
        color = "amber"

    if not title:
        return render(
            request,
            "note_form.html",
            status_code=400,
            note={"title": title, "content": content, "color": color},
            colors=NOTE_COLORS,
            error="Please add a title before saving.",
        )

    now = utc_now()
    notes_collection.insert_one(
        {
            "title": title,
            "content": content,
            "color": color,
            "created_at": now,
            "updated_at": now,
        }
    )
    return RedirectResponse("/?message=Note+created", status_code=303)


@app.get("/notes/{note_id}", response_class=HTMLResponse)
async def view_note(request: Request, note_id: str):
    object_id = parse_object_id(note_id)
    doc = notes_collection.find_one({"_id": object_id}) if object_id else None
    if not doc:
        return render(request, "not_found.html", status_code=404)

    return render(request, "note_detail.html", note=serialize_note(doc))


@app.get("/notes/{note_id}/edit", response_class=HTMLResponse)
async def edit_note_form(request: Request, note_id: str):
    object_id = parse_object_id(note_id)
    doc = notes_collection.find_one({"_id": object_id}) if object_id else None
    if not doc:
        return render(request, "not_found.html", status_code=404)

    return render(
        request,
        "note_form.html",
        note=serialize_note(doc),
        colors=NOTE_COLORS,
        error="",
    )


@app.post("/notes/{note_id}")
async def update_note(
    request: Request,
    note_id: str,
    title: str = Form(...),
    content: str = Form(""),
    color: str = Form("amber"),
):
    object_id = parse_object_id(note_id)
    doc = notes_collection.find_one({"_id": object_id}) if object_id else None
    if not doc:
        return render(request, "not_found.html", status_code=404)

    title = title.strip()
    content = content.strip()
    if color not in NOTE_COLORS:
        color = "amber"

    if not title:
        note = serialize_note(doc)
        note.update({"title": title, "content": content, "color": color})
        return render(
            request,
            "note_form.html",
            status_code=400,
            note=note,
            colors=NOTE_COLORS,
            error="Please add a title before saving.",
        )

    notes_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "title": title,
                "content": content,
                "color": color,
                "updated_at": utc_now(),
            }
        },
    )
    return RedirectResponse("/?message=Note+updated", status_code=303)


@app.post("/notes/{note_id}/delete")
async def delete_note(note_id: str):
    object_id = parse_object_id(note_id)
    if object_id:
        notes_collection.delete_one({"_id": object_id})
    return RedirectResponse("/?message=Note+deleted", status_code=303)
