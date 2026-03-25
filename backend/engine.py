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
    CompositeVideoClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeAudioClip,
    concatenate_audioclips, 
    vfx, 
    afx
)

# Define fixed icons for the pill (as requested in the visual look)
ICON_MAP = {
    'bed': "🛏", # These Unicode icons are placeholders.
    'bath': "🛁",
    'sqft': "📏"
}

# Define outline icons as point-draw data. 
# Coordinate values are internal to a unit box and will be scaled.
# Coordinate format: (x, y)
# Define outline icons as lists of paths (to allow pen lifts)
BED_PATHS = [
    [(0.1, 0.2), (0.1, 0.8)], # left headboard
    [(0.1, 0.6), (0.9, 0.6), (0.9, 0.8)], # bed frame
    [(0.2, 0.6), (0.2, 0.4), (0.5, 0.4), (0.5, 0.6)] # pillow
]
BATH_PATHS = [
    [(0.1, 0.5), (0.1, 0.8), (0.9, 0.8), (0.9, 0.5), (0.1, 0.5)], # tub
    [(0.2, 0.8), (0.2, 0.9)], # left leg
    [(0.8, 0.8), (0.8, 0.9)], # right leg
    [(0.8, 0.5), (0.8, 0.1), (0.6, 0.1), (0.6, 0.2)] # showerhead
]
SQFT_PATHS = [
    [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)] # square box
]


# Fix for MoviePy 1.0.3 & Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS



# --- HELPER FUNCTIONS ---
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# --- FONT & MUSIC MAPPING ---
FONT_MAP = {
    "Roboto": "fonts/Roboto-Bold.ttf",
    "Inter": "fonts/Inter-Bold.ttf",
    "Cinzel": "fonts/Cinzel-Bold.ttf",
    "Playfair": "fonts/PlayfairDisplay-Bold.ttf",
    "Prata": "fonts/Prata-Bold.ttf",
}

MUSIC_MAP = {
    "Upbeat": "music/Upbeat.mp3",
    "Luxury": "music/Luxury.mp3",
    "Motivation": "music/Motivation.mp3"
}

