import streamlit as st
import sqlite3
import pandas as pd
import openpyxl
import os
import io
import base64
import re
import json
import google.generativeai as genai
from PIL import Image
from streamlit_paste_button import paste_image_button

# --- Configuration & UI Setup (Must be first Streamlit command) ---
st.set_page_config(page_title="Abdul", page_icon="abdul_logo_nobg.png", layout="wide")

# --- Configuration & Database Setup ---
DB_FILE = "cctv_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS camera_installations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            license_plate TEXT,
            installation_position TEXT NOT NULL,
            cable_length_m REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dropdown_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            option_value TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_memory (
            image_hash TEXT PRIMARY KEY,
            position TEXT NOT NULL
        )
    ''')
    c.execute("SELECT COUNT(*) FROM dropdown_options")
    if c.fetchone()[0] == 0:
        defaults = [
            ("company", "เธเธฃเธดเธฉเธฑเธ— เธ•เธฑเธงเธญเธขเนเธฒเธ เธเธณเธเธฑเธ”"),
            ("vehicle", "เธฃเธ–เธเธฃเธฐเธเธฐ"), ("vehicle", "เธฃเธ–เธเธฑเธช"), ("vehicle", "เธฃเธ–เธเธฃเธฃเธ—เธธเธ"), ("vehicle", "เธฃเธ–เธ•เธนเน"),
            ("position", "เธชเนเธญเธเธซเธเนเธฒเธเธเธเธฑเธ"), ("position", "เธชเนเธญเธเธซเนเธญเธเนเธ”เธขเธชเธฒเธฃ"), ("position", "เธชเนเธญเธเธ–เธเธ"),
            ("position", "เธเธเธเธฃเธฐเธเธเธเนเธฒเธข"), ("position", "เธเธเธเธฃเธฐเธเธเธเธงเธฒ"), ("position", "เนเธเธ•เธนเนเธชเธดเธเธเนเธฒ"), ("position", "เธชเนเธญเธเธซเธฅเธฑเธเธฃเธ–")
        ]
        c.executemany("INSERT INTO dropdown_options (category, option_value) VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()

import hashlib
def get_image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

def get_ai_memory(image_hash):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT position FROM ai_memory WHERE image_hash = ?", (image_hash,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_ai_memory(image_hash, position):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ai_memory (image_hash, position) VALUES (?, ?)", (image_hash, position))
    conn.commit()
    conn.close()

def get_dropdown_options(category):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT option_value FROM dropdown_options WHERE category = ?", (category,))
    opts = [row[0] for row in c.fetchall()]
    conn.close()
    return opts

def add_dropdown_option(category, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM dropdown_options WHERE category = ? AND option_value = ?", (category, value))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO dropdown_options (category, option_value) VALUES (?, ?)", (category, value))
        conn.commit()
    conn.close()

def delete_dropdown_option(category, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM dropdown_options WHERE category = ? AND option_value = ?", (category, value))
    conn.commit()
    conn.close()

def add_data(company, vehicle, position, length, plate=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO camera_installations (company_name, vehicle_type, installation_position, cable_length_m, license_plate)
        VALUES (?, ?, ?, ?, ?)
    ''', (company, vehicle, position, length, plate))
    conn.commit()
    conn.close()

def delete_company_data(company):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM camera_installations WHERE company_name = ?", (company,))
    conn.commit()
    conn.close()

def delete_vehicle_data(company, vehicle):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM camera_installations WHERE company_name = ? AND vehicle_type = ?", (company, vehicle))
    conn.commit()
    conn.close()

def get_all_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM camera_installations ORDER BY timestamp DESC", conn)
    conn.close()
    return df

# Upgrade DB for old versions (add license_plate if missing)
def upgrade_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("SELECT license_plate FROM camera_installations LIMIT 1")
    except:
        c.execute("ALTER TABLE camera_installations ADD COLUMN license_plate TEXT")
        conn.commit()
    conn.close()

# Initialize DB on start
init_db()
upgrade_db()

import re
def predict_vehicle_type(plate):
    if not plate: return None
    plate = plate.strip().replace(" ", "")
    # Patterns for Thai Plates
    if re.match(r'^[1][0-9]-\d{4}$', plate): return "เธฃเธ–เนเธ”เธขเธชเธฒเธฃเธชเธฒเธเธฒเธฃเธ“เธฐ (เธเธฑเธช)"
    if re.match(r'^[3][0-9]-\d{4}$', plate): return "เธฃเธ–เนเธ”เธขเธชเธฒเธฃเนเธกเนเธเธฃเธฐเธเธณเธ—เธฒเธ (30-)"
    if re.match(r'^[7][0-9]-\d{4}$', plate): return "เธฃเธ–เธเธฃเธฃเธ—เธธเธเธชเธฒเธเธฒเธฃเธ“เธฐ (เธซเธฑเธงเธฅเธฒเธ/เธเนเธงเธ)"
    if re.match(r'^[89][0-9]-\d{4}$', plate): return "เธฃเธ–เธเธฃเธฃเธ—เธธเธเธชเนเธงเธเธเธธเธเธเธฅ (80-)"
    if re.match(r'^\d?[เธเธเธ’][เธ-เธฎ]\d{1,4}$', plate): return "เธฃเธ–เธเธฃเธฐเธเธฐ (เธเนเธฒเธขเน€เธเธตเธขเธง)"
    if re.match(r'^\d?[เธเธก][เธ-เธฎ]\d{1,4}$', plate): return "เธฃเธ–เธ•เธนเน/เธฃเธ–เธขเธเธ•เนเธเธฑเนเธเธชเนเธงเธเธเธธเธเธเธฅ (>7 เธ—เธตเนเธเธฑเนเธ)"
    if re.match(r'^\d?[เธ-เธฎ]{2}\d{1,4}$', plate): return "เธฃเธ–เธขเธเธ•เนเธเธฑเนเธเธชเนเธงเธเธเธธเธเธเธฅ (เน€เธเนเธ/SUV)"
    return None

