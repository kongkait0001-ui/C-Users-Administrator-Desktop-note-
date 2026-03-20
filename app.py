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
            ("company", "บริษัท ตัวอย่าง จำกัด"),
            ("vehicle", "รถกระบะ"), ("vehicle", "รถบัส"), ("vehicle", "รถบรรทุก"), ("vehicle", "รถตู้"),
            ("position", "ส่องหน้าคนขับ"), ("position", "ส่องห้องโดยสาร"), ("position", "ส่องถนน"),
            ("position", "บนกระจกซ้าย"), ("position", "บนกระจกขวา"), ("position", "ในตู้สินค้า"), ("position", "ส่องหลังรถ")
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
    if re.match(r'^[1][0-9]-\d{4}$', plate): return "รถโดยสารสาธารณะ (บัส)"
    if re.match(r'^[3][0-9]-\d{4}$', plate): return "รถโดยสารไม่ประจำทาง (30-)"
    if re.match(r'^[7][0-9]-\d{4}$', plate): return "รถบรรทุกสาธารณะ (หัวลาก/พ่วง)"
    if re.match(r'^[89][0-9]-\d{4}$', plate): return "รถบรรทุกส่วนบุคคล (80-)"
    if re.match(r'^\d?[นผฒ][ก-ฮ]\d{1,4}$', plate): return "รถกระบะ (ป้ายเขียว)"
    if re.match(r'^\d?[นม][ก-ฮ]\d{1,4}$', plate): return "รถตู้/รถยนต์นั่งส่วนบุคคล (>7 ที่นั่ง)"
    if re.match(r'^\d?[ก-ฮ]{2}\d{1,4}$', plate): return "รถยนต์นั่งส่วนบุคคล (เก๋ง/SUV)"
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
        Example: {{"CH1": "ส่องหน้าคนขับ", "CH2": "ส่องหลังรถ"}}
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
st.set_page_config(page_title="Abdul", page_icon="abdul_logo_nobg.png", layout="wide")

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
            st.info("⚠️ ไม่พบไฟล์โลโก้ (Logo not found)")
            
        st.markdown("<h1 style='text-align: center; color: #1e293b;'>Abdul</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #475569;'>AI CCTV Data Management System</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b;'>ระบบจัดการข้อมูลการติดตั้งกล้อง AI CCTV และความยาวสายเคเบิล</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        btn_c1, btn_c2, btn_c3 = st.columns([1, 2, 1])
        with btn_c2:
            if st.button("🚀 เข้าสู่ระบบ (Start Program)"):
                st.session_state.started = True
                st.rerun()
    st.stop()

col1, col2 = st.columns([1, 10])
with col1:
    st.image("abdul_logo_nobg.png", width=70)
with col2:
    st.title("Abdul - AI CCTV System")

# Sidebar navigation
st.sidebar.markdown("### 🔑 ตั้งค่า AI")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="ขอรับ API Key ฟรีได้ที่เว็บ Google AI Studio")

menu = ["เพิ่มข้อมูลใหม่", "ดูข้อมูลและค้นหา", "ตั้งค่าตัวเลือก Dropdown", "นำเข้าข้อมูลจาก Excel"]
choice = st.sidebar.selectbox("เมนูการใช้งาน", menu)

