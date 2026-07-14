# 🏛️ TTB Automated COLA Platform

---

## 📖 Overview
A modern, AI-driven prototype designed to streamline the Certificate of Label Approval (COLA) process for the Alcohol and Tobacco Tax and Trade Bureau (TTB). This platform utilizes a multi-modal computer vision pipeline to automate label verification, reducing manual agent workloads while maintaining high regulatory accuracy.

## 🏗️ Approach
The system employs a dual-tiered verification architecture:

*   **Fast Triage (Heuristic OCR):** Utilizes EasyOCR with image enhancement techniques to rapidly process standard, high-contrast text.
*   **Deep Triage (Spatial VLM):** Leverages Qwen2.5-VL, a dynamic-resolution Vision Language Model, to process complex, curved, or stylized label topographies that defeat standard OCR.

The application automatically checks label extractions against submitted application data for Brand Name, Class/Type, Alcohol Content (ABV), and the mandatory Government Health Warning. Results are routed into a role-based workspace for final human disposition.

## 🛡️ Security Architecture (Defense in Depth)
This application enforces a strict Zero Trust model across three distinct layers:
*   **The Network Edge (WAF):** A custom Debian Nginx reverse proxy running libmodsecurity3 and the OWASP Core Rule Set. It actively intercepts and drops HTTP-based SQLi, XSS, and directory traversal attacks before they reach the application.
*   **Identity & Access Management (IAM):** The proxy acts as a mock Identity Provider (IdP), challenging external traffic with Basic Auth and dynamically injecting mock JWT and RBAC headers (`TTB_Agent`) to authorized users.
*   **Application-Layer Guardrails:** To mitigate WebSocket blindspots, all user inputs and AI outputs are scrubbed by a Data Loss Prevention (DLP) masking function. All database transactions utilize parameterized SQLite queries to neutralize injection payloads.

## 🛠️ Tools Used
*   **Frontend/UI:** Streamlit
*   **Backend/Logic:** Python 3.10
*   **Database:** SQLite (local persistent storage)
*   **Security Gateway:** Nginx, ModSecurity (OWASP CRS)
*   **AI Inference Engine:** Ollama (Local containerized execution)
*   **Vision Models:** Qwen2.5-VL (VLM), EasyOCR (Optical Character Recognition)
*   **Containerization:** Docker & Docker Compose

## 📌 Assumptions Made
*   **Hardware:** The host environment has sufficient RAM/VRAM to execute Qwen2.5-VL locally via Docker.
*   **Network:** The application operates in an air-gapped or restricted internal network, necessitating local model inference rather than relying on external API calls.
*   **Data Integrity:** Bulk legacy uploads adhere to a standard CSV schema (`filename`, `brand_name`, `class_type`, `alc_content`, `net_contents`).

## ⚠️ Known Limitations
*   **Hardware Constraints:** The local deployment of Qwen2.5-VL is resource-intensive. Processing speeds and extraction accuracy are heavily constrained by the available compute allocated to the Docker environment. Running on a CPU is about 1min per image.
*   **WAF WebSocket Blindspot:** Streamlit operates primarily over WebSockets. Network-layer WAFs (like ModSecurity) cannot inspect continuous binary WebSocket frames, requiring the application to rely on Python-level data sanitization for form submissions.
*   **Mock Authentication:** The current IdP is a simulated gateway using `.htpasswd`. A production deployment would require an OAuth2-Proxy sidecar integrated with a true enterprise directory (e.g., Entra ID, Okta).
*   **Load Balancing/SSL Negotiation** Current live demo http://184.73.38.33, is running on HTTP. Enterprise application would be behind load balancer
*   **External Processing** Mail/Notification client is basic in JSON output, but is very simple
*   

## 🚀 Setup and Run Instructions

### 1. Start the Docker Environment
Ensure Docker is running on your machine. From the root directory of the project, spin up the stack:
`docker-compose up -d --build`

### 2. Pull the Vision Model
Once the containers are running, download the Qwen2.5-VL weights into the Ollama container:
`docker exec -it <your-ollama-container-name> ollama pull qwen2.5vl`

### 3. Access the Application
### 3a. LOCAL INSTALL
      Navigate to `http://localhost` in your web browser. 
      Authenticate using the demo gateway credentials:
      **Username:** `admin`
      **Password:** `~123PASSword!@#~`
### 3b. LIVE
      Navigate to http://184.73.38.33  (HTTP, not HTTPS)

## 🖥️ User Roles & Workflows

### 👤 Industry Applicant
Select **Industry Applicant** to submit new labels or upload bulk CSVs.

**Batch Method (CSV Format):**
> **Example Schema:** `filename,brand_name,class_type,alc_content,net_contents`

*   Include all images needed for the bulk upload.
*   The image file name must be in the first field (`filename`) to be processed during the batch process.

