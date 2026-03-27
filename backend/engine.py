import os
import time
import asyncio
import hashlib
import base64
import glob
import io
import threading
import edge_tts
import numpy as np
import requests

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from moviepy import (
    ImageClip, 
    VideoClip,
    CompositeVideoClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeAudioClip,
    concatenate_audioclips, 
)

# Fix for MoviePy 1.0.3 & Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- ICONS & PATHS ---
BED_PATHS = [[(0.1, 0.2), (0.1, 0.8)], [(0.1, 0.6), (0.9, 0.6), (0.9, 0.8)], [(0.2, 0.6), (0.2, 0.4), (0.5, 0.4), (0.5, 0.6)]]
BATH_PATHS = [[(0.1, 0.5), (0.1, 0.8), (0.9, 0.8), (0.9, 0.5), (0.1, 0.5)], [(0.2, 0.8), (0.2, 0.9)], [(0.8, 0.8), (0.8, 0.9)], [(0.8, 0.5), (0.8, 0.1), (0.6, 0.1), (0.6, 0.2)]]
SQFT_PATHS = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)]]

MUSIC_MAP = {"Upbeat": "music/Upbeat.mp3", "Luxury": "music/Luxury.mp3", "Motivation": "music/Motivation.mp3"}

# VOICE_MAP = {
#     # English Voices
#     "Deep/Luxury": "en-US-EricNeural",
#     "Friendly/Fast": "en-US-GuyNeural",
#     "Professional/Clean": "en-US-AndrewNeural",
#     "Female/Warm": "en-US-AvaNeural",
    
#     # Spanish Voices
#     "Spanish/Mexico-Male": "es-MX-JorgeNeural",
#     "Spanish/Mexico-Female": "es-MX-DaliaNeural",
#     "Spanish/Spain-Male": "es-ES-AlvaroNeural",
#     "Spanish/Spain-Female": "es-ES-ElviraNeural",
#     "Spanish/US-Male": "es-US-AlonsoNeural"
# }

# --- HELPER FUNCTIONS ---
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
    """Helper to draw text with a subtle drop shadow for maximum legibility."""
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill_color)

def create_gradient_scrim(width, height, max_alpha=180):
    """
    Creates a full-screen subtle dark overlay with a slight bottom emphasis.
    Keeps image visible while improving white text readability.
    """
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

