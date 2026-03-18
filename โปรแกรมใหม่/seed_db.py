from app import app, db
from models import User, CameraModel, Camera, CableType, CableRoll, WorkOrder, VehicleMapping, MdvrModel, CameraAiType
import datetime

def seed():
    with app.app_context():
        # Clear data
        db.drop_all()
        db.create_all()

        # Users
        u1 = User(username='admin', password_hash='pbkdf2:sha256...', full_name='Admin System', role='admin')
        u2 = User(username='tech1', password_hash='pbkdf2:sha256...', full_name='ช่างมานะ', role='technician')
        u3 = User(username='warehouse1', password_hash='pbkdf2:sha256...', full_name='คนโกดังสมชาย', role='warehouse')
        db.session.add_all([u1, u2, u3])

        # Master Data: AI Types
        ai1 = CameraAiType(type_name='DMS', description='Driver Monitoring System')
        ai2 = CameraAiType(type_name='ADAS', description='Advanced Driver Assistance Systems')
        db.session.add_all([ai1, ai2])
        db.session.commit()

        # Camera Models
        m1 = CameraModel(brand='Hikvision', model_name='DS-2CD2143G2', camera_type='IP', resolution='4MP', ai_type_id=ai1.id)
        m2 = CameraModel(brand='Dahua', model_name='HAC-HFW1500T', camera_type='AHD', resolution='5MP')
        db.session.add_all([m1, m2])

        # MDVR Models
        md1 = MdvrModel(brand='Streamax', model_name='X3-H0402', channel_count=4, is_ai_supported=True)
        md2 = MdvrModel(brand='Howen', model_name='V5-800', channel_count=8)
        db.session.add_all([md1, md2])
        db.session.commit()

        # Cameras
        c1 = Camera(serial_number='SN-CAM-1001', camera_model_id=m1.id, cable_length_m=5.0)
        c2 = Camera(serial_number='SN-CAM-1002', camera_model_id=m1.id, cable_length_m=12.0)
        c3 = Camera(serial_number='SN-CAM-2001', camera_model_id=m2.id, cable_length_m=15.0)
        db.session.add_all([c1, c2, c3])

        # Cable Types
        t1 = CableType(name='สาย RG59 + Power')
        t2 = CableType(name='สาย HDMI 1.5m')
        db.session.add_all([t1, t2])
        db.session.commit()

        # Cable Rolls
        r1 = CableRoll(cable_type_id=t1.id, roll_code='ROLL-RG-01', total_length_m=100.0, remaining_length_m=85.5)
        r2 = CableRoll(cable_type_id=t1.id, roll_code='ROLL-RG-02', total_length_m=200.0, remaining_length_m=200.0)
        db.session.add_all([r1, r2])

        # Vehicle Mappings - Using 'vehicle_type'
        v1 = VehicleMapping(company='Toyota', vehicle_type='รถบรรทุก 6 ล้อ', camera_position='หน้า', cable_length_m=5.0)
        v2 = VehicleMapping(company='Toyota', vehicle_type='รถบรรทุก 6 ล้อ', camera_position='หลัง', cable_length_m=12.0)
        v3 = VehicleMapping(company='Isuzu', vehicle_type='รถกระบะ', camera_position='หน้า', cable_length_m=6.0)
        v4 = VehicleMapping(company='Isuzu', vehicle_type='รถกระบะ', camera_position='หลัง', cable_length_m=15.0)
        db.session.add_all([v1, v2, v3, v4])

        # Sample Work Order
        wo = WorkOrder(order_number='WO-20260311-001', client_name='บริษัท ขนส่งไทย จำกัด', vehicle_plate='88-9999 กทม', technician_id=u2.id, status='pending')
        db.session.add(wo)

        db.session.commit()
        print("Database seeded with 'Vehicle Type' instead of 'Model'!")

if __name__ == '__main__':
    seed()
