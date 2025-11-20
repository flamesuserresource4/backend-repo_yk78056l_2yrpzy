"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Recipe schema used by the app
class Recipe(BaseModel):
    """
    Recipes collection schema
    Collection name: "recipe"
    """
    title: str = Field(..., description="Recipe title")
    ingredients: List[str] = Field(..., description="List of ingredients")
    steps: List[str] = Field(..., description="Step-by-step preparation instructions")
    source: Optional[str] = Field(None, description="Where the recipe came from (e.g., 'image', 'manual', 'seed')")
    image_filename: Optional[str] = Field(None, description="Original uploaded image filename if available")