if choice == "เพิ่มข้อมูลใหม่":
    st.subheader("📝 บันทึกข้อมูลการติดตั้ง")
    
    tab1, tab2 = st.tabs(["✨ บันทึกทีละรายการ (แนะนำ)", "📊 บันทึกแบบตาราง (หลายบริษัท)"])
    
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
        st.markdown("#### 🦅 ค้นหาตำแหน่งด้วย AI (Vision Assistant)")
        if not gemini_api_key:
            st.warning("⚠️ กรุณาใส่ Gemini API Key ที่แถบเมนูข้างเพื่อเปิดใช้ระบบวิเคราะห์ภาพ")
        
        # Add paste support initialization
        if "pasted_images" not in st.session_state:
            st.session_state.pasted_images = []

        col_up1, col_up2 = st.columns([3, 1])
        with col_up1:
            uploaded_files = st.file_uploader("📸 ลากรูปภาพ (หรือรูปกริด) มาวางเพื่อวิเคราะห์ตำแหน่ง", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        with col_up2:
            st.write("") # spacing
            st.write("") # spacing
            pasted_img = paste_image_button("📋 วางจากคลิปบอร์ด", key="paste_btn", use_container_width=True)
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
                if st.button("🗑️ ล้างภาพที่วาง", key="clear_pasted"):
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
            st.image(all_files_to_analyze, width=150, caption=[f"ภาพที่ {i+1}" for i in range(len(all_files_to_analyze))])
            
            if st.button("🔍 เริ่มวิเคราะห์ภาพทั้งหมดด้วย AI"):
                with st.spinner("AI กำลังวิเคราะห์ทุกมุมมอง..."):
                    all_pos_opts = get_dropdown_options("position")
                    ai_results = analyze_camera_vision(uploaded_files, gemini_api_key, all_pos_opts)
                    
                    if "error" in ai_results:
                        st.error(ai_results["error"])
                    else:
                        st.session_state["ai_suggestions"] = ai_results
                        st.success(f"✅ วิเคราะห์เสร็จสิ้น! พบข้อมูลตำแหน่งใน {len(ai_results)} ช่องสัญญาณ")
                        
                        # Show result summaries with memory info
                        cols = st.columns(4)
                        all_remembered = True
                        for idx, (ch, pos) in enumerate(ai_results.items()):
                            with cols[idx % 4]:
                                st.info(f"**{ch}:** {pos}")
                        
                        st.divider()
                        st.info("💡 **คำแนะนำ:** ตรวจสอบข้อมูลที่ฟอร์มด้านล่าง หาก AI ทายผิด ให้แก้ไขในฟอร์มแล้วกดบันทึกข้อมูลรถ AI จะจำความถูกต้องไว้สำหรับภาพชุดนี้ครับ")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='company-card'>", unsafe_allow_html=True)
        with st.form("add_form_final", clear_on_submit=False): # Don't clear to keep company name
            col1, col2 = st.columns(2)
            with col1:
                selected_comp = st.selectbox("🏢 เลือกบริษัท", options=["-- เลือกจากรายการ --"] + all_companies)
                new_comp = st.text_input("➕ หรือพิมพ์ชื่อบริษัทใหม่")
                in_plate = st.text_input("🔢 ป้ายทะเบียนรถ", placeholder="เช่น 70-1234 หรือ 1กข-5555")
            with col2:
                # Prediction + Memory logic
                prediction = predict_vehicle_type(in_plate)
                history_veh = get_last_veh_by_plate(in_plate)
                
                if history_veh:
                    st.success(f"📌 ความจำระบบ: ทะเบียนนี้คือ **{history_veh}**")
                    if st.button(f"✨ ใช้ {history_veh}"):
                        st.session_state["suggested_veh"] = history_veh
                elif prediction:
                    st.info(f"💡 คำแนะนำ: ระบบวิเคราะห์ว่าเป็น **{prediction}**")
                
                # Use value from session state if suggested
                val_veh = st.session_state.get("suggested_veh", "")
                
                settings_veh = get_dropdown_options("vehicle")
                existing_v = sorted(df_existing['vehicle_type'].unique().tolist()) if not df_existing.empty else []
                all_v_opts = sorted(list(set(settings_veh + existing_v)))
                
                selected_veh = st.selectbox("🚗 เลือกประเภทรถ", options=["-- เลือกจากรายการ --"] + all_v_opts)
                new_veh = st.text_input("➕ หรือพิมพ์ประเภทรถใหม่ (ถ้าไม่มีในรายการ)", value=val_veh)
                
                # Reset suggestion after use (optional, but keep it simple)
                if val_veh: 
                    st.session_state["suggested_veh"] = "" # Clear for next entry
                
            st.divider()
            st.markdown("**📸 ระบุตำแหน่งติดตั้ง (CH1 - CH8)**")
            
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
                
                comp_for_len = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เลือกจากรายการ --" else "")
                veh_for_len = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เลือกจากรายการ --" else "")
                
                def_len_a = get_suggested_length(comp_for_len, veh_for_len, p_a) if p_a else 5.0
                with c2: l_a = st.number_input(f"สาย {ch_a_num} (ม.)", min_value=0.0, max_value=50.0, step=0.5, value=def_len_a, key=f"l_a_{r}", label_visibility="collapsed")
                
                # CH B
                ch_b_num = r*2+2
                ch_b_key = f"CH{ch_b_num}"
                s_b = ai_suggestions.get(ch_b_key, ai_suggestions.get(str(ch_b_num), ""))
                idx_b = pos_options.index(s_b) if s_b in pos_options else 0
                
                with c3: p_b = st.selectbox(f"CH {ch_b_num}", options=pos_options, index=idx_b, key=f"p_b_{r}")
                def_len_b = get_suggested_length(comp_for_len, veh_for_len, p_b) if p_b else 5.0
                with c4: l_b = st.number_input(f"สาย {ch_b_num} (ม.)", min_value=0.0, max_value=50.0, step=0.5, value=def_len_b, key=f"l_b_{r}", label_visibility="collapsed")
                
                if p_a: entries_list.append((p_a, l_a))
                if p_b: entries_list.append((p_b, l_b))
            
            if st.form_submit_button("💾 บันทึกข้อมูลรถคันนี้", use_container_width=True):
                company_name = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เลือกจากรายการ --" else "")
                vehicle_type = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เลือกจากรายการ --" else "")
                
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
                        
                        st.success(f"✅ บันทึกข้อมูลและสอน AI เรียบร้อยแล้ว!")
                        st.balloons()
                        # Reset suggested values
                        if "ai_suggestions" in st.session_state: del st.session_state["ai_suggestions"]
                        st.rerun()
                else:
                    st.error("⚠️ กรุณาระบุชื่อบริษัทและประเภทรถ")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("### 📋 กรอกแบบตาราง Excel")
        st.info("ใช้สำหรับกรอกข้อมูลทีละหลายบริษัทพร้อมกัน")
        
        if 'batch_df_v3' not in st.session_state:
            st.session_state.batch_df_v3 = pd.DataFrame([
                {"บริษัท": "", "ประเภทรถ": "", "ตำแหน่ง": "", "สาย (ม.)": 0.0} for _ in range(10)
            ])
            
        edited_df = st.data_editor(
            st.session_state.batch_df_v3,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "บริษัท": st.column_config.TextColumn("🏢 บริษัท", required=True),
                "ประเภทรถ": st.column_config.TextColumn("🚗 รถ", required=True),
                "ตำแหน่ง": st.column_config.SelectboxColumn("📸 ตำแหน่ง", options=get_dropdown_options("position")),
                "สาย (ม.)": st.column_config.NumberColumn("📏 สาย", min_value=0, max_value=50, step=0.5)
            },
            key="batch_editor_v3"
        )
        
        if st.button("🚀 บันทึกทั้งหมดจากตาราง", type="primary"):
            valid_rows = edited_df[edited_df["บริษัท"].str.strip() != ""]
            if not valid_rows.empty:
                count = 0
                for _, row in valid_rows.iterrows():
                    c, v, p, l = row["บริษัท"].strip(), row["ประเภทรถ"].strip(), row["ตำแหน่ง"].strip(), float(row["สาย (ม.)"])
                    if c and v and p:
                        add_data(c, v, p, l)
                        count += 1
                st.success(f"บันทึกสำเร็จ {count} รายการ")
                st.rerun()

