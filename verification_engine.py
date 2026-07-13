import re
import io
import os
import json
import base64
import urllib.request
import easyocr
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


# Initialize the EasyOCR reader
reader = easyocr.Reader(['en'], gpu=False)

def enhance_image_for_reading(img_bytes):
    if not img_bytes:
        return None
    image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    new_width = int(image.width * 2.5)
    new_height = int(image.height * 2.5)
    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(1.5)

def sanitize_label_text(text):
    """
    Acts as an autocorrect for common computer vision kerning errors 
    found on stylized alcohol labels.
    """
    if not text:
        return ""
        
    corrections = {
        "Nol": "Vol", "NOL": "VOL", "Alc Nol": "Alc/Vol",
        "ALC NOL": "ALC/VOL", "8Y VOL": "BY VOL", 
        "8y Vol": "By Vol", "0/0": "%"
    }
    
    clean_text = text
    for wrong, right in corrections.items():
        clean_text = clean_text.replace(wrong, right)
        
    return clean_text

#RUN PII MASK OVER DATA
def mask_sensitive_data(text):
    """
    Output DLP Guardrail (Application-Layer Data Masking).
    Scrubbing occurs natively before database writing or UI rendering.
    """
    if not text:
        return ""
        
    # Redact Social Security Numbers (and identical Tax IDs)
    text = re.sub(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b', '[REDACTED: SSN/TAX ID]', text)
    
    # Redact Phone Numbers
    text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED: PHONE]', text)
    
    # Redact standard Email Addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED: EMAIL]', text)
    
    return text
# --- AI EXTRACTION WRAPPERS ---
def extract_with_ocr(img_bytes):
    try:
        enhanced_img = enhance_image_for_reading(img_bytes)
        if not enhanced_img:
            return ""
        img_np = np.array(enhanced_img)
        results = reader.readtext(img_np, detail=0)
        raw_string = " ".join(results)
        return sanitize_label_text(raw_string)
    except Exception as e:
        print(f"OCR Exception: {e}")
        return ""



def extract_with_vlm(img_bytes):
    try:
        if not img_bytes:
            return ""
            
        image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        
        # KEEP THIS: Shrink the image so the CPU can handle the matrix math
        image.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=85)
        optimized_bytes = img_byte_arr.getvalue()
        
        # REVERT 1: Dynamically grab the Guardrail Proxy URL from Docker environment
        # This ensures traffic goes to http://ai-guardrail:8000 first
        ollama_url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        
        b64_img = base64.b64encode(optimized_bytes).decode('utf-8')
        
        # REVERT 2: Ensure it targets the provisioned Qwen model
        payload = {
            "model": "qwen2.5vl:3b",
            "messages": [{
                "role": "user",
                "content": "Read all the text in this image exactly as written. Output ONLY the transcribed text. Do not use formatting.",
                "images": [b64_img]
            }],
            "options": {
                "num_ctx": 2048 # KEEP THIS: Shrink the RAM allocation footprint
            },
            "stream": False
        }
        
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(f"{ollama_url}/api/chat", data=req_data, headers={'Content-Type': 'application/json'})
        
        # KEEP THIS: Massive 10-minute timeout to let the local/AWS CPU finish thinking
        with urllib.request.urlopen(req, timeout=600.0) as response:
            response_data = json.loads(response.read().decode())
            raw_string = response_data.get('message', {}).get('content', '')
            
        return sanitize_label_text(raw_string) # Assuming sanitize_label_text is defined above
        
    except Exception as e:
        raise RuntimeError(f"VLM Timeout or Connection Drop: {str(e)}")
        
def verify_general_field(expected_value, extracted_text):
    if not expected_value:
        return False
    expected_words = expected_value.upper().split()
    extracted_upper = extracted_text.upper()
    return all(word in extracted_upper for word in expected_words)

def verify_alcohol_field(expected_value, extracted_text):
    if not expected_value or not extracted_text:
        return False

    app_match = re.search(r'(\d+(?:\.\d+)?)', expected_value)
    if not app_match:
        return False  
        
    applicant_val = float(app_match.group(1))
    raw_text_upper = extracted_text.upper()
    label_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:%|ALC|APV|VOL|PROOF)', raw_text_upper)

    for match in label_matches:
        if float(match) == applicant_val:
            return True
            
    return False

def verify_health_warning(extracted_text):
    if not extracted_text:
        return False
        
    legal_warning = "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."
    
    def normalize_for_strict_match(text):
        return re.sub(r'[^A-Z0-9]', '', text.upper())
        
    clean_extracted = normalize_for_strict_match(extracted_text)
    clean_legal = normalize_for_strict_match(legal_warning)
    
    if clean_legal in clean_extracted:
        return True
        
    return False

def process_label(images_list, app_data, use_vlm=True):
    extracted_text = ""
    extraction_source = ""
    
    if use_vlm:
        for img_bytes in images_list:
            if img_bytes:
                extracted_text += extract_with_vlm(img_bytes) + " "
        extraction_source = "Qwen2.5-VL"
    else:
        for img_bytes in images_list:
            if img_bytes:
                extracted_text += extract_with_ocr(img_bytes) + " "
        extraction_source = "EasyOCR"
    
    # --- NEW: APPLICATION-LAYER DLP ---
    # Scrub the raw text instantly, regardless of which engine extracted it
    extracted_text = mask_sensitive_data(extracted_text)
    
    results = {
        "Brand Name Match": verify_general_field(app_data.get('brand_name', ''), extracted_text),
        "Class/Type Match": verify_general_field(app_data.get('class_type', ''), extracted_text),
        "Alcohol Content Match": verify_alcohol_field(app_data.get('alc_content', ''), extracted_text),
        "Health Warning Exact Match": verify_health_warning(extracted_text)
    }
    
    overall_pass = all(results.values())
    
    return {
        "status": "APPROVED" if overall_pass else "FLAGGED",
        "details": results,
        "raw_text": extracted_text.strip(),
        "extraction_source": extraction_source
    }