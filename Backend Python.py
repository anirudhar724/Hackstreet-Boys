"""
Hosp - Hospital Resource Management Backend
Standard Triage Queue and Resource Management API

Run with:
    pip install flask flask-cors sqlalchemy
    python app.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Hosp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================

class ResourceModel(db.Model):
    __tablename__ = 'resources'
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'ICU', 'Surgery', 'General'
    is_vacant = db.Column(db.Boolean, default=True)
    occupied_by = db.Column(db.Integer, nullable=True)

class PatientModel(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    severity = db.Column(db.Integer, nullable=False) # 1: Critical, 2: Moderate, 3: Mild
    disease = db.Column(db.String(100), nullable=True)
    arrival_time = db.Column(db.Float, nullable=False)
    room_id = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(30), default='QUEUED') # 'QUEUED', 'IN_TREATMENT', 'DISCHARGED'

class StaffModel(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class TreatmentLogModel(db.Model):
    __tablename__ = 'treatment_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    treatment_id = db.Column(db.String(50))
    patient_id = db.Column(db.Integer)
    staff_id = db.Column(db.String(20))
    details = db.Column(db.String(255))
    date_str = db.Column(db.String(50))

def find_vacant_room_for_severity(severity):
    """Finds appropriate vacant room based on patient triage severity."""
    if severity == 1:
        # Severity 1 prefers ICU, then Operating Room/Surgery, then General Ward
        room = ResourceModel.query.filter_by(is_vacant=True, type='ICU').first()
        if not room:
            room = ResourceModel.query.filter_by(is_vacant=True, type='Surgery').first()
        if not room:
            room = ResourceModel.query.filter_by(is_vacant=True).first()
        return room
    else:
        # Severity 2 & 3 prefer General Ward first, then backup available rooms
        room = ResourceModel.query.filter_by(is_vacant=True, type='General').first()
        if not room:
            room = ResourceModel.query.filter_by(is_vacant=True).first()
        return room

def seed_database():
    """Seeds initial 18 vacant rooms across 3 departments and staff with zero default patients."""
    if ResourceModel.query.count() == 0:
        rooms = [
            # ICU Section (6 Rooms)
            ResourceModel(id='ICU-1', name='ICU Bed 1', type='ICU', is_vacant=True, occupied_by=None),
            ResourceModel(id='ICU-2', name='ICU Bed 2', type='ICU', is_vacant=True, occupied_by=None),
            ResourceModel(id='ICU-3', name='ICU Bed 3', type='ICU', is_vacant=True, occupied_by=None),
            ResourceModel(id='ICU-4', name='ICU Bed 4', type='ICU', is_vacant=True, occupied_by=None),
            ResourceModel(id='ICU-5', name='ICU Bed 5', type='ICU', is_vacant=True, occupied_by=None),
            ResourceModel(id='ICU-6', name='ICU Bed 6', type='ICU', is_vacant=True, occupied_by=None),

            # Operating Rooms / Surgical Suites (4 Rooms)
            ResourceModel(id='OR-1', name='Operating Suite 1', type='Surgery', is_vacant=True, occupied_by=None),
            ResourceModel(id='OR-2', name='Operating Suite 2', type='Surgery', is_vacant=True, occupied_by=None),
            ResourceModel(id='OR-3', name='Operating Suite 3', type='Surgery', is_vacant=True, occupied_by=None),
            ResourceModel(id='OR-4', name='Operating Suite 4', type='Surgery', is_vacant=True, occupied_by=None),

            # General Wards (8 Beds)
            ResourceModel(id='GW-1', name='General Ward Bed 1', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-2', name='General Ward Bed 2', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-3', name='General Ward Bed 3', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-4', name='General Ward Bed 4', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-5', name='General Ward Bed 5', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-6', name='General Ward Bed 6', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-7', name='General Ward Bed 7', type='General', is_vacant=True, occupied_by=None),
            ResourceModel(id='GW-8', name='General Ward Bed 8', type='General', is_vacant=True, occupied_by=None),
        ]
        db.session.add_all(rooms)

        staff_members = [
            StaffModel(id='DOC-101', name='Dr. Sarah Vance', role='Surgeon'),
            StaffModel(id='DOC-102', name='Dr. Michael Chen', role='ICU Specialist'),
            StaffModel(id='NUR-201', name='Nurse Lisa Taylor', role='Senior Nurse')
        ]
        db.session.add_all(staff_members)
        db.session.commit()

# ==================== API ENDPOINTS ====================

@app.route('/api/simulation/burst', methods=['POST'])
def simulation_burst():
    """Generates a batch surge of simulated patients with varying severities."""
    data = request.json or {}
    count = int(data.get('count', 5))
    import random

    diseases = {
        1: ['Acute Myocardial Infarction', 'Severe Surgical Trauma', 'Respiratory Failure', 'Septic Shock'],
        2: ['Complex Fracture', 'Acute Appendicitis', 'Severe Asthma Flare', 'Dehydration'],
        3: ['Laceration Repair', 'Upper Respiratory Infection', 'Minor Sprain', 'Migraine']
    }
    names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Chris', 'Emma', 'Liam', 'Sophia', 'Noah', 'Olivia']

    created_ids = []
    for _ in range(count):
        last_p = PatientModel.query.order_by(PatientModel.id.desc()).first()
        new_id = (last_p.id + 1) if last_p else 1

        sev_roll = random.random()
        severity = 1 if sev_roll < 0.2 else (2 if sev_roll < 0.7 else 3)
        name = f"{random.choice(names)} #{new_id}"
        disease = random.choice(diseases[severity])
        age = random.randint(18, 75)
        gender = random.choice(['Male', 'Female'])

        available_room = find_vacant_room_for_severity(severity)
        status = 'QUEUED'
        assigned_room_id = None

        if available_room:
            status = 'IN_TREATMENT'
            assigned_room_id = available_room.id
            available_room.is_vacant = False
            available_room.occupied_by = new_id

            log = TreatmentLogModel(
                treatment_id=f"TRT-{random.randint(1000, 9999)}",
                patient_id=new_id,
                staff_id='DOC-102' if severity == 1 else 'DOC-101',
                details=f"Surge Admission: {disease}. Allocated to {available_room.name}",
                date_str=datetime.now().strftime("%I:%M:%S %p")
            )
            db.session.add(log)

        new_patient = PatientModel(
            id=new_id,
            name=name,
            age=age,
            gender=gender,
            severity=severity,
            disease=disease,
            arrival_time=time.time(),
            room_id=assigned_room_id,
            status=status
        )

        db.session.add(new_patient)
        created_ids.append(new_id)

    db.session.commit()
    return jsonify({'success': True, 'count': count, 'patient_ids': created_ids})

@app.route('/api/state', methods=['GET'])
def get_state():
    resources = ResourceModel.query.all()
    staff = StaffModel.query.all()
    logs = TreatmentLogModel.query.order_by(TreatmentLogModel.id.desc()).all()

    queued_patients = PatientModel.query.filter_by(status='QUEUED').all()
    # Sort queue by severity ascending (1 > 2 > 3), then age, then arrival time (FCFS)
    queued_patients.sort(key=lambda p: (p.severity, p.age, p.arrival_time))

    queue_data = [{
        'id': p.id,
        'name': p.name,
        'age': p.age,
        'gender': p.gender,
        'severity': p.severity,
        'severityTag': '1 - Critical' if p.severity == 1 else ('2 - Moderate' if p.severity == 2 else '3 - Mild'),
        'disease': p.disease or 'Unspecified',
        'arrivalTime': p.arrival_time
    } for p in queued_patients]

    return jsonify({
        'rooms': [{'id': r.id, 'name': r.name, 'type': r.type, 'isVacant': r.is_vacant, 'occupiedBy': r.occupied_by} for r in resources],
        'staff': [{'id': s.id, 'name': s.name, 'role': s.role} for s in staff],
        'queue': queue_data,
        'treatments': [{'id': t.treatment_id, 'patientId': t.patient_id, 'staffId': t.staff_id, 'details': t.details, 'date': t.date_str} for t in logs]
    })

@app.route('/api/patient', methods=['POST'])
def add_patient():
    data = request.json or {}
    last_p = PatientModel.query.order_by(PatientModel.id.desc()).first()
    new_id = (last_p.id + 1) if last_p else 1

    severity = int(data.get('severity', 2))
    name = data.get('name', f'Patient #{new_id}')
    age = int(data.get('age', 30))
    gender = data.get('gender', 'Male')
    disease = data.get('disease', 'General Triage')

    available_room = find_vacant_room_for_severity(severity)

    status = 'QUEUED'
    assigned_room_id = None

    if available_room:
        status = 'IN_TREATMENT'
        assigned_room_id = available_room.id
        available_room.is_vacant = False
        available_room.occupied_by = new_id

        # Create treatment log
        import random
        log = TreatmentLogModel(
            treatment_id=f"TRT-{random.randint(1000, 9999)}",
            patient_id=new_id,
            staff_id='DOC-102' if severity == 1 else 'DOC-101',
            details=f"Admitted for {disease}. Allocated to {available_room.name}",
            date_str=datetime.now().strftime("%I:%M:%S %p")
        )
        db.session.add(log)

    new_patient = PatientModel(
        id=new_id,
        name=name,
        age=age,
        gender=gender,
        severity=severity,
        disease=disease,
        arrival_time=time.time(),
        room_id=assigned_room_id,
        status=status
    )

    db.session.add(new_patient)
    db.session.commit()

    return jsonify({
        'success': True,
        'patient_id': new_id,
        'assigned_room': assigned_room_id,
        'message': f'Patient {name} admitted.'
    })

@app.route('/api/discharge/<int:patient_id>', methods=['POST'])
def discharge_patient(patient_id):
    patient = PatientModel.query.get(patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404

    patient.status = 'DISCHARGED'
    room_id = patient.room_id

    if room_id:
        room_res = ResourceModel.query.get(room_id)
        if room_res:
            room_res.is_vacant = True
            room_res.occupied_by = None

            # Automatically allocate freed room to top queued patient
            next_queued = PatientModel.query.filter_by(status='QUEUED').order_by(PatientModel.severity.asc(), PatientModel.arrival_time.asc()).first()
            if next_queued:
                import random
                next_queued.status = 'IN_TREATMENT'
                next_queued.room_id = room_id
                room_res.is_vacant = False
                room_res.occupied_by = next_queued.id

                log = TreatmentLogModel(
                    treatment_id=f"TRT-{random.randint(1000, 9999)}",
                    patient_id=next_queued.id,
                    staff_id='DOC-101',
                    details=f"Triage Re-allocation: Assigned to {room_res.name} upon room discharge",
                    date_str=datetime.now().strftime("%I:%M:%S %p")
                )
                db.session.add(log)

    db.session.commit()
    return jsonify({'success': True, 'message': f'Patient {patient.name} discharged.'})

@app.route('/api/reset', methods=['POST'])
def reset_system():
    db.drop_all()
    db.create_all()
    seed_database()
    return jsonify({'success': True, 'message': 'System state reset to defaults.'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
    print("Hosp Backend running on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)