def create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status, agent, broker, phone, mls_source, mls_number, theme_color, base_dir):
    if not show_details and not show_price: return []
    color_white, color_light_gray = (255, 255, 255, 255), (210, 210, 210, 255)
    color_pill_fill, color_pill_outline = (25, 25, 25, 140), (255, 255, 255, 40)

    overlay_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    scrim = create_gradient_scrim(tw, th)
    overlay_img.paste(scrim, (0, 0), mask=scrim)
    
    draw = ImageDraw.Draw(overlay_img)
    f_status = get_font(font_choice, int(th * 0.080), base_dir)
    f_price = get_font(font_choice, int(th * 0.050), base_dir)
    f_pill = get_font(font_choice, int(th * 0.022), base_dir)
    f_addr = get_font(font_choice, int(th * 0.024), base_dir)
    f_agent = get_font(font_choice, int(th * 0.018), base_dir)
    f_cta = get_font(font_choice, int(th * 0.024), base_dir)

    y_status, y_price, y_pill, y_addr, y_agent, y_cta = int(th * 0.20), int(th * 0.32), int(th * 0.62), int(th * 0.74), int(th * 0.85), int(th * 0.91)

    if status:
        bbox = draw.textbbox((0, 0), status.strip(), font=f_status)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_status), status.strip(), f_status, color_white)

    if show_price and price:
        p_str = f"${int(float(str(price).replace('$', '').replace(',', ''))):,}"
        bbox = draw.textbbox((0, 0), p_str, font=f_price)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_price), p_str, f_price, color_white)

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

    if addr:
        bbox = draw.textbbox((0, 0), addr, font=f_addr)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_addr), addr, f_addr, color_light_gray)

    if phone:
        txt = f"Agent Contact: {phone}"
        bbox = draw.textbbox((0, 0), txt, font=f_agent)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_agent), txt, f_agent, color_white)

    bbox = draw.textbbox((0, 0), "SCHEDULE SHOWING!", font=f_cta)
    x_pos = (tw - (bbox[2] - bbox[0])) // 2
    draw_text_with_shadow(draw, (x_pos, y_cta), "SCHEDULE SHOWING!", f_cta, color_white)

    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    overlay_img.save(temp)
    return [ImageClip(temp).with_duration(dur)]

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None, theme_color="#552448"):
    if not text: return []
    rgb_highlight = hex_to_rgb(theme_color) + (255,)
    font = get_font(font_choice, int(target_h * 0.027), base_dir)
    text = str(text).upper().strip()
    words = text.split()
    draw_t = ImageDraw.Draw(Image.new('RGBA', (1,1)))
    space_w = int(draw_t.textlength(" ", font=font))
    
    lines_data, current_line_words, current_line_w, max_h_line = [], [], 0, 0
    for word in words:
        bbox = draw_t.textbbox((0,0), word, font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if current_line_words and (current_line_w + space_w + w) > (target_w * 0.8):
            lines_data.append((current_line_w, max_h_line, current_line_words))
            current_line_words, current_line_w, max_h_line = [(word, w, h)], w, h
        else:
            current_line_w += (space_w if current_line_words else 0) + w
            max_h_line = max(max_h_line, h)
            current_line_words.append((word, w, h))
    if current_line_words: lines_data.append((current_line_w, max_h_line, current_line_words))

    bw, bh = int(max([ld[0] for ld in lines_data]) + (target_w * 0.05)), int(sum([ld[1] for ld in lines_data]) + (len(lines_data) * target_h * 0.01) + (target_w * 0.05))
    x1, y1 = (target_w - bw) // 2, int(target_h * 0.85)
    
    bg_overlay = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    draw_bg = ImageDraw.Draw(bg_overlay)
    draw_bg.rounded_rectangle([x1, y1, x1+bw, y1+bh], radius=15, fill=(40, 40, 40, 220), outline=(255, 255, 255, 60), width=2)
    
    word_positions, curr_y, word_idx = [], y1 + (target_w * 0.025), 0
    for line_w, line_h, words_in_line in lines_data:
        curr_x = (target_w - line_w) // 2
        for word_text, w, h in words_in_line:
            word_positions.append((word_idx, word_text, curr_x, curr_y))
            draw_bg.text((curr_x, curr_y), word_text, font=font, fill=(255, 255, 255))
            curr_x += w + space_w
            word_idx += 1
        curr_y += line_h + (target_h * 0.01)

    hash_id = hashlib.md5(text.encode()).hexdigest()[:8]
    base_temp = os.path.join(base_dir, f"temp_cap_base_{job_id}_{hash_id}.png") 
    bg_overlay.save(base_temp)
    layers = [ImageClip(base_temp).with_duration(duration)]
    
    if timings:
        for w_idx, word_text, x, y in word_positions:
            if w_idx < len(timings):
                s, e, _ = timings[w_idx]
                if s >= duration: continue
                hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
                ImageDraw.Draw(hl_img).text((x, y), word_text, font=font, fill=rgb_highlight)
                hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_{hash_id}_{w_idx}.png") 
                hl_img.save(hl_temp)
                layers.append(ImageClip(hl_temp).with_start(s).with_duration(min(e + 0.1, duration) - s))
    return layers

def create_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir):
    rgb_theme = hex_to_rgb(theme_color)
    img_bg = Image.new('RGB', (target_w, target_h), (10, 10, 12)) 
    ImageDraw.Draw(img_bg).rectangle([0, 0, target_w, 6], fill=rgb_theme)
    temp_bg = os.path.join(base_dir, f"temp_end_bg_{job_id}.png") 
    img_bg.save(temp_bg)
    
    def _text_clip(text, base_size, color, y, start, job_id, name):
        if not text: return None
        size = base_size
        font = get_font(font_choice, size, base_dir)
        txt_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        
        # Dynamic Scaling: Shrink font if text is wider than 90% of screen
        max_width = target_w * 0.90
        while (bbox[2] - bbox[0]) > max_width and size > 12:
            size -= 2
            font = get_font(font_choice, size, base_dir)
            bbox = draw.textbbox((0, 0), text, font=font)

        draw.text(((target_w - (bbox[2]-bbox[0])) / 2, y), text, font=font, fill=color)
        path = os.path.join(base_dir, f"temp_end_txt_{name}_{job_id}.png") 
        txt_img.save(path)
        return ImageClip(path).with_start(start).with_duration(max(0.1, duration - start))

    layers, curr_y, fade = [ImageClip(temp_bg).with_duration(duration)], int(target_h * 0.25), 0.5
    courtesy_text = "Cortesía de:" if language == "Spanish" else "Listing Courtesy of:"
    
    # Store base font sizes instead of pre-rendered fonts
    elements_to_draw = [
        ("¡AGENDA TU CITA!" if language == "Spanish" else "SCHEDULE A SHOWING!", int(target_h * 0.045), (160, 160, 170), "cta"), 
        (phone, int(target_h * 0.065), (255, 255, 255), "ph"), 
        (website, int(target_h * 0.035), (200, 200, 255), "web"), 
        (courtesy_text, int(target_h * 0.020), (180, 180, 190), "courtesy"), 
        (agent_name.upper(), int(target_h * 0.030), (255, 255, 255), "ag"), 
        (brokerage, int(target_h * 0.022), (140, 140, 150), "br")
    ]
    
    for t, base_sz, c, n in elements_to_draw:
        clip = _text_clip(t, base_sz, c, curr_y, fade, job_id, n)
        if clip: layers.append(clip)
        
        if n == "cta": curr_y += 80
        elif n in ["ph", "web"]: curr_y += 70
        elif n == "courtesy": curr_y += 30
        else: curr_y += 50
        fade += 0.6
    
    mls_txt = f"Source: {mls_source} | MLS# {mls_number}" if (mls_source or mls_number) else ""
    mls_clip = _text_clip(mls_txt, int(target_h * 0.016), (80, 80, 90), target_h - 60, 2.5, job_id, "mls")
    if mls_clip: layers.append(mls_clip)
    
    return CompositeVideoClip(layers, size=(target_w, target_h)).with_duration(duration)

