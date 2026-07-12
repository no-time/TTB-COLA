import sqlite3

DB_NAME = "ttb_data.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_name TEXT, class_type TEXT, alc_content TEXT, net_contents TEXT,
                front_label BLOB, back_label BLOB,
                status TEXT DEFAULT 'PENDING',
                rejection_reason TEXT,
                ai_details TEXT, ai_raw_text TEXT,
                locked_at TIMESTAMP
            )
        ''')
        # Failsafes to alter the schema if the table already existed
        try: conn.execute("ALTER TABLE applications ADD COLUMN ai_details TEXT")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE applications ADD COLUMN ai_raw_text TEXT")
        except sqlite3.OperationalError: pass
        try: conn.execute("ALTER TABLE applications ADD COLUMN locked_at TIMESTAMP")
        except sqlite3.OperationalError: pass

def add_application(data, front_blob, back_blob):
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO applications (brand_name, class_type, alc_content, net_contents, front_label, back_label)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['brand_name'], data['class_type'], data['alc_content'], data['net_contents'], front_blob, back_blob))

def get_applications(status=None):
    with get_connection() as conn:
        if status:
            return conn.execute("SELECT * FROM applications WHERE status = ?", (status,)).fetchall()
        return conn.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()

def update_status(app_id, status, reason=""):
    with get_connection() as conn:
        # If locking for AI, set the timestamp. Otherwise, clear it.
        if status == "PROCESSING":
            conn.execute("UPDATE applications SET status = ?, rejection_reason = ?, locked_at = CURRENT_TIMESTAMP WHERE id = ?", (status, reason, app_id))
        else:
            conn.execute("UPDATE applications SET status = ?, rejection_reason = ?, locked_at = NULL WHERE id = ?", (status, reason, app_id))

def update_ai_results(app_id, status, details, raw_text):
    with get_connection() as conn:
        # Clear the lock timestamp since the AI successfully finished
        conn.execute("UPDATE applications SET status = ?, ai_details = ?, ai_raw_text = ?, locked_at = NULL WHERE id = ?", 
                     (status, details, raw_text, app_id))

def auto_unlock_stuck_applications(timeout_minutes=20):
    """Reverts applications locked longer than the timeout back to PENDING."""
    with get_connection() as conn:
        cursor = conn.execute(f'''
            UPDATE applications 
            SET status = 'PENDING', 
                rejection_reason = 'System automatically unlocked due to processing timeout.',
                locked_at = NULL
            WHERE status = 'PROCESSING' 
              AND locked_at <= datetime('now', '-{timeout_minutes} minutes')
        ''')
        return cursor.rowcount

def wipe_database():
    """Drops the table entirely and recreates a fresh schema."""
    with get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS applications")
    init_db()