elif choice == "ดูข้อมูลและค้นหา":
    st.subheader("🔍 ตรวจสอบข้อมูลแยกตามบริษัท")
    
    df = get_all_data()
    if df.empty:
        st.info("ยังไม่มีข้อมูลในระบบ")
    else:
        # Search and Hierarchy logic
        all_comps = sorted(df['company_name'].unique().tolist())
        search = st.selectbox("🔎 ค้นหาชื่อบริษัท", ["-- ทั้งหมด --"] + all_comps)
        
        display_comps = all_comps if search == "-- ทั้งหมด --" else [search]
        
        for comp in display_comps:
            with st.expander(f"🏢 {comp}", expanded=(len(display_comps) == 1)):
                comp_df = df[df['company_name'] == comp]
                
                # Delete Company Button
                c_head1, c_head2 = st.columns([5, 1])
                with c_head2:
                    if st.button("🗑️ ลบทั้งบริษัท", key=f"del_comp_{comp}"):
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
                                st.markdown(f"<div class='company-card'><h4>🚗 {vt}</h4><p>กล้อง {len(vt_df)} ตัว</p>", unsafe_allow_html=True)
                                vt_table = vt_df[['installation_position', 'cable_length_m']].rename(columns={'installation_position':'ตำแหน่ง', 'cable_length_m':'สาย (ม.)'})
                                st.table(vt_table)
                                if st.button(f"🗑️ ลบ {vt}", key=f"del_vt_{comp}_{vt}"):
                                    delete_vehicle_data(comp, vt)
                                    st.rerun()
                                st.markdown("</div>", unsafe_allow_html=True)
                
                # Quick add for this company
                with st.popover(f"➕ เพิ่มรถใหม่ให้ {comp}"):
                    with st.form(f"quick_add_{comp}"):
                        qv = st.text_input("ประเภทรถ")
                        qp_opts = [""] + get_dropdown_options("position")
                        q_entries = []
                        for r in range(4):
                            qc1, qc2, qc3, qc4 = st.columns([2, 1, 2, 1])
                            with qc1: p1 = st.selectbox(f"CH {r*2+1}", options=qp_opts, key=f"q1_{comp}_{r}")
                            q_len1 = get_suggested_length(comp, qv, p1) if p1 else 5.0
                            with qc2: l1 = st.number_input(f"ม. {r*2+1}", 0.0, 50.0, value=q_len1, key=f"ql1_{comp}_{r}", label_visibility="collapsed")
                            with qc3: p2 = st.selectbox(f"CH {r*2+2}", options=qp_opts, key=f"q2_{comp}_{r}")
                            q_len2 = get_suggested_length(comp, qv, p2) if p2 else 5.0
                            with qc4: l2 = st.number_input(f"ม. {r*2+2}", 0.0, 50.0, value=q_len2, key=f"ql2_{comp}_{r}", label_visibility="collapsed")
                            if p1: q_entries.append((p1, l1))
                            if p2: q_entries.append((p2, l2))
                        if st.form_submit_button("บันทึก"):
                            if qv and q_entries:
                                for p, l in q_entries: add_data(comp, qv, p, l)
                                st.success("เพิ่มข้อมูลสำเร็จ!")
                                st.rerun()
                            else: st.error("กรุณาระบุข้อมูลให้ครบ")
