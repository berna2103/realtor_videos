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

from engine import render_cinematic_video
# NEW VERSION
from scraper import fetch_zillow_data, analyze_scenes_batch, generate_fb_post_content

app = FastAPI(title="Cinematic Listing AI Backend")

supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

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

class MetaDef(BaseModel):
    address: str; price: str; beds: str; baths: str; sqft: str; agent: str; brokerage: str; phone: str = ""; website: str = ""; mls_source: str; mls_number: str

class SceneDef(BaseModel):
    id: str
    image_path: str
    room_type: str
    caption: str
    effect: str  # This now receives 'pan_left', 'pan_right', etc.
    enable_vo: bool
    image_url: Optional[str] = None


class RenderRequest(BaseModel):
    user_id: Optional[str] = None
    meta: Optional[MetaDef] = None
    scenes: Optional[List[SceneDef]] = None
    format: Optional[str] = "Vertical (1080x1920)"
    language: Optional[str] = "English"
    voice: Optional[str] = "Professional/Clean"
    font: Optional[str] = "Montserrat"
    music: Optional[str] = "none"
    primary_color: str = "#552448"
    logo_data: Optional[str] = None

def background_render_task(job_id: str, req: RenderRequest):
    """ENHANCEMENT: Handles the new async render function."""
    try:
        jobs[job_id]["status"] = "rendering"
        output_filename = f"listing_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Run the async render function in a controlled loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(render_cinematic_video(job_id, req, output_path, BASE_DIR))

        if success:
            final_video_url = f"{get_base_url()}/outputs/{output_filename}"
            if supabase:
                try:
                    with open(output_path, "rb") as f:
                        supabase.storage.from_("listings").upload(path=output_filename, file=f.read(), file_options={"content-type": "video/mp4"})
                    final_video_url = supabase.storage.from_("listings").get_public_url(output_filename)
                    if req.user_id:
                        supabase.table("user_videos").insert({"user_id": req.user_id, "video_url": final_video_url, "property_address": req.meta.address if req.meta else "New Listing"}).execute()
                except Exception as e: print(f"Supabase upload failed: {e}")

            jobs[job_id].update({"status": "completed", "progress": 100, "video_url": final_video_url})
    except Exception as e:
        print(f"\n--- FATAL ERROR RENDERING JOB {job_id} ---")
        traceback.print_exc()  # <--- This will print the actual error to your terminal!
        jobs[job_id].update({"status": "failed", "error": str(e)})

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
        
        # 2. Generate content (FB Post and the Batch Video Script)
        fb_draft = generate_fb_post_content(meta_data, req.language)
        base_url = get_base_url()
        
        # --- NEW ENHANCEMENT: Call Gemini ONCE for all images ---
        batch_analysis = analyze_scenes_batch(downloaded_images, req.language, meta_data)
        # --------------------------------------------------------

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

        return {"meta": meta_data, "fbDraft": fb_draft, "scenes": scenes}
        
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