def get_font(font_name, size, base_dir):
    fonts_dir = os.path.join(base_dir, 'fonts')
    if font_name and os.path.exists(fonts_dir):
        search_term = str(font_name).split()[0].lower()
        for file in os.listdir(fonts_dir):
            if file.lower().endswith('.ttf') and search_term in file.lower():
                font_path = os.path.join(fonts_dir, file)
                try: return ImageFont.truetype(font_path, int(size))
                except Exception: pass
                    
    system_fonts = ["arial.ttf", "Helvetica.ttc", "tahoma.ttf", "verdana.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for sys_font in system_fonts:
        try: return ImageFont.truetype(sys_font, int(size))
        except: continue
            
    return ImageFont.load_default()

def ease_in_out(t, duration):
    p = max(0.0, min(1.0, t / duration))
    return p * p * (3 - 2 * p)

def wrap_text_by_pixels(text, font, max_pixels):
    if not text: return []
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    words = str(text).split()
    lines, current_line = [], []
    for word in words:
        test_line = ' '.join(current_line + [word]) if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_pixels: current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line: lines.append(' '.join(current_line))
    return lines

def draw_unit_icon(draw, paths, center_x, center_y, scale_factor, color):
    """Draws a unit outline icon from a list of paths."""
    for path in paths:
        scaled_points = [(p[0] * scale_factor + center_x - (scale_factor/2), 
                          p[1] * scale_factor + center_y - (scale_factor/2)) for p in path]
        draw.line(scaled_points, fill=color, width=2)

def create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status, agent, broker, phone, mls_source, mls_number, theme_color, base_dir):
    if not show_details and not show_price:
        return []

    # Text Colors from image reference
    color_white = (255, 255, 255, 255)
    color_light_gray = (210, 210, 210, 255) 
    color_pill_fill = (25, 25, 25, 140) 
    color_pill_outline = (255, 255, 255, 40) 

    overlay_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_img)
    
    # Use the dynamic get_font helper to load the user's chosen font style
    f_status = get_font(font_choice, int(th * 0.080), base_dir) # MASSIVE title
    f_price = get_font(font_choice, int(th * 0.050), base_dir)  # Large price
    f_pill = get_font(font_choice, int(th * 0.022), base_dir)   # Small pill text
    f_addr = get_font(font_choice, int(th * 0.024), base_dir)   # Medium address
    f_agent = get_font(font_choice, int(th * 0.018), base_dir)  # Agent contact
    f_cta = get_font(font_choice, int(th * 0.024), base_dir)    # CTA

    # --- ABSOLUTE Y-POSITIONING (Creates the cinematic gap) ---
    y_status = int(th * 0.20)
    y_price = int(th * 0.32)
    y_pill = int(th * 0.62)
    y_addr = int(th * 0.74)
    y_agent = int(th * 0.85)
    y_cta = int(th * 0.91)

    # --- 1. Large Status Text ---
    if status:
        status_txt = status.strip()
        bbox = draw.textbbox((0, 0), status_txt, font=f_status)
        draw.text(((tw - (bbox[2] - bbox[0])) // 2, y_status), status_txt, font=f_status, fill=color_white)

    # --- 2. Medium Price Text ---
    if show_price and price:
        clean_price = str(price).replace('$', '').replace(',', '').strip()
        try:
            p_str = f"${int(float(clean_price)):,}"
        except ValueError:
            p_str = str(price)

        bbox = draw.textbbox((0, 0), p_str, font=f_price)
        draw.text(((tw - (bbox[2] - bbox[0])) // 2, y_price), p_str, font=f_price, fill=color_white)

    # --- 3. The Details Pill (Spaced, no dots) ---
    if show_details:
        details = []
        if beds: details.append(('bed', str(beds) + " beds"))
        if baths: details.append(('bath', str(baths) + " baths"))
        if sqft: details.append(('sqft', str(sqft) + " Sqft."))

        if details:
            pill_h = int(th * 0.06)
            icon_draw_scale = int(pill_h * 0.4)
            gap_icon_text = int(tw * 0.015) # Gap between icon and text
            gap_items = int(tw * 0.04)      # Gap between beds/baths/sqft blocks
            
            blocks_data = []
            total_content_width = 0

            # Calculate total width
            for icon_type, txt_val in details:
                txt_bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
                txt_w = txt_bbox[2] - txt_bbox[0]
                block_w = icon_draw_scale + gap_icon_text + txt_w
                blocks_data.append((icon_type, txt_val, block_w))
                total_content_width += block_w

            total_content_width += (len(details) - 1) * gap_items
            ext_padding = int(tw * 0.06) # Padding inside the ends of the pill
            pill_w = total_content_width + (ext_padding * 2)

            px, py = (tw - pill_w) // 2, y_pill
            
            # Draw pill background
            draw.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=pill_h // 2, fill=color_pill_fill, outline=color_pill_outline, width=2)

            curr_x = px + ext_padding
            icon_center_y = py + (pill_h // 2)

            # Draw Icons and Text
            for i, (icon_type, txt_val, block_w) in enumerate(blocks_data):
                icon_paths = None
                if icon_type == 'bed': icon_paths = BED_PATHS
                elif icon_type == 'bath': icon_paths = BATH_PATHS
                elif icon_type == 'sqft': icon_paths = SQFT_PATHS
                
                draw_unit_icon(draw, icon_paths, curr_x + (icon_draw_scale // 2), icon_center_y, icon_draw_scale, color_light_gray)
                curr_x += icon_draw_scale + gap_icon_text

                # Vertically center text in pill
                txt_bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
                txt_h = txt_bbox[3] - txt_bbox[1]
                text_y = py + (pill_h - txt_h) // 2 - int(th * 0.005) 
                
                draw.text((curr_x, text_y), txt_val, font=f_pill, fill=color_light_gray)
                curr_x += (block_w - icon_draw_scale - gap_icon_text) + gap_items

    # --- 4. Main Address Line (Preserve Casing) ---
    if addr:
        # We no longer split it, we use the whole address string just like the image
        bbox = draw.textbbox((0, 0), addr, font=f_addr)
        draw.text(((tw - (bbox[2] - bbox[0])) // 2, y_addr), addr, font=f_addr, fill=color_light_gray)

    # --- 5. Agent Number & CTA ---
    if phone:
        agent_txt = f"Agent Contact: {phone}"
        bbox = draw.textbbox((0, 0), agent_txt, font=f_agent)
        draw.text(((tw - (bbox[2] - bbox[0])) // 2, y_agent), agent_txt, font=f_agent, fill=color_white)

    cta_txt = "SCHEDULE SHOWING!"
    bbox = draw.textbbox((0, 0), cta_txt, font=f_cta)
    draw.text(((tw - (bbox[2] - bbox[0])) // 2, y_cta), cta_txt, font=f_cta, fill=color_white)

    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    overlay_img.save(temp)
    return [ImageClip(temp).with_duration(dur)]

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None, theme_color="#552448"):
    if not text: return []
    
    # Convert hex theme color to RGB for the highlight
    rgb_highlight = hex_to_rgb(theme_color) + (255,)
    
    base_font_size = int(target_h * 0.027)
    font = get_font(font_choice, base_font_size, base_dir)
    text = str(text).upper().strip()
    words = text.split()
    max_text_width_px = target_w * 0.8
    draw_t = ImageDraw.Draw(Image.new('RGBA', (1,1)))
    space_w = int(draw_t.textlength(" ", font=font))
    
    lines_data, current_line_words, current_line_w, max_h_line = [], [], 0, 0
    for word in words:
        bbox = draw_t.textbbox((0,0), word, font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if current_line_words and (current_line_w + space_w + w) > max_text_width_px:
            lines_data.append((current_line_w, max_h_line, current_line_words))
            current_line_words, current_line_w, max_h_line = [(word, w, h)], w, h
        else:
            if current_line_words: current_line_w += space_w + w
            else: current_line_w = w
            max_h_line = max(max_h_line, h)
            current_line_words.append((word, w, h))
    if current_line_words: lines_data.append((current_line_w, max_h_line, current_line_words))

    max_w = max([ld[0] for ld in lines_data]) if lines_data else 0
    total_h = sum([ld[1] for ld in lines_data]) + (max(0, len(lines_data) - 1)) * (target_h * 0.01)
    
    padding = int(target_w * 0.05)
    bw, bh = int(max_w + padding), int(total_h + padding)
    x1, y1 = (target_w - bw) // 2, int(target_h * 0.85)
    
    word_positions, curr_y, word_idx = [], y1 + (padding // 2), 0
    for line_w, line_h, words_in_line in lines_data:
        curr_x = (target_w - line_w) // 2
        for word_text, w, h in words_in_line:
            word_positions.append((word_idx, word_text, curr_x, curr_y))
            curr_x += w + space_w
            word_idx += 1
        curr_y += line_h + (target_h * 0.01)

    bg_overlay = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    draw_bg = ImageDraw.Draw(bg_overlay)
    draw_bg.rounded_rectangle([x1, y1, x1+bw, y1+bh], radius=15, fill=(40, 40, 40, 220), outline=(255, 255, 255, 60), width=2)
    for w_idx, word_text, x, y in word_positions:
        draw_bg.text((x, y), word_text, font=font, fill=(255, 255, 255))
        
    hash_id = hashlib.md5(text.encode()).hexdigest()[:8]
    base_temp = os.path.join(base_dir, f"temp_cap_base_{job_id}_{hash_id}.png") 
    bg_overlay.save(base_temp)
    
    layers = [ImageClip(base_temp).with_duration(duration)]
    
    if timings:
        for w_idx, word_text, x, y in word_positions:
            if w_idx < len(timings):
                start_time, end_time, _ = timings[w_idx]
                if start_time >= duration: continue
                # Add a small buffer to end_time for smoother visual transitions
                display_end = min(end_time + 0.1, duration)
                
                hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
                draw_hl = ImageDraw.Draw(hl_img)
                # Apply the Brand Kit color here
                draw_hl.text((x, y), word_text, font=font, fill=rgb_highlight)
                hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_{hash_id}_{w_idx}.png") 
                hl_img.save(hl_temp)
                layers.append(ImageClip(hl_temp).with_start(start_time).with_duration(display_end - start_time))
                
    return layers

def create_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir):
    from PIL import Image, ImageDraw, ImageOps
    rgb_theme = hex_to_rgb(theme_color)
    
    bg_color = (10, 10, 12)
    img_bg = Image.new('RGB', (target_w, target_h), bg_color) 
    draw_bg = ImageDraw.Draw(img_bg)
    draw_bg.rectangle([0, 0, target_w, 6], fill=rgb_theme)
    
    temp_bg = os.path.join(base_dir, f"temp_end_bg_{job_id}.png") 
    img_bg.save(temp_bg)
    base_clip = ImageClip(temp_bg).with_duration(duration)

    f_cta = get_font(font_choice, int(target_h * 0.045), base_dir)
    f_phone = get_font(font_choice, int(target_h * 0.065), base_dir)
    f_website = get_font(font_choice, int(target_h * 0.035), base_dir)
    f_name = get_font(font_choice, int(target_h * 0.030), base_dir)
    f_broker = get_font(font_choice, int(target_h * 0.022), base_dir)
    f_mls = get_font(font_choice, int(target_h * 0.016), base_dir)
    
    cta_text = "¡AGENDA TU CITA!" if language == "Spanish" else "SCHEDULE A SHOWING!"
    phone_text = phone if phone else ""
    website_text = website if website else ""
    agent_text = agent_name.upper() if agent_name else ""
    broker_text = brokerage if brokerage else ""
    mls_text = f"Source: {mls_source} | MLS# {mls_number}" if (mls_source or mls_number) else ""

    def _create_text_clip(text, font, fill_color, y_pos, start_time, clip_duration, job_id, unique_name):
        if not text: return None
        txt_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        bbox = txt_draw.textbbox((0, 0), text, font=font)
        txt_draw.text(((target_w - (bbox[2]-bbox[0])) / 2, y_pos), text, font=font, fill=fill_color)
        temp_path = os.path.join(base_dir, f"temp_end_txt_{unique_name}_{job_id}.png") 
        txt_img.save(temp_path)
        return (ImageClip(temp_path)
                .with_start(start_time)
                .with_duration(max(0.1, clip_duration - start_time)))

    curr_y = int(target_h * 0.30)
    fade_start = 0.5  
    fade_step = 0.6   
    layers = [base_clip]

    cta_clip = _create_text_clip(cta_text, f_cta, (160, 160, 170), curr_y, fade_start, duration, job_id, "cta")
    if cta_clip: layers.append(cta_clip)
    curr_y += 80
    fade_start += fade_step

    phone_clip = _create_text_clip(phone_text, f_phone, (255, 255, 255), curr_y, fade_start, duration, job_id, "phone")
    if phone_clip: layers.append(phone_clip)
    curr_y += 70
    fade_start += fade_step
    
    website_clip = _create_text_clip(website_text, f_website, (200, 200, 255), curr_y, fade_start, duration, job_id, "website")
    if website_clip: layers.append(website_clip)
    curr_y += 70
    fade_start += fade_step

    agent_clip = _create_text_clip(agent_text, f_name, (255, 255, 255), curr_y, fade_start, duration, job_id, "agent")
    if agent_clip: layers.append(agent_clip)
    curr_y += 50
    fade_start += fade_step

    broker_clip = _create_text_clip(broker_text, f_broker, (140, 140, 150), curr_y, fade_start, duration, job_id, "broker")
    if broker_clip: layers.append(broker_clip)
    
    mls_clip = _create_text_clip(mls_text, f_mls, (80, 80, 90), target_h - 60, fade_start, duration, job_id, "mls")
    if mls_clip: layers.append(mls_clip)

    final_end_screen = CompositeVideoClip(layers, size=(target_w, target_h))
    return final_end_screen.with_duration(duration)

def generate_edge_audio(text, voice, output_path):
    timings = []
    
    async def _amain():
        communicate = edge_tts.Communicate(text, voice)
        with open(output_path, "wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": 
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 10000000.0
                    end = (chunk["offset"] + chunk["duration"]) / 10000000.0
                    timings.append((start, end, chunk["text"]))
                    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            new_loop.run_until_complete(_amain())
            new_loop.close()
            
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
    else:
        asyncio.run(_amain())
        
    return timings

def create_animated_clip(job_id, i, scene_data, tw, th, is_first, addr, price, beds, baths, sqft, lang, font_choice, show_price, show_details, voice_model, status_choice, agent_name, brokerage, phone, mls_source, mls_number, target_slide_dur, timing_mode, theme_color, logo_path, base_dir):
    dur = target_slide_dur
    vo_clip, vo_timings = None, None
    
    if scene_data.get('enable_vo') and scene_data.get('caption'):
        try:
            vo_path = os.path.join(base_dir, f"temp_vo_{job_id}_{scene_data['id']}.mp3") 
            vo_timings = generate_edge_audio(scene_data['caption'], voice_model, vo_path)
            vo_clip = AudioFileClip(vo_path)
            dur = max(target_slide_dur, vo_clip.duration + 0.3)
        except: pass

    img_path = scene_data['image_path']
    img_url = scene_data.get('image_url')
    
    if not os.path.exists(img_path) and img_url and img_url.startswith('http'):
        r = requests.get(img_url)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            with open(img_path, 'wb') as f:
                f.write(r.content)

    clip = ImageClip(img_path)
    w, h = clip.size
    target_ratio = tw / th
    current_ratio = w / h

    if current_ratio > target_ratio:
        clip = clip.resized(height=th)
        x_center = clip.w / 2
        clip = clip.cropped(x1=x_center - tw/2, y1=0, x2=x_center + tw/2, y2=th)
    else:
        clip = clip.resized(width=tw)
        y_center = clip.h / 2
        clip = clip.cropped(x1=0, y1=y_center - th/2, x2=tw, y2=y_center + th/2)
    
    base = clip

    animated = base.resized(lambda t: 1.0 + 0.15 * ease_in_out(t, dur))

    if is_first: 
        # BUG 1 FIXED HERE: Removed the extra [ ] brackets
        overlay_layers = create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status_choice, agent_name, brokerage, phone, mls_source, mls_number, theme_color, base_dir)
    else: 
        overlay_layers = create_glass_caption(
            job_id, 
            scene_data['caption'], 
            dur, 
            tw, 
            th, 
            font_choice, 
            base_dir, 
            vo_timings,
            theme_color=theme_color 
        )
        
    layers = [animated.with_duration(dur)]
    layers.extend(overlay_layers)
    
    if logo_path and os.path.exists(logo_path):
        logo_canvas = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        logo_img = Image.open(logo_path).convert("RGBA")
        logo_w = int(tw * 0.16)
        logo_img.thumbnail((logo_w, logo_w), Image.Resampling.LANCZOS)
        logo_canvas.paste(logo_img, (40, 40), mask=logo_img)
        logo_temp = os.path.join(base_dir, f"temp_logo_overlay_{job_id}_{i}.png")
        logo_canvas.save(logo_temp)
        layers.append(ImageClip(logo_temp).with_duration(dur))

    final_clip = CompositeVideoClip(layers, size=(tw, th)).with_duration(dur)
    if vo_clip: final_clip = final_clip.with_audio(vo_clip)
    return final_clip

def render_cinematic_video(job_id, req, output_path, base_dir):
    clips = []
    final = None
    logo_file_path = None
    req_dict = req if isinstance(req, dict) else req.model_dump()
    meta = req_dict.get('meta', {})
    scenes = req_dict.get('scenes', [])
    
    try:
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        # Optimization: Use 720p for faster rendering
        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)

        for i, scene in enumerate(scenes):
            clips.append(create_animated_clip(
                job_id, i, scene, tw, th, (i==0), meta.get('address',''), meta.get('price',''), 
                meta.get('beds',''), meta.get('baths',''), meta.get('sqft',''), req_dict.get('language','English'),
                req_dict.get('font','Montserrat'), True, True, req_dict.get('voice','en-US-ChristopherNeural'),
                req_dict.get('status_choice','Just Listed'), meta.get('agent',''), meta.get('brokerage',''),
                meta.get('phone',''), meta.get('mls_source',''), meta.get('mls_number',''), 3.0, 'Auto',
                req_dict.get('primary_color','#552448'), logo_file_path, base_dir
            ))

        end_screen = create_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), meta.get('phone',''), meta.get('website',''), 5.0, 
            req_dict.get('language','English'), meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Montserrat'), req_dict.get('primary_color','#552448'), base_dir
        )
        clips.append(end_screen)

        final = concatenate_videoclips(clips)

        music_choice = req_dict.get('music')
        if music_choice and music_choice != "none" and music_choice in MUSIC_MAP:
            music_file = os.path.join(base_dir, MUSIC_MAP[music_choice])
            if os.path.exists(music_file):
                bg_music = AudioFileClip(music_file)
                
                if bg_music.duration < final.duration:
                    bg_music = concatenate_audioclips([bg_music] * (int(final.duration / bg_music.duration) + 1))
                
                bg_music = bg_music.with_duration(final.duration).with_volume_scaled(0.08)
                
                if final.audio: 
                    final.audio = CompositeAudioClip([bg_music, final.audio])
                else: 
                    final.audio = bg_music

        final.write_videofile(
            output_path, fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            # bitrate="3000k",
            threads=4, 
            preset="ultrafast", 
            logger=None, 
            ffmpeg_params=["-movflags", "faststart"]
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