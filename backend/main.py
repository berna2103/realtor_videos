import os
import uuid
import asyncio
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client, Client
import traceback
import requests
import urllib.parse

# Import the GenAI SDK for the auto-neighborhood feature
from google import genai

from engine import render_cinematic_video
from scraper import fetch_zillow_data, analyze_scenes_batch, generate_fb_post_content

app = FastAPI(title="Cinematic Listing AI Backend")

# Setup Supabase
supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Setup Gemini API Key for local tasks
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_base_url():
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    return f"https://{domain}" if domain else "http://127.0.0.1:8000"

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR, INPUT_DIR = os.path.join(BASE_DIR, "output"), os.path.join(BASE_DIR, "raw_photos")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/raw_photos", StaticFiles(directory=INPUT_DIR), name="raw_photos")

jobs = {}

# --- MODELS ---

class FetchRequest(BaseModel):
    zillowUrl: str
    language: Optional[str] = "English"
    user_id: Optional[str] = None
    neighborhood_context: Optional[str] = ""

class MetaDef(BaseModel):
    address: str 
    price: str 
    beds: str 
    baths: str 
    sqft: str 
    agent: str 
    brokerage: str 
    phone: str = "" 
    website: str = "" 
    mls_source: str 
    mls_number: str 
    custom_cta: Optional[str] = None
    neighborhood_context: Optional[str] = ""

class SceneDef(BaseModel):
    id: str
    image_path: str
    room_type: str
    caption: str
    effect: str 
    enable_vo: bool
    image_url: Optional[str] = None


class RenderRequest(BaseModel):
    user_id: Optional[str] = None
    meta: Optional[MetaDef] = None
    scenes: Optional[List[SceneDef]] = None
    format: Optional[str] = "Vertical (1080x1920)"
    language: Optional[str] = "English"
    voice: Optional[str] = "English-US-Bella"
    font: Optional[str] = "Inter"
    music: Optional[str] = "none"
    primary_color: str = "#552448"
    logo_data: Optional[str] = None
    status_choice: Optional[str] = "Home For Sale"
    is_own_listing: Optional[bool] = True
    custom_cta: Optional[str] = None
    show_captions: Optional[bool] = True  
    enable_voice: Optional[bool] = True

# --- BACKGROUND RENDER TASK ---

