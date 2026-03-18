import pandas as pd
from models import db, VehicleMapping

def import_vehicle_mappings(file_path):
    try:
        df = pd.read_excel(file_path)
        # Expected columns: บริษัท, ประเภทรถ, ตำแหน่งกล้อง, ความยาวสายที่ใช้ (เมตร)
        
        for index, row in df.iterrows():
            mapping = VehicleMapping.query.filter_by(
                company=row['บริษัท'],
                vehicle_type=row['ประเภทรถ'],
                camera_position=row['ตำแหน่งกล้อง']
            ).first()
            
            if not mapping:
                mapping = VehicleMapping(
                    company=row['บริษัท'],
                    vehicle_type=row['ประเภทรถ'],
                    camera_position=row['ตำแหน่งกล้อง'],
                    cable_length_m=row['ความยาวสายที่ใช้ (เมตร)']
                )
                db.session.add(mapping)
            else:
                mapping.cable_length_m = row['ความยาวสายที่ใช้ (เมตร)']
        
        db.session.commit()
        return True, "Import Successful"
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def create_sample_excel(file_path):
    data = {
        'บริษัท': ['Toyota', 'Toyota', 'Isuzu', 'Isuzu'],
        'ประเภทรถ': ['รถบรรทุก 6 ล้อ', 'รถบรรทุก 6 ล้อ', 'รถกระบะ', 'รถกระบะ'],
        'ตำแหน่งกล้อง': ['หน้า', 'หลัง', 'หน้า', 'หลัง'],
        'ความยาวสายที่ใช้ (เมตร)': [5, 15, 6, 18]
    }
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)
    return file_path
