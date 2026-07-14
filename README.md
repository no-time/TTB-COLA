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
*   **Hardware Constraints:** The local deployment of Qwen2.5-VL is resource-intensive. Processing speeds and extraction accuracy are heavily constrained by the available compute allocated to the Docker environment. 
*   **WAF WebSocket Blindspot:** Streamlit operates primarily over WebSockets. Network-layer WAFs (like ModSecurity) cannot inspect continuous binary WebSocket frames, requiring the application to rely on Python-level data sanitization for form submissions.
*   **Mock Authentication:** The current IdP is a simulated gateway using `.htpasswd`. A production deployment would require an OAuth2-Proxy sidecar integrated with a true enterprise directory (e.g., Entra ID, Okta).

## 🚀 Setup and Run Instructions

### 1. Start the Docker Environment
Ensure Docker is running on your machine. From the root directory of the project, spin up the stack:
`docker-compose up -d --build`

### 2. Pull the Vision Model
Once the containers are running, download the Qwen2.5-VL weights into the Ollama container:
`docker exec -it <your-ollama-container-name> ollama pull qwen2.5vl`

### 3. Access the Application
Navigate to `http://localhost` in your web browser. 
Authenticate using the demo gateway credentials:
**Username:** `admin`
**Password:** `~123PASSword!@#~`

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
