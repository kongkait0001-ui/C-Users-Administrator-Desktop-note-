import streamlit as st
import sqlite3
import pandas as pd
import openpyxl
import os
import io

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

def add_data(company, vehicle, position, length):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO camera_installations (company_name, vehicle_type, installation_position, cable_length_m)
        VALUES (?, ?, ?, ?)
    ''', (company, vehicle, position, length))
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

# Initialize DB on start
init_db()

# --- UI Setup ---
st.set_page_config(page_title="Abdul", page_icon="abdul_logo_nobg.png", layout="wide")

# Custom CSS for premium look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stDataFrame {
        border: 1px solid #e6e9ef;
        border-radius: 5px;
    }
    h1 {
        color: #1e293b;
    }
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-20px); }
        100% { transform: translateY(0px); }
    }
    .floating-img {
        animation: float 3s ease-in-out infinite;
        display: block;
        margin-left: auto;
        margin-right: auto;
        max-width: 350px;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

if 'started' not in st.session_state:
    st.session_state.started = False

if not st.session_state.started:
    # Reduce top spacing to fit on screen
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        import base64
        with open("abdul_logo_nobg.png", "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode()
            
        # Adjusted max-width for better fit
        st.markdown(f'<img src="data:image/png;base64,{b64_string}" class="floating-img" style="max-width: 250px;">', unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; font-size: 3.5em; margin-bottom: 0px;'>Abdul</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #475569; margin-top: -10px;'>AI CCTV Data Management System</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; margin-top: -5px;'>ระบบจัดการข้อมูลการติดตั้งกล้อง AI CCTV และความยาวสายเคเบิล</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        btn_c1, btn_c2, btn_c3 = st.columns([1, 2, 1])
        with btn_c2:
            if st.button("🚀 เข้าสู่ระบบ (Start Program)"):
                st.session_state.started = True
                st.rerun()
    st.stop()

col1, col2 = st.columns([1, 15])
with col1:
    st.image("abdul_logo_nobg.png", width=80)
with col2:
    st.title("Abdul - AI CCTV Data Management System")
st.markdown("ระบบจัดการข้อมูลการติดตั้งกล้อง AI CCTV และความยาวสายเคเบิล")

# Sidebar navigation
menu = ["เพิ่มข้อมูลใหม่", "ดูข้อมูลและค้นหา", "ตั้งค่าตัวเลือก Dropdown", "นำเข้าข้อมูลจาก Excel"]
choice = st.sidebar.selectbox("เมนูการใช้งาน", menu)

if choice == "เพิ่มข้อมูลใหม่":
    st.subheader("📝 กรอกข้อมูลการติดตั้งใหม่")
    
    df_existing = get_all_data()
    
    settings_companies = get_dropdown_options("company")
    existing_companies_data = sorted(df_existing['company_name'].unique().tolist()) if not df_existing.empty else []
    all_companies = sorted(list(set(settings_companies + existing_companies_data)))
    
    settings_vehicles = get_dropdown_options("vehicle")
    existing_vehicles_data = sorted(df_existing['vehicle_type'].unique().tolist()) if not df_existing.empty else []
    all_vehicles = sorted(list(set(settings_vehicles + existing_vehicles_data)))
    
    comp_options = ["-- เลือกบริษัทที่มีอยู่ --"] + all_companies
    veh_options = ["-- เลือกประเภทรถ --"] + all_vehicles
    
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            selected_comp = st.selectbox("ชื่อบริษัท (เลือกจากรายการ)", options=comp_options)
            new_comp = st.text_input("➕ หรือพิมพ์ชื่อบริษัทใหม่")
        with col2:
            selected_veh = st.selectbox("ประเภทรถที่ใช้ (เลือกจากรายการ)", options=veh_options)
            new_veh = st.text_input("➕ หรือพิมพ์ประเภทรถใหม่")
            
        st.markdown("---")
        st.markdown("**📸 ระบุตำแหน่งที่ติดตั้งและความยาวสาย (ระบุได้สูงสุด 8 ตำแหน่งพร้อมกัน)**")
        
        positions = []
        lengths = []
        
        pos_options = [""] + get_dropdown_options("position")
        len_options = [0.0] + [float(i) for i in range(1, 17)]
        
        for i in range(1, 9):
            col_p, col_l = st.columns(2)
            with col_p:
                pos = st.selectbox(f"ตำแหน่งที่ {i}", options=pos_options, key=f"pos_{i}")
                positions.append(pos)
            with col_l:
                length = st.selectbox(f"ความยาวสายตำแหน่งที่ {i} (เมตร)", options=len_options, key=f"len_{i}")
                lengths.append(length)
            
        submit_button = st.form_submit_button("บันทึกข้อมูล")
        
        if submit_button:
            company_name = new_comp.strip() if new_comp.strip() else (selected_comp if selected_comp != "-- เลือกบริษัทที่มีอยู่ --" else "")
            vehicle_type = new_veh.strip() if new_veh.strip() else (selected_veh if selected_veh != "-- เลือกประเภทรถ --" else "")
            
            if company_name and vehicle_type:
                # Add to DB setting if new
                if company_name not in settings_companies:
                    add_dropdown_option("company", company_name)
                if vehicle_type not in settings_vehicles:
                    add_dropdown_option("vehicle", vehicle_type)
                added_count = 0
                for pos, length in zip(positions, lengths):
                    if pos.strip(): # if not empty
                        add_data(company_name, vehicle_type, pos.strip(), length)
                        added_count += 1
                
                if added_count > 0:
                    st.success(f"✅ บันทึกข้อมูลของบริษัท {company_name} จำนวน {added_count} ตำแหน่ง เรียบร้อยแล้ว!")
                else:
                    st.warning("⚠️ กรุณาระบุตำแหน่งที่ติดตั้งอย่างน้อย 1 ตำแหน่ง")
            else:
                st.error("⚠️ กรุณากรอกชื่อบริษัทและประเภทรถให้ครบ")

elif choice == "ดูข้อมูลและค้นหา":
    st.subheader("🔍 ค้นหาและตรวจสอบข้อมูล")
    
    df = get_all_data()
    
    # Search Filter
    all_search_companies = sorted(df['company_name'].unique().tolist()) if not df.empty else []
    search_query = st.selectbox("🔎 ค้นหาด้วยชื่อบริษัท", ["-- แสดงทั้งหมด --"] + all_search_companies)
    
    if search_query and search_query != "-- แสดงทั้งหมด --":
        filtered_df = df[df['company_name'] == search_query]
    else:
        filtered_df = df

    # Display summary metrics
    if not filtered_df.empty:
        st.markdown("💡 **คลิกที่ชื่อบริษัท** ในรายการด้านล่างเพื่อดูรายละเอียด")
        
        # Unique list of companies
        company_list = filtered_df['company_name'].drop_duplicates().sort_values().tolist()
        
        if 'selected_company_view' not in st.session_state:
            st.session_state.selected_company_view = None
            
        with st.container(height=250, border=True):
            for comp in company_list:
                # Using button for direct text click
                if st.button(f"🏢 {comp}", key=f"btn_comp_{comp}", type="secondary", use_container_width=True):
                    st.session_state.selected_company_view = comp
                    
        selected_company = st.session_state.selected_company_view
        
        if selected_company and selected_company in company_list:
            
            st.divider()
            
            col_comp_title, col_comp_del = st.columns([4, 1])
            with col_comp_title:
                st.subheader(f"🏢 ข้อมูลบริษัท: {selected_company}")
            with col_comp_del:
                if st.button("🗑️ ลบทั้งบริษัท", key="del_comp", use_container_width=True):
                    delete_company_data(selected_company)
                    st.rerun()
            
            # Get data for selected company
            company_data = df[df['company_name'] == selected_company]
            
            # Get unique vehicle types for the dropdown
            vehicle_list = sorted(company_data['vehicle_type'].unique())
            
            selected_v_type = st.selectbox(
                f"🚗 เลือกประเภทรถของ {selected_company}", 
                ["-- เลือกประเภทรถ --"] + vehicle_list
            )
            
            if selected_v_type != "-- เลือกประเภทรถ --":
                # Show details for the specific vehicle type
                v_detail = company_data[company_data['vehicle_type'] == selected_v_type]
                
                col_v_title, col_v_del = st.columns([4, 1])
                with col_v_title:
                    st.markdown(f"📊 **รายละเอียดของ {selected_v_type}:**")
                with col_v_del:
                    if st.button("🗑️ ลบรถประเภทนี้", key="del_veh", use_container_width=True):
                        delete_vehicle_data(selected_company, selected_v_type)
                        st.rerun()
                        
                display_details = v_detail[['installation_position', 'cable_length_m']].rename(columns={
                    'installation_position': 'ตำแหน่งติดตั้ง',
                    'cable_length_m': 'ความยาวสาย (ม.)'
                })
                st.table(display_details)
            
            # Add new vehicle type for this company
            with st.expander(f"➕ เพิ่มประเภทรถหรือตำแหน่งใหม่สำหรับ {selected_company}"):
                with st.form("add_vehicle_form", clear_on_submit=True):
                    
                    settings_veh = get_dropdown_options("vehicle")
                    all_v = sorted(list(set(settings_veh + df['vehicle_type'].unique().tolist())))
                    
                    sel_new_v = st.selectbox("ประเภทรถ (เลือกจากรายการ)", options=["-- เลือกประเภทรถ --"] + all_v)
                    txt_new_v = st.text_input("➕ หรือพิมพ์ประเภทรถใหม่")
                    
                    st.markdown("**📸 ระบุตำแหน่งที่ติดตั้ง (เพิ่มได้สูงสุด 8 ตำแหน่งพร้อมกัน)**")
                    new_positions = []
                    new_lengths = []
                    
                    pos_options = [""] + get_dropdown_options("position")
                    len_options = [0.0] + [float(i) for i in range(1, 17)]
                    
                    for i in range(1, 9):
                        col_p, col_l = st.columns(2)
                        with col_p:
                            p = st.selectbox(f"ตำแหน่งที่ {i}", options=pos_options, key=f"newp_{i}")
                            new_positions.append(p)
                        with col_l:
                            l = st.selectbox(f"ความยาวสาย {i} (ม.)", options=len_options, key=f"newl_{i}")
                            new_lengths.append(l)
                    
                    if st.form_submit_button("บันทึกข้อมูลรถใหม่"):
                        final_v_type = txt_new_v.strip() if txt_new_v.strip() else (sel_new_v if sel_new_v != "-- เลือกประเภทรถ --" else "")
                        
                        if final_v_type:
                            # Save setting if new
                            if final_v_type not in settings_veh:
                                add_dropdown_option("vehicle", final_v_type)
                                
                            added_count = 0
                            for p, l in zip(new_positions, new_lengths):
                                if p.strip():
                                    add_data(selected_company, final_v_type, p.strip(), l)
                                    added_count += 1
                                    
                            if added_count > 0:
                                st.success(f"✅ เพิ่มข้อมูล {final_v_type} จำนวน {added_count} ตำแหน่ง เรียบร้อยแล้ว!")
                                st.rerun()
                            else:
                                st.warning("⚠️ กรุณาระบุตำแหน่งที่ติดตั้งอย่างน้อย 1 ตำแหน่ง")
                        else:
                            st.error("กรุณากรอกประเภทรถ")
    else:
        st.info("ยังไม่มีข้อมูลรายชื่อบริษัท")
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