**Manual Method:**
*   Fill in the submission form.
*   Upload images (there is a front label and back label, but you can upload multiple or single image files).

### 🛡️ TTB Review Agent
Select **TTB Review Agent** to access the triage queues and run the AI verification engine.

*   **📝 Manual Review Desk:** Reviewer can Approve Directly or Deny with a reason.
*   **🤖 AI Batch Triage:** 
    *   Choose **"Fast (OCR Only)"**: This model is better for "perfect" labels due to hardware limitations.
    *   Choose **"Run Deep Triage (VLM Only)"**: Better accuracy but slower, functional for demo purposes.
*   **⚠️ Flagged Queue:** Failed AI batches route here. Reviewers can compare the raw extraction against the submitted image, force approval, or reject.
*   **✅ Approved Registry:** Final audit log allowing a reviewer to spot-check and revoke automated approvals.

## 🔧 Demo & Misc Tools
*   **🔐 IAM Security Viewer:** Located in the sidebar to reveal the server-side RBAC headers injected by the Nginx gateway.
*   **🚨 Wipe Database (Reset Demo):** Removes all items that exist in the database to test.
*   **🔓 Unlock Stuck Applications (Failsafe):** Manually drops database processing locks in the event of an idle timeout.

#      Screenshots
<img width="3756" height="1656" alt="image" src="https://github.com/user-attachments/assets/f5390559-6186-4aef-afd8-46dccbd39ca7" />
Initial login with Upstream headers shown (on left)

<img width="3198" height="1146" alt="image" src="https://github.com/user-attachments/assets/9164a972-11ab-417b-adb7-8b53e33712b1" />
Single batch upload, with front and back labels attached (you can upload multiple images)

<img width="3096" height="610" alt="image" src="https://github.com/user-attachments/assets/3f2f5695-61a5-4aa7-8bdc-9c18564c0840" />
Batch upload (CSV included in this repository, and batch images associated with this CSV are in batch_imgs directory)

<img width="3238" height="742" alt="image" src="https://github.com/user-attachments/assets/4c230c8a-e0a6-4f6f-8989-19d0f48c3e75" />

Queue shown after initial upload

<img width="482" height="976" alt="image" src="https://github.com/user-attachments/assets/b65b24a6-bb02-4f99-87b8-23593b34c7c3" />

Industry applicant and TTB Reviewer are included in same application (these would be separate in enterprise)

<img width="3834" height="1424" alt="image" src="https://github.com/user-attachments/assets/c8a63c8b-aee0-4656-8d4a-104aee8963b8" />
<img width="2808" height="1154" alt="image" src="https://github.com/user-attachments/assets/fca504f7-4f2b-48ac-9475-d00c27f275f2" />

Agent Workspace: 4 queues - Manual, these can be approved/denied with rationale;

<img width="2362" height="1236" alt="image" src="https://github.com/user-attachments/assets/1b8c3dbe-8b91-4290-88a1-9601e70e9170" />

AI Batch processing Fast (EasyOCR) or More Accurate (Qwen 2.5-VL)

<img width="3114" height="534" alt="image" src="https://github.com/user-attachments/assets/eb100eae-86da-4949-9040-d9e16896b7f0" />
<img width="3130" height="1476" alt="image" src="https://github.com/user-attachments/assets/6ec082db-c1cc-4f0a-9d55-398d06f3ba4f" />
<img width="3142" height="1436" alt="image" src="https://github.com/user-attachments/assets/d2ab919b-d63f-4769-9dd4-7ed3444873a6" />

Flagged Agent Queue (Raw output is for troubleshooting, and would not need to be included in normal reviewer dashboard) 
Rationale for denial is auto formatted/included if a fail occurs, but can be changed

<img width="3140" height="1444" alt="image" src="https://github.com/user-attachments/assets/047ee6c5-e231-451d-9da6-f9b867b67349" />

Approved Registry, auto submitted to this queue if passed AI Batch Approval. Can be revoked/sent back to queue with revoke approval & flag


### Security Controls
<img width="2930" height="1308" alt="image" src="https://github.com/user-attachments/assets/2a0511a0-fdf3-4229-b8ea-7e58f43b41b0" />
Uses simple redaction (this is configured to go through improved PII controls, right now just running through regex controls)

Input sanitization (within Script)

<img width="1828" height="312" alt="image" src="https://github.com/user-attachments/assets/dc6d9a8a-35a6-4b5c-a573-de069cb3a395" />

**Uses OWASP Top 10 (prevents basic SQLi/XSS)**

