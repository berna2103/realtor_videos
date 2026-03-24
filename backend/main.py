import os
import uuid
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from supabase import create_client, Client # <-- Added Supabase

from engine import render_cinematic_video
from scraper import fetch_zillow_data, analyze_image_with_gemini, generate_fb_post_content

app = FastAPI(title="Cinematic Listing AI Backend")

# --- INITIALIZE SUPABASE ---
supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if supabase_url and supabase_key:
    supabase: Client = create_client(supabase_url, supabase_key)
else:
    supabase = None

def get_base_url():
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if domain: return f"https://{domain}"
    return "http://127.0.0.1:8000"

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INPUT_DIR = os.path.join(BASE_DIR, "raw_photos")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/raw_photos", StaticFiles(directory=INPUT_DIR), name="raw_photos")

jobs = {}

class FetchRequest(BaseModel):
    zillowUrl: str
    language: Optional[str] = "English"

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

class SceneDef(BaseModel):
    id: str
    image_path: str
    room_type: str
    caption: str
    effect: str
    enable_vo: bool

class RenderRequest(BaseModel):
    user_id: Optional[str] = None # <-- Added User ID requirement
    meta: Optional[MetaDef] = None
    scenes: Optional[List[SceneDef]] = None
    format: Optional[str] = "Vertical (1080x1920)"
    language: Optional[str] = "English"
    voice: Optional[str] = "en-US-ChristopherNeural"
    font: Optional[str] = "Montserrat"
    music: Optional[str] = "none"
    timing_mode: str = "Auto"
    show_price: bool = True
    show_details: bool = True
    status_choice: str = "Just Listed"
    primary_color: str = "#552448"
    logo_data: Optional[str] = None

def background_render_task(job_id: str, req: RenderRequest):
    try:
        jobs[job_id]["status"] = "rendering"
        output_filename = f"listing_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        success = render_cinematic_video(job_id, req, output_path, BASE_DIR)
        if success:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["video_url"] = f"{get_base_url()}/outputs/{output_filename}"
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        # Handle refunding a credit here if needed!

@app.post("/api/fetch-zillow")
async def fetch_zillow(req: FetchRequest):
    # Same as before
    try:
        meta_data, downloaded_images = fetch_zillow_data(req.zillowUrl)
        fb_draft = generate_fb_post_content(meta_data, req.language)
        base_url = get_base_url()
        scenes = []
        for img_path in downloaded_images:
            analysis = analyze_image_with_gemini(img_path, req.language, meta_data.get('description', ''))
            scenes.append({
                "id": str(uuid.uuid4()), "image_path": img_path, 
                "image_url": f"{base_url}/raw_photos/{os.path.basename(img_path)}", 
                "room_type": analysis.get("room_type", "Room"), "caption": analysis.get("caption", "Beautiful Home"),
                "effect": analysis.get("effect", "zoom_in"), "enable_vo": True
            })
        return {"meta": meta_data, "fbDraft": fb_draft, "scenes": scenes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/render-video")
async def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    # --- CREDIT CHECK LOGIC ---
    if supabase and req.user_id:
        # Atomic deduction RPC call
        response = supabase.rpc("deduct_credit", {"target_user_id": req.user_id}).execute()
        if not response.data:
             raise HTTPException(status_code=402, detail="Insufficient credits")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "video_url": None, "error": None}
    background_tasks.add_task(background_render_task, job_id, req)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return job