elif choice == "ตั้งค่าตัวเลือก Dropdown":
    st.subheader("⚙️ จัดการรายการตัวเลือก Dropdown")
    
    col_c, col_v, col_p = st.columns(3)
    
    with col_c:
        st.markdown("### 🏢 ชื่อบริษัท")
        comp_opts = get_dropdown_options("company")
        
        with st.form("add_comp_opt", clear_on_submit=True):
            new_c = st.text_input("เพิ่มชื่อบริษัทใหม่")
            if st.form_submit_button("เพิ่มบริษัท"):
                if new_c.strip():
                    add_dropdown_option("company", new_c.strip())
                    st.rerun()
        
        for c in comp_opts:
            c1, c2 = st.columns([4, 1])
            c1.write(c)
            if c2.button("❌", key=f"del_c_{c}", help=f"ลบ {c}"):
                delete_dropdown_option("company", c)
                st.rerun()

    with col_v:
        st.markdown("### 🚙 ประเภทรถ")
        veh_opts = get_dropdown_options("vehicle")
        
        with st.form("add_veh_opt", clear_on_submit=True):
            new_v = st.text_input("เพิ่มประเภทรถใหม่")
            if st.form_submit_button("เพิ่มประเภทรถ"):
                if new_v.strip():
                    add_dropdown_option("vehicle", new_v.strip())
                    st.rerun()
        
        for v in veh_opts:
            c1, c2 = st.columns([4, 1])
            c1.write(v)
            if c2.button("❌", key=f"del_v_{v}", help=f"ลบ {v}"):
                delete_dropdown_option("vehicle", v)
                st.rerun()
                
    with col_p:
        st.markdown("### 📸 ตำแหน่งติดตั้ง")
        pos_opts = get_dropdown_options("position")
        
        with st.form("add_pos_opt", clear_on_submit=True):
            new_p = st.text_input("เพิ่มตำแหน่งติดตั้งใหม่")
            if st.form_submit_button("เพิ่มตำแหน่ง"):
                if new_p.strip():
                    add_dropdown_option("position", new_p.strip())
                    st.rerun()
                    
        for p in pos_opts:
            c1, c2 = st.columns([4, 1])
            c1.write(p)
            if c2.button("❌", key=f"del_p_{p}", help=f"ลบ {p}"):
                delete_dropdown_option("position", p)
                st.rerun()