async def generate_edge_audio_async(text, voice, output_path):
    timings = []
    communicate = edge_tts.Communicate(text, voice)
    with open(output_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                timings.append((chunk["offset"]/10000000.0, (chunk["offset"]+chunk["duration"])/10000000.0, chunk["text"]))
    return timings

def create_animated_clip(job_id, i, scene_data, tw, th, is_first, addr, price, beds, baths, sqft, lang, font_choice, show_price, show_details, voice_model, status_choice, agent_name, brokerage, phone, mls_source, mls_number, target_slide_dur, timing_mode, theme_color, logo_path, base_dir, vo_data=None):
    dur = target_slide_dur
    vo_clip, vo_timings = None, None
    
    if vo_data:
        try:
            vo_clip = AudioFileClip(vo_data["path"])
            vo_timings = vo_data["timings"]
            dur = max(target_slide_dur, vo_clip.duration + 0.3)
        except: pass

    img_path = scene_data['image_path']
    img_url = scene_data.get('image_url', '') # Safely get the URL

    if not os.path.exists(img_path) and img_url.startswith('http'):
        try:
            r = requests.get(img_url, timeout=15)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, 'wb') as f: 
                    f.write(r.content)
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch image {img_url} - {e}")

    # Effect Configuration
    effect = scene_data.get('effect', 'zoom_in')
    scale_factor = 1.3  # 30% buffer for panning

    clip = ImageClip(img_path)
    
    # Resize image to be larger than the frame to allow panning
    img_aspect = clip.w / clip.h
    video_aspect = tw / th
    if img_aspect > video_aspect:
        clip = clip.resized(height=th * scale_factor)
    else:
        clip = clip.resized(width=tw * scale_factor)
    
    # Pre-fetch the base frame as a numpy array (Massive memory saver)
    base_frame = clip.get_frame(0)
    h_base, w_base, _ = base_frame.shape

    # Notice we removed 'get_frame' from the arguments, it only needs 't'
    def make_frame(t):
        progress = ease_in_out(t, dur)

        if effect == "pan_right":
            x = int((w_base - tw) * progress)
            y = int((h_base - th) / 2)
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_left":
            x = int((w_base - tw) * (1 - progress))
            y = int((h_base - th) / 2)
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_up":
            x = int((w_base - tw) / 2)
            y = int((h_base - th) * (1 - progress))
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_down":
            x = int((w_base - tw) / 2)
            y = int((h_base - th) * progress)
            return base_frame[y:y+th, x:x+tw]
        else: # Default Zoom
            zoom = 1.0 + (0.15 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            # Fast resize using Pillow, back to numpy
            pil_img = Image.fromarray(cropped).resize((tw, th), Image.Resampling.LANCZOS)
            return np.array(pil_img)

    # Completely bypass .fl() and instantiate a fresh VideoClip
    animated_base = VideoClip(make_frame, duration=dur)
    layers = [animated_base]

    # Add overlays (Preserve your existing Title/Caption logic)
    if is_first:
        layers.extend(create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status_choice, agent_name, brokerage, phone, mls_source, mls_number, theme_color, base_dir))
    else:
        layers.extend(create_glass_caption(job_id, scene_data['caption'], dur, tw, th, font_choice, base_dir, vo_timings, theme_color))
        
    final = CompositeVideoClip(layers, size=(tw, th)).with_duration(dur)
    if vo_clip: final = final.with_audio(vo_clip)
    return final

