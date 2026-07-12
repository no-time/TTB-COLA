import streamlit as st
import database as db
from verification_engine import process_label, mask_sensitive_data
import json
import csv
import io
import traceback
import time  # <-- Added for database lock throttling

# Initialize Database on boot
db.init_db()

st.set_page_config(page_title="TTB Modernization Platform", layout="wide")

# Sidebar
st.sidebar.title("System Login")
user_role = st.sidebar.selectbox("Select Role", ["Industry Applicant", "TTB Review Agent"])

# Demo Reset Button
st.sidebar.markdown("---")
if st.sidebar.button("🚨 Wipe Database (Reset Demo)"):
    db.wipe_database()
    st.sidebar.success("Database wiped! Starting fresh.")
    st.rerun()
    
# --- DEMO ONLY: IAM SECURITY VIEWER ---
with st.sidebar.expander("🔐 IAM & Security Context (Demo)"):
    st.markdown("**Upstream Headers Injected by API Gateway:**")
    try:
        # Pull the raw headers Streamlit received from Nginx
        headers = st.context.headers
        
        jwt_header = headers.get('Authorization', 'Not Found')
        rbac_user = headers.get('X-Forwarded-User', 'Not Found')
        rbac_group = headers.get('X-Forwarded-Groups', 'Not Found')
        
        st.code(f"Authorization: {jwt_header}\n"
                f"X-Forwarded-User: {rbac_user}\n"
                f"X-Forwarded-Groups: {rbac_group}", 
                language="http")
    except AttributeError:
        st.error("Header reflection not supported in this Streamlit version.")


st.title("🏛️ TTB Automated COLA Platform")