def fetch_real_places(lat: float, lng: float, place_type: str) -> str:
    """Fetches real local places using precise coordinates and the New Places API."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key or not lat or not lng:
        return ""

    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName.text" 
    }

    # 1. Removed "top" to broaden the search
    # 2. Changed to locationBias so Google guarantees results
    payload = {
        "textQuery": place_type, 
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lng
                },
                "radius": 2000.0  # 2000 meters
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        
        # --- NEW: Print raw Google data to the terminal ---
        print(f"RAW GOOGLE RESPONSE [{place_type}]: {data}")

        if "error" in data:
            print(f"Google API Error [{place_type}]: {data['error'].get('message', 'Unknown error')}")
            return ""

        places = data.get("places", [])
        
        # Grab the names of the top 2 results
        names = []
        for place in places[:3]:
            name = place.get("displayName", {}).get("text")
            if name:
                names.append(name)

        return ", ".join(names)

    except Exception as e:
        print(f"Places API Exception: {e}")
        return ""
    
def background_render_task(job_id: str, req: RenderRequest):
    """Handles the async render function and cleans up disk space."""
    try:
        jobs[job_id]["status"] = "rendering"
        jobs[job_id]["progress"] = 2
        output_filename = f"listing_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Run the async render function in a controlled loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(render_cinematic_video(job_id, req, output_path, BASE_DIR))

        if success:
            jobs[job_id]["progress"] = 99 
            final_video_url = f"{get_base_url()}/outputs/{output_filename}"
            
            if supabase:
                try:
                    with open(output_path, "rb") as f:
                        supabase.storage.from_("listings").upload(
                            path=output_filename, 
                            file=f.read(), 
                            file_options={"content-type": "video/mp4"}
                        )
                    final_video_url = supabase.storage.from_("listings").get_public_url(output_filename)
                    
                    if req.user_id:
                        supabase.table("user_videos").insert({
                            "user_id": req.user_id, 
                            "video_url": final_video_url, 
                            "property_address": req.meta.address if req.meta else "New Listing"
                        }).execute()
                    
                    # Prevent "Disk Full" server crashes by deleting local file after cloud upload
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                            print(f"Cleaned up local file: {output_filename}")
                    except Exception as cleanup_error:
                        print(f"Could not remove local file: {cleanup_error}")

                except Exception as e: 
                    print(f"Supabase upload failed: {e}")
                    # If Supabase fails, it will gracefully fallback to serving the local URL

            jobs[job_id].update({"status": "completed", "progress": 100, "video_url": final_video_url})
            
    except Exception as e:
        print(f"\n--- FATAL ERROR RENDERING JOB {job_id} ---")
        traceback.print_exc()  
        jobs[job_id].update({"status": "failed", "error": str(e), "progress": 0})
            
# --- ENDPOINTS ---

@app.post("/api/fetch-zillow")
async def fetch_zillow(req: FetchRequest):
    if supabase and req.user_id:
        # Check credits
        user_data = supabase.table("user_credits").select("balance").eq("user_id", req.user_id).single().execute()
        if user_data.data and user_data.data.get("credits", 0) < 1: 
            raise HTTPException(status_code=402, detail="Insufficient credits.")
    
    try:
        # 1. Fetch data and images
        meta_data, downloaded_images = fetch_zillow_data(req.zillowUrl)
        downloaded_images = list(dict.fromkeys(downloaded_images))

        # --- SMART HYPER-LOCAL NEIGHBORHOOD SYSTEM ---
        if req.neighborhood_context and req.neighborhood_context.strip():
            meta_data['neighborhood_context'] = req.neighborhood_context.strip()
        else:
            address_str = meta_data.get("address", "")
            
            # Safely extract latitude and longitude from the Zillow metadata
            try:
                lat = float(meta_data.get("latitude")) if meta_data.get("latitude") else None
                lng = float(meta_data.get("longitude")) if meta_data.get("longitude") else None
            except (ValueError, TypeError):
                lat, lng = None, None

            if address_str and GEMINI_API_KEY:
                try:
                    # 1. Fetch 100% real data from Google Maps using coordinates
                    if lat and lng:
                        real_restaurants = fetch_real_places(lat, lng, "restaurants")
                        real_parks = fetch_real_places(lat, lng, "parks")
                        real_transit = fetch_real_places(lat, lng, "transit stations")
                        real_schools = fetch_real_places(lat, lng, "schools")
                        real_shopping = fetch_real_places(lat, lng, "shopping centers")
                    else:
                        print("Warning: Latitude or Longitude missing. Cannot fetch exact places.")
                        real_restaurants = real_parks = real_transit = real_schools = real_shopping = ""

                    print(f"Real places for {address_str} ({lat}, {lng}):\nRestaurants: {real_restaurants}\nParks: {real_parks}\nTransit: {real_transit}\nSchools: {real_schools}\nShopping: {real_shopping}")
                    
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    
                    # 2. Force Gemini to use ONLY the data we just scraped
                    vibe_prompt = f"""
                    You are a highly knowledgeable local real estate expert for {address_str}.
                    Write a 3-sentence neighborhood lifestyle pitch for a homebuyer. 
                    
                    You MUST mention these exact local restaurants: {real_restaurants}.
                    You MUST mention these exact nearby parks: {real_parks}.
                    You MUST mention these exact transit stations: {real_transit}.
                    You MUST mention these exact schools: {real_schools}.
                    You MUST mention these exact shopping centers: {real_shopping}.

                    Weave them into a natural, exciting pitch. 
                    CRITICAL: Do NOT invent, guess, or hallucinate any other places, restaurants, or amenities.
                    """
                    response = client.models.generate_content(model='gemini-2.0-flash', contents=vibe_prompt)
                    meta_data['neighborhood_context'] = response.text.strip()
                except Exception as e:
                    print(f"Failed to auto-generate neighborhood context: {e}")
                    meta_data['neighborhood_context'] = ""
        # ---------------------------------------------

        print(f"Fetched metadata: {meta_data}")
        
        # 2. Generate content (FB Post and the Batch Video Script)
        base_url = get_base_url()
        address_str = meta_data.get("address", "New Listing")
        
        # Multi-Platform Social Drafts
        facebook_draft = generate_fb_post_content(meta_data, req.language)
        social_drafts = {
            "facebook": facebook_draft,
            "instagram": f"📸 Just Listed! {address_str} 🏡\n\nLink in bio for more details or drop a comment if you want a private tour! 👇\n\n#RealEstate #JustListed #DreamHome #HouseHunting",
            "tiktok": f"Wait until you see the inside of this house! 🤯🏡 {address_str} #realestate #hometour #property"
        }
        
        # Call Gemini to write the script using the new text-only approach
        batch_analysis = analyze_scenes_batch(downloaded_images, req.language, meta_data)

        scenes = []
        for i, img_path in enumerate(downloaded_images):
            # Find the specific script for this image index from the batch result
            analysis = next((item for item in batch_analysis if item.get("image_index") == i), {})
            
            original_filename = os.path.basename(img_path)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"
            public_url = f"{base_url}/raw_photos/{original_filename}"
            
            if supabase:
                try:
                    with open(img_path, "rb") as f:
                        supabase.storage.from_("listings").upload(
                            path=unique_filename, 
                            file=f.read(), 
                            file_options={"content-type": "image/jpeg"}
                        )
                    public_url = supabase.storage.from_("listings").get_public_url(unique_filename)
                except Exception as e: 
                    print(f"Supabase photo upload failed: {e}")

            # 3. Build the scene using the batch-aware analysis
            scenes.append({
                "id": str(uuid.uuid4()), 
                "image_path": img_path, 
                "image_url": public_url, 
                "room_type": analysis.get("room_type", "Room"), 
                "caption": analysis.get("caption", "Explore this beautiful property."), 
                "effect": analysis.get("effect", "zoom_in"), 
                "enable_vo": True
            })

        return {"meta": meta_data, "socialDrafts": social_drafts, "scenes": scenes}
        
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/api/render-video")
async def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    if supabase and req.user_id:
        response = supabase.rpc("deduct_credit", {"target_user_id": req.user_id}).execute()
        if not response.data: raise HTTPException(status_code=402, detail="Insufficient credits.")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "video_url": None, "error": None}
    background_tasks.add_task(background_render_task, job_id, req)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return job