def get_last_veh_by_plate(plate):
    if not plate: return None
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT vehicle_type FROM camera_installations WHERE license_plate = ? ORDER BY timestamp DESC LIMIT 1", (plate.strip(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_suggested_length(company, vehicle, position):
    if not company or not vehicle or not position: return 5.0 # default
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT cable_length_m FROM camera_installations 
        WHERE company_name = ? AND vehicle_type = ? AND installation_position = ? 
        ORDER BY timestamp DESC LIMIT 1
    """, (company, vehicle, position))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 5.0

def analyze_camera_vision(files, api_key, available_options):
    """
    Analyzes one or more images (or a grid) and returns a mapping of CH -> position.
    Checks memory first.
    """
    try:
        # Calculate composite hash for memory
        hashes = sorted([get_image_hash(f.getvalue()) for f in files])
        composite_hash = hashlib.md5("".join(hashes).encode()).hexdigest()
        
        # Check memory
        remembered_data = get_ai_memory(composite_hash)
        if remembered_data:
            try:
                # Try parsing as JSON for multi-view
                return json.loads(remembered_data)
            except:
                # Fallback to single position if it's old data
                return {"CH1": remembered_data}

        # If no memory, call AI
        genai.configure(api_key=api_key)
        
        vision_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'gemini' in m.name and ('flash' in m.name or 'vision' in m.name):
                        vision_models.append(m.name)
            if not vision_models: vision_models = ['models/gemini-1.5-flash']
        except: vision_models = ['models/gemini-1.5-flash']

        content_parts = []
        for f in files:
            img_data = f.getvalue()
            content_parts.append({ "mime_type": "image/jpeg", "data": img_data })
        
        opts_str = ", ".join(available_options)
        
        prompt = f"""
        You are an expert CCTV installation technician for TRUCKS and LOGISTICS vehicles.
        Identify the camera positions for each view. Use ONLY these options: [{opts_str}].
        
        Return ONLY a JSON object mapping channel names (CH1, CH2...) to positions.
        If it's a grid, detect labels in the image.
        Example: {{"CH1": "เธชเนเธญเธเธซเธเนเธฒเธเธเธเธฑเธ", "CH2": "เธชเนเธญเธเธซเธฅเธฑเธเธฃเธ–"}}
        """
        content_parts.append(prompt)
        
        last_err = ""
        for m_name in vision_models:
            try:
                model = genai.GenerativeModel(model_name=m_name)
                response = model.generate_content(content_parts)
                text = response.text.strip()
                if "```json" in text:
                    text = text.split("```json")[-1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[-1].split("```")[0].strip()
                
                result_map = json.loads(text)
                # Save to memory immediately for future use
                save_ai_memory(composite_hash, json.dumps(result_map, ensure_ascii=False))
                return result_map
            except Exception as inner_e:
                last_err = str(inner_e)
                continue
        
        return {"error": f"AI Error: {last_err}"}
    except Exception as e:
        return {"error": f"AI Config Error: {str(e)}"}

# --- UI Setup ---
# --- UI Setup removed from here ---

# Custom CSS for premium & mobile-friendly look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    /* Global button styling */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #007bff;
        color: white;
        font-weight: 600;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0056b3;
        transform: translateY(-1px);
    }
    /* Input fields styling */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 8px !important;
    }
    /* Card-like container for data */
    .company-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    /* Responsive Font Sizes & Mobile Tweaks */
    @media (max-width: 600px) {
        h1 { font-size: 1.8em !important; }
        h2 { font-size: 1.5em !important; }
        h3 { font-size: 1.2em !important; }
        .stMarkdown p { font-size: 1em !important; }
        .floating-img { max-width: 200px !important; }
        /* Make buttons easier to tap on mobile */
        .stButton>button {
            height: 4em !important;
            font-size: 1.1em !important;
        }
        /* Reduce padding for sidebars/main on mobile */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }
    /* Animation for logo */
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
        100% { transform: translateY(0px); }
    }
    .floating-img {
        animation: float 4s ease-in-out infinite;
        display: block;
        margin: 0 auto;
        max-width: 280px;
        width: 100%;
        filter: drop-shadow(0 10px 15px rgba(0,0,0,0.1));
    }
    </style>
    """, unsafe_allow_html=True)

if 'started' not in st.session_state:
    st.session_state.started = False

def start_app():
    st.session_state.started = True

