import os
from datetime import datetime, timezone
from math import ceil
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import User, Chat, Message, Payment

app = FastAPI(title="Chatjob API (UK chat platform)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_doc(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


@app.get("/")
def root():
    return {"message": "Chatjob backend running", "currency": "EUR"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:60]}"
    except Exception as e:
        response["backend"] = f"❌ Error: {str(e)[:60]}"
    return response


# Auth / Users (simplified sign-up)
class SignupPayload(BaseModel):
    name: str
    role: str  # creator or customer
    rate_eur_per_min: Optional[float] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


@app.post("/users")
def create_user(payload: SignupPayload):
    if payload.role not in ("creator", "customer"):
        raise HTTPException(status_code=400, detail="role must be 'creator' or 'customer'")
    if payload.role == "creator" and (payload.rate_eur_per_min is None or payload.rate_eur_per_min < 0):
        raise HTTPException(status_code=400, detail="Creators must specify a non-negative rate_eur_per_min")

    user = User(
        name=payload.name,
        role=payload.role,
        rate_eur_per_min=payload.rate_eur_per_min if payload.role == "creator" else None,
        wallet_eur=0.0,
        bio=payload.bio,
        avatar_url=payload.avatar_url,
    )
    user_id = create_document("user", user)
    return {"user_id": user_id, "user": {**user.model_dump(), "id": user_id}}


@app.get("/users/{user_id}")
def get_user(user_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    doc = db.user.find_one({"_id": __import__('bson').ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_doc(doc)


@app.get("/creators")
def list_creators():
    creators = get_documents("user", {"role": "creator"})
    return [serialize_doc(c) for c in creators]


# Wallet operations (EUR)
class TopUpPayload(BaseModel):
    user_id: str
    amount_eur: float


@app.post("/wallet/topup")
def wallet_topup(payload: TopUpPayload):
    if payload.amount_eur <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from bson import ObjectId
    u = db.user.find_one({"_id": ObjectId(payload.user_id)})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    new_balance = round(float(u.get("wallet_eur", 0.0)) + payload.amount_eur, 2)
    db.user.update_one({"_id": ObjectId(payload.user_id)}, {"$set": {"wallet_eur": new_balance, "updated_at": datetime.now(timezone.utc)}})
    pay = Payment(user_id=payload.user_id, kind="topup", amount_eur=payload.amount_eur)
    create_document("payment", pay)
    return {"wallet_eur": new_balance}


# Chats and messages
class StartChatPayload(BaseModel):
    creator_id: str
    customer_id: str


@app.post("/chats")
def start_chat(payload: StartChatPayload):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from bson import ObjectId
    creator = db.user.find_one({"_id": ObjectId(payload.creator_id), "role": "creator"})
    customer = db.user.find_one({"_id": ObjectId(payload.customer_id), "role": "customer"})
    if not creator or not customer:
        raise HTTPException(status_code=400, detail="Invalid creator or customer")
    rate = float(creator.get("rate_eur_per_min", 0.0))
    chat = Chat(
        creator_id=payload.creator_id,
        customer_id=payload.customer_id,
        status="active",
        rate_eur_per_min=rate,
        started_at=now_iso(),
    )
    chat_id = create_document("chat", chat)
    return {"chat_id": chat_id, "chat": {**chat.model_dump(), "id": chat_id}}


@app.get("/chats/{chat_id}/messages")
def list_messages(chat_id: str):
    msgs = get_documents("message", {"chat_id": chat_id})
    msgs = sorted(msgs, key=lambda m: m.get("sent_at", ""))
    return [serialize_doc(m) for m in msgs]


class SendMessagePayload(BaseModel):
    sender_id: str
    content: str


@app.post("/chats/{chat_id}/messages")
def send_message(chat_id: str, payload: SendMessagePayload):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    # basic check chat exists
    from bson import ObjectId
    chat = db.chat.find_one({"_id": ObjectId(chat_id)})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    msg = Message(chat_id=chat_id, sender_id=payload.sender_id, content=payload.content, sent_at=now_iso())
    mid = create_document("message", msg)
    return {"message_id": mid}


@app.post("/chats/{chat_id}/end")
def end_chat(chat_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from bson import ObjectId
    chat = db.chat.find_one({"_id": ObjectId(chat_id)})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("status") == "ended":
        return serialize_doc(chat)

    # compute minutes and cost
    started_at = chat.get("started_at")
    rate = float(chat.get("rate_eur_per_min", 0.0))
    try:
        started_dt = datetime.fromisoformat(started_at)
    except Exception:
        started_dt = datetime.now(timezone.utc)
    minutes = max(1, ceil((datetime.now(timezone.utc) - started_dt).total_seconds() / 60.0))
    total_cost = round(minutes * rate, 2)

    # settle: deduct customer wallet, credit creator wallet
    creator_id = chat.get("creator_id")
    customer_id = chat.get("customer_id")

    creator = db.user.find_one({"_id": ObjectId(creator_id)})
    customer = db.user.find_one({"_id": ObjectId(customer_id)})
    if not creator or not customer:
        raise HTTPException(status_code=400, detail="Creator or customer not found")

    cust_balance = float(customer.get("wallet_eur", 0.0))
    if cust_balance < total_cost:
        # allow negative balance to complete the chat, mark debt as negative payment
        pass
    new_cust = round(cust_balance - total_cost, 2)
    db.user.update_one({"_id": ObjectId(customer_id)}, {"$set": {"wallet_eur": new_cust, "updated_at": datetime.now(timezone.utc)}})
    db.user.update_one({"_id": ObjectId(creator_id)}, {"$set": {"wallet_eur": round(float(creator.get("wallet_eur", 0.0)) + total_cost, 2), "updated_at": datetime.now(timezone.utc)}})

    # record payments
    create_document("payment", Payment(user_id=customer_id, kind="settlement", amount_eur=-total_cost, chat_id=chat_id))
    create_document("payment", Payment(user_id=creator_id, kind="settlement", amount_eur=total_cost, chat_id=chat_id))

    # update chat
    db.chat.update_one(
        {"_id": ObjectId(chat_id)},
        {"$set": {
            "status": "ended",
            "ended_at": now_iso(),
            "total_minutes": minutes,
            "total_cost_eur": total_cost,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    updated = db.chat.find_one({"_id": ObjectId(chat_id)})
    return serialize_doc(updated)


# Seeding sample creators for demo
@app.post("/seed")
def seed_creators():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if db.user.count_documents({"role": "creator"}) > 0:
        return {"message": "Seed data already exists"}
    creators = [
        User(name="Sophie", role="creator", rate_eur_per_min=1.2, bio="Career coach and tech mentor", avatar_url="https://images.unsplash.com/photo-1544005313-94ddf0286df2"),
        User(name="Liam", role="creator", rate_eur_per_min=0.9, bio="Fitness and wellbeing chat", avatar_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e"),
        User(name="Olivia", role="creator", rate_eur_per_min=1.5, bio="Relationship advice and support", avatar_url="https://images.unsplash.com/photo-1547425260-76bcadfb4f2c"),
    ]
    for c in creators:
        create_document("user", c)
    return {"message": "Creators seeded"}
