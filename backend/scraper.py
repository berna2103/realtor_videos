import os
import re
import requests
import json
import uuid
from pydantic import BaseModel
import PIL.Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, "raw_photos")
os.makedirs(INPUT_FOLDER, exist_ok=True)

class SceneAnalysis(BaseModel):
    room_type: str
    caption: str
    effect: str

def fetch_zillow_data(url: str):
    """Scrapes Zillow using RapidAPI and downloads the first 15 images."""
    match = re.search(r'([0-9]+)_zpid', url)
    if not match: raise ValueError("Invalid Zillow URL. Make sure it contains a ZPID.")
    zpid = match.group(1)
    
    api_url = f"https://api.pullapi.com/zillow/property/{zpid}"
    headers = {
        "x-api-key": RAPIDAPI_KEY, 
        "x-rapidapi-key": RAPIDAPI_KEY, 
        "x-rapidapi-host": "zillow-scraper-api.p.rapidapi.com"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Primary API failed, trying backup: {e}")
        api_url = f"https://zillow-scraper-api.p.rapidapi.com/zillow/property/{zpid}"
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()

    data = response.json().get("data", {})
    
    # Extract Meta Data
    meta = {
        "address": "", "price": "", "beds": "", "baths": "", 
        "sqft": "", "agent": "", "brokerage": "", 
        "mls_source": "", "mls_number": "", "description": data.get("description", "")
    }

    if data.get("address") and data.get("city"):
        meta["address"] = f"{data.get('address')}, {data.get('city')}, {data.get('state', '')}"
    if data.get("price"): meta["price"] = f"{data.get('price'):,}"
    if data.get("bedrooms"): meta["beds"] = str(data.get("bedrooms"))
    if data.get("bathrooms"): meta["baths"] = str(data.get("bathrooms"))
    
    if data.get("livingArea"): meta["sqft"] = f"{data.get('livingArea'):,}"
    elif data.get("livingAreaValue"): meta["sqft"] = f"{int(data.get('livingAreaValue')):,}"

    # Extract images
    image_urls = data.get("image_urls", [])
    unique_urls = list(dict.fromkeys(image_urls))
    
    # Clear old photos
    for f in os.listdir(INPUT_FOLDER):
        os.remove(os.path.join(INPUT_FOLDER, f))

    downloaded_paths = []
    # Limit to 15 images to keep the Next.js loading time reasonable
    for i, img_url in enumerate(unique_urls[:25]):
        try:
            res = requests.get(img_url, timeout=10)
            res.raise_for_status()
            # Use ZPID in filename to prevent browser caching mismatches
            file_path = os.path.join(INPUT_FOLDER, f"{zpid}_{i:02d}.jpg") 
            with open(file_path, 'wb') as f:
                f.write(res.content)
            downloaded_paths.append(file_path)
        except Exception as e:
            print(f"Failed to download image: {e}")
            
    return meta, downloaded_paths

def analyze_image_with_gemini(image_path: str, language: str, description: str):
    """Uses Gemini to identify the room and write a caption."""
    client = genai.Client(api_key=API_KEY)
    img = PIL.Image.open(image_path)
    
    prompt = f"""
You are an award-winning real estate video director and licensed real estate marketing expert.
Your goal is to create cinematic, social-media-ready narration that subtly SELLS the home while remaining fully compliant with REALTOR® Code of Ethics and Illinois real estate advertising rules.

Analyze the provided image and return a JSON object with EXACTLY these keys:

1. "room_type":
Clearly identify the space (e.g., kitchen, living_room, bedroom, bathroom, front_exterior, backyard, aerial_view, entryway, dining_room).

2. "caption":
Create a compelling spoken sentence in {language}, MAX 8 words.

STRICT RULES:
- Must sound natural when spoken as a voiceover
- Focus on lifestyle, features, or experience (NOT hype)
- Avoid exaggeration, guarantees, or misleading claims
- DO NOT use phrases like:
  "perfect", "best", "guaranteed", "dream home", "won’t last"
- DO NOT reference protected classes or neighborhoods in a biased way
- DO NOT speculate (e.g., "ideal for families", "safe area")

STYLE:
- Subtle persuasion, not aggressive selling
- Highlight tangible features (light, space, finishes, layout)
- Use sensory or visual language when possible

GOOD EXAMPLES:
- "Bright kitchen with generous counter space"
- "Sunlit living area with open flow"
- "Spacious backyard ready for relaxing evenings"

3. "effect":
Choose the SINGLE best cinematic motion effect for this image.

Available effects:
- zoom_in, zoom_out, slow_zoom_in, slow_zoom_out
- pan_left_to_right, pan_right_to_left
- tilt_up, tilt_down
- dolly_in, dolly_out
- parallax_left, parallax_right, parallax_depth
- push_in, pull_out
- reveal_left, reveal_right, reveal_up, reveal_down
- drone_rise, drone_drop, drone_forward, drone_backward
- orbit_left, orbit_right
- cinematic_float, steady_hold

Effect selection rules:
- Exterior/front → drone_rise, orbit, slow_zoom_out
- Aerial → drone movements ONLY
- Kitchen/indoor rooms → slow_zoom_in, dolly_in, parallax_depth
- Narrow spaces → push_in or tilt_up
- Large/open spaces → parallax or cinematic_float
- Backyard → drone or slow pan
- Tight/static shots → subtle motion (slow_zoom_in)

Return ONLY valid JSON. No explanation.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SceneAnalysis,
                temperature=0.2
            )
        )
        data = json.loads(response.text)
        return data if isinstance(data, dict) else data[0]
    except Exception as e:
        print(f"Gemini Error: {e}")
        return {"room_type": "Room", "caption": "Beautiful home.", "effect": "zoom_in"}

def generate_fb_post_content(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    prompt = f"""
    Generate a compelling Facebook post for this property in {language}.
    Description: {meta.get('description', '')}
    Include emojis, a strong headline, and standard contact info (708-314-0477).
    """
    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text
    except Exception:
        return "Check out our new listing! Contact us at 708-314-0477 for details."