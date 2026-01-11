import sqlite3
import os
import json
from datetime import datetime

DB_PATH = "patients_data/patients.db"
os.makedirs("patients_data", exist_ok=True)
os.makedirs("patients_data/patient_photos", exist_ok=True)


class PatientDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.create_tables()
        self.migrate_database()

    def create_tables(self):
        cursor = self.conn.cursor()

        # Patients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                blood_group TEXT,
                bed_number TEXT,
                emergency_contact TEXT,
                doctor_name TEXT,
                admission_date TEXT,
                medical_condition TEXT,
                photo_path TEXT,
                status TEXT DEFAULT 'Active',
                created_at TEXT
            )
        ''')

        # Medicines table - UPDATED
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                medicine_name TEXT NOT NULL,
                dosage TEXT,
                frequency TEXT,
                start_date TEXT,
                end_date TEXT,
                time_slots TEXT,
                instructions TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        ''')

        # Fall incidents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fall_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                incident_time TEXT,
                incident_type TEXT,
                snapshot_path TEXT,
                video_path TEXT,
                response_time INTEGER,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        ''')

        # Vital signs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vital_signs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                recorded_at TEXT,
                temperature REAL,
                blood_pressure TEXT,
                heart_rate INTEGER,
                oxygen_level INTEGER,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        ''')

        self.conn.commit()

    def migrate_database(self):
        """Add missing columns to existing tables"""
        cursor = self.conn.cursor()

        try:
            # Check if status column exists in medicines
            cursor.execute("PRAGMA table_info(medicines)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'status' not in columns:
                cursor.execute('ALTER TABLE medicines ADD COLUMN status TEXT DEFAULT "active"')
                print("✓ Added 'status' column to medicines table")

            if 'created_at' not in columns:
                cursor.execute('ALTER TABLE medicines ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP')
                print("✓ Added 'created_at' column to medicines table")

            self.conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")

    def add_patient(self, patient_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO patients 
            (name, age, gender, blood_group, bed_number, emergency_contact, 
             doctor_name, admission_date, medical_condition, photo_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            patient_data['name'],
            patient_data.get('age'),
            patient_data.get('gender'),
            patient_data.get('blood_group'),
            patient_data.get('bed_number'),
            patient_data.get('emergency_contact'),
            patient_data.get('doctor_name'),
            patient_data.get('admission_date', datetime.now().strftime("%Y-%m-%d")),
            patient_data.get('medical_condition'),
            patient_data.get('photo_path'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_patients(self, status='Active'):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM patients WHERE status = ?', (status,))
        return cursor.fetchall()

    def get_patient(self, patient_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM patients WHERE id = ?', (patient_id,))
        return cursor.fetchone()

    def update_patient(self, patient_id, updates):
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [patient_id]
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE patients SET {set_clause} WHERE id = ?', values)
        self.conn.commit()

    def discharge_patient(self, patient_id):
        """Mark patient as discharged (status set to 'Discharged')."""
        try:
            self.update_patient(patient_id, {'status': 'Discharged'})
            return True
        except Exception:
            return False

    def delete_patient(self, patient_id):
        """Delete patient and related records from the database."""
        try:
            cursor = self.conn.cursor()
            # Delete related records first
            cursor.execute('DELETE FROM medicines WHERE patient_id = ?', (patient_id,))
            cursor.execute('DELETE FROM fall_incidents WHERE patient_id = ?', (patient_id,))
            cursor.execute('DELETE FROM vital_signs WHERE patient_id = ?', (patient_id,))
            # Delete patient
            cursor.execute('DELETE FROM patients WHERE id = ?', (patient_id,))
            self.conn.commit()
            return True
        except Exception:
            return False

    def add_medicine(self, medicine_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO medicines 
            (patient_id, medicine_name, dosage, frequency, start_date, end_date, time_slots, instructions, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            medicine_data['patient_id'],
            medicine_data['medicine_name'],
            medicine_data.get('dosage'),
            medicine_data.get('frequency'),
            medicine_data.get('start_date'),
            medicine_data.get('end_date'),
            json.dumps(medicine_data.get('time_slots', [])),
            medicine_data.get('instructions'),
            medicine_data.get('status', 'active')
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_patient_medicines(self, patient_id, active_only=False):
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute('SELECT * FROM medicines WHERE patient_id = ? AND status = "active"', (patient_id,))
        else:
            cursor.execute('SELECT * FROM medicines WHERE patient_id = ?', (patient_id,))

        meds = cursor.fetchall()
        # Parse time_slots JSON
        result = []
        for med in meds:
            med_list = list(med)
            if len(med_list) > 7 and med_list[7]:  # time_slots column
                try:
                    med_list[7] = json.loads(med_list[7])
                except:
                    med_list[7] = []
            result.append(tuple(med_list))
        return result

    # NEW METHODS FOR MEDICINE MANAGEMENT
    def update_medicine_status(self, medicine_id, status):
        """Update medicine status (active/completed/discontinued)"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE medicines SET status = ? WHERE id = ?', (status, medicine_id))
        self.conn.commit()

    def update_medicine(self, medicine_id, updates):
        """Update medicine details"""
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [medicine_id]
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE medicines SET {set_clause} WHERE id = ?', values)
        self.conn.commit()

    def delete_medicine(self, medicine_id):
        """Delete a medicine record"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM medicines WHERE id = ?', (medicine_id,))
        self.conn.commit()
        return True

    def log_fall_incident(self, incident_data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO fall_incidents 
            (patient_id, incident_time, incident_type, snapshot_path, video_path, response_time, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            incident_data['patient_id'],
            incident_data.get('incident_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            incident_data.get('incident_type'),
            incident_data.get('snapshot_path'),
            incident_data.get('video_path'),
            incident_data.get('response_time'),
            incident_data.get('notes')
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_patient_incidents(self, patient_id, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM fall_incidents 
            WHERE patient_id = ? 
            ORDER BY incident_time DESC 
            LIMIT ?
        ''', (patient_id, limit))
        return cursor.fetchall()

    def get_incident_statistics(self, patient_id):
        cursor = self.conn.cursor()

        # Total incidents
        cursor.execute('SELECT COUNT(*) FROM fall_incidents WHERE patient_id = ?', (patient_id,))
        total = cursor.fetchone()[0]

        # Incidents by type
        cursor.execute('''
            SELECT incident_type, COUNT(*) 
            FROM fall_incidents 
            WHERE patient_id = ? 
            GROUP BY incident_type
        ''', (patient_id,))
        by_type = cursor.fetchall()

        # Incidents this week
        cursor.execute('''
            SELECT COUNT(*) FROM fall_incidents 
            WHERE patient_id = ? 
            AND incident_time >= date('now', '-7 days')
        ''', (patient_id,))
        this_week = cursor.fetchone()[0]

        return {
            'total': total,
            'by_type': by_type,
            'this_week': this_week
        }

    def close(self):
        self.conn.close()