if not st.session_state.started:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        import base64
        logo_path = "abdul_logo_nobg.png"
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode()
            st.markdown(f'<img src="data:image/png;base64,{b64_string}" class="floating-img" style="max-width: 250px;">', unsafe_allow_html=True)
        else:
            st.info("โ ๏ธ เนเธกเนเธเธเนเธเธฅเนเนเธฅเนเธเน (Logo not found)")
            
        st.markdown("<h1 style='text-align: center; color: #1e293b;'>Abdul</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #475569;'>AI CCTV Data Management System</h3>", unsafe_allow_html=True)
    st.sidebar.markdown("### ๐”‘ เธ•เธฑเนเธเธเนเธฒ AI")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="เธเธญเธฃเธฑเธ API Key เธเธฃเธตเนเธ”เนเธ—เธตเนเน€เธงเนเธ Google AI Studio")
    
    menu = ["เน€เธเธดเนเธกเธเนเธญเธกเธนเธฅเนเธซเธกเน", "เธ”เธนเธเนเธญเธกเธนเธฅเนเธฅเธฐเธเนเธเธซเธฒ", "เธ•เธฑเนเธเธเนเธฒเธ•เธฑเธงเน€เธฅเธทเธญเธ Dropdown", "เธเธณเน€เธเนเธฒเธเนเธญเธกเธนเธฅเธเธฒเธ Excel"]
    choice = st.sidebar.selectbox("เน€เธกเธเธนเธเธฒเธฃเนเธเนเธเธฒเธ", menu)
    
    if choice == "เน€เธเธดเนเธกเธเนเธญเธกเธนเธฅเนเธซเธกเน":
        st.subheader("๐“ เธเธฑเธเธ—เธถเธเธเนเธญเธกเธนเธฅเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธ")
        
        tab1, tab2 = st.tabs(["โจ เธเธฑเธเธ—เธถเธเธ—เธตเธฅเธฐเธฃเธฒเธขเธเธฒเธฃ (เนเธเธฐเธเธณ)", "๐“ เธเธฑเธเธ—เธถเธเนเธเธเธ•เธฒเธฃเธฒเธ (เธซเธฅเธฒเธขเธเธฃเธดเธฉเธฑเธ—)"])
        
        df_existing = get_all_data()
        settings_companies = get_dropdown_options("company")
        existing_companies_data = sorted(df_existing['company_name'].unique().tolist()) if not df_existing.empty else []
        all_companies = sorted(list(set(settings_companies + existing_companies_data)))
        
        settings_vehicles = get_dropdown_options("vehicle")
        existing_vehicles_data = sorted(df_existing['vehicle_type'].unique().tolist()) if not df_existing.empty else []
        all_vehicles = sorted(list(set(settings_vehicles + existing_vehicles_data)))
        
        with tab1:
            # AI Vision Section
            st.markdown("<div class='company-card' style='background: #f0f7ff; border-left: 5px solid #007bff;'>", unsafe_allow_html=True)
            st.markdown("#### ๐ฆ… เธเนเธเธซเธฒเธ•เธณเนเธซเธเนเธเธ”เนเธงเธข AI (Vision Assistant)")
            if not gemini_api_key:
                st.warning("โ ๏ธ เธเธฃเธธเธ“เธฒเนเธชเน Gemini API Key เธ—เธตเนเนเธ–เธเน€เธกเธเธนเธเนเธฒเธเน€เธเธทเนเธญเน€เธเธดเธ”เนเธเนเธฃเธฐเธเธเธงเธดเน€เธเธฃเธฒเธฐเธซเนเธ เธฒเธ")
            
            # Add paste support initialization
            if "pasted_images" not in st.session_state:
                st.session_state.pasted_images = []
    
            col_up1, col_up2 = st.columns([3, 1])
            with col_up1:
                uploaded_files = st.file_uploader("๐“ธ เธฅเธฒเธเธฃเธนเธเธ เธฒเธ (เธซเธฃเธทเธญเธฃเธนเธเธเธฃเธดเธ”) เธกเธฒเธงเธฒเธเน€เธเธทเนเธญเธงเธดเน€เธเธฃเธฒเธฐเธซเนเธ•เธณเนเธซเธเนเธ", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            with col_up2:
                st.write("") # spacing
                st.write("") # spacing
                
                pasted_img = paste_image_button("๐“ เธงเธฒเธเธเธฒเธเธเธฅเธดเธเธเธญเธฃเนเธ”", key="paste_btn", use_container_width=True)
    
                if pasted_img and pasted_img.image_data:
                    # Use hash to avoid duplicates and infinite loops on rerun
                    import hashlib
                    temp_buf = io.BytesIO()
                    pasted_img.image_data.save(temp_buf, format="PNG")
                    img_hash = hashlib.md5(temp_buf.getvalue()).hexdigest()
                    
                    if st.session_state.get("last_pasted_hash") != img_hash:
                        st.session_state.last_pasted_hash = img_hash
                        temp_buf.name = f"pasted_image_{len(st.session_state.pasted_images)+1}.png"
                        st.session_state.pasted_images.append(temp_buf)
                        st.rerun()
                
                if st.session_state.pasted_images:
                    if st.button("๐—‘๏ธ เธฅเนเธฒเธเธ เธฒเธเธ—เธตเนเธงเธฒเธ", key="clear_pasted"):
                        st.session_state.pasted_images = []
                        if "last_pasted_hash" in st.session_state:
                            del st.session_state["last_pasted_hash"]
                        st.rerun()
    
            # Combine both sources
            all_files_to_analyze = []
            if uploaded_files:
                all_files_to_analyze.extend(uploaded_files)
            if st.session_state.pasted_images:
                all_files_to_analyze.extend(st.session_state.pasted_images)
    
            if all_files_to_analyze and gemini_api_key:
                # Display thumbnails
                st.image(all_files_to_analyze, width=150, caption=[f"เธ เธฒเธเธ—เธตเน {i+1}" for i in range(len(all_files_to_analyze))])
                
                if st.button("๐” เน€เธฃเธดเนเธกเธงเธดเน€เธเธฃเธฒเธฐเธซเนเธ เธฒเธเธ—เธฑเนเธเธซเธกเธ”เธ”เนเธงเธข AI"):
                    with st.spinner("AI เธเธณเธฅเธฑเธเธงเธดเน€เธเธฃเธฒเธฐเธซเนเธ—เธธเธเธกเธธเธกเธกเธญเธ..."):
                        all_pos_opts = get_dropdown_options("position")
                        ai_results = analyze_camera_vision(all_files_to_analyze, gemini_api_key, all_pos_opts)
                        
                        if "error" in ai_results:
                            st.error(ai_results["error"])
                        else:
                            st.session_state["ai_suggestions"] = ai_results
                            st.success(f"โ… เธงเธดเน€เธเธฃเธฒเธฐเธซเนเน€เธชเธฃเนเธเธชเธดเนเธ! เธเธเธเนเธญเธกเธนเธฅเธ•เธณเนเธซเธเนเธเนเธ {len(ai_results)} เธเนเธญเธเธชเธฑเธเธเธฒเธ“")
                            
                            # Show result summaries with memory info
                            cols = st.columns(4)
                            all_remembered = True
                            for idx, (ch, pos) in enumerate(ai_results.items()):
                                with cols[idx % 4]:
                                    st.info(f"**{ch}:** {pos}")
                            
                            st.divider()
                            st.info("๐’ก **เธเธณเนเธเธฐเธเธณ:** เธ•เธฃเธงเธเธชเธญเธเธเนเธญเธกเธนเธฅเธ—เธตเนเธเธญเธฃเนเธกเธ”เนเธฒเธเธฅเนเธฒเธ เธซเธฒเธ AI เธ—เธฒเธขเธเธดเธ” เนเธซเนเนเธเนเนเธเนเธเธเธญเธฃเนเธกเนเธฅเนเธงเธเธ”เธเธฑเธเธ—เธถเธเธเนเธญเธกเธนเธฅเธฃเธ– AI เธเธฐเธเธณเธเธงเธฒเธกเธ–เธนเธเธ•เนเธญเธเนเธงเนเธชเธณเธซเธฃเธฑเธเธ เธฒเธเธเธธเธ”เธเธตเนเธเธฃเธฑเธ")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    
            st.markdown("<div class='company-card'>", unsafe_allow_html=True)
            with st.form("add_form_final", clear_on_submit=False): # Don't clear to keep company name
                col1, col2 = st.columns(2)
                with col1:
                    selected_comp = st.selectbox("๐ข เน€เธฅเธทเธญเธเธเธฃเธดเธฉเธฑเธ—", options=["-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --"] + all_companies)
                    new_comp = st.text_input("โ• เธซเธฃเธทเธญเธเธดเธกเธเนเธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—เนเธซเธกเน")
                    in_plate = st.text_input("๐”ข เธเนเธฒเธขเธ—เธฐเน€เธเธตเธขเธเธฃเธ–", placeholder="เน€เธเนเธ 70-1234 เธซเธฃเธทเธญ 1เธเธ-5555")
                with col2:
                    # Prediction + Memory logic
                    prediction = predict_vehicle_type(in_plate)
                    history_veh = get_last_veh_by_plate(in_plate)
                    
                    if history_veh:
                        st.success(f"๐“ เธเธงเธฒเธกเธเธณเธฃเธฐเธเธ: เธ—เธฐเน€เธเธตเธขเธเธเธตเนเธเธทเธญ **{history_veh}**")
                        if st.button(f"โจ เนเธเน {history_veh}"):
                            st.session_state["suggested_veh"] = history_veh
                    elif prediction:
                        st.info(f"๐’ก เธเธณเนเธเธฐเธเธณ: เธฃเธฐเธเธเธงเธดเน€เธเธฃเธฒเธฐเธซเนเธงเนเธฒเน€เธเนเธ **{prediction}**")
                    
                    # Use value from session state if suggested
                    val_veh = st.session_state.get("suggested_veh", "")
                    
                    settings_veh = get_dropdown_options("vehicle")
                    existing_v = sorted(df_existing['vehicle_type'].unique().tolist()) if not df_existing.empty else []
                    all_v_opts = sorted(list(set(settings_veh + existing_v)))
                    
                    selected_veh = st.selectbox("๐— เน€เธฅเธทเธญเธเธเธฃเธฐเน€เธ เธ—เธฃเธ–", options=["-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --"] + all_v_opts)
                    new_veh = st.text_input("โ• เธซเธฃเธทเธญเธเธดเธกเธเนเธเธฃเธฐเน€เธ เธ—เธฃเธ–เนเธซเธกเน (เธ–เนเธฒเนเธกเนเธกเธตเนเธเธฃเธฒเธขเธเธฒเธฃ)", value=val_veh)
                    
                    # Reset suggestion after use (optional, but keep it simple)
                    if val_veh: 
                        st.session_state["suggested_veh"] = "" # Clear for next entry
                    
                st.divider()
                st.markdown("**๐“ธ เธฃเธฐเธเธธเธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธ (CH1 - CH8)**")
                
                pos_options = [""] + get_dropdown_options("position")
                len_options = [float(i) for i in range(1, 21)]
                
                entries_list = []
                for r in range(4):
                    c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
                    
                    ai_suggestions = st.session_state.get("ai_suggestions", {})
                    
                    # CH A
                    ch_a_num = r*2+1
                    ch_a_key = f"CH{ch_a_num}"
                    s_a = ai_suggestions.get(ch_a_key, ai_suggestions.get(str(ch_a_num), ""))
                    idx_a = pos_options.index(s_a) if s_a in pos_options else 0
                    
                    with c1: 
                        p_a = st.selectbox(f"CH {ch_a_num}", options=pos_options, index=idx_a, key=f"p_a_{r}")
                    
                    comp_for_len = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --" else "")
                    veh_for_len = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --" else "")
                    
                    def_len_a = get_suggested_length(comp_for_len, veh_for_len, p_a) if p_a else 5.0
                    with c2: l_a = st.number_input(f"เธชเธฒเธข {ch_a_num} (เธก.)", min_value=0.0, max_value=50.0, step=0.5, value=def_len_a, key=f"l_a_{r}", label_visibility="collapsed")
                    
                    # CH B
                    ch_b_num = r*2+2
                    ch_b_key = f"CH{ch_b_num}"
                    s_b = ai_suggestions.get(ch_b_key, ai_suggestions.get(str(ch_b_num), ""))
                    idx_b = pos_options.index(s_b) if s_b in pos_options else 0
                    
                    with c3: p_b = st.selectbox(f"CH {ch_b_num}", options=pos_options, index=idx_b, key=f"p_b_{r}")
                    def_len_b = get_suggested_length(comp_for_len, veh_for_len, p_b) if p_b else 5.0
                    with c4: l_b = st.number_input(f"เธชเธฒเธข {ch_b_num} (เธก.)", min_value=0.0, max_value=50.0, step=0.5, value=def_len_b, key=f"l_b_{r}", label_visibility="collapsed")
                    
                    if p_a: entries_list.append((p_a, l_a))
                    if p_b: entries_list.append((p_b, l_b))
                
                if st.form_submit_button("๐’พ เธเธฑเธเธ—เธถเธเธเนเธญเธกเธนเธฅเธฃเธ–เธเธฑเธเธเธตเน", use_container_width=True):
                    company_name = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --" else "")
                    vehicle_type = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เน€เธฅเธทเธญเธเธเธฒเธเธฃเธฒเธขเธเธฒเธฃ --" else "")
                    
                    if company_name and vehicle_type:
                        if entries_list:
                            # Auto-add to dropdowns if new
                            if company_name not in settings_companies: add_dropdown_option("company", company_name)
                            if vehicle_type not in settings_vehicles: add_dropdown_option("vehicle", vehicle_type)
                            
                            # --- Memory Saving (Teaching) ---
                            if all_files_to_analyze:
                                # Save the CURRENT mapped positions for these files as memory
                                hashes = sorted([get_image_hash(f.getvalue()) for f in all_files_to_analyze])
                                composite_hash = hashlib.md5("".join(hashes).encode()).hexdigest()
                                
                                current_mapping = {}
                                for i, (p, l) in enumerate(entries_list):
                                    # Reconstruct CH name (rough estimation or from p_a_X keys)
                                    # For simplicity, we just save the list of used positions
                                    current_mapping[f"CH{i+1}"] = p
                                
                                save_ai_memory(composite_hash, json.dumps(current_mapping, ensure_ascii=False))
    
                            for p, l in entries_list:
                                add_data(company_name, vehicle_type, p, l, in_plate.strip())
                            
                            st.success(f"โ… เธเธฑเธเธ—เธถเธเธเนเธญเธกเธนเธฅเนเธฅเธฐเธชเธญเธ AI เน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")
                            st.balloons()
                            # Reset suggested values
                            if "ai_suggestions" in st.session_state: del st.session_state["ai_suggestions"]
                            st.rerun()
                    else:
                        st.error("โ ๏ธ เธเธฃเธธเธ“เธฒเธฃเธฐเธเธธเธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—เนเธฅเธฐเธเธฃเธฐเน€เธ เธ—เธฃเธ–")
            st.markdown("</div>", unsafe_allow_html=True)
    
        with tab2:
            st.markdown("### ๐“ เธเธฃเธญเธเนเธเธเธ•เธฒเธฃเธฒเธ Excel")
            st.info("เนเธเนเธชเธณเธซเธฃเธฑเธเธเธฃเธญเธเธเนเธญเธกเธนเธฅเธ—เธตเธฅเธฐเธซเธฅเธฒเธขเธเธฃเธดเธฉเธฑเธ—เธเธฃเนเธญเธกเธเธฑเธ")
            
            if 'batch_df_v3' not in st.session_state:
                st.session_state.batch_df_v3 = pd.DataFrame([
                    {"เธเธฃเธดเธฉเธฑเธ—": "", "เธเธฃเธฐเน€เธ เธ—เธฃเธ–": "", "เธ•เธณเนเธซเธเนเธ": "", "เธชเธฒเธข (เธก.)": 0.0} for _ in range(10)
                ])
                
            edited_df = st.data_editor(
                st.session_state.batch_df_v3,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "เธเธฃเธดเธฉเธฑเธ—": st.column_config.TextColumn("๐ข เธเธฃเธดเธฉเธฑเธ—", required=True),
                    "เธเธฃเธฐเน€เธ เธ—เธฃเธ–": st.column_config.TextColumn("๐— เธฃเธ–", required=True),
                    "เธ•เธณเนเธซเธเนเธ": st.column_config.SelectboxColumn("๐“ธ เธ•เธณเนเธซเธเนเธ", options=get_dropdown_options("position")),
                    "เธชเธฒเธข (เธก.)": st.column_config.NumberColumn("๐“ เธชเธฒเธข", min_value=0, max_value=50, step=0.5)
                },
                key="batch_editor_v3"
            )
            
            if st.button("๐€ เธเธฑเธเธ—เธถเธเธ—เธฑเนเธเธซเธกเธ”เธเธฒเธเธ•เธฒเธฃเธฒเธ", type="primary"):
                valid_rows = edited_df[edited_df["เธเธฃเธดเธฉเธฑเธ—"].str.strip() != ""]
                if not valid_rows.empty:
                    count = 0
                    for _, row in valid_rows.iterrows():
                        c, v, p, l = row["เธเธฃเธดเธฉเธฑเธ—"].strip(), row["เธเธฃเธฐเน€เธ เธ—เธฃเธ–"].strip(), row["เธ•เธณเนเธซเธเนเธ"].strip(), float(row["เธชเธฒเธข (เธก.)"])
                        if c and v and p:
                            add_data(c, v, p, l)
                            count += 1
                    st.success(f"เธเธฑเธเธ—เธถเธเธชเธณเน€เธฃเนเธ {count} เธฃเธฒเธขเธเธฒเธฃ")
                    st.rerun()
    
    elif choice == "เธ”เธนเธเนเธญเธกเธนเธฅเนเธฅเธฐเธเนเธเธซเธฒ":
        st.subheader("๐” เธ•เธฃเธงเธเธชเธญเธเธเนเธญเธกเธนเธฅเนเธขเธเธ•เธฒเธกเธเธฃเธดเธฉเธฑเธ—")
        
        df = get_all_data()
        if df.empty:
            st.info("เธขเธฑเธเนเธกเนเธกเธตเธเนเธญเธกเธนเธฅเนเธเธฃเธฐเธเธ")
        else:
            # Search and Hierarchy logic
            all_comps = sorted(df['company_name'].unique().tolist())
            search = st.selectbox("๐” เธเนเธเธซเธฒเธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—", ["-- เธ—เธฑเนเธเธซเธกเธ” --"] + all_comps)
            
            display_comps = all_comps if search == "-- เธ—เธฑเนเธเธซเธกเธ” --" else [search]
            
            for comp in display_comps:
                with st.expander(f"๐ข {comp}", expanded=(len(display_comps) == 1)):
                    comp_df = df[df['company_name'] == comp]
                    
                    # Delete Company Button
                    c_head1, c_head2 = st.columns([5, 1])
                    with c_head2:
                        if st.button("๐—‘๏ธ เธฅเธเธ—เธฑเนเธเธเธฃเธดเธฉเธฑเธ—", key=f"del_comp_{comp}"):
                            delete_company_data(comp)
                            st.rerun()
                    
                    # Show Vehicle Cards
                    v_types = sorted(comp_df['vehicle_type'].unique().tolist())
                    for i in range(0, len(v_types), 2):
                        v_cols = st.columns(2)
                        for j in range(2):
                            if i+j < len(v_types):
                                vt = v_types[i+j]
                                vt_df = comp_df[comp_df['vehicle_type'] == vt]
                                with v_cols[j]:
                                    st.markdown(f"<div class='company-card'><h4>๐— {vt}</h4><p>เธเธฅเนเธญเธ {len(vt_df)} เธ•เธฑเธง</p>", unsafe_allow_html=True)
                                    vt_table = vt_df[['installation_position', 'cable_length_m']].rename(columns={'installation_position':'เธ•เธณเนเธซเธเนเธ', 'cable_length_m':'เธชเธฒเธข (เธก.)'})
                                    st.table(vt_table)
                                    if st.button(f"๐—‘๏ธ เธฅเธ {vt}", key=f"del_vt_{comp}_{vt}"):
                                        delete_vehicle_data(comp, vt)
                                        st.rerun()
                                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Quick add for this company
                    with st.popover(f"โ• เน€เธเธดเนเธกเธฃเธ–เนเธซเธกเนเนเธซเน {comp}"):
                        with st.form(f"quick_add_{comp}"):
                            qv = st.text_input("เธเธฃเธฐเน€เธ เธ—เธฃเธ–")
                            qp_opts = [""] + get_dropdown_options("position")
                            q_entries = []
                            for r in range(4):
                                qc1, qc2, qc3, qc4 = st.columns([2, 1, 2, 1])
                                with qc1: p1 = st.selectbox(f"CH {r*2+1}", options=qp_opts, key=f"q1_{comp}_{r}")
                                q_len1 = get_suggested_length(comp, qv, p1) if p1 else 5.0
                                with qc2: l1 = st.number_input(f"เธก. {r*2+1}", 0.0, 50.0, value=q_len1, key=f"ql1_{comp}_{r}", label_visibility="collapsed")
                                with qc3: p2 = st.selectbox(f"CH {r*2+2}", options=qp_opts, key=f"q2_{comp}_{r}")
                                q_len2 = get_suggested_length(comp, qv, p2) if p2 else 5.0
                                with qc4: l2 = st.number_input(f"เธก. {r*2+2}", 0.0, 50.0, value=q_len2, key=f"ql2_{comp}_{r}", label_visibility="collapsed")
                                if p1: q_entries.append((p1, l1))
                                if p2: q_entries.append((p2, l2))
                            if st.form_submit_button("เธเธฑเธเธ—เธถเธ"):
                                if qv and q_entries:
                                    for p, l in q_entries: add_data(comp, qv, p, l)
                                    st.success("เน€เธเธดเนเธกเธเนเธญเธกเธนเธฅเธชเธณเน€เธฃเนเธ!")
                                    st.rerun()
                                else: st.error("เธเธฃเธธเธ“เธฒเธฃเธฐเธเธธเธเนเธญเธกเธนเธฅเนเธซเนเธเธฃเธ")
    elif choice == "เธ•เธฑเนเธเธเนเธฒเธ•เธฑเธงเน€เธฅเธทเธญเธ Dropdown":
        st.subheader("โ๏ธ เธเธฑเธ”เธเธฒเธฃเธฃเธฒเธขเธเธฒเธฃเธ•เธฑเธงเน€เธฅเธทเธญเธ Dropdown")
        
        col_c, col_v, col_p = st.columns(3)
        
        with col_c:
            st.markdown("### ๐ข เธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—")
            comp_opts = get_dropdown_options("company")
            
            with st.form("add_comp_opt", clear_on_submit=True):
                new_c = st.text_input("เน€เธเธดเนเธกเธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—เนเธซเธกเน")
                if st.form_submit_button("เน€เธเธดเนเธกเธเธฃเธดเธฉเธฑเธ—"):
                    if new_c.strip():
                        add_dropdown_option("company", new_c.strip())
                        st.rerun()
            
            for c in comp_opts:
                c1, c2 = st.columns([4, 1])
                c1.write(c)
                if c2.button("โ", key=f"del_c_{c}", help=f"เธฅเธ {c}"):
                    delete_dropdown_option("company", c)
                    st.rerun()
    
        with col_v:
            st.markdown("### ๐ เธเธฃเธฐเน€เธ เธ—เธฃเธ–")
            veh_opts = get_dropdown_options("vehicle")
            
            with st.form("add_veh_opt", clear_on_submit=True):
                new_v = st.text_input("เน€เธเธดเนเธกเธเธฃเธฐเน€เธ เธ—เธฃเธ–เนเธซเธกเน")
                if st.form_submit_button("เน€เธเธดเนเธกเธเธฃเธฐเน€เธ เธ—เธฃเธ–"):
                    if new_v.strip():
                        add_dropdown_option("vehicle", new_v.strip())
                        st.rerun()
            
            for v in veh_opts:
                c1, c2 = st.columns([4, 1])
                c1.write(v)
                if c2.button("โ", key=f"del_v_{v}", help=f"เธฅเธ {v}"):
                    delete_dropdown_option("vehicle", v)
                    st.rerun()
                    
        with col_p:
            st.markdown("### ๐“ธ เธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธ")
            pos_opts = get_dropdown_options("position")
            
            with st.form("add_pos_opt", clear_on_submit=True):
                new_p = st.text_input("เน€เธเธดเนเธกเธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธเนเธซเธกเน")
                if st.form_submit_button("เน€เธเธดเนเธกเธ•เธณเนเธซเธเนเธ"):
                    if new_p.strip():
                        add_dropdown_option("position", new_p.strip())
                        st.rerun()
                        
            for p in pos_opts:
                c1, c2 = st.columns([4, 1])
                c1.write(p)
                if c2.button("โ", key=f"del_p_{p}", help=f"เธฅเธ {p}"):
                    delete_dropdown_option("position", p)
                    st.rerun()
    
    elif choice == "เธเธณเน€เธเนเธฒเธเนเธญเธกเธนเธฅเธเธฒเธ Excel":
        st.subheader("๐“ฅ เธเธณเน€เธเนเธฒเธเนเธญเธกเธนเธฅเธเธฒเธเนเธเธฅเน Excel")
        st.markdown("""
        **เธเธณเนเธเธฐเธเธณ:** เนเธเธฅเน Excel เธชเธฒเธกเธฒเธฃเธ–เธกเธตเธเธญเธฅเธฑเธกเธเนเนเธ”เธเนเนเธ”เนเธเธฒเธเธฃเธฒเธขเธเธฒเธฃเธ•เนเธญเนเธเธเธตเน (เธกเธตเธญเธขเนเธฒเธเธเนเธญเธข 1 เธญเธขเนเธฒเธเธเนเน€เธเธดเนเธกเนเธ”เน):
        `เธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—`, `เธเธฃเธฐเน€เธ เธ—เธฃเธ–`, `เธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธ`, `เธเธงเธฒเธกเธขเธฒเธงเธชเธฒเธข (เน€เธกเธ•เธฃ)`
        """)
        
        # --- Generate Template Excel on the fly ---
        template_df = pd.DataFrame(columns=['เธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—', 'เธเธฃเธฐเน€เธ เธ—เธฃเธ–', 'เธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธ', 'เธเธงเธฒเธกเธขเธฒเธงเธชเธฒเธข (เน€เธกเธ•เธฃ)'])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False, sheet_name='Template')
        excel_data = output.getvalue()
        
        st.download_button(
            label="๐“ เธ”เธฒเธงเธเนเนเธซเธฅเธ”เนเธเธฅเน Excel เธชเธณเธซเธฃเธฑเธเธเธฃเธญเธเธเนเธญเธกเธนเธฅ (Template)",
            data=excel_data,
            file_name="cctv_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="เธ”เธฒเธงเธเนเนเธซเธฅเธ”เนเธเธฅเน Excel เธ•เนเธเนเธเธเนเธเธเธฃเธญเธเธเนเธญเธกเธนเธฅเน€เธเธทเนเธญเธเธณเน€เธเนเธฒเธชเธนเนเธฃเธฐเธเธ"
        )
        st.markdown("---")
        
        uploaded_file = st.file_uploader("เน€เธฅเธทเธญเธเนเธเธฅเน Excel (.xlsx)", type=["xlsx"])
        
        if uploaded_file is not None:
            try:
                # Read Excel
                df_excel = pd.read_excel(uploaded_file)
                st.write("เธ•เธฑเธงเธญเธขเนเธฒเธเธเนเธญเธกเธนเธฅเธเธฒเธเนเธเธฅเน:")
                st.dataframe(df_excel.head(), use_container_width=True)
                
                # Mapping columns (allowing for minor variations in naming)
                col_map = {
                    'เธเธทเนเธญเธเธฃเธดเธฉเธฑเธ—': 'company_name',
                    'เธ—เธฐเน€เธเธตเธขเธเธฃเธ–': 'license_plate',
                    'เธเธฃเธฐเน€เธ เธ—เธฃเธ–': 'vehicle_type',
                    'เธ•เธณเนเธซเธเนเธเธ•เธดเธ”เธ•เธฑเนเธ': 'installation_position',
                    'เธเธงเธฒเธกเธขเธฒเธงเธชเธฒเธข (เน€เธกเธ•เธฃ)': 'cable_length_m'
                }
                
                # Find matching columns
                available_cols = {thai: db for thai, db in col_map.items() if thai in df_excel.columns}
                
                if available_cols:
                    if st.button("เธขเธทเธเธขเธฑเธเธเธฒเธฃเธเธณเน€เธเนเธฒเธเนเธญเธกเธนเธฅ"):
                        conn = sqlite3.connect(DB_FILE)
                        
                        # Create temporary dataframe for matching columns
                        imported_df = pd.DataFrame()
                        for thai_name, db_col in available_cols.items():
                            imported_df[db_col] = df_excel[thai_name]
                        
                        # Add missing columns with default values
                        if 'company_name' not in imported_df.columns: imported_df['company_name'] = "-"
                        if 'vehicle_type' not in imported_df.columns: imported_df['vehicle_type'] = "-"
                        if 'installation_position' not in imported_df.columns: imported_df['installation_position'] = "-"
                        if 'cable_length_m' not in imported_df.columns: imported_df['cable_length_m'] = 0.0
                        
                        # Fill NaN values in existing data
                        imported_df['company_name'] = imported_df['company_name'].fillna("-")
                        imported_df['vehicle_type'] = imported_df['vehicle_type'].fillna("-")
                        imported_df['installation_position'] = imported_df['installation_position'].fillna("-")
                        imported_df['cable_length_m'] = imported_df['cable_length_m'].fillna(0.0)
                        
                        # Reorder columns to match DB
                        imported_df = imported_df[['company_name', 'vehicle_type', 'installation_position', 'cable_length_m']]
                        
                        # Save to DB
                        imported_df.to_sql('camera_installations', conn, if_exists='append', index=False)
                        conn.close()
                        st.success(f"โ… เธเธณเน€เธเนเธฒเธเนเธญเธกเธนเธฅ {len(imported_df)} เธฃเธฒเธขเธเธฒเธฃเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!")
                else:
                    st.error(f"โ ๏ธ เนเธกเนเธเธเธเธญเธฅเธฑเธกเธเนเธ—เธตเนเธฃเธญเธเธฃเธฑเธ")
                    st.info(f"เธเธฃเธธเธ“เธฒเธ•เธฑเนเธเธเธทเนเธญเธซเธฑเธงเธ•เธฒเธฃเธฒเธเนเธ Excel เธญเธขเนเธฒเธเธเนเธญเธข 1 เธญเธขเนเธฒเธเธเธฒเธ: {', '.join(col_map.keys())}")
                    
            except Exception as e:
                st.error(f"โ เน€เธเธดเธ”เธเนเธญเธเธดเธ”เธเธฅเธฒเธ”: {e}")
    
    # Footer
    st.sidebar.markdown("---")
