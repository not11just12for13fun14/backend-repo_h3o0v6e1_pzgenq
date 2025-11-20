"""
Database Schemas for Food Delivery App

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- Restaurant -> "restaurant"
- MenuItem -> "menuitem"
- Order -> "order"
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class Restaurant(BaseModel):
    name: str = Field(..., description="Restaurant name")
    cuisine: str = Field(..., description="Cuisine type")
    rating: float = Field(4.5, ge=0, le=5, description="Average rating")
    image_url: Optional[str] = Field(None, description="Hero image URL")
    delivery_time_min: int = Field(25, ge=5, le=120, description="Estimated minutes for delivery")
    delivery_fee: float = Field(2.99, ge=0, description="Delivery fee in dollars")

class MenuItem(BaseModel):
    restaurant_id: str = Field(..., description="Restaurant ID this item belongs to")
    name: str = Field(..., description="Dish name")
    description: Optional[str] = Field(None, description="Dish description")
    price: float = Field(..., ge=0, description="Price in dollars")
    image_url: Optional[str] = Field(None, description="Image URL for the item")
    is_popular: bool = Field(False, description="Whether this is a popular item")

class OrderItem(BaseModel):
    menu_item_id: str
    restaurant_id: str
    name: str
    price: float
    quantity: int = Field(1, ge=1)

class Order(BaseModel):
    user_name: str
    address: str
    items: List[OrderItem]
    total: float = Field(..., ge=0)
    status: str = Field("placed", description="placed, confirmed, preparing, on_the_way, delivered")
    payment_method: str = Field("cod", description="cod, card, wallet")
