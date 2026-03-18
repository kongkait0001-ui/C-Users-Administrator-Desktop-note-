from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.Enum('admin', 'technician', 'warehouse', name='user_roles'), default='technician')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CameraModel(db.Model):
    __tablename__ = 'camera_models'
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(50))
    model_name = db.Column(db.String(100), nullable=False)
    camera_type = db.Column(db.String(50)) # AHD, IP, etc.
    ai_type_id = db.Column(db.Integer, db.ForeignKey('camera_ai_types.id'))
    resolution = db.Column(db.String(50))
    
    cameras = db.relationship('Camera', backref='model', lazy=True)

class CameraAiType(db.Model):
    __tablename__ = 'camera_ai_types'
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), nullable=False) # DMS, ADAS, etc.
    description = db.Column(db.Text)

class MdvrModel(db.Model):
    __tablename__ = 'mdvr_models'
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(50))
    model_name = db.Column(db.String(100), nullable=False)
    channel_count = db.Column(db.Integer)
    is_ai_supported = db.Column(db.Boolean, default=False)

class Camera(db.Model):
    __tablename__ = 'cameras'
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    camera_model_id = db.Column(db.Integer, db.ForeignKey('camera_models.id'), nullable=False)
    status = db.Column(db.Enum('in_stock', 'reserved', 'installed', 'damaged', name='item_status'), default='in_stock')
    cable_length_m = db.Column(db.Float, default=0.0) # Added cable length
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CableType(db.Model):
    __tablename__ = 'cable_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), default='เมตร')
    
    rolls = db.relationship('CableRoll', backref='type', lazy=True)

class CableRoll(db.Model):
    __tablename__ = 'cable_rolls'
    id = db.Column(db.Integer, primary_key=True)
    cable_type_id = db.Column(db.Integer, db.ForeignKey('cable_types.id'), nullable=False)
    roll_code = db.Column(db.String(50), nullable=False)
    total_length_m = db.Column(db.Float, nullable=False)
    remaining_length_m = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')

class WorkOrder(db.Model):
    __tablename__ = 'work_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    client_name = db.Column(db.String(100))
    vehicle_plate = db.Column(db.String(50))
    technician_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('WorkOrderItem', backref='order', lazy=True)

class WorkOrderItem(db.Model):
    __tablename__ = 'work_order_items'
    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=False)
    camera_model_id = db.Column(db.Integer, db.ForeignKey('camera_models.id'))
    install_position = db.Column(db.String(50))
    cable_type_id = db.Column(db.Integer, db.ForeignKey('cable_types.id'))
    estimated_cable_length_m = db.Column(db.Float)
    actual_cable_length_m = db.Column(db.Float)
    assigned_camera_sn = db.Column(db.String(100))

class VehicleMapping(db.Model):
    __tablename__ = 'vehicle_cable_mappings'
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(100), nullable=False) # Changed from brand
    vehicle_type = db.Column(db.String(100), nullable=False) # Changed from model_name
    camera_position = db.Column(db.String(50), nullable=False)
    cable_length_m = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
