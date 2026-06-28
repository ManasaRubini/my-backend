from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from cachetools import TTLCache
from passlib.context import CryptContext
from math import radians, sin, cos, sqrt, atan2
import datetime
import requests
import os
import shutil

from database import conn, cursor
from models import (
    Issue,
    Comment,
    UserRegister,
    UserLogin,
    Event
)

app = FastAPI(title="LocalPulse API")

# ========================
# AUTH CONFIG (kept as-is)
# ========================
SECRET_KEY = "localpulse_secret_key"
ALGORITHM = "HS256"

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# ========================
# CACHE (NEW - IMPORTANT)
# ========================
cache = TTLCache(maxsize=200, ttl=600)

# ========================
# DISTANCE FUNCTION
# ========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# ========================
# STATIC FILES (images)
# ========================
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)

# =========================================================
# 🆕 NEARBY API (USED BY FLUTTER EXPLORE + CLUSTERING)
# =========================================================
@app.get("/nearby")
def nearby(type: str, lat: float, lon: float):

    key = f"{type}-{lat}-{lon}"

    if key in cache:
        return cache[key]

    tag_map = {
        "hospital": "amenity=hospital",
        "police": "amenity=police",
        "fire": "amenity=fire_station",
        "water": "office=water_utility",
        "waste": "amenity=waste_disposal"
    }

    tag = tag_map.get(type, "amenity=hospital")

    query = f"""
    [out:json];
    (
      node[{tag}]({lat-0.05},{lon-0.05},{lat+0.05},{lon+0.05});
      way[{tag}]({lat-0.05},{lon-0.05},{lat+0.05},{lon+0.05});
      relation[{tag}]({lat-0.05},{lon-0.05},{lat+0.05},{lon+0.05});
    );
    out center;
    """

    try:
        headers = {
            "User-Agent": "LocalPulse/1.0 (contact@example.com)"
        }

        res = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            headers=headers,
            timeout=15
        )

        data = res.json()

        result = []

        for e in data["elements"]:
            lat2 = e.get("lat") or e.get("center", {}).get("lat")
            lon2 = e.get("lon") or e.get("center", {}).get("lon")

            if lat2 and lon2:
                result.append({
                    "lat": lat2,
                    "lon": lon2,
                    "name": e.get("tags", {}).get("name", "Unknown")
                })

        cache[key] = result
        return result

    except Exception:
        return []


# =========================================================
# 🆕 SEARCH API (USED BY SEARCH BAR IN FLUTTER)
# =========================================================
@app.get("/search")
def search(q: str):

    url = "https://nominatim.openstreetmap.org/search"

    headers = {
        "User-Agent": "LocalPulse/1.0"
    }

    params = {
        "q": q,
        "format": "json",
        "limit": 1
    }

    try:
        res = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        print("Status:", res.status_code)
        print("Body:", res.text)

        data = res.json()

        if not data:
            return {"lat": 0, "lon": 0, "name": ""}

        return {
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"]),
            "name": data[0]["display_name"]
        }

    except Exception as e:
        return {"error": str(e)}
# =========================================================
# ISSUE SYSTEM (UNCHANGED - YOUR ORIGINAL CODE)
# =========================================================

@app.post("/issues/create")
async def create_issue(
    user_name: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    anonymous: bool = Form(...),
    image: UploadFile | None = File(None)
):

    image_url = ""

    if image is not None:
        os.makedirs("uploads", exist_ok=True)

        file_path = f"uploads/{image.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        image_url = file_path

    cursor.execute(
        """
        INSERT INTO issues (
            user_name, title, description, image_url,
            category, location, latitude, longitude, anonymous
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_name, title, description, image_url,
            category, location, latitude, longitude, anonymous
        )
    )

    conn.commit()

    return {"message": "Post created successfully"}


@app.get("/issues/all")
def get_issues():

    cursor.execute("SELECT * FROM issues")
    rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "user_name": row[1],
            "title": row[2],
            "description": row[3],
            "image_url": f"https://my-backend-4hfj.onrender.com/{row[4]}" if row[4] else "",
            "category": row[5],
            "location": row[6],
            "latitude": row[7],
            "longitude": row[8],
            "anonymous": bool(row[9]),
            "upvotes": row[10],
            "status": row[11]
        }
        for row in rows
    ]


@app.get("/issues/nearby")
def get_nearby_issues(lat: float, lng: float, radius_km: float = 5):

    print("User Location:", lat, lng)
    cursor.execute("SELECT * FROM issues")
    rows = cursor.fetchall()

    nearby = []

    for row in rows:

        print("Stored:", row[7], row[8])

        distance = haversine_km(lat, lng, row[7], row[8])

        print("Distance:", distance)
        print(
    row[2],
    row[7],
    row[8],
    haversine_km(lat, lng, row[7], row[8])
)
        if distance <= radius_km:
            nearby.append({
                "id": row[0],
                "title": row[2],
                "distance_km": distance
            })

    return nearby

@app.put("/issues/upvote/{issue_id}")
def upvote_issue(issue_id: int):

    cursor.execute(
        "UPDATE issues SET upvotes = upvotes + 1 WHERE id = ?",
        (issue_id,)
    )

    conn.commit()

    return {"message": "Issue upvoted"}


@app.post("/comments/add")
def add_comment(comment: Comment):

    cursor.execute(
        "INSERT INTO comments (issue_id, user_name, comment) VALUES (?, ?, ?)",
        (comment.issue_id, comment.user_name, comment.comment)
    )

    conn.commit()

    return {"message": "Comment added"}


@app.get("/comments/{issue_id}")
def get_comments(issue_id: int):

    cursor.execute("SELECT * FROM comments WHERE issue_id = ?", (issue_id,))
    rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "issue_id": row[1],
            "user_name": row[2],
            "comment": row[3]
        }
        for row in rows
    ]


@app.post("/register")
def register(user: UserRegister):

    cursor.execute(
        "INSERT INTO users (username, password, phone, address) VALUES (?, ?, ?, ?)",
        (user.username, user.password, user.phone, user.address)
    )

    conn.commit()

    return {"message": "User registered successfully"}


@app.post("/login")
def login(user: UserLogin):

    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (user.username, user.password)
    )

    result = cursor.fetchone()

    if result:
        return {"message": "Login successful", "username": user.username}

    return {"error": "Invalid credentials"}


@app.get("/profile/{username}")
def get_profile(username: str):

    cursor.execute(
        "SELECT username, phone, address FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()

    if not user:
        return {"error": "User not found"}

    return {
        "username": user[0],
        "phone": user[1],
        "address": user[2]
    }


@app.post("/events/create")
def create_event(event: Event):

    cursor.execute(
        """
        INSERT INTO events (
            title, description, category,
            location_name, latitude, longitude, start_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.title,
            event.description,
            event.category,
            event.location_name,
            event.latitude,
            event.longitude,
            event.start_time
        )
    )

    conn.commit()

    return {"message": "Event created successfully"}


@app.get("/events/nearby")
def get_nearby_events():

    cursor.execute("SELECT * FROM events")
    rows = cursor.fetchall()

    events = []

    for row in rows:
        events.append({
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "category": row[3],
            "location_name": row[4],
            "latitude": row[5],
            "longitude": row[6],
            "start_time": row[7]
        })

    return events


@app.get("/events/{event_id}")
def get_event(event_id: int):

    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()

    if not row:
        return {"error": "Event not found"}

    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "category": row[3],
        "location_name": row[4],
        "latitude": row[5],
        "longitude": row[6],
        "start_time": row[7]
    }


@app.get("/")
def root():
    return {"message": "LocalPulse Backend Running"}