# ==========================================
# ROLE 1: INDUSTRY APPLICANT
# ==========================================
if user_role == "Industry Applicant":
    st.subheader("🍺 Industry Portal")
    
    with st.form("cola_form"):
        st.write("**Submit New Application**")
        col1, col2 = st.columns(2)
        with col1:
            brand = st.text_input("Brand Name", "CARLO GIACOSA")
            class_type = st.text_input("Class/Type", "BARBARESCO")
        with col2:
            alc = st.text_input("Alcohol Content", "14%")
            net = st.text_input("Net Contents", "750 ML")
            
        st.write("**Label Artwork**")
        front_img = st.file_uploader("Front Label", type=['jpg', 'png'])
        back_img = st.file_uploader("Back Label", type=['jpg', 'png'])
        
        if st.form_submit_button("Submit Application"):
            if not front_img:
                st.error("Front label is required.")
            else:
                f_bytes = front_img.read()
                b_bytes = back_img.read() if back_img else None
                
                # --- NEW: INPUT DLP MASKING (Form Submission) ---
                data = {
                    "brand_name": mask_sensitive_data(brand), 
                    "class_type": mask_sensitive_data(class_type), 
                    "alc_content": mask_sensitive_data(alc), 
                    "net_contents": mask_sensitive_data(net)
                }
                
                db.add_application(data, f_bytes, b_bytes)
                st.success("Application successfully submitted to the TTB queue.")

    st.divider()

    # Section A.2: Bulk CSV Upload
    with st.expander("📁 Bulk Application Upload (CSV)", expanded=False):
        st.markdown("""
        **Format Requirement:** CSV must match the legacy batch format with headers: 
        `filename`, `brand_name`, `class_type`, `alc_content`, `net_contents`
        """)
        csv_file = st.file_uploader("1. Upload 'batch_data.csv'", type=['csv'])
        bulk_images = st.file_uploader("2. Upload All Referenced Images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
        
        if st.button("Process Bulk Ingestion"):
            if not csv_file or not bulk_images:
                st.error("Please upload both the CSV and the corresponding image files.")
            else:
                image_dict = {img.name: img.read() for img in bulk_images}
                csv_reader = csv.DictReader(io.StringIO(csv_file.getvalue().decode('utf-8')))
                success_count = 0
                missing_images = []
                
                for row in csv_reader:
                    f_name = row.get('filename', '').strip()
                    f_bytes = image_dict.get(f_name)
                    
                    if f_bytes: 
                        # --- NEW: INPUT DLP MASKING (CSV Bulk Upload) ---
                        masked_row_data = {
                            "brand_name": mask_sensitive_data(str(row.get('brand_name', ''))),
                            "class_type": mask_sensitive_data(str(row.get('class_type', ''))),
                            "alc_content": mask_sensitive_data(str(row.get('alc_content', ''))),
                            "net_contents": mask_sensitive_data(str(row.get('net_contents', '')))
                        }
                        
                        db.add_application(masked_row_data, f_bytes, None)
                        success_count += 1
                    else:
                        missing_images.append(f_name)
                        
                if success_count > 0:
                    st.success(f"Successfully ingested {success_count} applications from CSV!")
                if missing_images:
                    st.warning(f"Skipped {len(missing_images)} rows. Could not find uploaded images for: {', '.join(missing_images[:5])}...")

    st.divider()

    st.write("**My Applications Dashboard**")
    my_apps = db.get_applications()
    if not my_apps:
        st.info("No applications submitted yet.")
        
    for app in my_apps:
        status_icon = "✅" if app[7] == 'APPROVED' else "❌" if app[7] == 'REJECTED' else "⏳"
        with st.expander(f"{status_icon} ID: {app[0]} | {app[1]} - {app[7]}"):
            if app[7] == 'REJECTED':
                st.error(f"**Rejection Reason from TTB:** {app[8]}")
            st.write(f"Class: {app[2]} | ABV: {app[3]}")

# ==========================================
# ROLE 2: TTB REVIEW AGENT
# ==========================================

elif user_role == "TTB Review Agent":
    st.subheader("🛡️ Agent Workspace")
    
    # --- NEW: AUTO-HEALING QUEUE SWEEP ---
    # Automatically rescues items stranded by dropped WebSockets
    recovered_count = db.auto_unlock_stuck_applications(timeout_minutes=20)
    if recovered_count > 0:
        st.toast(f"Auto-Healing: {recovered_count} stranded applications safely returned to the PENDING queue.", icon="🔧")
    
    pending_apps = db.get_applications(status='PENDING')
    flagged_apps = db.get_applications(status='FLAGGED')
    approved_apps = db.get_applications(status='APPROVED')
    
    # Create the 4-tab interface
    tab_manual, tab_ai, tab_flagged, tab_approved = st.tabs([
        f"📝 Manual Review Desk ({len(pending_apps)})", 
        f"🤖 AI Batch Triage ({len(pending_apps)})", 
        f"⚠️ Flagged Queue ({len(flagged_apps)})",
        f"✅ Approved Registry ({len(approved_apps)})"
    ])
    
    # ------------------------------------------
    # TAB 1: MANUAL REVIEW DESK
    # ------------------------------------------
    with tab_manual:
        st.write("**Direct Human Review** (Bypasses AI verification entirely)")
        if not pending_apps:
            st.success("No pending applications currently require manual processing.")
            
        for app in pending_apps:
            with st.expander(f"Pending Application #{app[0]} - {app[1]}"):
                col_img, col_data = st.columns(2)
                
                with col_img:
                    if app[5]: st.image(app[5], caption="Front Label", use_container_width=True)
                    if app[6]: st.image(app[6], caption="Back Label", use_container_width=True)
                
                with col_data:
                    st.write(f"**Brand:** {app[1]}")
                    st.write(f"**Class:** {app[2]}")
                    st.write(f"**ABV:** {app[3]}")
                    st.markdown("---")
                    
                    if st.button("Approve Directly", key=f"man_app_{app[0]}"):
                        db.update_status(app[0], "APPROVED")
                        st.rerun()
                        
                    man_reason = st.text_input("Rejection Reason:", key=f"man_reason_{app[0]}")
                    if st.button("Reject Directly", key=f"man_rej_{app[0]}"):
                        if man_reason:
                            db.update_status(app[0], "REJECTED", man_reason)
                            st.rerun()
                        else:
                            st.error("A reason must be provided to reject an application.")

    # ------------------------------------------
    # TAB 2: AI BATCH TRIAGE
    # ------------------------------------------
    with tab_ai:
        st.write("**Automated Verification Engine**")
        
        # --- FAILSAFE UNLOCK ---
        processing_apps = db.get_applications(status='PROCESSING')
        if processing_apps:
            st.warning(f"⏳ {len(processing_apps)} applications are currently locked for AI processing.")
            if st.button("Unlock Stuck Applications (Failsafe)"):
                for app in processing_apps:
                    db.update_status(app[0], "PENDING", "")
                st.rerun()

        if not pending_apps:
            st.info("No pending applications in the queue.")
        else:
            st.write("**Select applications to analyze:**")
            
            # --- NEW: STATEFUL SELECT ALL / SELECT NONE BUTTONS ---
            col_sel1, col_sel2, _ = st.columns([1, 1, 3])
            with col_sel1:
                if st.button("☑️ Select All"):
                    for app in pending_apps:
                        st.session_state[f"ai_chk_{app[0]}"] = True
                    st.rerun()
            with col_sel2:
                if st.button("☐ Select None"):
                    for app in pending_apps:
                        st.session_state[f"ai_chk_{app[0]}"] = False
                    st.rerun()

            selected_apps = []
            
            # Generate a stateful checkbox for every pending application
            for app in pending_apps:
                chk_key = f"ai_chk_{app[0]}"
                
                # Default all checkboxes to True on the very first load
                if chk_key not in st.session_state:
                    st.session_state[chk_key] = True
                    
                # Read the value strictly from session_state
                if st.checkbox(f"App #{app[0]} - {app[1]} ({app[2]})", key=chk_key):
                    selected_apps.append(app)
            
            st.markdown("---")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                run_fast = st.button("⚡ Run Fast Triage (OCR Only)", help="Takes seconds. Fails complex labels.")
            with col_btn2:
                run_deep = st.button("🧠 Run Deep Triage (VLM Only)", help="Highly accurate. Takes significantly longer.")
                
            if run_fast or run_deep:
                if not selected_apps:
                    st.error("Please select at least one application to process.")
                else:
                    use_vlm = run_deep 
                    
                    # --- RECORD LOCKING ---
                    for app in selected_apps:
                        db.update_status(app[0], "PROCESSING", "Locked: Actively being analyzed by AI.")
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, app in enumerate(selected_apps):
                        status_text.text(f"Analyzing Application #{app[0]} ({app[1]})...")
                        app_data = {"brand_name": app[1], "class_type": app[2], "alc_content": app[3], "net_contents": app[4]}
                        images = [app[5], app[6]] 
                        
                        try:
                            # 1. Attempt AI Processing
                            result = process_label(images, app_data, use_vlm=use_vlm)
                            
                            # 2. Write Success/Flag to Database
                            db.update_ai_results(app[0], result['status'], json.dumps(result['details']), result['raw_text'])
                            
                        except Exception as e:
                            # 3. THE CATCH AND RELEASE FAILSAFE
                            error_msg = f"Reverted to queue due to system timeout or error. ({str(e)})"
                            db.update_status(app[0], "PENDING", error_msg)
                            st.toast(f"App #{app[0]} timed out and was returned to the PENDING queue.", icon="⚠️")
                        
                        # 4. Throttling: Let the SQLite journal file settle to prevent write-locks
                        time.sleep(0.5)
                        
                        progress_bar.progress((i + 1) / len(selected_apps))
                        
                    st.success("Batch processing complete!")
                    time.sleep(1) # Final pause before the UI refreshes
                    st.rerun()
    # ------------------------------------------
    # TAB 3: FLAGGED QUEUE
    # ------------------------------------------
    with tab_flagged:
        st.write("**Manual Intervention Required** (Failed AI verification)")
        if not flagged_apps:
            st.success("No applications currently require manual intervention.")
        else:
            col_mass1, col_mass2 = st.columns(2)
            with col_mass1:
                if st.button("🚨 Force Approve ALL Flagged Applications"):
                    for app in flagged_apps:
                        db.update_status(app[0], "APPROVED")
                    st.rerun()
            with col_mass2:
                mass_reason = st.text_input("Mass Rejection Reason:", key="mass_rej_reason")
                if st.button("🛑 Reject ALL Flagged Applications"):
                    if mass_reason:
                        for app in flagged_apps:
                            db.update_status(app[0], "REJECTED", mass_reason)
                        st.rerun()
                    else:
                        st.error("Please provide a reason to mass-reject.")
            
            st.markdown("---")
            
            for app in flagged_apps:
                with st.expander(f"⚠️ Flagged Application #{app[0]} - {app[1]}"):
                    col_img, col_data = st.columns(2)
                    
                    with col_img:
                        if app[5]: st.image(app[5], caption="Front Label", use_container_width=True)
                        if app[6]: st.image(app[6], caption="Back Label", use_container_width=True)
                    
                    with col_data:
                        st.write(f"**Brand:** {app[1]}")
                        st.write(f"**Class:** {app[2]}")
                        st.write(f"**ABV:** {app[3]}")
                        st.markdown("---")
                        
                        default_reason = ""
                        
                        if len(app) > 9 and app[9]:
                            st.write("**AI Verification Output:**")
                            checks = json.loads(app[9])
                            failed_checks = []
                            
                            for field, passed in checks.items():
                                icon = "✅" if passed else "❌"
                                st.write(f"{icon} {field}")
                                if not passed:
                                    failed_checks.append(field)
                                    
                            if failed_checks:
                                default_reason = "Failed TTB Requirements: " + ", ".join(failed_checks)
                                
                            if len(app) > 10 and app[10]:
                                with st.expander("🔍 View Raw Engine Extraction"):
                                    st.code(app[10], language="text")
                        
                        st.markdown("---")
                        
                        if st.button("Force Approve", key=f"flag_app_{app[0]}"):
                            db.update_status(app[0], "APPROVED")
                            st.rerun()
                            
                        reason = st.text_input("Rejection Reason:", value=default_reason, key=f"flag_reason_{app[0]}")
                        if st.button("Reject & Notify Applicant", key=f"flag_rej_{app[0]}"):
                            if reason:
                                db.update_status(app[0], "REJECTED", reason)
                                st.rerun()
                            else:
                                st.error("A reason must be provided to reject an application.")

    # ------------------------------------------
    # TAB 4: APPROVED REGISTRY (Audit)
    # ------------------------------------------
    with tab_approved:
        st.write("**Approved Applications Audit Log** (Spot-check automated approvals)")
        if not approved_apps:
            st.info("No approved applications on file.")
        else:
            for app in approved_apps:
                with st.expander(f"✅ Approved Application #{app[0]} - {app[1]}"):
                    col_img, col_data = st.columns(2)
                    
                    with col_img:
                        if app[5]: st.image(app[5], caption="Front Label", use_container_width=True)
                        if app[6]: st.image(app[6], caption="Back Label", use_container_width=True)
                    
                    with col_data:
                        st.write(f"**Brand:** {app[1]}")
                        st.write(f"**Class:** {app[2]}")
                        st.write(f"**ABV:** {app[3]}")
                        st.markdown("---")
                        
                        if len(app) > 9 and app[9]:
                            st.write("**AI Verification Output:**")
                            checks = json.loads(app[9])
                            for field, passed in checks.items():
                                icon = "✅" if passed else "❌"
                                st.write(f"{icon} {field}")
                                
                            if len(app) > 10 and app[10]:
                                with st.expander("🔍 View Raw Engine Extraction"):
                                    st.code(app[10], language="text")
                        
                        st.markdown("---")
                        
                        if st.button("Revoke Approval & Flag", key=f"revoke_app_{app[0]}"):
                            db.update_status(app[0], "FLAGGED", "Automated approval revoked by auditing agent.")
                            st.rerun()