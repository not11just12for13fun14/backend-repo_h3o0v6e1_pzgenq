import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Restaurant, MenuItem, Order, OrderItem

app = FastAPI(title="Food Delivery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert Mongo documents

def serialize_doc(doc):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc

@app.get("/")
def read_root():
    return {"message": "Food Delivery Backend is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Seed endpoint to create sample restaurants and menu items
@app.post("/seed")
def seed_data():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Avoid duplicate seeding
    existing = list(db.restaurant.find().limit(1))
    if existing:
        return {"message": "Seed data already exists"}

    restaurants = [
        Restaurant(
            name="Saffron Kitchen",
            cuisine="Indian",
            rating=4.7,
            image_url="https://images.unsplash.com/photo-1604908176997-431a1f6734b2",
            delivery_time_min=30,
            delivery_fee=2.99
        ),
        Restaurant(
            name="Tokyo Bites",
            cuisine="Japanese",
            rating=4.6,
            image_url="https://images.unsplash.com/photo-1553621042-f6e147245754",
            delivery_time_min=25,
            delivery_fee=3.49
        ),
        Restaurant(
            name="Green Bowl",
            cuisine="Healthy",
            rating=4.8,
            image_url="https://images.unsplash.com/photo-1543353071-087092ec393e",
            delivery_time_min=20,
            delivery_fee=1.99
        ),
    ]

    rest_ids = []
    for r in restaurants:
        rid = create_document("restaurant", r)
        rest_ids.append(rid)

    # Menu items
    menu_items = [
        MenuItem(restaurant_id=rest_ids[0], name="Butter Chicken", description="Creamy tomato gravy", price=12.99, image_url="https://images.unsplash.com/photo-1604908554027-0e03f98dda4e", is_popular=True),
        MenuItem(restaurant_id=rest_ids[0], name="Paneer Tikka", description="Smoky cottage cheese", price=10.49, image_url="https://images.unsplash.com/photo-1596797038530-2c1072297e59"),
        MenuItem(restaurant_id=rest_ids[1], name="Salmon Sushi Set", description="12 pcs assorted", price=16.99, image_url="https://images.unsplash.com/photo-1553621042-f6e147245754", is_popular=True),
        MenuItem(restaurant_id=rest_ids[1], name="Chicken Ramen", description="Rich tonkotsu broth", price=13.49, image_url="https://images.unsplash.com/photo-1543353071-087092ec393e"),
        MenuItem(restaurant_id=rest_ids[2], name="Super Green Bowl", description="Kale, avocado, quinoa", price=11.99, image_url="https://images.unsplash.com/photo-1540420773420-3366772f4999", is_popular=True),
        MenuItem(restaurant_id=rest_ids[2], name="Falafel Wrap", description="Herby chickpea goodness", price=9.49, image_url="https://images.unsplash.com/photo-1625944528755-7344a5bc9c89"),
    ]

    for m in menu_items:
        create_document("menuitem", m)

    return {"message": "Seed data inserted"}

# Public endpoints

@app.get("/restaurants")
def list_restaurants():
    items = get_documents("restaurant")
    return [serialize_doc(i) for i in items]

@app.get("/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id: str):
    items = get_documents("menuitem", {"restaurant_id": restaurant_id})
    return [serialize_doc(i) for i in items]

class CreateOrderPayload(BaseModel):
    user_name: str
    address: str
    items: List[OrderItem]

@app.post("/orders")
def create_order(payload: CreateOrderPayload):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Calculate total
    total = 0.0
    for it in payload.items:
        total += it.price * it.quantity

    order = Order(
        user_name=payload.user_name,
        address=payload.address,
        items=payload.items,
        total=round(total, 2),
        status="placed",
        payment_method="cod",
    )
    oid = create_document("order", order)
    return {"order_id": oid, "total": order.total, "status": order.status}
