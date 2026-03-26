import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import base64
import re
import json
import hashlib
from PIL import Image
import google.generativeai as genai
from streamlit_paste_button import paste_image_button

# Database Setup
DB_FILE = "cctv_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Ensure tables match existing schema
    c.execute('''
        CREATE TABLE IF NOT EXISTS camera_installations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            installation_position TEXT NOT NULL,
            cable_length_m REAL NOT NULL,
            license_plate TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dropdown_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            option_value TEXT NOT NULL,
            UNIQUE(category, option_value)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_memory (
            image_hash TEXT PRIMARY KEY,
            position_mapping TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Pre-populate some defaults if empty
    c.execute("SELECT COUNT(*) FROM dropdown_options")
    if c.fetchone()[0] == 0:
        defaults = [
            ("company", "บริษัท ตัวอย่าง จำกัด"),
            ("vehicle", "รถกระบะ"), ("vehicle", "รถบัส"), ("vehicle", "รถบรรทุก"), ("vehicle", "รถตู้"),
            ("position", "ส่องหน้าคนขับ"), ("position", "ส่องห้องโดยสาร"), ("position", "ส่องถนน"),
            ("position", "บนกระจกซ้าย"), ("position", "บนกระจกขวา"), ("position", "ในตู้สินค้า"), ("position", "ส่องหลังรถ")
        ]
        c.executemany("INSERT OR IGNORE INTO dropdown_options (category, option_value) VALUES (?, ?)", defaults)
    
    conn.commit()
    conn.close()

def get_image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

def get_ai_memory(image_hash):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT position_mapping FROM ai_memory WHERE image_hash = ?", (image_hash,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_ai_memory(image_hash, mapping):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ai_memory (image_hash, position_mapping) VALUES (?, ?)", (image_hash, mapping))
    conn.commit()
    conn.close()

def get_dropdown_options(category):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT option_value FROM dropdown_options WHERE category = ? ORDER BY option_value", (category,))
        options = [row[0] for row in c.fetchall()]
        conn.close()
        return options
    except Exception as e:
        # Fallback if table name or columns differ slightly (legacy support)
        return []

def add_dropdown_option(category, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO dropdown_options (category, option_value) VALUES (?, ?)", (category, value))
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
    # Upgrade for camera_installations (license_plate)
    try:
        c.execute("SELECT license_plate FROM camera_installations LIMIT 1")
    except:
        c.execute("ALTER TABLE camera_installations ADD COLUMN license_plate TEXT")
        conn.commit()
    
    # Upgrade for ai_memory (position_mapping)
    try:
        c.execute("SELECT position_mapping FROM ai_memory LIMIT 1")
    except:
        # Check if 'position' column exists from old versions
        c.execute("PRAGMA table_info(ai_memory)")
        cols = [row[1] for row in c.fetchall()]
        if 'position' in cols:
            c.execute("ALTER TABLE ai_memory RENAME COLUMN position TO position_mapping")
        else:
            c.execute("ALTER TABLE ai_memory ADD COLUMN position_mapping TEXT")
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
    if re.match(r'^\d?[นผฎ][ก-ฮ]\d{1,4}$', plate): return "รถกระบะ (ป้ายเขียว)"
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
    try:
        # Calculate composite hash for memory
        hashes = sorted([get_image_hash(f.getvalue()) for f in files])
        composite_hash = hashlib.md5("".join(hashes).encode()).hexdigest()
        
        # Check memory
        remembered_data = get_ai_memory(composite_hash)
        if remembered_data:
            try:
                return json.loads(remembered_data)
            except:
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
                save_ai_memory(composite_hash, json.dumps(result_map, ensure_ascii=False))
                return result_map
            except Exception as inner_e:
                last_err = str(inner_e)
                continue
        
        return {"error": f"AI Error: {last_err}"}
    except Exception as e:
        return {"error": f"AI Config Error: {str(e)}"}

# --- UI Setup ---
st.set_page_config(page_title="Abdul - AI CCTV Data Management", page_icon="📝", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #007bff; color: white; font-weight: 600; border: none; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: #0056b3; transform: translateY(-1px); }
    .stTextInput>div>div>input, .stSelectbox>div>div>div { border-radius: 8px !important; }
    .company-card { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    @media (max-width: 600px) { h1 { font-size: 1.8em !important; } .block-container { padding: 1rem !important; } }
    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-15px); } 100% { transform: translateY(0px); } }
    .floating-img { animation: float 4s ease-in-out infinite; display: block; margin: 0 auto; max-width: 250px; width: 100%; filter: drop-shadow(0 10px 15px rgba(0,0,0,0.1)); }
    </style>
    """, unsafe_allow_html=True)

if 'started' not in st.session_state:
    st.session_state.started = False

def start_app():
    st.session_state.started = True

# App Content
if not st.session_state.started:
    # Landing / Splash Screen
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        logo_path = "abdul_logo_nobg.png"
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode()
            st.markdown(f'<img src="data:image/png;base64,{b64_string}" class="floating-img">', unsafe_allow_html=True)
        else:
            st.info("⚠️ ไม่พบไฟล์โลโก้")
            
        st.markdown("<h1 style='text-align: center; color: #1e293b;'>Abdul</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #475569;'>AI CCTV Data Management System</h3>", unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        if st.button("🚀 เข้าสู่โปรแกรม (Start)", key="start_main"):
            start_app()
            st.rerun()

else:
    # Main App UI
    st.sidebar.markdown("### 🔑 ตั้งค่า AI")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="ขอรับ API Key ฟรีได้ที่เว็บ Google AI Studio")
    
    menu = ["➕ เพิ่มข้อมูลใหม่", "🔍 ดูข้อมูลและค้นหา", "⚙️ ตัวเลือก Dropdown", "📥 นำเข้าจาก Excel"]
    choice = st.sidebar.selectbox("เมนูการใช้งาน", menu)
    
    if choice == "➕ เพิ่มข้อมูลใหม่":
        st.subheader("📝 บันทึกข้อมูลการติดตั้ง")
        tab1, tab2 = st.tabs(["✨ บันทึกทีละรายการ", "📊 บันทึกแบบตาราง"])
        
        df_existing = get_all_data()
        settings_companies = get_dropdown_options("company")
        existing_companies_data = sorted(df_existing['company_name'].unique().tolist()) if not df_existing.empty else []
        all_companies = sorted(list(set(settings_companies + existing_companies_data)))
        
        settings_vehicles = get_dropdown_options("vehicle")
        existing_vehicles_data = sorted(df_existing['vehicle_type'].unique().tolist()) if not df_existing.empty else []
        all_vehicles = sorted(list(set(settings_vehicles + existing_vehicles_data)))
        
        with tab1:
            st.markdown("<div class='company-card' style='background: #f0f7ff; border-left: 5px solid #007bff;'>", unsafe_allow_html=True)
            st.markdown("#### 🦅 ค้นหาตำแหน่งด้วย AI")
            if not gemini_api_key: st.warning("⚠️ กรุณาใส่ Gemini API Key")
            
            if "pasted_images" not in st.session_state: st.session_state.pasted_images = []
    
            col_up1, col_up2 = st.columns([3, 1])
            with col_up1: uploaded_files = st.file_uploader("📸 ลากรูปภาพมาวาง", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
            with col_up2:
                st.write("<br>", unsafe_allow_html=True)
                pasted_img = paste_image_button("📋 วางจากคลิปบอร์ด", key="paste_btn", use_container_width=True)
                if pasted_img and pasted_img.image_data:
                    temp_buf = io.BytesIO()
                    pasted_img.image_data.save(temp_buf, format="PNG")
                    img_hash = hashlib.md5(temp_buf.getvalue()).hexdigest()
                    if st.session_state.get("last_pasted_hash") != img_hash:
                        st.session_state.last_pasted_hash = img_hash
                        temp_buf.name = f"pasted_image_{len(st.session_state.pasted_images)}.png"
                        st.session_state.pasted_images.append(temp_buf)
                        st.rerun()
                if st.session_state.pasted_images:
                    if st.button("🗑️ ล้างภาพที่วาง"):
                        st.session_state.pasted_images = []
                        st.rerun()
            
            all_to_analyze = (uploaded_files if uploaded_files else []) + st.session_state.pasted_images
            if all_to_analyze and gemini_api_key:
                st.image(all_to_analyze, width=150)
                if st.button("🔍 เริ่มวิเคราะห์ด้วย AI"):
                    with st.spinner("AI กำลังทำงาน..."):
                        ai_results = analyze_camera_vision(all_to_analyze, gemini_api_key, get_dropdown_options("position"))
                        if isinstance(ai_results, dict) and "error" in ai_results: st.error(ai_results["error"])
                        else:
                            st.session_state["ai_suggestions"] = ai_results
                            # Automatically populate the selectboxes
                            pos_opts = get_dropdown_options("position")
                            
                            cur_c = st.session_state.get("new_comp", "").strip() or st.session_state.get("sel_comp", "")
                            if cur_c == "-- เลือกจากรายการ --": cur_c = ""
                            cur_v = st.session_state.get("new_veh", "").strip() or st.session_state.get("sel_veh", "")
                            if cur_v == "-- เลือกจากรายการ --": cur_v = ""

                            for r in range(4):
                                for i in range(2):
                                    ch_num = r*2+i+1
                                    ch_key = f"CH{ch_num}"
                                    if isinstance(ai_results, dict) and ch_key in ai_results:
                                        sug = str(ai_results[ch_key]).strip()
                                        if sug in pos_opts:
                                            st.session_state[f"p_{r}_{i}"] = sug
                                            # Also set suggested length
                                            st.session_state[f"l_{r}_{i}"] = get_suggested_length(cur_c, cur_v, sug)
                            
                            st.success("✅ วิเคราะห์และกรอกข้อมูลให้เสร็จสิ้น!")
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    
            with st.form("add_form_final"):
                c1, c2 = st.columns(2)
                with c1:
                    selected_comp = st.selectbox("🏢 เลือกบริษัท", options=["-- เลือกจากรายการ --"] + all_companies, key="sel_comp")
                    new_comp = st.text_input("➕ หรือพิมพ์บริษัทใหม่", key="new_comp")
                    in_plate = st.text_input("🔢 ป้ายทะเบียนรถ", placeholder="70-1234", key="in_plate")
                with c2:
                    pred = predict_vehicle_type(in_plate)
                    hist = get_last_veh_by_plate(in_plate)
                    if hist: st.success(f"📌 ความจำระบบ: {hist}")
                    elif pred: st.info(f"💡 AI แนะนำ: {pred}")
                    
                    all_v_opts = sorted(list(set(settings_vehicles + existing_vehicles_data)))
                    selected_veh = st.selectbox("🚚 เลือกประเภทรถ", options=["-- เลือกจากรายการ --"] + all_v_opts, key="sel_veh")
                    new_veh = st.text_input("➕ หรือพิมพ์รถใหม่", value=hist if hist else (pred if pred else ""), key="new_veh")
                
                st.markdown("**📸 ตำแหน่งติดตั้ง**")
                pos_opts = [""] + get_dropdown_options("position")
                entries = []
                for r in range(4):
                    cols = st.columns([2, 1, 2, 1])
                    ai_s = st.session_state.get("ai_suggestions", {})
                    for i in range(2):
                        ch_num = r*2+i+1
                        ch_key = f"CH{ch_num}"
                        sug = ai_s.get(ch_key, "")
                        idx = pos_opts.index(sug) if sug in pos_opts else 0
                        with cols[i*2]: p = st.selectbox(f"CH {ch_num}", pos_opts, index=idx, key=f"p_{r}_{i}")
                        def_l = get_suggested_length(new_comp if new_comp else selected_comp, new_veh if new_veh else selected_veh, p) if p else 5.0
                        with cols[i*2+1]: l = st.number_input(f"ม. {ch_num}", 0.0, 50.0, def_l, step=0.5, key=f"l_{r}_{i}", label_visibility="collapsed")
                        if p: entries.append((p, l))
                
                if st.form_submit_button("💾 บันทึกข้อมูล"):
                    comp_name = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เลือกจากรายการ --" else "")
                    veh_name = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เลือกจากรายการ --" else "")
                    if comp_name and veh_name and entries:
                        if comp_name not in settings_companies: add_dropdown_option("company", comp_name)
                        if veh_name not in settings_vehicles: add_dropdown_option("vehicle", veh_name)
                        for p, l in entries: add_data(comp_name, veh_name, p, l, in_plate.strip())
                        st.success("✅ บันทึกสำเร็จ!")
                        if "ai_suggestions" in st.session_state: del st.session_state["ai_suggestions"]
                        st.rerun()
                    else: st.error("⚠️ กรุณากรอกข้อมูลให้ครบ")

        with tab2:
            st.markdown("### 📋 ตารางบันทึกแบบหลายรายการ")
            if 'batch_df' not in st.session_state:
                st.session_state.batch_df = pd.DataFrame([{"บริษัท": "", "ประเภทรถ": "", "ตำแหน่ง": "", "สาย (ม.)": 0.0} for _ in range(10)])
            edited_df = st.data_editor(st.session_state.batch_df, num_rows="dynamic")
            if st.button("🚀 บันทึกทั้งหมด"):
                v_rows = edited_df[edited_df["บริษัท"].str.strip() != ""]
                for _, row in v_rows.iterrows():
                    if row["บริษัท"] and row["ประเภทรถ"] and row["ตำแหน่ง"]: add_data(row["บริษัท"], row["ประเภทรถ"], row["ตำแหน่ง"], float(row["สาย (ม.)"]))
                st.success("✅ บันทึกสำเร็จ!")
                st.rerun()

    elif choice == "🔍 ดูข้อมูลและค้นหา":
        st.subheader("🔍 ตรวจสอบข้อมูล")
        df = get_all_data()
        if df.empty: st.info("ยังไม่มีข้อมูล")
        else:
            all_comps = sorted(df['company_name'].unique().tolist())
            
            # --- Smart Selection View ---
            st.markdown("##### 🏢 เลือกบริษัทเพื่อดูรายละเอียด")
            comp_summary = df.groupby('company_name').size().reset_index(name='จำนวนรายการ')
            # Selectable Table
            selected_rows = st.dataframe(comp_summary, use_container_width=True, on_select="rerun", selection_mode="single-row")
            
            # Use selection or fallback to selectbox
            sel_comp = None
            if selected_rows and selected_rows.get('selection', {}).get('rows'):
                sel_idx = selected_rows['selection']['rows'][0]
                sel_comp = comp_summary.iloc[sel_idx]['company_name']
                st.info(f"กำลังดูข้อมูล: **{sel_comp}**")
            
            search = st.selectbox("หรือค้นหาจากรายชื่อ:", ["-- ทั้งหมด --"] + all_comps, index=(all_comps.index(sel_comp)+1) if sel_comp in all_comps else 0)
            target_comps = all_comps if search == "-- ทั้งหมด --" else [search]
            
            for comp in target_comps:
                with st.expander(f"🏢 {comp}", expanded=(len(target_comps) == 1)):
                    sub_df = df[df['company_name'] == comp]
                    if st.button(f"🗑️ ลบข้อมูลทั้งหมดของ {comp}", key=f"del_{comp}"):
                        delete_company_data(comp)
                        st.rerun()
                    
                    v_types = sorted(sub_df['vehicle_type'].unique().tolist())
                    for v_type in v_types:
                        vt_df = sub_df[sub_df['vehicle_type'] == v_type]
                        # Get unique license plates for this vehicle type group
                        plates = vt_df['license_plate'].dropna().unique().tolist()
                        plates = [p for p in plates if p.strip()] # Filter empty
                        plate_str = f" <span style='color: #007bff;'>[{', '.join(plates)}]</span>" if plates else ""
                        
                        st.markdown(f"<div class='company-card'><b>🚚 {v_type}</b>{plate_str} ({len(vt_df)} รายการ)", unsafe_allow_html=True)
                        st.table(vt_df[['installation_position', 'cable_length_m']].rename(columns={'installation_position':'ตำแหน่ง', 'cable_length_m':'สาย (ม.)'}))
                        if st.button(f"🗑️ ลบ {v_type}", key=f"del_{comp}_{v_type}"):
                            delete_vehicle_data(comp, v_type)
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

    elif choice == "⚙️ ตัวเลือก Dropdown":
        st.subheader("⚙️ จัดการตัวเลือก")
        cols = st.columns(3)
        cats = [("company", "🏢 บริษัท"), ("vehicle", "🚚 รถ"), ("position", "📸 ตำแหน่ง")]
        for i, (cat, name) in enumerate(cats):
            with cols[i]:
                st.markdown(f"### {name}")
                opts = get_dropdown_options(cat)
                with st.form(f"add_{cat}"):
                    nv = st.text_input("เพิ่มใหม่")
                    if st.form_submit_button("➕ เพิ่ม"):
                        if nv: add_dropdown_option(cat, nv); st.rerun()
                for o in opts:
                    c_1, c_2 = st.columns([4, 1])
                    c_1.write(o)
                    if c_2.button("❌", key=f"d_{cat}_{o}"): delete_dropdown_option(cat, o); st.rerun()

    elif choice == "📥 นำเข้าจาก Excel":
        st.subheader("📥 นำเข้าข้อมูล Excel")
        st.markdown("**คอลัมน์ที่ต้องการ:** `ชื่อบริษัท`, `ประเภทรถ`, `ตำแหน่งติดตั้ง`, `ความยาวสาย (เมตร)`")
        t_df = pd.DataFrame(columns=['ชื่อบริษัท', 'ประเภทรถ', 'ตำแหน่งติดตั้ง', 'ความยาวสาย (เมตร)'])
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w: t_df.to_excel(w, index=False)
        st.download_button("📄 ดาวน์โหลด Template", out.getvalue(), "template.xlsx")
        
        up = st.file_uploader("เลือกไฟล์ .xlsx", type=["xlsx"])
        if up:
            df_up = pd.read_excel(up)
            st.dataframe(df_up.head())
            m = {'ชื่อบริษัท':'company_name', 'ประเภทรถ':'vehicle_type', 'ตำแหน่งติดตั้ง':'installation_position', 'ความยาวสาย (เมตร)':'cable_length_m'}
            avail = {k: v for k, v in m.items() if k in df_up.columns}
            if avail and st.button("✅ ยืนยันการนำเข้า"):
                conn = sqlite3.connect(DB_FILE)
                final_up = pd.DataFrame()
                for k, v in avail.items(): final_up[v] = df_up[k]
                for c in ['company_name', 'vehicle_type', 'installation_position']:
                    if c not in final_up.columns: final_up[c] = "-"
                    final_up[c] = final_up[c].fillna("-")
                if 'cable_length_m' not in final_up.columns: final_up['cable_length_m'] = 0.0
                final_up['cable_length_m'] = final_up['cable_length_m'].fillna(0.0)
                final_up[['company_name', 'vehicle_type', 'installation_position', 'cable_length_m']].to_sql('camera_installations', conn, if_exists='append', index=False)
                conn.close()
                st.success("✅ นำเข้าเสร็จสิ้น!")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 ออกจากโปรแกรม (Reset)"):
        st.session_state.started = False
        st.rerun()