2026/07/14 04:33:58 [error] 7#7: *191 [client [REDACTED_CLIENT_IP]] **ModSecurity: Access denied with code 403 (phase 2).** Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `13' ) [file "/usr/share/modsecurity-crs/rules/REQUEST-949-BLOCKING-EVALUATION.conf"] [line "81"] [id "949110"] [rev ""] [msg "Inbound Anomaly Score Exceeded (Total Score: 13)"] [data ""] [severity "2"] [ver "OWASP_CRS/3.3.4"] [maturity "0"] [accuracy "0"] [tag "application-multi"] [tag "language-multi"] [tag "platform-multi"] [tag "attack-generic"] [hostname "172.18.0.5"] [uri "/favicon.ico"] [unique_id "[REDACTED_UNIQUE_ID]"] [ref ""], client: [REDACTED_CLIENT_IP], server: localhost, request: "GET /favicon.ico HTTP/1.1", host: "[REDACTED_HOST_IP]", referrer: "**http://[REDACTED_HOST_IP]/%3Cscript%3Ealert('Vulnerable')%3C/script%3E**" 

[REDACTED_CLIENT_IP] - admin [14/Jul/2026:04:33:58 +0000] "GET /favicon.ico HTTP/1.1" 403 555 "http://[REDACTED_HOST_IP]/%3Cscript%3Ealert('Vulnerable')%3C/script%3E" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"


**Network Proxy (FAST API)**
Every time Streamlit sends a base64 image and a prompt to the AI, it actually hits the FastAPI proxy first. 
This allows the proxy to inspect the inbound prompt (to block prompt injections or jailbreak attempts) 
and inspect the outbound AI response (to ensure it isn't hallucinating malicious code) before it ever reaches the user interface.

**IAM/MFA**
Uses JWT to control user access (this is shown on left a general token to provide username/password access with dummy token)

<img width="428" height="416" alt="image" src="https://github.com/user-attachments/assets/a20f31d0-4d23-4517-bfad-e73ccc156c4a" />


(As shown)Authorization: Basic YWRtaW46fjEyM1BBU1N3b3JkIUAjfg==
X-Forwarded-User: Not Found
X-Forwarded-Groups: Not Found

# Data Flow/Protections

```
       [ External User / Web Browser ]
                     |
                     | 1. HTTP Request (Image Upload / Form Data)
                     v (Port 80)
=========================================================
| LAYER 1: THE INGRESS PROXY & WAF                      |
| (Nginx + ModSecurity)                                 |
=========================================================
      | - Inspects headers, URIs, and payloads.
      | - BLOCKS: XSS (e.g., <script>), SQLi, anomalies.
      | - ALLOWS: Safe traffic forwards to backend.
      |
      v (Port 8501)
=========================================================
| LAYER 2: THE APPLICATION FRONTEND                     |
| (Streamlit UI)                                        |
=========================================================
      | - User clicks "Run Deep Triage (VLM)".
      | - Image is scaled down (thumbnail) and Base64 encoded.
      |
      v (HTTP POST)
=========================================================
| LAYER 3: THE INBOUND AI GUARDRAIL                     |
| (FastAPI Proxy - Port 8000)                           |
=========================================================
      | - Intercepts the traffic before it hits the AI.
      | - Scans the user prompt for jailbreaks/injections.
      |
      v (Port 11434)
=========================================================
| LAYER 4: THE AI ENGINE                                |
| (Ollama Server running Moondream)                     |
=========================================================
      | - CPU runs the matrix math on the Base64 image.
      | - Generates raw transcribed text.
      |
      v
=========================================================
| LAYER 5: THE OUTBOUND AI GUARDRAIL                    |
| (FastAPI Proxy)                                       |
=========================================================
      | - Inspects the AI's response before Streamlit sees it.
      | - Prevents malicious code hallucination.
      |
      v
=========================================================
| LAYER 6: THE APPLICATION DLP GUARDRAIL                |
| (Python Backend: `mask_sensitive_data`)               |
=========================================================
      | - Raw text enters Python memory.
      | - Regex immediately scrubs and replaces:
      |     * SSNs -> [REDACTED: SSN/TAX ID]
      |     * Phones -> [REDACTED: PHONE]
      |     * Emails -> [REDACTED: EMAIL]
      |
      v
=========================================================
| LAYER 7: THE VERIFICATION ENGINE                      |
| (Python Backend: `verify_alcohol_field`, etc.)        |
=========================================================
      | - Compares extracted values against expected app data.
      | - Checks Brand Name, Class, Alcohol %, Warnings.
      |
      v
[ FINAL OUTPUT: Streamlit UI renders "APPROVED" or "FLAGGED" ]
```


# The Three Failsafes Explained
This diagram highlights that your application is secured at three completely isolated checkpoints:

* The Edge Checkpoint (Nginx/ModSecurity): Stops traditional web attacks from even touching your application code.

* The AI Checkpoint (FastAPI): Wraps the AI engine in a protective bubble so users can't trick it, and it can't accidentally attack the user.

* The Data Checkpoint (Python DLP): Ensures that even if the AI perfectly extracts sensitive information from a label, it is destroyed in 
application memory before it can ever be stored in a database or rendered on the screen.











