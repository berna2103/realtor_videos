import os
import uuid
import asyncio
import io
import zipfile
import shutil
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel
from supabase import create_client, Client
import traceback
import requests
import base64
from PIL import Image

from engine import render_cinematic_video, create_carousel_cover, create_carousel_end_card, resize_and_crop
from scraper import fetch_zillow_data, analyze_scenes_batch, generate_fb_post_content, generate_ig_caption
from google import genai

app = FastAPI(title="Cinematic Listing AI Backend")

supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

headshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "headshot.jpg")

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

class FetchRequest(BaseModel):
    zillowUrl: str
    language: Optional[str] = "English"
    user_id: Optional[str] = None
    neighborhood_context: Optional[str] = ""

# --- UPDATED: Added listing_agent, listing_brokerage, views, saves ---
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
    custom_tagline: Optional[str] = None
    social_handle: Optional[str] = None
    headshot_data: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_brokerage: Optional[str] = None
    views: Optional[int] = 0
    saves: Optional[int] = 0

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
    carousel_format: Optional[str] = "4:5 (Standard Post)"
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

def fetch_real_places(lat: float, lng: float, place_type: str) -> str:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key or not lat or not lng: return ""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "places.displayName.text"}
    payload = {"textQuery": place_type, "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 2000.0}}}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        if "error" in data: return ""
        places = data.get("places", [])
        names = [place.get("displayName", {}).get("text") for place in places[:3] if place.get("displayName", {}).get("text")]
        return ", ".join(names)
    except: return ""

def update_job_status(job_id: str, updates: dict):
    if job_id in jobs:
        jobs[job_id].update(updates)
    if supabase:
        try:
            supabase.table("video_jobs").update(updates).eq("job_id", job_id).execute()
        except:
            pass

def background_render_task(job_id: str, req: RenderRequest):
    try:
        update_job_status(job_id, {"status": "rendering", "progress": 2})
        output_filename = f"listing_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(render_cinematic_video(job_id, req, output_path, BASE_DIR))

        if success:
            update_job_status(job_id, {"progress": 99})
            final_video_url = f"{get_base_url()}/outputs/{output_filename}"
            
            if supabase:
                try:
                    with open(output_path, "rb") as f:
                        supabase.storage.from_("listings").upload(path=output_filename, file=f.read(), file_options={"content-type": "video/mp4"})
                    final_video_url = supabase.storage.from_("listings").get_public_url(output_filename)
                    if req.user_id:
                        supabase.table("user_videos").insert({"user_id": req.user_id, "video_url": final_video_url, "property_address": req.meta.address if req.meta else "New Listing"}).execute()
                    try:
                        if os.path.exists(output_path): os.remove(output_path)
                    except: pass
                except: pass

            update_job_status(job_id, {"status": "completed", "progress": 100, "video_url": final_video_url})
            
    except Exception as e:
        traceback.print_exc()  
        update_job_status(job_id, {"status": "failed", "error": str(e), "progress": 0})
            
@app.post("/api/fetch-zillow")
async def fetch_zillow(req: FetchRequest):
    if supabase and req.user_id:
        user_data = supabase.table("user_credits").select("balance").eq("user_id", req.user_id).single().execute()
        balance = user_data.data.get("balance", 0) if user_data.data else 0
        if user_data.data and user_data.data.get("credits", balance) < 1: 
            raise HTTPException(status_code=402, detail="Insufficient credits.")
    
    try:
        job_id = str(uuid.uuid4())
        meta_data, downloaded_images = fetch_zillow_data(req.zillowUrl, job_id)
        downloaded_images = list(dict.fromkeys(downloaded_images))

        if req.neighborhood_context and req.neighborhood_context.strip():
            meta_data['neighborhood_context'] = req.neighborhood_context.strip()
        else:
            address_str = meta_data.get("address", "")
            try:
                lat = float(meta_data.get("latitude")) if meta_data.get("latitude") else None
                lng = float(meta_data.get("longitude")) if meta_data.get("longitude") else None
            except: lat, lng = None, None

            if address_str and GEMINI_API_KEY:
                try:
                    if lat and lng:
                        real_restaurants = fetch_real_places(lat, lng, "restaurants")
                        real_parks = fetch_real_places(lat, lng, "parks")
                        real_transit = fetch_real_places(lat, lng, "transit stations")
                        real_schools = fetch_real_places(lat, lng, "schools")
                        real_shopping = fetch_real_places(lat, lng, "shopping centers")
                    else:
                        real_restaurants = real_parks = real_transit = real_schools = real_shopping = ""
                    
                    client = genai.Client(api_key=GEMINI_API_KEY)
                    vibe_prompt = f"You are a highly knowledgeable local real estate expert for {address_str}. Write a 3-sentence neighborhood lifestyle pitch for a homebuyer. You MUST mention these exact local restaurants: {real_restaurants}. You MUST mention these exact nearby parks: {real_parks}. You MUST mention these exact transit stations: {real_transit}. You MUST mention these exact schools: {real_schools}. You MUST mention these exact shopping centers: {real_shopping}. Weave them into a natural, exciting pitch. CRITICAL: Do NOT invent, guess, or hallucinate any other places, restaurants, or amenities."
                    response = client.models.generate_content(model='gemini-3.6-flash', contents=vibe_prompt)
                    meta_data['neighborhood_context'] = response.text.strip()
                except: meta_data['neighborhood_context'] = ""

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            fb_task = loop.run_in_executor(pool, generate_fb_post_content, meta_data, req.language)
            ig_task = loop.run_in_executor(pool, generate_ig_caption, meta_data, req.language)
            scenes_task = loop.run_in_executor(pool, analyze_scenes_batch, downloaded_images, req.language, meta_data)
            
            facebook_draft, instagram_draft, batch_analysis = await asyncio.gather(fb_task, ig_task, scenes_task)

        social_drafts = {
            "facebook": facebook_draft,
            "instagram": instagram_draft,
            "tiktok": f"Wait until you see the inside of this house! 🤯🏡 {meta_data.get('address', 'New Listing')} #realestate #hometour #property"
        }
        
        scenes = []
        for i, img_path in enumerate(downloaded_images):
            analysis = next((item for item in batch_analysis if item.get("image_index") == i), {})
            original_filename = os.path.basename(img_path)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"
            public_url = f"{get_base_url()}/raw_photos/{job_id}/{original_filename}"
            
            if supabase:
                try:
                    with open(img_path, "rb") as f:
                        supabase.storage.from_("listings").upload(path=unique_filename, file=f.read(), file_options={"content-type": "image/jpeg"})
                    public_url = supabase.storage.from_("listings").get_public_url(unique_filename)
                except: pass

            scenes.append({
                "id": str(uuid.uuid4()), 
                "image_path": img_path, 
                "image_url": public_url, 
                "room_type": analysis.get("room_type", "Room"), 
                "caption": analysis.get("caption", "Explore this beautiful property."), 
                "effect": analysis.get("effect", "zoom_in"), 
                "enable_vo": True
            })

        return {"meta": meta_data, "socialDrafts": social_drafts, "scenes": scenes, "job_id": job_id}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/render-video")
async def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    if supabase and req.user_id:
        response = supabase.rpc("deduct_credit", {"target_user_id": req.user_id}).execute()
        if not response.data: raise HTTPException(status_code=402, detail="Insufficient credits.")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "video_url": None, "error": None, "job_id": job_id}
    
    if supabase:
        try:
            supabase.table("video_jobs").insert({"job_id": job_id, "status": "queued", "progress": 0}).execute()
        except: pass

    background_tasks.add_task(background_render_task, job_id, req)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    if supabase:
        try:
            res = supabase.table("video_jobs").select("*").eq("job_id", job_id).execute()
            if res.data:
                return res.data[0]
        except: pass
        
    job = jobs.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/generate-carousel")
