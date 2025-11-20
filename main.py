import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from database import db, create_document, get_documents
from schemas import Recipe

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngredientsRequest(BaseModel):
    ingredients: List[str]

@app.get("/")
def read_root():
    return {"message": "Recipe AI backend ready"}

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
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
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

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# --- Core features ---
# 1) Upload photo of a dish → return a best-guess recipe
# Note: In this environment we don't have a vision model by default.
# We'll implement a heuristic placeholder that stores the image metadata
# and returns a friendly, structured recipe guess. You can later
# connect a vision API (e.g., OpenAI, Google) if desired.

@app.post("/api/recipes/from-image")
async def recipe_from_image(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Read small chunk just to ensure stream works (not saved to disk here)
    await file.read()  # consume to avoid hanging upload streams

    # Very simple heuristic guess based on filename keywords
    name_lower = filename.lower()
    if any(k in name_lower for k in ["pizza", "margherita"]):
        title = "Domowa pizza margherita"
        ingredients = [
            "Ciasto do pizzy",
            "Sos pomidorowy",
            "Mozzarella",
            "Świeża bazylia",
            "Oliwa z oliwek",
            "Sól, pieprz"
        ]
        steps = [
            "Rozgrzej piekarnik do 250°C.",
            "Rozwałkuj ciasto, posmaruj sosem.",
            "Dodaj plastry mozzarelli i listki bazylii.",
            "Skrop oliwą i dopraw.",
            "Piec 8–12 minut do zrumienienia."
        ]
    elif any(k in name_lower for k in ["salad", "salat", "sałat"]):
        title = "Kolorowa sałatka warzywna"
        ingredients = [
            "Miks sałat",
            "Pomidor",
            "Ogórek",
            "Czerwona cebula",
            "Oliwa, sok z cytryny",
            "Sól, pieprz"
        ]
        steps = [
            "Warzywa pokrój w kostkę.",
            "Wymieszaj z miksem sałat.",
            "Skrop oliwą i sokiem z cytryny, dopraw do smaku."
        ]
    else:
        title = "Prosty przepis na rozpoznane danie"
        ingredients = [
            "Podstawowe warzywa (np. cebula, czosnek)",
            "Główny składnik (np. kurczak/warzywa/makaron)",
            "Przyprawy (sól, pieprz, papryka)",
            "Tłuszcz do smażenia",
            "Dodatek (np. ryż/makaron/pieczywo)"
        ]
        steps = [
            "Przygotuj składniki: pokrój warzywa i główny składnik.",
            "Podsmaż na rozgrzanym tłuszczu, dopraw do smaku.",
            "Duś lub piecz do miękkości.",
            "Podawaj z wybranym dodatkiem."
        ]

    recipe = Recipe(
        title=title,
        ingredients=ingredients,
        steps=steps,
        source="image",
        image_filename=filename
    )

    try:
        doc_id = create_document("recipe", recipe)
    except Exception:
        doc_id = None

    return {
        "id": doc_id,
        "title": recipe.title,
        "ingredients": recipe.ingredients,
        "steps": recipe.steps
    }

# 2) Provide ingredients → get possible recipes

@app.post("/api/recipes/from-ingredients")
async def recipes_from_ingredients(payload: IngredientsRequest):
    user_ings = [i.strip().lower() for i in payload.ingredients if i.strip()]
    if not user_ings:
        raise HTTPException(status_code=400, detail="Podaj co najmniej jeden składnik")

    # Seed a tiny in-code catalog for matching. In a production app
    # you would keep a larger catalog in the database. We'll also store
    # user queries for history/analytics via create_document.
    catalog = [
        Recipe(
            title="Spaghetti aglio e olio",
            ingredients=["makaron", "czosnek", "oliwa z oliwek", "pietruszka", "papryczka chili", "sól"],
            steps=[
                "Ugotuj makaron al dente.",
                "Na oliwie podsmaż czosnek i chili.",
                "Wymieszaj z makaronem i posiekaną pietruszką, dopraw."
            ],
            source="seed"
        ),
        Recipe(
            title="Sałatka grecka",
            ingredients=["pomidor", "ogórek", "cebula czerwona", "ser feta", "oliwki", "oliwa", "oregano", "sól"],
            steps=[
                "Warzywa pokrój w kostkę.",
                "Dodaj fetę i oliwki, skrop oliwą, posyp oregano.",
                "Dopraw solą i delikatnie wymieszaj."
            ],
            source="seed"
        ),
        Recipe(
            title="Kurczak curry",
            ingredients=["kurczak", "cebula", "czosnek", "imbir", "pasta curry", "mleczko kokosowe", "ryż", "sól"],
            steps=[
                "Podsmaż cebulę, czosnek i imbir.",
                "Dodaj kurczaka i pastę curry, smaż chwilę.",
                "Wlej mleczko kokosowe i duś do miękkości. Podawaj z ryżem."
            ],
            source="seed"
        ),
    ]

    # Simple matching: count overlaps. Return those with at least 2 matches or single if only one provided
    scored = []
    for r in catalog:
        r_ings = [i.lower() for i in r.ingredients]
        overlap = len(set(user_ings) & set(r_ings))
        scored.append((overlap, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [r for score, r in scored if (len(user_ings) == 1 and score >= 1) or (len(user_ings) > 1 and score >= 2)]
    if not results and scored:
        # fallback: top one
        results = [scored[0][1]]

    # Store the query in DB (best-effort)
    try:
        create_document("recipe_query", {"ingredients": user_ings, "matches": [r.title for r in results]})
    except Exception:
        pass

    return [
        {
            "title": r.title,
            "ingredients": r.ingredients,
            "steps": r.steps
        } for r in results
    ]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