async def render_cinematic_video(job_id, req, output_path, base_dir):
    clips, final = [], None
    req_dict = req if isinstance(req, dict) else req.model_dump()
    meta, scenes = req_dict.get('meta', {}), req_dict.get('scenes', [])
    logo_file_path = None

    # Expanded Voice Map with Spanish Options
    VOICE_MAP = {
        "Deep/Luxury": "en-US-EricNeural",
        "Friendly/Fast": "en-US-GuyNeural",
        "Professional/Clean": "en-US-AndrewNeural",
        "Female/Warm": "en-US-AvaNeural",
        "Spanish/Mexico-Male": "es-MX-JorgeNeural",
        "Spanish/Mexico-Female": "es-MX-DaliaNeural",
        "Spanish/Spain-Male": "es-ES-AlvaroNeural",
        "Spanish/US-Male": "es-US-AlonsoNeural"
    }

    try:
        # Handle Logo processing
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        # Set Resolution based on format
        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)

        # Voice Selection Logic
        requested_voice = req_dict.get('voice', 'Professional/Clean')
        lang = req_dict.get('language', 'English')
        
        # Auto-fallback: If language is Spanish but an English voice is selected, use Jorge
        if lang == "Spanish" and "en-US" in VOICE_MAP.get(requested_voice, "en-US"):
            voice_id = "es-MX-JorgeNeural"
        else:
            voice_id = VOICE_MAP.get(requested_voice, "en-US-AndrewNeural")

        # Generate Audio for all enabled scenes
        vo_tasks, vo_map = [], {}
        for s in scenes:
            if s.get('enable_vo') and s.get('caption'):
                p = os.path.join(base_dir, f"temp_vo_{job_id}_{s['id']}.mp3")
                vo_tasks.append(generate_edge_audio_async(s['caption'], voice_id, p))
                vo_map[s['id']] = {"path": p}
        
        if vo_tasks:
            results = await asyncio.gather(*vo_tasks)
            for sid, res in zip(vo_map.keys(), results):
                vo_map[sid]["timings"] = res

        # Build Video Clips using the new animated logic
        for i, scene in enumerate(scenes):
            clips.append(create_animated_clip(
                job_id, i, scene, tw, th, (i==0), 
                meta.get('address',''), meta.get('price',''), 
                meta.get('beds',''), meta.get('baths',''), meta.get('sqft',''), 
                lang, req_dict.get('font','Montserrat'), 
                req_dict.get('show_price', True), req_dict.get('show_details', True), 
                voice_id, req_dict.get('status_choice','Just Listed'), 
                meta.get('agent',''), meta.get('brokerage',''), meta.get('phone',''), 
                meta.get('mls_source',''), meta.get('mls_number',''), 
                3.5, 'Auto', req_dict.get('primary_color','#552448'), 
                logo_file_path, base_dir, vo_data=vo_map.get(scene['id'])
            ))

        # Add the End Screen
        clips.append(create_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), 
            meta.get('phone',''), meta.get('website',''), 5.0, lang, 
            meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Montserrat'), req_dict.get('primary_color','#552448'), base_dir
        ))

        # Concatenate and Mix Audio
        final = concatenate_videoclips(clips)
        m_choice = req_dict.get('music')
        if m_choice and m_choice != "none" and m_choice in MUSIC_MAP:
            m_file = os.path.join(base_dir, MUSIC_MAP[m_choice])
            if os.path.exists(m_file):
                bg = AudioFileClip(m_file)
                if bg.duration < final.duration: 
                    bg = concatenate_audioclips([bg] * (int(final.duration / bg.duration) + 1))
                bg = bg.with_duration(final.duration).with_volume_scaled(0.08)
                
                if final.audio:
                    final.audio = CompositeAudioClip([bg, final.audio])
                else:
                    final.audio = bg

        # Final Render
        final.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            threads=4, 
            preset="medium", 
            logger=None, 
            ffmpeg_params=["-movflags", "faststart"]
        )
        return True

    finally:
        # Cleanup temp files
        for c in clips: 
            try: c.close()
            except: pass
        if final:
            try: final.close()
            except: pass
        for tf in glob.glob(os.path.join(base_dir, f"temp_*{job_id}*")):
            try: os.remove(tf)
            except: pass


