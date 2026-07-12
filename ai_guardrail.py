from fastapi import FastAPI, Request, HTTPException
import httpx
import re
import os

app = FastAPI()
OLLAMA_URL = os.environ.get("TARGET_OLLAMA_URL", "http://ollama-server:11434")

def detect_image_anomalies(base64_img):
    """
    Input Sanitization Guardrail.
    In a full production environment, this would map the base-256 pixel grid 
    to detect LSB steganography, adversarial noise, or prompt injection payloads 
    hidden within the image metadata.
    """
    if len(base64_img) > 15000000: 
        raise HTTPException(status_code=400, detail="Image rejected: Payload exceeds secure limits.")
    return True

def mask_sensitive_data(text):
    """
    Output DLP Guardrail (Python-based Data Masking).
    Mimics a Microsoft Presidio scanner using regex to redact PII/PHI.
    """
    # Redact Social Security Numbers
    text = re.sub(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b', '[REDACTED: SSN]', text)
    
    # Redact Phone Numbers
    text = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED: PHONE]', text)
    
    # Redact standard Email Addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED: EMAIL]', text)
    
    return text

@app.post("/api/chat")
async def chat_proxy(request: Request):
    """Intercepts the exact endpoint the Ollama Python client uses."""
    payload = await request.json()
    
    # --- 1. INPUT SANITIZATION ---
    messages = payload.get("messages", [])
    for msg in messages:
        if "images" in msg:
            for img in msg["images"]:
                detect_image_anomalies(img) 
                
    # --- 2. FORWARD TO VLM ---
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat", 
                json=payload, 
                timeout=180.0
            )
            response.raise_for_status()
            ollama_data = response.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"VLM Connection Failed: {str(e)}")
            
    # --- 3. OUTPUT DLP (MASKING) ---
    if "message" in ollama_data and "content" in ollama_data["message"]:
        raw_text = ollama_data["message"]["content"]
        
        sanitized_text = mask_sensitive_data(raw_text)
        ollama_data["message"]["content"] = sanitized_text
        
    return ollama_data