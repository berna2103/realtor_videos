import os
import uuid
import time
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Imports moved cleanly to the top
from engine import render_cinematic_video
from scraper import fetch_zillow_data, analyze_image_with_gemini, generate_fb_post_content

app = FastAPI(title="Cinematic Listing AI Backend")

# --- 1. CORS CONFIGURATION ---
# This allows your Next.js frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DIRECTORY SETUP ---
# Consolidated and cleaned up to prevent mounting crashes
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INPUT_DIR = os.path.join(BASE_DIR, "raw_photos")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)

# Mount the directories ONCE
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/raw_photos", StaticFiles(directory=INPUT_DIR), name="raw_photos")

# --- 3. IN-MEMORY JOB STORE ---
jobs = {}

# --- 4. PYDANTIC MODELS (Data Validation) ---
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
    meta: Optional[MetaDef] = None
    scenes: Optional[List[SceneDef]] = None
    format: Optional[str] = "Vertical (1080x1920)"
    language: Optional[str] = "English"
    voice: Optional[str] = "en-US-ChristopherNeural"
    # Restored branding fields so they don't get deleted by FastAPI!
    font: Optional[str] = "Montserrat"
    music: Optional[str] = "none"
    timing_mode: str = "Auto"
    show_price: bool = True
    show_details: bool = True
    status_choice: str = "Just Listed"
    primary_color: str = "#552448"
    logo_data: Optional[str] = None

# --- 5. BACKGROUND WORKER ---
def background_render_task(job_id: str, req: RenderRequest):
    try:
        jobs[job_id]["status"] = "rendering"
        
        output_filename = f"listing_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Execute the MoviePy render
        success = render_cinematic_video(job_id, req, output_path, BASE_DIR)

        if success:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["video_url"] = f"http://localhost:8000/outputs/{output_filename}"

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


# --- 6. API ENDPOINTS ---
@app.post("/api/fetch-zillow")
async def fetch_zillow(req: FetchRequest):
    """Fetches real Zillow data, downloads images, and runs Gemini analysis."""
    try:
        # 1. Scrape Zillow and download images
        meta_data, downloaded_images = fetch_zillow_data(req.zillowUrl)
        
        # 2. Generate the Facebook Post
        fb_draft = generate_fb_post_content(meta_data, req.language)
        
        # 3. Analyze each downloaded image with Gemini
        scenes = []
        for img_path in downloaded_images:
            analysis = analyze_image_with_gemini(img_path, req.language, meta_data.get('description', ''))
            
            # Extract just the filename (e.g., "00_zillow.jpg")
            filename = os.path.basename(img_path)
            
            scenes.append({
                "id": str(uuid.uuid4()),
                "image_path": img_path, 
                "image_url": f"http://127.0.0.1:8000/raw_photos/{filename}", 
                "room_type": analysis.get("room_type", "Room"),
                "caption": analysis.get("caption", "Beautiful Home"),
                "effect": analysis.get("effect", "zoom_in"),
                "enable_vo": True
            })

        return {
            "meta": meta_data,
            "fbDraft": fb_draft,
            "scenes": scenes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/render-video")
async def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    """Receives the storyboard, kicks off the render task, and returns a Job ID."""
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "video_url": None,
        "error": None
    }
    
    background_tasks.add_task(background_render_task, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Next.js will poll this endpoint to update the UI."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job