# if __name__ == "__main__":
#     print("Starting quick image test...")
    
#     # 1. Setup Test Variables
#     test_base_dir = "."
#     test_job_id = "quicktest"
#     test_tw, test_th = 720, 1280 # Vertical format test
    
#     # 2. Create a dummy light-colored background to test the dark scrim & shadows
#     dummy_bg = Image.new('RGB', (test_tw, test_th), (180, 190, 200)) 
#     dummy_bg_path = os.path.join(test_base_dir, "test_dummy_bg.jpg")
#     dummy_bg.save(dummy_bg_path)
    
#     test_scene_data = {'image_path': dummy_bg_path, 'caption': 'Test'}
    
#     # 3. Test the Title Screen (Includes scrim, drop shadows, icons, etc.)
#     print("Rendering Title Screen frame...")
#     title_clip = create_animated_clip(
#         job_id=test_job_id, i=0, scene_data=test_scene_data, tw=test_tw, th=test_th, 
#         is_first=True, addr="1234 Cinematic Way, Los Angeles, CA", price="2450000", 
#         beds=5, baths=4, sqft=3200, lang="English", font_choice="Roboto-Bold", # Make sure this font exists in your /fonts folder
#         show_price=True, show_details=True, voice_model="en-US-ChristopherNeural", 
#         status_choice="Just Listed", agent_name="Jane Doe", brokerage="Prestige Realty", 
#         phone="(555) 123-4567", mls_source="CRMLS", mls_number="SR24000000", 
#         target_slide_dur=3.0, timing_mode="Auto", theme_color="#552448", 
#         logo_path=None, base_dir=test_base_dir
#     )
#     title_clip.save_frame("test_output_title.png", t=0.0)
    
#     # 4. Test the End Screen (Includes Listing Courtesy Of & Auto-scaling text)
#     print("Rendering End Screen frame...")
#     end_clip = create_end_screen(
#         job_id=test_job_id, target_w=test_tw, target_h=test_th, 
#         agent_name="Jane Doe", brokerage="Prestige International Real Estate Group", # Long name to test scaling
#         phone="(555) 123-4567", website="www.janedoerealestate.com", duration=5.0, 
#         language="English", mls_source="CRMLS", mls_number="SR24000000", 
#         font_choice="Montserrat", theme_color="#552448", base_dir=test_base_dir
#     )
#     end_clip.save_frame("test_output_endscreen.png", t=0.0)
    
#     print("Done! Open 'test_output_title.png' and 'test_output_endscreen.png' to check your layout.")