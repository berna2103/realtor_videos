import os
import re
import requests
import json
import math
from typing import List
from pydantic import BaseModel
import PIL.Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
# ---> THE FIX: Load the new API key from your .env file (checking both casing styles to be safe) <---
ZILLOW_API_KEY = os.getenv("zillow_api_key") or os.getenv("ZILLOW_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, "raw_photos")
os.makedirs(INPUT_FOLDER, exist_ok=True)

class SceneAnalysis(BaseModel):
    image_index: int
    room_type: str
    caption: str
    effect: str

class VideoScript(BaseModel):
    scenes: List[SceneAnalysis]

def fetch_zillow_data(url: str, job_id: str):
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
    
    # FIX: We removed "agent", "brokerage", and "phone" from here. 
    # This prevents the backend from erasing your personal profile info in the frontend!
    meta = {
        "address": "", "price": "", "beds": "", "baths": "", 
        "sqft": "", "mls_source": "", "mls_number": "", 
        "description": data.get("description", ""),
        "neighborhood_context": data.get("neighborhoodRegion", {}).get("name", "")
    }

    if data.get("address") and data.get("city"):
        meta["address"] = f"{data.get('address')}, {data.get('city')}, {data.get('state', '')}"
    if data.get("price"): meta["price"] = f"{data.get('price'):,}"
    if data.get("bedrooms"): meta["beds"] = str(data.get("bedrooms"))
    if data.get("bathrooms"): meta["baths"] = str(data.get("bathrooms"))
    
    sqft_val = data.get("living_area_sqft") or data.get("livingArea") or data.get("livingAreaValue")
    if sqft_val:
        meta["sqft"] = f"{int(sqft_val):,}"

    lat = data.get("latitude") or data.get("lat")
    lng = data.get("longitude") or data.get("lng")
    
    if not lat and data.get("location"):
        lat = data.get("location", {}).get("latitude")
        lng = data.get("location", {}).get("longitude")
        
    meta["latitude"] = lat
    meta["longitude"] = lng
    
    try:
        if ZILLOW_API_KEY:
            print("Testing new Zillow API for agent and FOMO data...")
            test_url = "https://zillow-scraper-1000-free-calls.p.rapidapi.com/properties/detail"
            test_querystring = {"property_id": zpid}
            test_headers = {
                "x-rapidapi-key": ZILLOW_API_KEY, 
                "x-rapidapi-host": "zillow-scraper-1000-free-calls.p.rapidapi.com",
                "Content-Type": "application/json"
            }
            
            test_response = requests.get(test_url, headers=test_headers, params=test_querystring, timeout=25)
            
            if test_response.status_code == 200:
                test_data = test_response.json()
                agent_data = test_data.get("agent", {})
                
                if agent_data:
                    # FIX: Save listing agent data in a separate variable so it doesn't overwrite YOU
                    if agent_data.get("agent_name"): meta["listing_agent"] = agent_data.get("agent_name")
                    if agent_data.get("broker_name"): meta["listing_brokerage"] = agent_data.get("broker_name")
                    if agent_data.get("mls_name"): meta["mls_source"] = agent_data.get("mls_name")
                    if agent_data.get("mls_id"): meta["mls_number"] = agent_data.get("mls_id")
                
                # --- NEW: FOMO STATS ---
                meta["views"] = test_data.get("page_view_count", 0)
                meta["saves"] = test_data.get("favorite_count", 0)
                
    except Exception as test_e:
        print(f"Test API failed (ignoring safely): {test_e}")

    image_urls = data.get("image_urls", [])
    unique_urls = list(dict.fromkeys(image_urls))
    
    job_folder = os.path.join(INPUT_FOLDER, job_id)
    os.makedirs(job_folder, exist_ok=True)

    downloaded_paths = []
    for i, img_url in enumerate(unique_urls[:20]):
        try:
            res = requests.get(img_url, timeout=10)
            res.raise_for_status()
            file_path = os.path.join(job_folder, f"{zpid}_{i:02d}.jpg") 
            with open(file_path, 'wb') as f:
                f.write(res.content)
            downloaded_paths.append(file_path)
        except Exception as e:
            pass
            
    return meta, downloaded_paths

def analyze_scenes_batch(image_paths: List[str], language: str, meta_data: dict):
    client = genai.Client(api_key=API_KEY)
    num_scenes = len(image_paths)
    if num_scenes == 0: return []
    
    target_count = min(10, num_scenes)
    
    address_str = meta_data.get('address', '')
    city = address_str.split(',')[1].strip() if ',' in address_str else "your area"
    
    prompt = f"""
You are a professional, high-end real estate marketer and video editor. I am providing you with {num_scenes} images of a property.
STRICT LANGUAGE: {language}.
ADDRESS: {address_str}
MLS DESCRIPTION: {meta_data.get('description')}
NEIGHBORHOOD CONTEXT: {meta_data.get('neighborhood_context')}

CRITICAL INSTRUCTIONS:
1. REVIEW the images and select the BEST {target_count} images to tell the story of this home.
2. SCENE 1 MUST be a short, elegant, professional hook. STRICT MAX OF 6 WORDS. (e.g., "Stunning new listing in {city}." or "Beautifully updated modern home."). Do NOT over-exaggerate or use clickbait.
3. Keep the energy warm, professional, and concise. 
4. Write EXACTLY {target_count} sequential captions for your chosen images. Max 10 words per caption.

Return ONLY a valid JSON array with EXACTLY {target_count} objects.
Each object must contain: "image_index" (int), "room_type" (str), "caption" (str), "effect" (str - zoom_in, zoom_out, pan_right, pan_left, pan_up, luxury_breathe)
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash', 
            contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=VideoScript, temperature=0.4)
        )
        data = json.loads(response.text)
        return data.get("scenes", [])
    except Exception as e:
        print(f"Gemini Script Error: {e}")
        return []
    
import math

def generate_fb_post_content(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    
    address = meta.get('address', 'this stunning new listing')
    price = meta.get('price', '')
    beds = meta.get('beds', '-')
    baths = meta.get('baths', '-')
    sqft = meta.get('sqft', '-')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')
    phone = meta.get('phone', '') 
    mls_source = meta.get('mls_source', '')
    mls_number = meta.get('mls_number', '')
    
    listing_agent = meta.get('listing_agent', '')
    listing_brokerage = meta.get('listing_brokerage', '')
    views = meta.get('views', 0)
    saves = meta.get('saves', 0)

    try:
        city = address.split(',')[1].strip().upper() if ',' in address else "NEW LISTING"
    except:
        city = "NEW LISTING"

    downpayment_str = ""
    disclaimer = "*Est. 3% conventional down payment. Subject to approval. Not a commitment to lend."
    if price:
        try:
            raw_price = float(str(price).replace('$', '').replace(',', ''))
            three_percent = raw_price * 0.03
            downpayment = math.ceil(three_percent / 100.0) * 100
            downpayment_str = f"${int(downpayment):,}"
        except ValueError:
            pass

    # 1. Ask Gemini to write ONLY the creative parts
    prompt = f"""
    You are a top-producing real estate agent writing a Facebook post in {language}.
    Property description: {meta.get('description', '')}

    Return EXACTLY this format and nothing else:
    🏡 [1-3 WORD CATCHY DESCRIPTION] | {city}

    ✨ [Short feature 1]. [Short feature 2]. [Short feature 3].

    A great opportunity for anyone looking for a beautifully updated home in {city.title()}!

    📩 Message me for details or to schedule a private showing.
    """
    
    try:
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
        creative_text = response.text.strip()
    except Exception:
        creative_text = f"🏡 BEAUTIFUL HOME | {city}\n\n✨ Move-in ready. Great location. Must see.\n\nA great opportunity for anyone looking for a beautifully updated home in {city.title()}!\n\n📩 Message me for details or to schedule a private showing."

    # Split the creative text so we can inject the hardcoded stats in the middle
    lines = creative_text.split('\n')
    headline = lines[0] if lines else f"🏡 NEW LISTING | {city}"
    body = '\n'.join(lines[1:]).strip()

    # 2. Hardcode the Stats & FOMO (Guarantees they always show up)
    details = f"📍 {address}"
    if price:
        details += f"\n💰 {price}"
    if downpayment_str:
        details += f"\n🔑 Own it for an estimated {downpayment_str} down!*"
    
    details += f"\n\n🛏️ {beds} Beds | 🛁 {baths} Baths | 📐 {sqft} Sq Ft"

    if views and int(views) > 0:
        details += f"\n\n🔥 HIGH DEMAND: Over {int(views):,} views and {int(saves):,} saves on Zillow! Don't let someone else beat you to it."

    # 3. Hardcode the Compliance Footer
    agent_name = agent if agent else "Agent"
    broker_name = brokerage if brokerage else "Brokerage"
    
    footer = f"Listed by {agent_name} | {broker_name}"
    
    # If it's not your listing, add the listing agent courtesy line
    if listing_agent and listing_agent != agent_name:
        footer += f"\nListing Courtesy of: {listing_agent} | {listing_brokerage}"
        
    if mls_number:
        footer += f"\nMLS #{mls_number} | {mls_source}"
        
    if downpayment_str:
        footer += f"\n\n{disclaimer}"
        
    tags = f"#RealEstate #{city.replace(' ', '')}RealEstate #{city.replace(' ', '')}Homes"

    # 4. Assemble the final post
    return f"{headline}\n\n{details}\n\n{body}\n\n{footer}\n\n{tags}"


def generate_ig_caption(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    
    address = meta.get('address', 'this stunning new listing')
    price = meta.get('price', '')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')
    phone = meta.get('phone', '')
    website = meta.get('website', 'Link in bio')
    
    listing_agent = meta.get('listing_agent', '')
    listing_brokerage = meta.get('listing_brokerage', '')
    views = meta.get('views', 0)
    saves = meta.get('saves', 0)

    try:
        city = address.split(',')[1].strip().upper() if ',' in address else "NEW LISTING"
    except:
        city = "NEW LISTING"

    downpayment_str = ""
    disclaimer = "*Est. 3% conventional down payment. Subject to approval. Not a commitment to lend."
    if price:
        try:
            raw_price = float(str(price).replace('$', '').replace(',', ''))
            three_percent = raw_price * 0.03
            downpayment = math.ceil(three_percent / 100.0) * 100
            downpayment_str = f"${int(downpayment):,}"
        except ValueError:
            pass

    prompt = f"""
    You are a top-producing real estate agent writing an Instagram caption in {language}.
    Property details: {meta.get('description', '')}

    Return EXACTLY this format to describe the home:
    -[Exciting house feature 1]‼️
    -[Exciting house feature 2]✅
    -[Exciting house feature 3]🔑
    -[Exciting house feature 4]🏡
    """
    
    try:
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
        features = response.text.strip()
    except Exception:
        features = "-Modern updates‼️\n-Open concept layout✅\n-Move-in ready🔑\n-Great location🏡"

    # Assemble Instagram Caption exactly like your high-converting example
    ig_post = f"{city}📍 — Comment “Info” for more details 🙌\n"
    
    if downpayment_str:
        ig_post += f"\nUp to $15,000 in down payment assistance 😊\n"
        ig_post += f"Own it for an estimated {downpayment_str} down!*\n"
        ig_post += f"-Down payment assistance with 600+ credit score‼️\n"
        ig_post += f"-0% downpayment options🔑\n"
        ig_post += f"-We specialize in self-employed clients🏡\n"
    
    if views and int(views) > 0:
        ig_post += f"\n🔥 Over {int(views):,} views and {int(saves):,} saves!\n"

    ig_post += f"\n{features}\n\n"
    ig_post += f"**SCHEDULE FREE CONSULTATION ⬇️**\n{website}\n{phone} 😊\nHABLO ESPAÑOL\n\n"
    
    # Compliance Footer
    agent_name = agent if agent else "Agent"
    ig_post += f"Listed by {agent_name} | {brokerage if brokerage else 'Brokerage'}"
    
    if listing_agent and listing_agent != agent_name:
        ig_post += f"\nListing Courtesy of: {listing_agent} | {listing_brokerage}"
    
    if downpayment_str:
        ig_post += f"\n\n{disclaimer}"

    ig_post += f"\n\n#reels #viral #realestate #trending #{city.replace(' ', '')}RealEstate"

    return ig_post

    