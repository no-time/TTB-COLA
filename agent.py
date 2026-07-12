import streamlit as st
import sqlite3
import json
from verification_engine import process_label

st.set_page_config(layout="wide")
st.title("🛡️ TTB Reviewer Queue")

# Fetch all pending applications
conn = sqlite3.connect("ttb_data.db")
pending = conn.execute("SELECT * FROM applications WHERE status='PENDING'").fetchall()
conn.close()

if st.button("Run Batch AI Verification"):
    for app in pending:
        # 1. Run engine
        images = json.loads(app[5])
        app_data = {"brand_name": app[1], "class_type": app[2], "alc_content": app[3], "net_contents": app[4]}
        result = process_label(images, app_data)
        
        # 2. Update DB based on result
        status = "APPROVED" if result['status'] == 'Pass' else "REJECTED"
        conn = sqlite3.connect("ttb_data.db")
        conn.execute("UPDATE applications SET status=? WHERE id=?", (status, app[0]))
        conn.commit()
        conn.close()
    st.rerun()

# Display Review Queue
for app in pending:
    with st.expander(f"Application #{app[0]} - {app[1]}"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Brand:** {app[1]} | **Class:** {app[2]}")
            # Add buttons for Manual Override or Reject with Reason
            if st.button(f"Reject #{app[0]}", key=f"rej_{app[0]}"):
                reason = st.text_input("Reason for rejection:", key=f"reason_{app[0]}")
                if st.button("Confirm Rejection", key=f"conf_{app[0]}"):
                    # Update DB with status REJECTED and reason
                    pass