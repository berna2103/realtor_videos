import os
import warnings

# --- SUPPRESS ALL KOKORO & PYTORCH TERMINAL WARNINGS ---
os.environ["HF_HUB_DISABLE_WARNINGS"] = "1"
warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
warnings.filterwarnings("ignore", message=".*weight_norm is deprecated.*")

import asyncio
import sys
import hashlib
import base64
import glob
import io
import requests
import random
import math
import numpy as np
import re
import json
import soundfile as sf
from kokoro import KPipeline
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from proglog import ProgressBarLogger

from moviepy import (
    ImageClip, VideoClip, CompositeVideoClip, concatenate_videoclips, 
    AudioFileClip, CompositeAudioClip, concatenate_audioclips, 
)
# ---> THE FIX: Correct MoviePy 2.0+ Effect Imports <---
from moviepy.audio.fx.MultiplyVolume import MultiplyVolume
from moviepy.audio.fx.AudioFadeOut import AudioFadeOut
from moviepy.video.fx.CrossFadeIn import CrossFadeIn

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# --- FIX: Pass explicit repo_id to silence the Kokoro default warnings ---
pipelines = {
    'a': KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M'),
    'e': KPipeline(lang_code='e', repo_id='hexgrad/Kokoro-82M')
}

IG_WIDTH = 1080
IG_HEIGHT = 1350

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- HELPERS ---
def normalize_tts_text(text):
    if not text: return text
    text = re.sub(r'[\r\n]+', '. ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\bsqft\b', 'square feet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bft\.?\b', 'feet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbd\.?\b', 'bedroom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bba\.?\b', 'bathroom', text, flags=re.IGNORECASE)
    return text.strip()

def set_progress(job_id, percent):
    # Delegate to main.py's update_job_status so it writes to Supabase and memory correctly
    if 'main' in sys.modules:
        main_mod = sys.modules['main']
        if hasattr(main_mod, 'update_job_status'):
            main_mod.update_job_status(job_id, {"progress": percent})
        elif hasattr(main_mod, 'jobs') and job_id in main_mod.jobs:
            main_mod.jobs[job_id]['progress'] = percent

class JobRenderLogger(ProgressBarLogger):
    def __init__(self, job_id, start_progress=50, end_progress=98):
        super().__init__()
        self.job_id = job_id
        self.start_progress = start_progress
        self.end_progress = end_progress

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            bar_data = self.bars.get(bar)
            if bar_data and bar_data.get('total'):
                total = bar_data['total']
                if total > 0:
                    fraction = value / total
                    current_prog = int(self.start_progress + (self.end_progress - self.start_progress) * fraction)
                    set_progress(self.job_id, current_prog)

BED_PATHS = [[(0.1, 0.2), (0.1, 0.8)], [(0.1, 0.6), (0.9, 0.6), (0.9, 0.8)], [(0.2, 0.6), (0.2, 0.4), (0.5, 0.4), (0.5, 0.6)]]
BATH_PATHS = [[(0.1, 0.5), (0.1, 0.8), (0.9, 0.8), (0.9, 0.5), (0.1, 0.5)], [(0.2, 0.8), (0.2, 0.9)], [(0.8, 0.8), (0.8, 0.9)], [(0.8, 0.5), (0.8, 0.1), (0.6, 0.1), (0.6, 0.2)]]
SQFT_PATHS = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)]]
MUSIC_MAP = {"top1": "music/top1.mp3", "top2": "music/top2.mp3", "top3": "music/top3.mp3", "top4": "music/top4.mp3", "top5": "music/top5.mp3"}

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(font_name, size, base_dir):
    fonts_dir = os.path.join(base_dir, 'fonts')
    if font_name and os.path.exists(fonts_dir):
        search_term = str(font_name).split()[0].lower()
        for file in os.listdir(fonts_dir):
            if file.lower().endswith('.ttf') and search_term in file.lower():
                font_path = os.path.join(fonts_dir, file)
                try: return ImageFont.truetype(font_path, int(size))
                except Exception: pass
    return ImageFont.load_default()

def ease_in_out(t, duration):
    p = max(0.0, min(1.0, t / duration))
    return p * p * (3 - 2 * p)

def draw_text_with_shadow(draw, pos, text, font, fill_color, shadow_color=(0, 0, 0, 200), offset=2):
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill_color)

def create_gradient_scrim(width, height, max_alpha=180):
    mask = Image.new('L', (1, height), color=0)
    for y in range(height):
        base_alpha = max_alpha * 0.5
        gradient_alpha = max_alpha * ((y / height) ** 1.5)
        alpha = int(min(base_alpha + gradient_alpha, max_alpha))
        mask.putpixel((0, y), alpha)
    mask = mask.resize((width, height))
    scrim = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    black = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    scrim.paste(black, (0, 0), mask=mask)
    return scrim

def draw_unit_icon(draw, paths, center_x, center_y, scale_factor, color):
    for path in paths:
        scaled_points = [(p[0] * scale_factor + center_x - (scale_factor/2), 
                          p[1] * scale_factor + center_y - (scale_factor/2)) for p in path]
        draw.line(scaled_points, fill=color, width=2)

def format_address(full_addr, hide_exact=False):
    if not hide_exact or not full_addr:
        return full_addr
    try:
        parts = [p.strip() for p in full_addr.split(',')]
        if len(parts) >= 3:
            city = parts[-2]
            state_zip = parts[-1].split()
            state = state_zip[0] if state_zip else ""
            return f"{city}, {state}"
    except Exception:
        pass
    return full_addr

def get_dynamic_cta(status_val, language, custom_cta_val=None):
    if custom_cta_val and custom_cta_val.strip(): 
        return custom_cta_val.strip().upper()
    cta_map = {
        "English": {
            "Just Sold": "VIEW OUR SUCCESS STORIES!",
            "Under Contract": "JOIN BACKUP LIST!",
            "Coming Soon": "GET EARLY ACCESS!",
            "Open House": "VISIT US THIS WEEKEND!",
            "Price Reduced": "NEW PRICE - SEE IT TODAY!",
            "Just Listed": "BE THE FIRST TO SEE IT!",
            "Home For Sale": "SCHEDULE A SHOWING!",
            "default": "SCHEDULE A SHOWING!"
        }
    }
    lang_dict = cta_map.get(language, cta_map["English"])
    return lang_dict.get(status_val, lang_dict["default"])

