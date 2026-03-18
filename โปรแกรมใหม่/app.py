import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db, User, CameraModel, Camera, CableType, CableRoll, WorkOrder, WorkOrderItem, VehicleMapping, MdvrModel, CameraAiType
from datetime import datetime
import import_manager
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cctv_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret-key-123'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

@app.route('/')
def dashboard():
    # Summaries for dashboard
    counts = {
        'pending_orders': WorkOrder.query.filter_by(status='pending').count(),
        'cameras_in_stock': Camera.query.filter_by(status='in_stock').count()
    }
    return render_template('dashboard.html', **counts)

@app.route('/inventory')
def inventory():
    cameras = Camera.query.all()
    return render_template('inventory.html', cameras=cameras)

@app.route('/work-orders')
def work_orders():
    orders = WorkOrder.query.all()
    return render_template('work_orders.html', orders=orders)

@app.route('/smart_search', methods=['GET', 'POST'])
def smart_search():
    companies = db.session.query(VehicleMapping.company).distinct().all()
    companies = [c[0] for c in companies]
    
    results = None
    show_import = False
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'search':
            company = request.form.get('company')
            v_type = request.form.get('vehicle_type')
            position = request.form.get('position')
            
            query = VehicleMapping.query
            if company: query = query.filter_by(company=company)
            if v_type: query = query.filter_by(vehicle_type=v_type)
            if position: query = query.filter_by(camera_position=position)
            
            results = query.all()
        
        elif action == 'import':
            show_import = True
            if 'file' not in request.files:
                flash('ไม่พบไฟล์')
            else:
                file = request.files['file']
                if file.filename == '':
                    flash('กรุณาเลือกไฟล์')
                elif file:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                    file.save(file_path)
                    success, message = import_manager.import_vehicle_mappings(file_path)
                    flash(message)
                    return redirect(url_for('smart_search'))
            
    return render_template('smart_search.html', companies=companies, results=results, show_import=show_import)

@app.route('/get-models/<company>')
def get_models(company):
    models = db.session.query(VehicleMapping.model_name).filter_by(company=company).distinct().all()
    return jsonify([m[0] for m in models])

@app.route('/import-data', methods=['GET', 'POST'])
def import_data():
    return redirect(url_for('smart_search', show_import=True))

@app.route('/download-template')
def download_template():
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'sample_template.xlsx')
    import_manager.create_sample_excel(path)
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