async def generate_carousel(req: RenderRequest):
    try:
        zip_buffer = io.BytesIO()
        job_id = str(uuid.uuid4())
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            address = req.meta.address if req.meta and req.meta.address else "CHICAGO, IL"
            city_state = address.split(',')[-2].strip() + ", " + address.split(',')[-1].strip().split()[0] if ',' in address else address
            
            beds = req.meta.beds if req.meta else ""
            baths = req.meta.baths if req.meta else ""
            sqft = req.meta.sqft if req.meta else ""
            specs = f"{beds} BEDS | {baths} BATHS | {sqft} SQFT"
            
            tagline = req.meta.custom_tagline if req.meta and req.meta.custom_tagline else "JUST LISTED 🏡"
            agent = req.meta.agent if req.meta else "Agent Name"
            brokerage = req.meta.brokerage if req.meta else "Brokerage"
            phone = req.meta.phone if req.meta else ""
            social_handle = req.meta.social_handle if req.meta else ""
            price = req.meta.price if req.meta else ""
            
            local_headshot = None
            for ext in ["headshot.jpg", "headshot.jpeg", "headshot.png", "headshot.webp"]:
                candidate = os.path.join(BASE_DIR, "assets", ext)
                if os.path.exists(candidate):
                    local_headshot = candidate
                    break
            headshot_path = local_headshot

            local_logo = None
            for ext in ["logo.png", "logo.jpg", "logo.jpeg", "logo.webp"]:
                candidate = os.path.join(BASE_DIR, "assets", ext)
                if os.path.exists(candidate):
                    local_logo = candidate
                    break
            logo_path = local_logo

            tw, th = (1080, 1920) if "9:16" in (req.carousel_format or "") else (1080, 1350)

            if req.logo_data and ',' in req.logo_data:
                logo_data = base64.b64decode(req.logo_data.split(',', 1)[1])
                logo_path = os.path.join(BASE_DIR, f"temp_c_logo_{job_id}.png")
                Image.open(io.BytesIO(logo_data)).save(logo_path)
                
            if req.meta and req.meta.headshot_data and ',' in req.meta.headshot_data:
                hs_data = base64.b64decode(req.meta.headshot_data.split(',', 1)[1])
                headshot_path = os.path.join(BASE_DIR, f"temp_hs_{job_id}.png")
                Image.open(io.BytesIO(hs_data)).save(headshot_path)
            
            # 1. Generate Cover (Now passes individual fields for the pills)
            if req.scenes and len(req.scenes) > 0:
                cover_img = create_carousel_cover(
                    req.scenes[0].image_path, 
                    city_state, 
                    req.meta.beds if req.meta else "", 
                    req.meta.baths if req.meta else "", 
                    req.meta.sqft if req.meta else "", 
                    tagline, 
                    price, 
                    BASE_DIR, 
                    target_w=tw, 
                    target_h=th
                )
                img_byte_arr = io.BytesIO()
                cover_img.save(img_byte_arr, format='JPEG', quality=95)
                zip_file.writestr("01_cover.jpg", img_byte_arr.getvalue())
            
            if req.scenes and len(req.scenes) > 1:
                for i, scene in enumerate(req.scenes[1:19]): 
                    slide_img = resize_and_crop(scene.image_path, target_w=tw, target_h=th).convert("RGB")
                    img_byte_arr = io.BytesIO()
                    slide_img.save(img_byte_arr, format='JPEG', quality=90)
                    zip_file.writestr(f"{i+2:02d}_interior.jpg", img_byte_arr.getvalue())
                
            # --- UPDATED: Pass compliance variables into end card ---
            end_card = create_carousel_end_card(
                agent, brokerage, phone, social_handle, BASE_DIR, headshot_path, logo_path, 
                target_w=tw, target_h=th, theme_color=req.primary_color,
                is_own_listing=req.is_own_listing,
                listing_agent=req.meta.listing_agent if req.meta else None,
                listing_brokerage=req.meta.listing_brokerage if req.meta else None
            )
            img_byte_arr = io.BytesIO()
            end_card.save(img_byte_arr, format='JPEG', quality=95)
            zip_file.writestr("99_contact.jpg", img_byte_arr.getvalue())
            
        zip_buffer.seek(0)
        safe_addr = "".join(c for c in address if c.isalnum() or c in " ,_-").replace(" ", "_")
        
        try:
            if logo_path and "temp_c_logo_" in logo_path and os.path.exists(logo_path): 
                os.remove(logo_path)
            if headshot_path and "temp_hs_" in headshot_path and os.path.exists(headshot_path): 
                os.remove(headshot_path)
        except: pass
        
        return Response(
            content=zip_buffer.getvalue(), 
            media_type="application/x-zip-compressed", 
            headers={"Content-Disposition": f'attachment; filename="carousel_{safe_addr}.zip"'}
        )
    except Exception as e:
        print(f"Carousel Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ProfileUpdate(BaseModel):
    user_id: str
    agent_name: Optional[str] = None
    brokerage: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    social_handle: Optional[str] = None
    headshot_data: Optional[str] = None 
    logo_data: Optional[str] = None     

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured.")
    
    res = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
    if res.data:
        return res.data[0]
    return {}

@app.post("/api/profile")
async def update_profile(req: ProfileUpdate):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured.")
        
    update_data = {
        "user_id": req.user_id,
        "agent_name": req.agent_name,
        "brokerage": req.brokerage,
        "phone": req.phone,
        "website": req.website,
        "social_handle": req.social_handle
    }
    
    def upload_b64(b64_str, filename):
        header, encoded = b64_str.split(",", 1)
        file_data = base64.b64decode(encoded)
        content_type = header.split(":")[1].split(";")[0]
        path = f"{req.user_id}/{filename}"
        
        supabase.storage.from_("brand_assets").upload(
            path=path, 
            file=file_data, 
            file_options={"content-type": content_type, "upsert": "true"}
        )
        return supabase.storage.from_("brand_assets").get_public_url(path)

    if req.headshot_data and req.headshot_data.startswith("data:image"):
        update_data["headshot_url"] = upload_b64(req.headshot_data, "headshot.jpg")
        
    if req.logo_data and req.logo_data.startswith("data:image"):
        update_data["logo_url"] = upload_b64(req.logo_data, "logo.png")
        
    res = supabase.table("user_profiles").upsert(update_data).execute()
    return {"success": True, "profile": res.data[0] if res.data else {}}