elif choice == "นำเข้าข้อมูลจาก Excel":
    st.subheader("📥 นำเข้าข้อมูลจากไฟล์ Excel")
    st.markdown("""
    **คำแนะนำ:** ไฟล์ Excel สามารถมีคอลัมน์ใดก็ได้จากรายการต่อไปนี้ (มีอย่างน้อย 1 อย่างก็เพิ่มได้):
    `ชื่อบริษัท`, `ประเภทรถ`, `ตำแหน่งติดตั้ง`, `ความยาวสาย (เมตร)`
    """)
    
    # --- Generate Template Excel on the fly ---
    template_df = pd.DataFrame(columns=['ชื่อบริษัท', 'ประเภทรถ', 'ตำแหน่งติดตั้ง', 'ความยาวสาย (เมตร)'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Template')
    excel_data = output.getvalue()
    
    st.download_button(
        label="📄 ดาวน์โหลดไฟล์ Excel สำหรับกรอกข้อมูล (Template)",
        data=excel_data,
        file_name="cctv_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="ดาวน์โหลดไฟล์ Excel ต้นแบบไปกรอกข้อมูลเพื่อนำเข้าสู่ระบบ"
    )
    st.markdown("---")
    
    uploaded_file = st.file_uploader("เลือกไฟล์ Excel (.xlsx)", type=["xlsx"])
    
    if uploaded_file is not None:
        try:
            # Read Excel
            df_excel = pd.read_excel(uploaded_file)
            st.write("ตัวอย่างข้อมูลจากไฟล์:")
            st.dataframe(df_excel.head(), use_container_width=True)
            
            # Mapping columns (allowing for minor variations in naming)
            col_map = {
                'ชื่อบริษัท': 'company_name',
                'ทะเบียนรถ': 'license_plate',
                'ประเภทรถ': 'vehicle_type',
                'ตำแหน่งติดตั้ง': 'installation_position',
                'ความยาวสาย (เมตร)': 'cable_length_m'
            }
            
            # Find matching columns
            available_cols = {thai: db for thai, db in col_map.items() if thai in df_excel.columns}
            
            if available_cols:
                if st.button("ยืนยันการนำเข้าข้อมูล"):
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
                    st.success(f"✅ นำเข้าข้อมูล {len(imported_df)} รายการเรียบร้อยแล้ว!")
            else:
                st.error(f"⚠️ ไม่พบคอลัมน์ที่รองรับ")
                st.info(f"กรุณาตั้งชื่อหัวตารางใน Excel อย่างน้อย 1 อย่างจาก: {', '.join(col_map.keys())}")
                
        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("พัฒนาด้วย Python & Streamlit")