# --- INSTAGRAM CAROUSEL GENERATORS (100% VECTOR NO EXTERNAL LOGOS NEEDED) ---

def draw_vector_map_pin(draw, x, y, scale=1.0):
    w = int(45 * scale)
    h = int(65 * scale)
    
    # Drop Shadow
    draw.ellipse((x - w//3, y - w//8, x + w//3, y + w//8), fill=(0, 0, 0, 140))
    
    # Pin Geometry
    head_radius = w // 2
    cy = y - h + head_radius
    
    # Red Pin Body (Triangle pointing down)
    draw.polygon([
        (x - head_radius * 0.85, cy + head_radius * 0.4), 
        (x + head_radius * 0.85, cy + head_radius * 0.4), 
        (x, y)
    ], fill=(225, 29, 72, 255))
    
    # Red Pin Head (Circle)
    draw.ellipse((x - head_radius, cy - head_radius, x + head_radius, cy + head_radius), fill=(225, 29, 72, 255))
    
    # White Inner Cutout
    dot_radius = int(head_radius * 0.35)
    draw.ellipse((x - dot_radius, cy - dot_radius, x + dot_radius, cy + dot_radius), fill=(255, 255, 255, 255))

def draw_vector_eho_logo(draw, get_font_func, x, y, size=50, base_dir=""):
    color = (150, 150, 150, 255)
    thickness = max(2, int(size * 0.08))
    
    # House Roof
    peak = (x + size//2, y)
    left = (x, y + size*0.45)
    right = (x + size, y + size*0.45)
    draw.line([left, peak, right], fill=color, width=thickness)
    
    # House Body
    body_left = x + size * 0.15
    body_right = x + size * 0.85
    body_bottom = y + size
    draw.line([(body_left, y + size*0.35), (body_left, body_bottom), (body_right, body_bottom), (body_right, y + size*0.35)], fill=color, width=thickness)
    
    # Equals Sign (=)
    eq_left = x + size * 0.35
    eq_right = x + size * 0.65
    draw.line([(eq_left, y + size*0.65), (eq_right, y + size*0.65)], fill=color, width=thickness)
    draw.line([(eq_left, y + size*0.80), (eq_right, y + size*0.80)], fill=color, width=thickness)
    
    # Text
    font = get_font_func("Montserrat", int(size * 0.35), base_dir)
    draw.text((x + size + 15, y + size*0.1), "EQUAL HOUSING", font=font, fill=color)
    draw.text((x + size + 15, y + size*0.5), "OPPORTUNITY", font=font, fill=color)

def create_circular_avatar(path, size, border_width=4, border_color=(34, 197, 94)):
    try:
        scale = 4
        large_size = size * scale
        large_border = border_width * scale

        img = Image.open(path).convert("RGB")
        img.thumbnail((large_size, large_size), Image.Resampling.LANCZOS)

        avatar = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))

        x = (large_size - img.width) // 2
        y = (large_size - img.height) // 2
        avatar.paste(img, (x, y))

        mask = Image.new("L", (large_size, large_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse(
            (0, 0, large_size - 1, large_size - 1),
            fill=255
        )
        avatar.putalpha(mask)

        border = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse(
            (
                large_border // 2,
                large_border // 2,
                large_size - large_border // 2 - 1,
                large_size - large_border // 2 - 1
            ),
            outline=border_color + (255,),
            width=large_border
        )
        avatar = Image.alpha_composite(avatar, border)
        avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

        return avatar
    except Exception as e:
        print(f"Avatar error: {e}")
        return None
    
# --- FIX: Added blur-pad for overly wide images ---
def resize_and_crop(img_path, target_w=1080, target_h=1350):
    """
    Forces a clean, full-bleed center crop. 
    Highly recommended for premium Instagram/Social Media aesthetics.
    """
    img = Image.open(img_path).convert("RGBA")
    img_aspect = img.width / img.height
    target_aspect = target_w / target_h
    
    # Calculate dimensions for a full-bleed center crop
    if img_aspect > target_aspect:
        # Image is wider than target aspect ratio (typical for real estate photos)
        new_height = target_h
        new_width = int(new_height * img_aspect)
    else:
        # Image is taller than target aspect ratio
        new_width = target_w
        new_height = int(new_width / img_aspect)
        
    # Resize with high-quality Lanczos filter
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Crop the exact center
    left = (new_width - target_w) / 2
    top = (new_height - target_h) / 2
    right = left + target_w
    bottom = top + target_h
    
    return img.crop((left, top, right, bottom))

def create_carousel_cover(img_path, location, beds, baths, sqft, tagline, price, base_dir, target_w=1080, target_h=1350):
    base_img = resize_and_crop(img_path, target_w, target_h)
    
    scrim = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    scrim_draw = ImageDraw.Draw(scrim)
    
    # --- Top Gradient for Downpayment Visibility ---
    end_top_y = int(target_h * 0.25)
    for y in range(end_top_y):
        progress = 1.0 - (y / end_top_y)
        alpha = int(200 * (progress ** 1.5))
        scrim_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
    
    # --- Bottom Gradient for Location/Specs Visibility ---
    start_y = int(target_h * 0.55) if target_h > 1500 else int(target_h * 0.66)
    for y in range(start_y, target_h):
        progress = (y - start_y) / (target_h - start_y)
        alpha = int(220 * (progress ** 1.5))
        scrim_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
        
    base_img.paste(scrim, (0, 0), scrim)
    
    draw = ImageDraw.Draw(base_img)
    
    def draw_centered(text, font, y, fill=(255, 255, 255, 255), stroke=1):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (target_w - (bbox[2] - bbox[0])) / 2
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=fill)

    bottom_padding = 380 if target_h > 1500 else 120
    y_specs = target_h - bottom_padding
    y_location = y_specs - 150
    y_tagline = y_location - 60
    
    # --- 1. Auto-Scale Price & Downpayment ---
    if price:
        p_font_size = 85
        font_price = get_font("Montserrat-Bold", p_font_size, base_dir)
        try:
            raw_price = float(str(price).replace('$', '').replace(',', ''))
            three_percent = raw_price * 0.03
            downpayment = math.ceil(three_percent / 100.0) * 100
            p_str = f"${int(downpayment):,} Down*"
        except ValueError:
            p_str = str(price)
            
        bbox_p = draw.textbbox((0, 0), p_str, font=font_price)
        while (bbox_p[2] - bbox_p[0]) > (target_w * 0.9):
            p_font_size -= 4
            font_price = get_font("Montserrat-Bold", p_font_size, base_dir)
            bbox_p = draw.textbbox((0, 0), p_str, font=font_price)
            
        draw_centered(p_str, font_price, 80 if target_h < 1500 else 140, stroke=2)

        disc_size = 18
        font_disc = get_font("Montserrat", disc_size, base_dir)
        disc_str = "*Est. 3% conventional down payment. Subject to approval. Not a commitment to lend."
        
        bbox_disc = draw.textbbox((0, 0), disc_str, font=font_disc)
        while (bbox_disc[2] - bbox_disc[0]) > (target_w * 0.95):
            disc_size -= 1
            font_disc = get_font("Montserrat", disc_size, base_dir)
            bbox_disc = draw.textbbox((0, 0), disc_str, font=font_disc)
            
        draw_centered(disc_str, font_disc, target_h - 40, fill=(180, 180, 190, 255), stroke=0)
    
    # --- 2. Auto-Scale Location & Map Pin ---
    loc_text = location.upper()
    loc_font_size = 140
    font_location = get_font("Playfair-Bold", loc_font_size, base_dir)
    
    bbox_loc = draw.textbbox((0, 0), loc_text, font=font_location)
    loc_w = bbox_loc[2] - bbox_loc[0]
    
    pin_base_size = 85
    pin_scale = 1.2
    
    while (pin_base_size + 25 + loc_w) > (target_w * 0.9):
        loc_font_size -= 5
        font_location = get_font("Playfair-Bold", loc_font_size, base_dir)
        bbox_loc = draw.textbbox((0, 0), loc_text, font=font_location)
        loc_w = bbox_loc[2] - bbox_loc[0]
        pin_scale = 1.2 * (loc_font_size / 140.0)
        pin_base_size = int(85 * (loc_font_size / 140.0))
        
    loc_h = bbox_loc[3] - bbox_loc[1]
    total_w = pin_base_size + 25 + loc_w
    start_x = (target_w - total_w) / 2
    
    pin_y = y_location + int(loc_h * 0.90) 
    draw_vector_map_pin(draw, start_x + (pin_base_size//2), pin_y, scale=pin_scale)
    
    text_x = start_x + pin_base_size + 25
    draw.text((text_x, y_location), loc_text, font=font_location, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(255, 255, 255, 255))
    
    # --- 3. Property Details Pills (Beds, Baths, Sqft) ---
    f_pill = get_font("Montserrat-Bold", 30, base_dir)
    color_light_gray = (210, 210, 210, 255)
    color_pill_fill = (25, 25, 25, 140)
    color_pill_outline = (255, 255, 255, 40)
    
    details = []
    if beds: details.append(('bed', str(beds) + " beds"))
    if baths: details.append(('bath', str(baths) + " baths"))
    if sqft: details.append(('sqft', str(sqft) + " Sqft."))
    
    if details:
        pill_h = 75
        icon_draw_scale = 35
        gap_icon_text = 15
        gap_items = 40
        ext_padding = 50
        
        blocks_data = []
        total_content_width = 0
        for icon_type, txt_val in details:
            bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
            txt_w = bbox[2] - bbox[0]
            block_w = icon_draw_scale + gap_icon_text + txt_w
            blocks_data.append((icon_type, txt_val, block_w))
            total_content_width += block_w
            
        pill_w = total_content_width + (len(details) - 1) * gap_items + (ext_padding * 2)
        
        # Scale down if pills are too wide for the screen
        if pill_w > (target_w * 0.95):
            scale_down = (target_w * 0.95) / pill_w
            pill_h = int(pill_h * scale_down)
            icon_draw_scale = int(icon_draw_scale * scale_down)
            f_pill = get_font("Montserrat-Bold", int(30 * scale_down), base_dir)
            pill_w = int(pill_w * scale_down)
            gap_icon_text = int(gap_icon_text * scale_down)
            gap_items = int(gap_items * scale_down)
            ext_padding = int(ext_padding * scale_down)
            # Recalculate block sizes
            blocks_data = []
            for icon_type, txt_val in details:
                bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
                txt_w = bbox[2] - bbox[0]
                block_w = icon_draw_scale + gap_icon_text + txt_w
                blocks_data.append((icon_type, txt_val, block_w))
        
        px = (target_w - pill_w) // 2
        
        # Position slightly lower than the old specs line to give it breathing room
        py = y_specs - 15
        
        draw.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=pill_h // 2, fill=color_pill_fill, outline=color_pill_outline, width=2)
        curr_x = px + ext_padding
        icon_center_y = py + (pill_h // 2)
        
        for icon_type, txt_val, block_w in blocks_data:
            paths = BED_PATHS if icon_type == 'bed' else BATH_PATHS if icon_type == 'bath' else SQFT_PATHS
            draw_unit_icon(draw, paths, curr_x + (icon_draw_scale // 2), icon_center_y, icon_draw_scale, color_light_gray)
            curr_x += icon_draw_scale + gap_icon_text
            txt_bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
            draw.text((curr_x, py + (pill_h - (txt_bbox[3] - txt_bbox[1])) // 2 - 5), txt_val, font=f_pill, fill=color_light_gray)
            curr_x += (block_w - icon_draw_scale - gap_icon_text) + gap_items
    
    # --- 4. Auto-Scale Tagline ---
    tagline_text = tagline.upper()
    tagline_font_size = 40
    font_tagline = get_font("Montserrat-Bold", tagline_font_size, base_dir)
    
    bbox_tagline = draw.textbbox((0, 0), tagline_text, font=font_tagline)
    while (bbox_tagline[2] - bbox_tagline[0]) > (target_w * 0.9):
        tagline_font_size -= 2
        font_tagline = get_font("Montserrat-Bold", tagline_font_size, base_dir)
        bbox_tagline = draw.textbbox((0, 0), tagline_text, font=font_tagline)
        
    draw_centered(tagline_text, font_tagline, y_tagline, stroke=1)
    
    return base_img.convert("RGB")

def create_carousel_end_card(agent_name, brokerage, phone, social_handle, base_dir, headshot_path=None, logo_path=None, target_w=1080, target_h=1350, theme_color="#10295A", is_own_listing=True, listing_agent=None, listing_brokerage=None):
    try:
        bg_color = hex_to_rgb(theme_color)
    except:
        bg_color = (16, 41, 90) 
        
    img = Image.new('RGB', (target_w, target_h), bg_color)
    draw = ImageDraw.Draw(img)
    
    font_xl = get_font("Playfair-Bold", 100, base_dir)
    font_large = get_font("Roboto-Bold", 50, base_dir)
    font_medium = get_font("Roboto-Bold", 40, base_dir)
    font_small = get_font("Montserrat", 28, base_dir)
    font_tiny = get_font("Montserrat", 20, base_dir)
    
    y = 120 if target_h < 1500 else 200
    
    text_ready = "Ready to Tour?"
    bbox_r = draw.textbbox((0, 0), text_ready, font=font_xl)
    x_r = (target_w - (bbox_r[2] - bbox_r[0])) / 2
    draw.text((x_r, y), text_ready, font=font_xl, fill=(255, 255, 255))
    y += 180
    
    if headshot_path and os.path.exists(headshot_path):
        avatar_size = 400
        avatar = create_circular_avatar(headshot_path, avatar_size)
        if avatar:
            ax = int((target_w - avatar_size) / 2)
            img.paste(avatar, (ax, int(y)), mask=avatar)
            y += avatar_size + 50
    else:
        y += 100 
    
    def draw_c(text, font, y_pos, color):
        if not text: return y_pos
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (target_w - (bbox[2] - bbox[0])) / 2
        draw.text((x, y_pos), text, font=font, fill=color)
        return y_pos + (bbox[3] - bbox[1]) + 20

    y = draw_c(agent_name.upper() if agent_name else " ", font_large, y, (255, 255, 255))
    y = draw_c("Licensed Real Estate Broker (IL)", font_small, y, (180, 180, 190))
    y += 20
    
    if phone: y = draw_c(phone, font_medium, y, (220, 220, 230))
    if social_handle: y = draw_c(f"IG: {social_handle}", font_medium, y, (220, 220, 230))
    y += 50
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((400, 140), Image.Resampling.LANCZOS)
            lx = int((target_w - logo_img.width) / 2)
            img.paste(logo_img, (lx, int(y)), mask=logo_img)
            y += logo_img.height + 30
        except: pass
        
    y = draw_c(brokerage.upper() if brokerage else "BROKERAGE NAME", font_medium, y, (255, 255, 255))
    
    # --- FOOTER & COMPLIANCE ---
    footer_y = target_h - (350 if target_h > 1500 else 150)
    draw_vector_eho_logo(draw, get_font, (target_w//2) - 130, footer_y, size=45, base_dir=base_dir)
    
    # If it's NOT your listing, give the listing agent credit above the MLS data
    mls_y_offset = 65
    if not is_own_listing and (listing_agent or listing_brokerage):
        la = listing_agent if listing_agent else "Listing Agent"
        lb = listing_brokerage if listing_brokerage else "Brokerage"
        credit_text = f"Listing Courtesy of {la} | {lb}"
        bbox_c = draw.textbbox((0, 0), credit_text, font=font_tiny)
        draw.text(((target_w - (bbox_c[2] - bbox_c[0])) / 2, footer_y + 60), credit_text, font=font_tiny, fill=(200, 200, 210))
        mls_y_offset = 90 # Push MLS text down a bit further

    mls_text = "REALTOR® | Information deemed reliable but not guaranteed."
    bbox_m = draw.textbbox((0, 0), mls_text, font=font_tiny)
    draw.text(((target_w - (bbox_m[2] - bbox_m[0])) / 2, footer_y + mls_y_offset), mls_text, font=font_tiny, fill=(160, 160, 170))

    return img

# --- VIDEO GENERATORS ---

def create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status, agent, broker, phone, mls_source, mls_number, theme_color, base_dir, custom_cta=None, logo_path=None, hide_exact_addr=False, hook_text=None):
    if not show_details: return []
    color_white, color_light_gray = (255, 255, 255, 255), (210, 210, 210, 255)
    color_pill_fill, color_pill_outline = (25, 25, 25, 140), (255, 255, 255, 40)

    overlay_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    scrim = create_gradient_scrim(tw, th)
    overlay_img.paste(scrim, (0, 0), mask=scrim)
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((int(tw * 0.4), int(th * 0.12)), Image.Resampling.LANCZOS)
            overlay_img.paste(logo_img, ((tw - logo_img.width) // 2, int(th * 0.05)), logo_img) 
        except Exception as e:
            pass

    draw = ImageDraw.Draw(overlay_img)
    
    # --- 1. THE VISUAL HOOK (Auto-Scaling & Centered) ---
    display_hook = hook_text if hook_text else status
    if display_hook:
        # Start with a slightly smaller baseline font for elegance
        hook_font_size = int(th * 0.055) 
        f_hook = get_font("Playfair-Bold", hook_font_size, base_dir)
        
        # Wrap text at ~20 characters so it stacks nicely
        wrapped_hook = textwrap.wrap(display_hook.strip(), width=20)
        
        # Auto-scale font down if the longest line exceeds 85% of screen width
        max_w = 0
        for line in wrapped_hook:
            bbox = draw.textbbox((0, 0), line, font=f_hook)
            if (bbox[2] - bbox[0]) > max_w: max_w = bbox[2] - bbox[0]
            
        while max_w > (tw * 0.85):
            hook_font_size -= 2
            f_hook = get_font("Playfair-Bold", hook_font_size, base_dir)
            max_w = 0
            for line in wrapped_hook:
                bbox = draw.textbbox((0, 0), line, font=f_hook)
                if (bbox[2] - bbox[0]) > max_w: max_w = bbox[2] - bbox[0]

        # Center the block of text vertically around the 35% mark
        total_h = len(wrapped_hook) * (hook_font_size * 1.2)
        current_y = int(th * 0.35) - int(total_h / 2)

        for line in wrapped_hook:
            bbox = draw.textbbox((0, 0), line, font=f_hook)
            draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, current_y), line, f_hook, color_white)
            current_y += (bbox[3] - bbox[1]) + 15

    # --- 2. PILLS (Beds/Baths/Sqft) ---
    # Shifted up to center nicely since price is removed
    y_pill = int(th * 0.52)
    f_pill = get_font(font_choice, int(th * 0.022), base_dir)
    if show_details:
        details = []
        if beds: details.append(('bed', str(beds) + " beds"))
        if baths: details.append(('bath', str(baths) + " baths"))
        if sqft: details.append(('sqft', str(sqft) + " Sqft."))
        if details:
            pill_h, icon_draw_scale = int(th * 0.06), int(th * 0.06 * 0.4)
            gap_icon_text, gap_items, ext_padding = int(tw * 0.015), int(tw * 0.04), int(tw * 0.06)
            blocks_data, total_content_width = [], 0
            for icon_type, txt_val in details:
                txt_w = draw.textbbox((0, 0), txt_val, font=f_pill)[2]
                block_w = icon_draw_scale + gap_icon_text + txt_w
                blocks_data.append((icon_type, txt_val, block_w))
                total_content_width += block_w
            pill_w = total_content_width + (len(details) - 1) * gap_items + (ext_padding * 2)
            
            px, py = (tw - pill_w) // 2, y_pill
            draw.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=pill_h // 2, fill=color_pill_fill, outline=color_pill_outline, width=2)
            curr_x, icon_center_y = px + ext_padding, py + (pill_h // 2)
            for icon_type, txt_val, block_w in blocks_data:
                paths = BED_PATHS if icon_type == 'bed' else BATH_PATHS if icon_type == 'bath' else SQFT_PATHS
                draw_unit_icon(draw, paths, curr_x + (icon_draw_scale // 2), icon_center_y, icon_draw_scale, color_light_gray)
                curr_x += icon_draw_scale + gap_icon_text
                txt_bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
                draw.text((curr_x, py + (pill_h - (txt_bbox[3] - txt_bbox[1])) // 2 - int(th * 0.005)), txt_val, font=f_pill, fill=color_light_gray)
                curr_x += (block_w - icon_draw_scale - gap_icon_text) + gap_items

    # --- 3. ADDRESS ---
    y_addr = int(th * 0.62)
    display_addr = format_address(addr, hide_exact_addr)
    if display_addr:
        addr_size = int(th * 0.024)
        f_addr = get_font(font_choice, addr_size, base_dir)
        bbox = draw.textbbox((0, 0), display_addr, font=f_addr)
        while (bbox[2] - bbox[0]) > (tw * 0.9):
            addr_size -= 2
            f_addr = get_font(font_choice, addr_size, base_dir)
            bbox = draw.textbbox((0, 0), display_addr, font=f_addr)
        draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, y_addr), display_addr, f_addr, color_light_gray)

    # --- 4. IL COMPLIANCE FOOTER ---
    # Keeps the video strictly compliant without overcrowding the frame
    footer_size = int(th * 0.018)
    f_footer = get_font("Montserrat", footer_size, base_dir)
    
    agent_name = agent if agent else "Agent"
    broker_name = broker if broker else "Brokerage"
    compliance_str = f"Listed by {agent_name} | {broker_name}"
    
    comp_bbox = draw.textbbox((0, 0), compliance_str, font=f_footer)
    draw_text_with_shadow(draw, ((tw - (comp_bbox[2] - comp_bbox[0])) // 2, th - int(th * 0.04)), compliance_str, f_footer, color_white, offset=1)

    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    overlay_img.save(temp)
    return [ImageClip(temp).with_duration(dur)]

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None, theme_color="#552448"):
    if not text or not timings: return []
    text = normalize_tts_text(text)
    rgb_highlight = hex_to_rgb(theme_color) + (255,)
    font = get_font(font_choice, int(target_h * 0.045), base_dir)
    words = str(text).upper().strip().split()
    y_pos = int(target_h * 0.85) 
    
    matched_words = []
    t_idx = 0
    for w_idx, word_text in enumerate(words):
        clean_visual = "".join(c for c in word_text.lower() if c.isalnum())
        if not clean_visual: continue
        s_time, e_time = None, None
        spoken_acc = ""
        while t_idx < len(timings):
            ts, te, t_word = timings[t_idx]
            if s_time is None: s_time = ts
            e_time = te
            spoken_acc += "".join(c for c in t_word.lower() if c.isalnum())
            t_idx += 1
            if clean_visual in spoken_acc or spoken_acc in clean_visual: break
        if s_time is not None and s_time < duration:
            matched_words.append({"idx": w_idx, "text": word_text, "start": s_time, "end": e_time})

    layers = []
    for i in range(len(matched_words)):
        curr = matched_words[i]
        adjusted_end = min(curr['end'] + 0.05, matched_words[i+1]['start'] if i + 1 < len(matched_words) else duration, duration)
        if curr['start'] >= adjusted_end: continue

        hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
        draw = ImageDraw.Draw(hl_img)
        bbox = draw.textbbox((0, 0), curr['text'], font=font)
        draw_text_with_shadow(draw, ((target_w - (bbox[2] - bbox[0])) // 2, y_pos), curr['text'], font, rgb_highlight)
        
        hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_word_{curr['idx']}.png")
        hl_img.save(hl_temp)
        layers.append(ImageClip(hl_temp).with_start(curr['start']).with_duration(adjusted_end - curr['start']))
        
    return layers

def create_video_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir, is_own_listing, status, custom_cta=None, logo_path=None, social_handle=None, headshot_path=None, listing_agent=None, listing_brokerage=None):
    try:
        bg_color = hex_to_rgb(theme_color)
    except:
        bg_color = (16, 41, 90)
        
    img = Image.new('RGB', (target_w, target_h), bg_color)
    draw = ImageDraw.Draw(img)
    
    scale = target_h / 1350.0
    
    font_xl = get_font("Playfair-Bold", int(100 * scale), base_dir)
    font_large = get_font("Montserrat", int(70 * scale), base_dir)
    font_medium = get_font("Montserrat", int(40 * scale), base_dir)
    font_small = get_font("Montserrat", int(28 * scale), base_dir)
    font_tiny = get_font("Montserrat", int(20 * scale), base_dir)
    
    y = int(120 * scale) if target_h < 1500 else int(200 * scale)
    
    cta_text = get_dynamic_cta(status, language, custom_cta) if custom_cta else "READY TO TOUR?"
    bbox_r = draw.textbbox((0, 0), cta_text, font=font_large)
    draw.text(((target_w - (bbox_r[2] - bbox_r[0])) / 2, y), cta_text, font=font_large, fill=(255, 255, 255))
    y += int(150 * scale)
    
    if headshot_path and os.path.exists(headshot_path):
        avatar_size = int(350 * scale) if target_w < target_h else int(250 * scale)
        avatar = create_circular_avatar(headshot_path, avatar_size)
        if avatar:
            ax = int((target_w - avatar_size) / 2)
            img.paste(avatar, (ax, y), mask=avatar)
            y += avatar_size + int(40 * scale)
    else:
        y += int(80 * scale)
        
    def draw_c(text, font, y_pos, color):
        if not text: return y_pos
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text(((target_w - (bbox[2] - bbox[0])) / 2, y_pos), text, font=font, fill=color)
        return y_pos + (bbox[3] - bbox[1]) + int(20 * scale)

    y = draw_c(agent_name.upper() if agent_name else "", font_large, y, (255, 255, 255))
    y = draw_c("Licensed Real Estate Broker (IL)", font_small, y, (180, 180, 190))
    y += int(20 * scale)
    
    if phone: y = draw_c(phone, font_medium, y, (220, 220, 230))
    if social_handle: y = draw_c(f"IG: {social_handle}", font_medium, y, (220, 220, 230))
    elif website: y = draw_c(website, font_medium, y, (220, 220, 230))
    
    y += int(40 * scale)
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((int(400 * scale), int(140 * scale)), Image.Resampling.LANCZOS)
            lx = int((target_w - logo_img.width) / 2)
            img.paste(logo_img, (lx, y), mask=logo_img)
            y += logo_img.height + int(30 * scale)
        except: pass
        
    y = draw_c(brokerage.upper() if brokerage else "", font_medium, y, (255, 255, 255))
    
    # --- FOOTER & COMPLIANCE ---
    footer_y = target_h - int(150 * scale)
    draw_vector_eho_logo(draw, get_font, (target_w//2) - int(130 * scale), footer_y, size=int(45 * scale), base_dir=base_dir)
    
    mls_y_offset = int(65 * scale)
    
    # --- FIXED: Now adds Listing Courtesy Of on the Video End Screen too ---
    if not is_own_listing and (listing_agent or listing_brokerage):
        la = listing_agent if listing_agent else "Listing Agent"
        lb = listing_brokerage if listing_brokerage else "Brokerage"
        credit_text = f"Listing Courtesy of {la} | {lb}"
        bbox_c = draw.textbbox((0, 0), credit_text, font=font_tiny)
        draw.text(((target_w - (bbox_c[2] - bbox_c[0])) / 2, footer_y + int(60 * scale)), credit_text, font=font_tiny, fill=(200, 200, 210))
        mls_y_offset = int(90 * scale)

    mls_text = "REALTOR® | Information deemed reliable but not guaranteed."
    if mls_source or mls_number:
        mls_text += f" | Source: {mls_source} {mls_number}"
        
    bbox_m = draw.textbbox((0, 0), mls_text, font=font_tiny)
    draw.text(((target_w - (bbox_m[2] - bbox_m[0])) / 2, footer_y + mls_y_offset), mls_text, font=font_tiny, fill=(160, 160, 170))

    temp_bg = os.path.join(base_dir, f"temp_vid_end_{job_id}.png")
    img.save(temp_bg)
    
    return ImageClip(temp_bg).with_duration(duration)

async def generate_kokoro_audio_async(text, voice, output_path):
    def _run_kokoro():
        timings = []
        audio_chunks = []
        clean_text = normalize_tts_text(text)
        print(f"🎙️ Starting TTS for: '{clean_text[:30]}...' using voice '{voice}'")
        
        try:
            # Kokoro pipelines expect the first character of the voice ID (e.g. 'a' for 'af_bella')
            lang_code = voice[0]
            if lang_code not in pipelines:
                print(f"⚠️ Warning: Language code '{lang_code}' not found in pipelines. Defaulting to 'a'.")
                lang_code = 'a'
                
            generator = pipelines[lang_code](clean_text, voice=voice, speed=1, split_pattern=r'(?<=[.,!?])\s+')
            chunk_offset_seconds = 0.0
            sample_rate = 24000 
            
            for result in generator:
                if result.audio is not None:
                    audio_chunks.append(result.audio)
                    
                current_text, current_start = [], None
                for token in (getattr(result, "tokens", []) or []):
                    t_text = getattr(token, "text", "")
                    if not t_text: continue
                    if current_start is None and getattr(token, "start_ts", None) is not None:
                        current_start = chunk_offset_seconds + float(token.start_ts)
                    current_text.append(t_text)
                    if getattr(token, "whitespace", ""):
                        word_text = "".join(current_text).strip()
                        if word_text: timings.append((current_start, chunk_offset_seconds + float(token.end_ts) if getattr(token, "end_ts", None) else current_start + 0.5, word_text))
                        current_text, current_start = [], None
                        
                if current_text and current_start is not None:
                    word_text = "".join(current_text).strip()
                    if word_text: timings.append((current_start, chunk_offset_seconds + float(getattr(token, "end_ts")) if getattr(token, "end_ts", None) else current_start + 0.5, word_text))
                
                if result.audio is not None:
                    chunk_offset_seconds += len(result.audio) / sample_rate
                
            if not audio_chunks:
                print(f"❌ Error: Kokoro returned no audio for text: '{clean_text}'")
                return None
                
            # Flatten and ensure the array is float32 for soundfile compatibility
            final_audio = np.concatenate(audio_chunks).astype(np.float32)
            sf.write(output_path, final_audio, sample_rate)
            print(f"✅ Successfully wrote audio to {output_path}")
            
            return timings
            
        except Exception as e:
            print(f"❌ CRITICAL KOKORO ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    return await asyncio.to_thread(_run_kokoro)

def create_animated_clip(job_id, i, scene_data, tw, th, is_first, addr, price, beds, baths, sqft, lang, font_choice, show_price, show_details, voice_model, status_choice, agent_name, brokerage, phone, mls_source, mls_number, target_slide_dur, timing_mode, theme_color, logo_path, base_dir, vo_data=None, custom_cta=None, show_captions=True):
    dur = target_slide_dur
    vo_clip, vo_timings = None, None
    
    if vo_data:
        try:
            vo_clip = AudioFileClip(vo_data["path"])
            vo_timings = vo_data["timings"]
            dur = max(target_slide_dur, vo_clip.duration + 0.3)
        except: pass

    img_path = scene_data['image_path']
    if not os.path.exists(img_path) and scene_data.get('image_url', '').startswith('http'):
        try:
            r = requests.get(scene_data['image_url'], timeout=15)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, 'wb') as f: f.write(r.content)
        except: pass

    effect = str(scene_data.get('effect', 'auto')).strip().lower()
    if effect == "auto" or not effect: effect = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left", "pan_up", "pan_down", "pan_up_left", "pan_down_right", "drone_push", "drone_pull", "luxury_breathe", "3d_pan_right", "3d_pan_left"])

    clip = ImageClip(img_path)
    clip = clip.resized(height=th * 1.35) if (clip.w / clip.h) > (tw / th) else clip.resized(width=tw * 1.35)
    base_frame = clip.get_frame(0)
    h_base, w_base, _ = base_frame.shape
    base_pil = Image.fromarray(base_frame)

    def make_frame(t):
        progress = ease_in_out(t, dur)
        
        # --- CINEMATIC SPEED LIMITERS ---
        # Prevent dizzying pans by centering the frame and only traveling across 30% of the available image.
        speed_factor = 0.30
        x_center = (w_base - tw) / 2
        y_center = (h_base - th) / 2
        x_travel = (w_base - tw) * speed_factor
        y_travel = (h_base - th) * speed_factor
        
        if effect == "pan_right": 
            x = int(x_center - (x_travel / 2) + (x_travel * progress))
            y = int(y_center)
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "pan_left": 
            x = int(x_center + (x_travel / 2) - (x_travel * progress))
            y = int(y_center)
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "pan_up": 
            x = int(x_center)
            y = int(y_center + (y_travel / 2) - (y_travel * progress))
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "pan_down": 
            x = int(x_center)
            y = int(y_center - (y_travel / 2) + (y_travel * progress))
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "pan_up_left": 
            x = int(x_center + (x_travel / 2) - (x_travel * progress))
            y = int(y_center + (y_travel / 2) - (y_travel * progress))
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "pan_down_right": 
            x = int(x_center - (x_travel / 2) + (x_travel * progress))
            y = int(y_center - (y_travel / 2) + (y_travel * progress))
            return base_frame[y:y+th, x:x+tw]
            
        elif effect == "3d_pan_right":
            x_offset = int(x_center - (x_travel / 2) + (x_travel * progress))
            y_offset = int(y_center)
            tilt = int(th * 0.04) # Reduced tilt for elegance
            left_tilt, right_tilt = tilt * progress, tilt * (1 - progress)
            return np.array(base_pil.transform((tw, th), Image.QUAD, (x_offset, y_offset - left_tilt, x_offset, y_offset + th + left_tilt, x_offset + tw, y_offset + th + right_tilt, x_offset + tw, y_offset - right_tilt), resample=Image.Resampling.BICUBIC))
            
        elif effect == "3d_pan_left":
            x_offset = int(x_center + (x_travel / 2) - (x_travel * progress))
            y_offset = int(y_center)
            tilt = int(th * 0.04)
            left_tilt, right_tilt = tilt * (1 - progress), tilt * progress
            return np.array(base_pil.transform((tw, th), Image.QUAD, (x_offset, y_offset - left_tilt, x_offset, y_offset + th + left_tilt, x_offset + tw, y_offset + th + right_tilt, x_offset + tw, y_offset - right_tilt), resample=Image.Resampling.BICUBIC))
            
        elif effect == "drone_push":
            zoom = 1.02 + (0.06 * progress) # Reduced zoom intensity
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).rotate(-1.0 + (2.0 * progress), resample=Image.Resampling.BICUBIC).resize((tw, th), Image.Resampling.LANCZOS))
            
        elif effect == "drone_pull":
            zoom = 1.08 - (0.06 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).rotate(1.0 - (2.0 * progress), resample=Image.Resampling.BICUBIC).resize((tw, th), Image.Resampling.LANCZOS))
            
        elif effect == "luxury_breathe":
            zoom = 1.0 + (0.08 * math.sin(progress * (math.pi / 2)))
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))
            
        elif effect == "zoom_out":
            zoom = 1.10 - (0.10 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))
            
        else: # Default zoom_in
            zoom = 1.0 + (0.10 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))
    layers = [VideoClip(make_frame, duration=dur)]

    if is_first:
        # Pass the scene caption (the viral hook) into the title overlay
        hook_text = scene_data.get('caption', status_choice)
        
        layers.extend(create_title_overlay(
            job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, 
            show_price, show_details, status_choice, agent_name, brokerage, phone, 
            mls_source, mls_number, theme_color, base_dir, 
            custom_cta=custom_cta, logo_path=logo_path, hide_exact_addr=False, hook_text=hook_text
        ))
    elif show_captions:
        layers.extend(create_glass_caption(job_id, scene_data.get('caption', ''), dur, tw, th, font_choice, base_dir, vo_timings, theme_color))
        
    final = CompositeVideoClip(layers, size=(tw, th)).with_duration(dur)
    if vo_clip: final = final.with_audio(vo_clip)
    return final

async def render_cinematic_video(job_id, req, output_path, base_dir):
    set_progress(job_id, 2)
    clips, final = [], None
    req_dict = req if isinstance(req, dict) else req.model_dump()
    meta, scenes = req_dict.get('meta', {}), req_dict.get('scenes', [])
    actual_custom_cta = req_dict.get('custom_cta') or meta.get('custom_cta')
    status_choice = req_dict.get('status_choice', 'Just Listed')
    theme_color = req_dict.get('primary_color', '#10295A')

    # --- 1. EXTRACT HEADSHOT & LOGO ---
    logo_file_path = None
    if req_dict.get('logo_data'):
        logo_val = req_dict.get('logo_data')
        logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
        if logo_val.startswith("http"):
            try:
                r = requests.get(logo_val, timeout=15)
                with open(logo_file_path, "wb") as f: f.write(r.content)
            except: pass
        elif ',' in logo_val:
            l_data = base64.b64decode(logo_val.split(',', 1)[1])
            Image.open(io.BytesIO(l_data)).save(logo_file_path)
    else:
        for ext in ["logo.png", "logo.jpg"]:
            cand = os.path.join(base_dir, "assets", ext)
            if os.path.exists(cand):
                logo_file_path = cand
                break

    headshot_file_path = None
    if meta.get('headshot_data'):
        hs_val = meta.get('headshot_data')
        headshot_file_path = os.path.join(base_dir, f"temp_v_hs_{job_id}.png")
        if hs_val.startswith("http"):
            try:
                r = requests.get(hs_val, timeout=15)
                with open(headshot_file_path, "wb") as f: f.write(r.content)
            except: pass
        elif ',' in hs_val:
            h_data = base64.b64decode(hs_val.split(',', 1)[1])
            Image.open(io.BytesIO(h_data)).save(headshot_file_path)
    else:
        for ext in ["headshot.jpg", "headshot.png"]:
            cand = os.path.join(base_dir, "assets", ext)
            if os.path.exists(cand):
                headshot_file_path = cand
                break

    VOICE_MAP = {
        "English-US-Bella": "af_bella",
        "English-US-Heart": "af_heart",
        "English-US-Fenrir": "am_fenrir",
        "English-US-Michael": "am_michael",
        "Spanish-Dora": "ef_dora",
        "Spanish-Alex": "em_alex"
    }

    try:
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        set_progress(job_id, 5)

        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)
        requested_voice = req_dict.get('voice', 'English-US-Bella')
        lang = req_dict.get('language', 'English')
        voice_id = VOICE_MAP.get(requested_voice, "af_bella")

        set_progress(job_id, 10)

        vo_tasks, vo_map = [], {}
        enable_voice = req_dict.get('enable_voice', True) 

        if enable_voice:
            for s in scenes:
                if s.get('enable_vo') and s.get('caption'):
                    p = os.path.join(base_dir, f"temp_vo_{job_id}_{s['id']}.wav")
                    vo_tasks.append(generate_kokoro_audio_async(s['caption'], voice_id, p))
                    vo_map[s['id']] = {"path": p}
        
            if vo_tasks:
                set_progress(job_id, 15)
                results = await asyncio.gather(*vo_tasks)
                for sid, res in zip(vo_map.keys(), results):
                    vo_map[sid]["timings"] = res

        set_progress(job_id, 25)

        total_scenes = len(scenes)
        for i, scene in enumerate(scenes):
            clips.append(create_animated_clip(
                job_id, i, scene, tw, th, (i==0), 
                meta.get('address',''), meta.get('price',''), 
                meta.get('beds',''), meta.get('baths',''), meta.get('sqft',''), 
                lang, req_dict.get('font','Montserrat'), 
                req_dict.get('show_price', True), req_dict.get('show_details', True), 
                voice_id, status_choice, meta.get('agent',''), 
                meta.get('brokerage',''), meta.get('phone',''), 
                meta.get('mls_source',''), meta.get('mls_number',''), 
                2.2, 'Auto', req_dict.get('primary_color','#552448'), # <-- Changed 3.5 to 2.2 for faster pacing
                logo_file_path, base_dir, vo_data=vo_map.get(scene['id']), 
                custom_cta=actual_custom_cta, show_captions=req_dict.get('show_captions', True)   
            ))
            if total_scenes > 0:
                set_progress(job_id, 25 + int(((i + 1) / total_scenes) * 20))

        clips.append(create_video_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), 
            meta.get('phone',''), meta.get('website',''), 5.0, lang, 
            meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Roboto'), theme_color, base_dir, 
            req_dict.get('is_own_listing', True), status=status_choice, 
            custom_cta=actual_custom_cta, logo_path=logo_file_path,
            social_handle=meta.get('social_handle', ''),
            headshot_path=headshot_file_path,
            listing_agent=meta.get('listing_agent'),
            listing_brokerage=meta.get('listing_brokerage')
        ))

        set_progress(job_id, 48)
        # --- APPLY CINEMATIC TRANSITIONS ---
        # Keep the first clip as-is
        transitioned_clips = [clips[0]]
        
        # Apply a smooth 0.3 second CrossFadeIn to all subsequent clips
        for clip in clips[1:]:
            transitioned_clips.append(clip.with_effects([CrossFadeIn(0.3)]))
            
        # method="compose" and padding="-0.3" overlap the clips so they fade into each other
        final = concatenate_videoclips(transitioned_clips, method="compose", padding=-0.3)
        
        m_choice = req_dict.get('music')
        if m_choice and m_choice != "none":
            m_file = None
            if m_choice in MUSIC_MAP:
                m_file = os.path.join(base_dir, MUSIC_MAP[m_choice])
            elif m_choice.startswith("http"):
                m_file = os.path.join(base_dir, f"temp_music_{job_id}.mp3")
                try:
                    r = requests.get(m_choice, timeout=15)
                    if r.status_code == 200:
                        with open(m_file, 'wb') as f: 
                            f.write(r.content)
                except requests.RequestException as e:
                    pass

            if m_file and os.path.exists(m_file):
                bg = AudioFileClip(m_file)
                if bg.duration < final.duration: 
                    bg = concatenate_audioclips([bg] * (int(final.duration / bg.duration) + 1))
                
                # --- MOVIEPY 2.0 FIX: MultiplyVolume Effect
                bg = bg.with_duration(final.duration).with_effects([MultiplyVolume(0.04)])
                
                if final.audio: 
                    final.audio = CompositeAudioClip([bg, final.audio])
                else: 
                    final.audio = bg
                
                # --- MOVIEPY 2.0 FIX: AudioFadeOut Effect
                final.audio = final.audio.with_effects([AudioFadeOut(2.0)])

        set_progress(job_id, 50)
        render_logger = JobRenderLogger(job_id, start_progress=50, end_progress=99)
        final.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac", 
            threads=4, preset="medium", logger=render_logger, 
            bitrate="8000k", ffmpeg_params=["-movflags", "faststart"]
        )
        return True

    finally:
        for c in clips: 
            try: c.close()
            except: pass
        if final:
            try: final.close()
            except: pass
        for tf in glob.glob(os.path.join(base_dir, f"temp_*{job_id}*")):
            try: os.remove(tf)
            except: pass