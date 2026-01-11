import os
from datetime import datetime
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("[ReportGen] fpdf not installed. Run: pip install fpdf")

class ReportGenerator:
    def __init__(self):
        self.output_dir = "reports"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_patient_report(self, patient_data, incidents, medicines, stats):
        """Generate comprehensive patient report"""
        if not PDF_AVAILABLE:
            print("[ReportGen] Cannot generate PDF - fpdf not installed")
            return None
        
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 10, "SafeGuard Vision - Patient Report", ln=True, align="C")
        pdf.ln(5)
        
        # Report date
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="R")
        pdf.ln(10)
        
        # Patient Information
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Patient Information", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 11)
        info = [
            ("Name", patient_data[1]),
            ("Age", patient_data[2]),
            ("Gender", patient_data[3]),
            ("Blood Group", patient_data[4]),
            ("Bed Number", patient_data[5]),
            ("Emergency Contact", patient_data[6]),
            ("Doctor", patient_data[7]),
            ("Admission Date", patient_data[8]),
            ("Condition", patient_data[9])
        ]
        
        for label, value in info:
            pdf.cell(60, 6, f"{label}:", border=0)
            pdf.cell(0, 6, str(value), ln=True, border=0)
        
        pdf.ln(10)
        
        # Statistics
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Fall Detection Statistics", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 6, f"Total Incidents: {stats['total']}", ln=True)
        pdf.cell(0, 6, f"This Week: {stats['this_week']}", ln=True)
        
        if stats['by_type']:
            pdf.ln(2)
            pdf.cell(0, 6, "By Type:", ln=True)
            for incident_type, count in stats['by_type']:
                pdf.cell(0, 6, f"  - {incident_type}: {count}", ln=True)
        
        pdf.ln(10)
        
        # Recent Incidents
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Recent Incidents (Last 10)", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 9)
        for incident in incidents[:10]:
            incident_id, pat_id, time, inc_type, snap, vid, resp, notes = incident
            pdf.cell(0, 5, f"{time} - {inc_type}", ln=True)
        
        if not incidents:
            pdf.cell(0, 6, "No incidents recorded", ln=True)
        
        pdf.ln(10)
        
        # Medicines
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Current Medications", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 10)
        for med in medicines:
            med_id, pat_id, name, dosage, freq, start, end, times, instructions = med
            pdf.cell(0, 6, f"{name} - {dosage}", ln=True)
            pdf.cell(0, 5, f"  Frequency: {freq}", ln=True)
            pdf.ln(2)
        
        if not medicines:
            pdf.cell(0, 6, "No medications recorded", ln=True)
        
        # Save PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"patient_{patient_data[0]}_report_{timestamp}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            pdf.output(filepath)
            print(f"[ReportGen] Generated: {filepath}")
            return filepath
        except Exception as e:
            print(f"[ReportGen] Error: {e}")
            return None