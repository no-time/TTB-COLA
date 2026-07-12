import easyocr
import re
from rapidfuzz import fuzz
import numpy as np
from PIL import Image
import io

# Initialize the OCR reader once
reader = easyocr.Reader(['en'], gpu=False)

def extract_text_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image)
    results = reader.readtext(image_np, detail=0)
    return " ".join(results)

def normalize_text(text):
    """Strips all non-alphanumeric characters (keeps spaces) for cleaner fuzzy matching."""
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()

def verify_general_field(expected_value, extracted_text, threshold=85):
    """The Forgiving Evaluator with text normalization."""
    if not expected_value:
        return True 
    
    # Clean both strings before comparing
    norm_expected = normalize_text(expected_value)
    norm_extracted = normalize_text(extracted_text)
    
    score = fuzz.token_set_ratio(norm_expected, norm_extracted)
    return score >= threshold

def verify_health_warning(extracted_text):
    """
    The Hybrid Evaluator:
    Strictly checks for the uppercase 'GOVERNMENT WARNING:', 
    but uses a high-threshold fuzzy match for the body to survive OCR artifacting.
    """
    # 1. Strict check: Must contain the exact uppercase prefix
    if "GOVERNMENT WARNING:" not in extracted_text:
        return False
        
    # 2. Fuzzy check: Compare the expected body against the extracted text
    expected_body = "(1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."
    
    # partial_ratio is great here because it looks for the best matching block 
    # within the messy OCR string, ignoring the extraneous label data around it.
    score = fuzz.partial_ratio(expected_body, extracted_text)
    
    # Require a 95% match. This is high enough to catch missing sentences, 
    # but low enough to forgive a missing 'a' or a swapped comma.
    return score >= 95
def process_label(image_bytes, app_data):
    """Master function to process a single label."""
    extracted_text = extract_text_from_image(image_bytes)
    
    results = {
        "Brand Name Match": verify_general_field(app_data['brand_name'], extracted_text),
        "Class/Type Match": verify_general_field(app_data['class_type'], extracted_text),
        "Alcohol Content Match": verify_general_field(app_data['alc_content'], extracted_text),
        "Net Contents Match": verify_general_field(app_data['net_contents'], extracted_text),
        "Health Warning Exact Match": verify_health_warning(extracted_text)
    }
    
    overall_pass = all(results.values())
    
    return {
        "status": "Pass" if overall_pass else "Flagged for Review",
        "details": results,
        "raw_text": extracted_text  # <-- ADD THIS LINE for debugging
    }