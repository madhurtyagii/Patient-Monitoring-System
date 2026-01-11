import os
import time
import threading
import cv2
import torch
from ultralytics import YOLO    
import tkinter as tk
from tkinter import (
    Tk,
    Label,
    Button,
    Frame,
    StringVar,
    BooleanVar,
    Text,
    Scrollbar,
    Scale,
    HORIZONTAL,
    Entry,
    messagebox,
    Toplevel,
)
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import datetime
import json
from collections import deque
import winsound

# Import your existing modules
from telegram_alert import send_telegram_alert
from patient_db import PatientDatabase
from video_recorder import VideoRecorder
from report_generator import ReportGenerator



# AUDIO ALERTS WITH WINSOUND

class AudioAlerts:
    """Audio alert system using winsound"""

    def __init__(self):
        self.enabled = True
        self.sounds = {
            "possible_fall": (800, 200),  # frequency, duration
            "confirmed_fall": (1000, 500),
            "system_start": (600, 100),
            "system_stop": (400, 100),
        }

    def set_enabled(self, enabled):
        self.enabled = enabled

    def play_alert(self, alert_type):
        if not self.enabled:
            return

        try:
            freq, duration = self.sounds.get(alert_type, (800, 200))
            winsound.Beep(freq, duration)
        except Exception as e:
            print(f"Audio alert error: {e}")



# CONFIG
CAM_INDEX = 0
DEVICE = 0 if torch.cuda.is_available() else "cpu"
MODEL = "yolov8n.pt"

CONFIG = {
    "drop_speed_threshold": 35,
    "aspect_ratio_threshold": 1.25,
    "impact_movement_time": 0.8,
    "stillness_time": 1.0,
    "min_movement_threshold": 4,
    "cooldown_time": 10,
    "video_buffer_seconds": 5,
    "audio_alerts_enabled": True,
    "auto_record_video": True,
}

CONFIG_FILE = "config.json"
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            CONFIG.update(json.load(f))
    except Exception:
        pass


def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(CONFIG, f, indent=2)
    except:
        pass


SNAP_DIR = "static/snapshots"
os.makedirs(SNAP_DIR, exist_ok=True)


# Helper functions
def center_of_box(x1, y1, x2, y2):
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def choose_largest_box(boxes):
    best = None
    max_area = -1
    for b in boxes:
        x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
        area = (x2 - x1) * (y2 - y1)
        if area > max_area:
            max_area = area
            best = (x1, y1, x2, y2, float(b.conf[0]))
    return best


def now_str():
    return time.strftime("%Y-%m-%d_%H-%M-%S")


# States
STATE_MONITOR = "monitor"
STATE_POSSIBLE_FALL = "possible_fall"
STATE_IMPACT_PHASE = "impact_phase"
STATE_STILLNESS_PHASE = "stillness_phase"
STATE_CONFIRMED_FALL = "confirmed_fall"


# MEDICINE ROSTER VIEW
class MedicineRosterView(Frame):
    """Medicine roster and schedule viewer"""

    def __init__(self, parent, db, patient_data):
        super().__init__(parent, bg="#1a1a1a")
        self.db = db
        self.patient_data = patient_data

        # Title
        title_frame = Frame(self, bg="#2d2d2d", height=60)
        title_frame.pack(fill=tk.X, padx=2, pady=2)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text=f"Medicine Roster - {patient_data[1]} (Bed: {patient_data[5]})",
            font=("Arial", 16, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Add Medicine Button
        Button(
            title_frame,
            text="➕ Add Medicine",
            command=self.add_medicine,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=10)

        # Refresh Button
        Button(
            title_frame,
            text="🔄 Refresh",
            command=self.refresh_list,
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 10),
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

        # Medicine List (Treeview)
        tree_container = Frame(self, bg="#1a1a1a")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Configure style
        style = ttk.Style()
        style.configure(
            "Medicine.Treeview",
            background="#1a1a1a",
            foreground="#ffffff",
            fieldbackground="#1a1a1a",
            font=("Arial", 10),
        )
        style.configure(
            "Medicine.Treeview.Heading",
            background="#2d2d2d",
            foreground="#00a8ff",
            font=("Arial", 11, "bold"),
        )

        columns = ("id", "medicine", "dosage", "frequency", "start", "end", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Medicine.Treeview",
            selectmode="browse",
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("medicine", text="Medicine Name")
        self.tree.heading("dosage", text="Dosage")
        self.tree.heading("frequency", text="Frequency")
        self.tree.heading("start", text="Start Date")
        self.tree.heading("end", text="End Date")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("medicine", width=200, anchor="w")
        self.tree.column("dosage", width=120, anchor="center")
        self.tree.column("frequency", width=150, anchor="center")
        self.tree.column("start", width=100, anchor="center")
        self.tree.column("end", width=100, anchor="center")
        self.tree.column("status", width=100, anchor="center")

        scrollbar = Scrollbar(tree_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action Buttons
        action_frame = Frame(self, bg="#1a1a1a")
        action_frame.pack(pady=15)

        Button(
            action_frame,
            text="✓ Mark Completed",
            command=self.mark_completed,
            bg="#00a8ff",
            fg="#ffffff",
            font=("Arial", 11),
            padx=20,
            pady=10,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        Button(
            action_frame,
            text="✕ Discontinue",
            command=self.discontinue,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11),
            padx=20,
            pady=10,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        self.refresh_list()

    def refresh_list(self):
        """Refresh medicine list"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        medicines = self.db.get_patient_medicines(
            self.patient_data[0], active_only=False
        )

        for med in medicines:
            med_id, _, name, dosage, freq, start, end, _, _, status, _ = med
            self.tree.insert(
                "",
                tk.END,
                values=(
                    med_id,
                    name,
                    dosage,
                    freq,
                    start,
                    end or "Ongoing",
                    status.upper(),
                ),
            )

    def add_medicine(self):
        """Open dialog to add new medicine"""
        dialog = Toplevel(self)
        dialog.title("Add Medicine")
        dialog.geometry("500x450")
        dialog.configure(bg="#1a1a1a")
        dialog.transient(self)
        dialog.grab_set()

        # Form fields
        fields = {}

        Label(
            dialog,
            text="Add New Medicine",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#00a8ff",
        ).pack(pady=15)

        form = Frame(dialog, bg="#1a1a1a")
        form.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # Medicine Name
        Label(
            form,
            text="Medicine Name*",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
        ).pack(anchor="w", pady=(10, 5))
        fields["name"] = Entry(
            form, font=("Arial", 11), bg="#2d2d2d", fg="#ffffff", relief=tk.FLAT
        )
        fields["name"].pack(fill=tk.X, ipady=8, ipadx=10)

        # Dosage
        Label(
            form, text="Dosage*", font=("Arial", 10, "bold"), bg="#1a1a1a", fg="#ffffff"
        ).pack(anchor="w", pady=(10, 5))
        fields["dosage"] = Entry(
            form, font=("Arial", 11), bg="#2d2d2d", fg="#ffffff", relief=tk.FLAT
        )
        fields["dosage"].pack(fill=tk.X, ipady=8, ipadx=10)

        # Frequency
        Label(
            form,
            text="Frequency*",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
        ).pack(anchor="w", pady=(10, 5))
        fields["frequency"] = ttk.Combobox(
            form,
            values=[
                "Once daily",
                "Twice daily",
                "Three times daily",
                "Four times daily",
                "Every 6 hours",
                "Every 8 hours",
                "Every 12 hours",
                "As needed",
            ],
            state="readonly",
            font=("Arial", 11),
        )
        fields["frequency"].pack(fill=tk.X, ipady=8)

        # Start Date
        Label(
            form,
            text="Start Date* (YYYY-MM-DD)",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
        ).pack(anchor="w", pady=(10, 5))
        fields["start_date"] = Entry(
            form, font=("Arial", 11), bg="#2d2d2d", fg="#ffffff", relief=tk.FLAT
        )
        fields["start_date"].insert(0, datetime.now().strftime("%Y-%m-%d"))
        fields["start_date"].pack(fill=tk.X, ipady=8, ipadx=10)

        # Notes
        Label(
            form, text="Notes", font=("Arial", 10, "bold"), bg="#1a1a1a", fg="#ffffff"
        ).pack(anchor="w", pady=(10, 5))
        fields["notes"] = Entry(
            form, font=("Arial", 11), bg="#2d2d2d", fg="#ffffff", relief=tk.FLAT
        )
        fields["notes"].pack(fill=tk.X, ipady=8, ipadx=10)

        # Buttons
        btn_frame = Frame(dialog, bg="#1a1a1a")
        btn_frame.pack(pady=20)

        def save():
            name = fields["name"].get().strip()
            dosage = fields["dosage"].get().strip()
            freq = fields["frequency"].get()
            start = fields["start_date"].get().strip()
            notes = fields["notes"].get().strip() or None

            if not all([name, dosage, freq, start]):
                messagebox.showerror("Error", "Please fill all required fields!")
                return

            medicine_data = {
                "patient_id": self.patient_data[0],
                "medicine_name": name,
                "dosage": dosage,
                "frequency": freq,
                "start_date": start,
                "end_date": None,
                "time_slots": [],
                "instructions": notes,
            }
            self.db.add_medicine(medicine_data)
            messagebox.showinfo("Success", "Medicine added successfully!")
            dialog.destroy()
            self.refresh_list()

        Button(
            btn_frame,
            text="✓ Save",
            command=save,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=10,
        ).pack(side=tk.LEFT, padx=5)

        Button(
            btn_frame,
            text="✕ Cancel",
            command=dialog.destroy,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11),
            padx=30,
            pady=10,
        ).pack(side=tk.LEFT, padx=5)

    def mark_completed(self):
        """Mark selected medicine as completed"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a medicine")
            return

        med_id = self.tree.item(selection[0], "values")[0]
        self.db.update_medicine_status(med_id, "completed")
        messagebox.showinfo("Success", "Medicine marked as completed")
        self.refresh_list()

    def discontinue(self):
        """Discontinue selected medicine"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a medicine")
            return

        med_id = self.tree.item(selection[0], "values")[0]
        confirm = messagebox.askyesno("Confirm", "Discontinue this medicine?")
        if confirm:
            self.db.update_medicine_status(med_id, "discontinued")
            messagebox.showinfo("Success", "Medicine discontinued")
            self.refresh_list()


# ENHANCED NEW PATIENT FORM
class NewPatientForm(Frame):
    """Modern patient registration form with dropdowns for gender and blood group"""

    def __init__(self, parent, db, on_save_callback):
        super().__init__(parent, bg="#1a1a1a")
        self.db = db
        self.on_save_callback = on_save_callback

        # Title
        title_frame = Frame(self, bg="#2d2d2d", height=60)
        title_frame.pack(fill=tk.X, padx=2, pady=2)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="New Patient Registration",
            font=("Arial", 16, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(pady=15)

        # Form container with grid layout
        form_container = Frame(self, bg="#1a1a1a")
        form_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Configure grid weights for responsive layout
        form_container.grid_columnconfigure(1, weight=1)

        self.entries = {}
        row = 0

        # Name field
        self._create_field(
            form_container, row, "Full Name*", "name", field_type="entry"
        )
        row += 1

        # Age field
        self._create_field(form_container, row, "Age", "age", field_type="entry")
        row += 1

        # Gender dropdown - ENHANCED
        self._create_field(
            form_container,
            row,
            "Gender",
            "gender",
            field_type="dropdown",
            options=["Male", "Female", "Other"],
        )
        row += 1

        # Blood Group dropdown - ENHANCED
        self._create_field(
            form_container,
            row,
            "Blood Group",
            "blood_group",
            field_type="dropdown",
            options=["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
        )
        row += 1

        # Bed Number field
        self._create_field(
            form_container, row, "Bed Number*", "bed_number", field_type="entry"
        )
        row += 1

        # Emergency Contact
        self._create_field(
            form_container,
            row,
            "Emergency Contact",
            "emergency_contact",
            field_type="entry",
        )
        row += 1

        # Doctor Name
        self._create_field(
            form_container, row, "Doctor Name", "doctor_name", field_type="entry"
        )
        row += 1

        # Medical Condition
        self._create_field(
            form_container,
            row,
            "Medical Condition",
            "medical_condition",
            field_type="entry",
        )
        row += 1

        # Button frame
        btn_frame = Frame(self, bg="#1a1a1a")
        btn_frame.pack(pady=20)

        Button(
            btn_frame,
            text="✓ Save Patient",
            command=self.save_patient,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        Button(
            btn_frame,
            text="✕ Clear Form",
            command=self.clear_form,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11),
            padx=30,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

    def _create_field(
        self, parent, row, label_text, key, field_type="entry", options=None
    ):
        """Creates a form field with label and input widget"""

        # Label
        Label(
            parent,
            text=label_text,
            font=("Arial", 11, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
            anchor="w",
        ).grid(row=row, column=0, sticky="w", pady=8, padx=(0, 15))

        # Input widget based on type
        if field_type == "entry":
            widget = Entry(
                parent,
                font=("Arial", 11),
                bg="#2d2d2d",
                fg="#ffffff",
                insertbackground="#ffffff",
                relief=tk.FLAT,
                bd=0,
            )
            widget.grid(row=row, column=1, sticky="ew", pady=8, ipady=8, ipadx=10)
            self.entries[key] = widget

        elif field_type == "dropdown":
            # FIXED COLORS - More visible
            style = ttk.Style()
            style.theme_use("clam")

            # Create unique style name for each dropdown
            style_name = f"{key}.TCombobox"

            style.configure(
                style_name,
                fieldbackground="#3d3d3d",  # Lighter background
                background="#3d3d3d",
                foreground="#ffffff",  # White text
                selectbackground="#00a8ff",
                selectforeground="#000000",
                arrowcolor="#00ff88",  # Bright green arrow
                borderwidth=1,
                relief=tk.FLAT,
            )

            style.map(
                style_name,
                fieldbackground=[("readonly", "#3d3d3d")],
                foreground=[("readonly", "#ffffff")],
                selectbackground=[("readonly", "#00a8ff")],
                selectforeground=[("readonly", "#000000")],
            )

            widget = ttk.Combobox(
                parent,
                values=options,
                state="readonly",
                font=("Arial", 11, "bold"),
                style=style_name,
            )  # Made font bold
            widget.grid(row=row, column=1, sticky="ew", pady=8, ipady=8)

            # Set default text
            if options:
                widget.set(f"Select {label_text}")

            # Make dropdown list more visible
            widget.option_add("*TCombobox*Listbox.background", "#2d2d2d")
            widget.option_add("*TCombobox*Listbox.foreground", "#ffffff")
            widget.option_add("*TCombobox*Listbox.selectBackground", "#00a8ff")
            widget.option_add("*TCombobox*Listbox.selectForeground", "#000000")
            widget.option_add("*TCombobox*Listbox.font", ("Arial", 11))

            self.entries[key] = widget

    def save_patient(self):
        """Validates and saves patient data"""

        # Validate required fields
        name = self.entries["name"].get().strip()
        bed = self.entries["bed_number"].get().strip()

        if not name:
            messagebox.showerror("Validation Error", "Patient name is required!")
            return

        if not bed:
            messagebox.showerror("Validation Error", "Bed number is required!")
            return

        # Collect data
        gender = self.entries["gender"].get()
        if gender.startswith("Select"):
            gender = None

        blood = self.entries["blood_group"].get()
        if blood.startswith("Select"):
            blood = None

        patient_data = {
            "name": name,
            "age": self.entries["age"].get().strip() or None,
            "gender": gender,
            "blood_group": blood,
            "bed_number": bed,
            "emergency_contact": self.entries["emergency_contact"].get().strip()
            or None,
            "doctor_name": self.entries["doctor_name"].get().strip() or None,
            "medical_condition": self.entries["medical_condition"].get().strip()
            or None,
            "admission_date": datetime.now().strftime("%Y-%m-%d"),
            "photo_path": None,
        }

        # Save to database
        patient_id = self.db.add_patient(patient_data)
        messagebox.showinfo(
            "Success", f"✓ Patient registered successfully!\nPatient ID: {patient_id}"
        )

        # Clear form and notify callback
        self.clear_form()
        if self.on_save_callback:
            self.on_save_callback()

    def clear_form(self):
        """Clears all form fields"""
        for key, widget in self.entries.items():
            if isinstance(widget, Entry):
                widget.delete(0, tk.END)
            elif isinstance(widget, ttk.Combobox):
                widget.set("")


# ENHANCED PATIENT LIST VIEW
class PatientListView(Frame):
    """Modern patient list using Treeview - Windows Explorer style"""

    def __init__(self, parent, db, on_select_callback):
        super().__init__(parent, bg="#1a1a1a")
        self.db = db
        self.on_select_callback = on_select_callback

        # Title bar
        title_frame = Frame(self, bg="#2d2d2d", height=60)
        title_frame.pack(fill=tk.X, padx=2, pady=2)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="Patient Database",
            font=("Arial", 16, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Refresh button
        Button(
            title_frame,
            text="🔄 Refresh",
            command=self.refresh_list,
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 10),
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

        # Delete button
        Button(
            title_frame,
            text="🗑 Delete",
            command=self.delete_patient,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 10),
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

        # Discharge button
        Button(
            title_frame,
            text="📤 Discharge",
            command=self.discharge_patient,
            bg="#ffd700",
            fg="#000000",
            font=("Arial", 10),
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=5)

        # Search bar
        search_frame = Frame(self, bg="#1a1a1a")
        search_frame.pack(fill=tk.X, padx=20, pady=10)

        Label(
            search_frame, text="🔍", font=("Arial", 14), bg="#1a1a1a", fg="#ffffff"
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.search_var = StringVar()
        self.search_var.trace("w", lambda *args: self.filter_patients())

        search_entry = Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Arial", 11),
            bg="#2d2d2d",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            bd=0,
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, ipadx=10)

        # Treeview container
        tree_container = Frame(self, bg="#1a1a1a")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # Configure Treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background="#1a1a1a",
            foreground="#ffffff",
            fieldbackground="#1a1a1a",
            borderwidth=0,
            font=("Arial", 10),
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2d2d2d",
            foreground="#00a8ff",
            borderwidth=0,
            font=("Arial", 11, "bold"),
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", "#00a8ff")],
            foreground=[("selected", "#000000")],
        )

        # Create Treeview with columns
        columns = ("id", "name", "age", "gender", "blood", "bed", "status")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse",
        )

        # Define column headings and widths
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Patient Name")
        self.tree.heading("age", text="Age")
        self.tree.heading("gender", text="Gender")
        self.tree.heading("blood", text="Blood Group")
        self.tree.heading("bed", text="Bed No.")
        self.tree.heading("status", text="Status")

        # Set column widths
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("age", width=60, anchor="center")
        self.tree.column("gender", width=80, anchor="center")
        self.tree.column("blood", width=100, anchor="center")
        self.tree.column("bed", width=80, anchor="center")
        self.tree.column("status", width=100, anchor="center")

        # Scrollbar
        scrollbar = Scrollbar(tree_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        btn_frame = Frame(self, bg="#1a1a1a")
        btn_frame.pack(pady=15)

        Button(
            btn_frame,
            text="✓ Select Patient",
            command=self.select_patient,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        # Load patients
        self.all_patients = []
        self.refresh_list()

        # Double-click to select
        self.tree.bind("<Double-1>", lambda e: self.select_patient())

    def refresh_list(self):
        """Reloads patient list from database"""
        self.all_patients = self.db.get_all_patients()
        self.filter_patients()

    def filter_patients(self):
        """Filters patients based on search query"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().lower()

        for patient in self.all_patients:
            # patient = (id, name, age, gender, blood_group, bed_number, ...)
            patient_id = patient[0]
            name = patient[1] or ""
            age = patient[2] or "N/A"
            gender = patient[3] or "N/A"
            blood = patient[4] or "N/A"
            bed = patient[5] or "N/A"
            status = "Active"

            # Filter logic
            if (
                query
                and query not in str(name).lower()
                and query not in str(bed).lower()
            ):
                continue

            # Insert row with alternating colors
            tags = (
                ("evenrow",) if len(self.tree.get_children()) % 2 == 0 else ("oddrow",)
            )
            self.tree.insert(
                "",
                tk.END,
                values=(patient_id, name, age, gender, blood, bed, status),
                tags=tags,
            )

        # Configure row colors
        self.tree.tag_configure("evenrow", background="#1a1a1a")
        self.tree.tag_configure("oddrow", background="#252525")

    def select_patient(self):
        """Returns selected patient to callback"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a patient from the list"
            )
            return

        # Get patient ID from selected row
        values = self.tree.item(selection[0], "values")
        patient_id = int(values[0])

        # Find full patient data
        patient_data = None
        for p in self.all_patients:
            if p[0] == patient_id:
                patient_data = p
                break

        if patient_data and self.on_select_callback:
            self.on_select_callback(patient_data)

    def delete_patient(self):
        """Deletes selected patient from database"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a patient to delete")
            return

        values = self.tree.item(selection[0], "values")
        patient_id = int(values[0])
        patient_name = values[1]

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete patient:\n\n{patient_name} (ID: {patient_id})\n\nThis action cannot be undone!",
        )

        if confirm:
            try:
                # Delete from database
                self.db.delete_patient(patient_id)
                messagebox.showinfo(
                    "Success", f"Patient {patient_name} has been deleted"
                )
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete patient:\n{str(e)}")

    def discharge_patient(self):
        """Discharges selected patient"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a patient to discharge"
            )
            return

        values = self.tree.item(selection[0], "values")
        patient_id = int(values[0])
        patient_name = values[1]

        # Confirm discharge
        confirm = messagebox.askyesno(
            "Confirm Discharge",
            f"Discharge patient:\n\n{patient_name} (ID: {patient_id})\n\nThis will mark the patient as discharged.",
        )

        if confirm:
            try:
                # Update discharge date in database
                self.db.discharge_patient(patient_id)
                messagebox.showinfo(
                    "Success", f"Patient {patient_name} has been discharged"
                )
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to discharge patient:\n{str(e)}")


# ENHANCED SETTINGS PANEL
class SettingsPanel(Frame):
    """Settings panel integrated in main window"""

    def __init__(self, parent, config):
        super().__init__(parent, bg="#1a1a1a")
        self.config = config

        # Title
        title_frame = Frame(self, bg="#2d2d2d", height=60)
        title_frame.pack(fill=tk.X, padx=2, pady=2)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="Detection Settings",
            font=("Arial", 16, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(pady=15)

        # Scrollable settings
        canvas = tk.Canvas(self, bg="#1a1a1a", highlightthickness=0)
        scrollbar = Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#1a1a1a")

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Settings
        self.sliders = {}
        settings = [
            ("Drop Speed Threshold", "drop_speed_threshold", 10, 100),
            ("Aspect Ratio Threshold", "aspect_ratio_threshold", 0.5, 3.0),
            ("Impact Movement Time (s)", "impact_movement_time", 0.1, 3.0),
            ("Stillness Time (s)", "stillness_time", 0.5, 5.0),
            ("Min Movement Threshold", "min_movement_threshold", 1, 20),
            ("Cooldown Time (s)", "cooldown_time", 5, 60),
            ("Video Buffer (s)", "video_buffer_seconds", 3, 15),
        ]

        for label, key, min_val, max_val in settings:
            frame = Frame(scrollable_frame, bg="#2d2d2d")
            frame.pack(fill=tk.X, padx=20, pady=8)

            Label(
                frame,
                text=label,
                font=("Arial", 11, "bold"),
                bg="#2d2d2d",
                fg="#ffffff",
            ).pack(anchor="w", padx=10, pady=5)

            value_label = Label(
                frame,
                text=f"{config[key]:.2f}",
                font=("Arial", 10),
                bg="#2d2d2d",
                fg="#00a8ff",
            )
            value_label.pack(anchor="e", padx=10)

            slider = Scale(
                frame,
                from_=min_val,
                to=max_val,
                resolution=0.1 if max_val <= 10 else 1,
                orient=HORIZONTAL,
                bg="#2d2d2d",
                fg="#ffffff",
                highlightthickness=0,
                troughcolor="#1a1a1a",
                command=lambda v, l=value_label: l.config(text=f"{float(v):.2f}"),
            )
            slider.set(config[key])
            slider.pack(fill=tk.X, padx=10, pady=5)

            self.sliders[key] = slider

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Checkboxes
        check_frame = Frame(self, bg="#1a1a1a")
        check_frame.pack(fill=tk.X, padx=20, pady=15)

        self.audio_var = BooleanVar(value=config.get("audio_alerts_enabled", True))
        tk.Checkbutton(
            check_frame,
            text="🔊 Audio Alerts",
            variable=self.audio_var,
            font=("Arial", 11),
            bg="#1a1a1a",
            fg="#ffffff",
            selectcolor="#2d2d2d",
            activebackground="#1a1a1a",
            activeforeground="#ffffff",
        ).pack(anchor="w", pady=5)

        self.video_var = BooleanVar(value=config.get("auto_record_video", True))
        tk.Checkbutton(
            check_frame,
            text="🎥 Auto Record Videos",
            variable=self.video_var,
            font=("Arial", 11),
            bg="#1a1a1a",
            fg="#ffffff",
            selectcolor="#2d2d2d",
            activebackground="#1a1a1a",
            activeforeground="#ffffff",
        ).pack(anchor="w", pady=5)

        # Buttons
        btn_frame = Frame(self, bg="#1a1a1a")
        btn_frame.pack(pady=20)

        Button(
            btn_frame,
            text="✓ Save Settings",
            command=self.save_settings,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        Button(
            btn_frame,
            text="↺ Reset Defaults",
            command=self.reset_defaults,
            bg="#ffd700",
            fg="#000000",
            font=("Arial", 11),
            padx=30,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

    def save_settings(self):
        for key, slider in self.sliders.items():
            self.config[key] = slider.get()

        self.config["audio_alerts_enabled"] = self.audio_var.get()
        self.config["auto_record_video"] = self.video_var.get()

        save_config()
        messagebox.showinfo("Success", "✓ Settings saved successfully!")

    def reset_defaults(self):
        defaults = {
            "drop_speed_threshold": 35,
            "aspect_ratio_threshold": 1.25,
            "impact_movement_time": 0.8,
            "stillness_time": 1.0,
            "min_movement_threshold": 4,
            "cooldown_time": 10,
            "video_buffer_seconds": 5,
        }

        for key, slider in self.sliders.items():
            if key in defaults:
                slider.set(defaults[key])


# MONITORING VIEW - FIXED
class MonitoringView(Frame):
    """Main monitoring interface with video feed and controls - FULLY FIXED"""

    def __init__(self, parent, patient_data, db, video_recorder, audio_alerts):
        super().__init__(parent, bg="#1a1a1a")
        self.patient_data = patient_data
        self.db = db
        self.video_recorder = video_recorder
        self.audio_alerts = audio_alerts

        # Detection variables
        self.model = YOLO(MODEL)
        self.cap = None
        self.running = False
        self.thread = None
        self.current_frame = None
        self.fps = 0
        self.frame_count = 0
        self.fps_timer = time.time()

        # Fall detection state
        self.state = STATE_MONITOR
        self.prev_cy = None
        self.movement_history = []
        self.fall_time = 0
        self.impact_start = 0
        self.still_start = 0
        self.last_alert = 0
        self.snapshot_path = ""
        self.video_path = ""
        self.last_confidence = 0.0
        self.fall_start_time = None

        # UI variables
        self.status_text = StringVar(value="Ready to Monitor")
        self.fps_text = StringVar(value="FPS: 0")
        self.confidence_text = StringVar(value="Confidence: 0%")
        self.alerts_enabled = BooleanVar(value=True)
        self.camera_status = StringVar(value="● Camera: OFF")
        self.preview_active = False  # For camera preview

        self.build_ui()
        self.update_gui_frame()

    def add_log_entry(self, text, color=None):
        """Add entry to event log"""
        try:
            self.log_text.config(state="normal")
            timestamp = time.strftime("%H:%M:%S")
            entry = f"[{timestamp}] {text}\n"

            if color:
                tag = f"color_{color}"
                self.log_text.tag_config(tag, foreground=color)
                self.log_text.insert("end", entry, tag)
            else:
                self.log_text.insert("end", entry)

            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except:
            pass

    def show_medicine_roster(self):
        """Open medicine roster window"""
        roster_window = Toplevel(self)
        roster_window.title(f"Medicine Roster - {self.patient_data[1]}")
        roster_window.geometry("1200x700")
        roster_window.configure(bg="#1a1a1a")
        roster_window.transient(self.master)

        # Center the window
        roster_window.update_idletasks()
        x = (roster_window.winfo_screenwidth() // 2) - (1200 // 2)
        y = (roster_window.winfo_screenheight() // 2) - (700 // 2)
        roster_window.geometry(f"1200x700+{x}+{y}")

        roster_view = MedicineRosterView(roster_window, self.db, self.patient_data)
        roster_view.pack(fill=tk.BOTH, expand=True)

    def show_patient_info(self):
        """Show detailed patient information"""
        patient = self.patient_data

        # Create info window - LARGER AND RESIZABLE
        info_window = Toplevel(self)
        info_window.title(f"Patient Information - {patient[1]}")
        info_window.geometry("900x800")  # Increased from 600x700
        info_window.configure(bg="#1a1a1a")
        info_window.transient(self.master)
        info_window.resizable(True, True)  # Made resizable
        info_window.minsize(700, 600)  # Set minimum size

        # Center window
        info_window.update_idletasks()
        x = (info_window.winfo_screenwidth() // 2) - (900 // 2)
        y = (info_window.winfo_screenheight() // 2) - (800 // 2)
        info_window.geometry(f"900x800+{x}+{y}")

        # Title
        title_frame = Frame(info_window, bg="#2d2d2d", height=70)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        Label(
            title_frame,
            text="Patient Information",
            font=("Arial", 18, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(side=tk.LEFT, padx=20, pady=20)

        # Status badge
        status_color = (
            "#00ff88"
            if (patient[11] if len(patient) > 11 else "Active") == "Active"
            else "#ffd700"
        )
        Label(
            title_frame,
            text=f"● {patient[11] if len(patient) > 11 else 'Active'}",
            font=("Arial", 12, "bold"),
            bg="#2d2d2d",
            fg=status_color,
        ).pack(side=tk.RIGHT, padx=20, pady=20)

        # Main container with grid for better layout
        main_container = Frame(info_window, bg="#1a1a1a")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Scrollable content
        canvas = tk.Canvas(main_container, bg="#1a1a1a", highlightthickness=0)
        scrollbar = Scrollbar(main_container, orient="vertical", command=canvas.yview)
        content_frame = Frame(canvas, bg="#1a1a1a")

        content_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # PATIENT DETAILS SECTION
        Label(
            content_frame,
            text="Personal Information",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#00a8ff",
        ).pack(anchor="w", padx=10, pady=(10, 15))

        # Patient details with better spacing
        details = [
            ("Patient ID", patient[0]),
            ("Full Name", patient[1]),
            ("Age", patient[2] or "N/A"),
            ("Gender", patient[3] or "N/A"),
            ("Blood Group", patient[4] or "N/A"),
            ("Bed Number", patient[5]),
            ("Emergency Contact", patient[6] or "N/A"),
            ("Doctor Name", patient[7] or "N/A"),
            ("Admission Date", patient[8] or "N/A"),
            ("Medical Condition", patient[9] or "N/A"),
        ]

        for label, value in details:
            # Field container - LARGER
            field_frame = Frame(content_frame, bg="#2d2d2d", height=50)
            field_frame.pack(fill=tk.X, padx=10, pady=6)
            field_frame.pack_propagate(False)

            Label(
                field_frame,
                text=label,
                font=("Arial", 12, "bold"),
                bg="#2d2d2d",
                fg="#ffffff",
                anchor="w",
            ).pack(side=tk.LEFT, padx=20, pady=12, fill=tk.Y)

            # Value with text wrapping for long content
            value_label = Label(
                field_frame,
                text=str(value),
                font=("Arial", 12),
                bg="#2d2d2d",
                fg="#00a8ff",
                anchor="e",
                wraplength=450,
            )
            value_label.pack(side=tk.RIGHT, padx=20, pady=12, fill=tk.Y)

        # STATISTICS SECTION
        stats_frame = Frame(content_frame, bg="#1a1a1a")
        stats_frame.pack(fill=tk.X, padx=10, pady=(20, 10))

        Label(
            stats_frame,
            text="Fall Incident Statistics",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#00a8ff",
        ).pack(anchor="w", pady=(0, 15))

        # Get statistics
        try:
            stats = self.db.get_incident_statistics(patient[0])

            # Create stats cards
            stats_container = Frame(stats_frame, bg="#1a1a1a")
            stats_container.pack(fill=tk.X)

            # Total incidents card
            card1 = Frame(stats_container, bg="#2d2d2d", height=80)
            card1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            card1.pack_propagate(False)

            Label(
                card1,
                text="TOTAL INCIDENTS",
                font=("Arial", 10, "bold"),
                bg="#2d2d2d",
                fg="#a0a0a0",
            ).pack(pady=(12, 5))
            Label(
                card1,
                text=str(stats["total"]),
                font=("Arial", 24, "bold"),
                bg="#2d2d2d",
                fg="#ff4757",
            ).pack()

            # This week card
            card2 = Frame(stats_container, bg="#2d2d2d", height=80)
            card2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            card2.pack_propagate(False)

            Label(
                card2,
                text="THIS WEEK",
                font=("Arial", 10, "bold"),
                bg="#2d2d2d",
                fg="#a0a0a0",
            ).pack(pady=(12, 5))
            Label(
                card2,
                text=str(stats["this_week"]),
                font=("Arial", 24, "bold"),
                bg="#2d2d2d",
                fg="#ffd700",
            ).pack()

            # Average per week (if we have data)
            if stats["total"] > 0:
                card3 = Frame(stats_container, bg="#2d2d2d", height=80)
                card3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                card3.pack_propagate(False)

                Label(
                    card3,
                    text="STATUS",
                    font=("Arial", 10, "bold"),
                    bg="#2d2d2d",
                    fg="#a0a0a0",
                ).pack(pady=(12, 5))

                status_txt = "MONITOR" if stats["this_week"] > 2 else "NORMAL"
                status_color = "#ff4757" if stats["this_week"] > 2 else "#00ff88"
                Label(
                    card3,
                    text=status_txt,
                    font=("Arial", 16, "bold"),
                    bg="#2d2d2d",
                    fg=status_color,
                ).pack()

        except Exception as e:
            Label(
                stats_frame,
                text="No incident data available",
                font=("Arial", 11),
                bg="#1a1a1a",
                fg="#666666",
            ).pack(anchor="w", pady=5)

        # Pack canvas and scrollbar
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Action buttons at bottom
        btn_container = Frame(info_window, bg="#1a1a1a")
        btn_container.pack(fill=tk.X, pady=15)

        btn_frame = Frame(btn_container, bg="#1a1a1a")
        btn_frame.pack()

        Button(
            btn_frame,
            text="📋 View Full History",
            command=lambda: self.show_incident_history(patient[0]),
            bg="#00a8ff",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=25,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        Button(
            btn_frame,
            text="✕ Close",
            command=info_window.destroy,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=25,
            pady=12,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=5)

        # Cleanup mousewheel binding when window closes
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            info_window.destroy()

        info_window.protocol("WM_DELETE_WINDOW", on_close)

    def show_incident_history(self, patient_id):
        """Show detailed incident history"""
        history_window = Toplevel(self)
        history_window.title("Fall Incident History")
        history_window.geometry("1000x600")
        history_window.configure(bg="#1a1a1a")

        # Title
        Label(
            history_window,
            text="Fall Incident History",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#00a8ff",
        ).pack(pady=15)

        # Treeview for incidents
        tree_container = Frame(history_window, bg="#1a1a1a")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        style = ttk.Style()
        style.configure(
            "History.Treeview",
            background="#1a1a1a",
            foreground="#ffffff",
            fieldbackground="#1a1a1a",
            font=("Arial", 10),
        )
        style.configure(
            "History.Treeview.Heading",
            background="#2d2d2d",
            foreground="#00a8ff",
            font=("Arial", 11, "bold"),
        )

        columns = ("id", "time", "type", "response", "notes")
        tree = ttk.Treeview(
            tree_container, columns=columns, show="headings", style="History.Treeview"
        )

        tree.heading("id", text="ID")
        tree.heading("time", text="Incident Time")
        tree.heading("type", text="Type")
        tree.heading("response", text="Response Time (s)")
        tree.heading("notes", text="Notes")

        tree.column("id", width=50, anchor="center")
        tree.column("time", width=180, anchor="w")
        tree.column("type", width=150, anchor="center")
        tree.column("response", width=120, anchor="center")
        tree.column("notes", width=400, anchor="w")

        scrollbar = Scrollbar(tree_container, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load incidents
        incidents = self.db.get_patient_incidents(patient_id, limit=100)
        for inc in incidents:
            # inc = (id, patient_id, incident_time, incident_type, snapshot, video, response_time, notes)
            tree.insert(
                "",
                tk.END,
                values=(
                    inc[0],
                    inc[2],
                    inc[3] or "Fall",
                    inc[6] or "N/A",
                    inc[7] or "No notes",
                ),
            )

        # Close button
        Button(
            history_window,
            text="✕ Close",
            command=history_window.destroy,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=30,
            pady=12,
        ).pack(pady=15)

    def build_ui(self):
        # Configure main frame grid for proper layout control
        self.grid_rowconfigure(0, weight=0)  # Patient bar - fixed
        self.grid_rowconfigure(1, weight=1)  # Content - flexible
        self.grid_rowconfigure(2, weight=0)  # Control bar - fixed at bottom
        self.grid_columnconfigure(0, weight=1)

        # Top bar - Patient info (ROW 0)
        patient_bar = Frame(self, bg="#2d2d2d", height=80)
        patient_bar.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        patient_bar.grid_propagate(False)

        Label(
            patient_bar,
            text=f"Monitoring: {self.patient_data[1]}",
            font=("Arial", 14, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(side=tk.LEFT, padx=20, pady=10)

        info_text = (
            f"Bed: {self.patient_data[5]} | Age: {self.patient_data[2] or 'N/A'}"
        )
        Label(
            patient_bar, text=info_text, font=("Arial", 10), bg="#2d2d2d", fg="#a0a0a0"
        ).place(x=20, y=45)

        # Status indicators
        status_frame = Frame(patient_bar, bg="#2d2d2d")
        status_frame.pack(side=tk.RIGHT, padx=20)

        Label(
            status_frame,
            textvariable=self.camera_status,
            font=("Arial", 10, "bold"),
            bg="#2d2d2d",
            fg="#00ff88",
        ).pack(anchor="e")
        Label(
            status_frame,
            textvariable=self.fps_text,
            font=("Arial", 10),
            bg="#2d2d2d",
            fg="#ffffff",
        ).pack(anchor="e")
        Label(
            status_frame,
            textvariable=self.status_text,
            font=("Arial", 11, "bold"),
            bg="#2d2d2d",
            fg="#00ff88",
        ).pack(anchor="e")

        # Main content - 2 column layout (ROW 1 - EXPANDABLE)
        content = Frame(self, bg="#1a1a1a")
        content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Configure content grid
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)  # Video side
        content.grid_columnconfigure(1, weight=0)  # Sidebar

        # Left: Video feed
        left = Frame(content, bg="#1a1a1a")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        left.grid_rowconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=0)
        left.grid_columnconfigure(0, weight=1)

        video_container = Frame(left, bg="#000000")
        video_container.grid(row=0, column=0, sticky="nsew")

        self.video_label = Label(
            video_container,
            bg="#000000",
            text="Camera Off",
            fg="#666666",
            font=("Arial", 24),
        )
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # Confidence bar
        conf_frame = Frame(left, bg="#2d2d2d", height=40)
        conf_frame.grid(row=1, column=0, sticky="ew")
        conf_frame.grid_propagate(False)

        Label(
            conf_frame,
            textvariable=self.confidence_text,
            font=("Arial", 10),
            bg="#2d2d2d",
            fg="#ffffff",
        ).pack(side=tk.LEFT, padx=15, pady=10)

        # Right: Snapshot + Log
        right = Frame(content, bg="#1a1a1a", width=450)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.grid_propagate(False)

        # Snapshot
        Label(
            right,
            text="Latest Snapshot",
            font=("Arial", 12, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.snapshot_label = Label(
            right, bg="#000000", text="No snapshot", fg="#666666", height=10
        )
        self.snapshot_label.pack(fill=tk.X, padx=10)

        # Event log
        Label(
            right,
            text="Event Log",
            font=("Arial", 11, "bold"),
            bg="#1a1a1a",
            fg="#ffffff",
        ).pack(anchor="w", padx=10, pady=(15, 5))

        log_container = Frame(right, bg="#1a1a1a")
        log_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = Text(
            log_container,
            bg="#1a1a1a",
            fg="#ffffff",
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set,
            wrap="word",
            state="disabled",
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Alert checkbox
        tk.Checkbutton(
            right,
            text="📱 Enable Telegram Alerts",
            variable=self.alerts_enabled,
            font=("Arial", 10),
            bg="#1a1a1a",
            fg="#ffffff",
            selectcolor="#2d2d2d",
            activebackground="#1a1a1a",
        ).pack(anchor="w", padx=10, pady=10)

        # Control buttons (ROW 2 - FIXED AT BOTTOM)
        control_bar = Frame(self, bg="#1a1a1a", height=80)
        control_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        control_bar.grid_propagate(False)

        # Configure grid for 6 buttons
        control_bar.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        # Row 1: Main controls
        self.start_btn = Button(
            control_bar,
            text="▶ Start Monitoring",
            command=self.start_monitoring,
            bg="#00ff88",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
        )
        self.start_btn.grid(row=0, column=0, padx=5, sticky="ew")

        self.stop_btn = Button(
            control_bar,
            text="⏸ Stop Monitoring",
            command=self.stop_monitoring,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, padx=5, sticky="ew")

        Button(
            control_bar,
            text="📷 Camera ON",
            command=self.camera_on,
            bg="#00a8ff",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
        ).grid(row=0, column=2, padx=5, sticky="ew")

        Button(
            control_bar,
            text="📷 Camera OFF",
            command=self.camera_off,
            bg="#ffd700",
            fg="#000000",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
        ).grid(row=0, column=3, padx=5, sticky="ew")

        Button(
            control_bar,
            text="💊 Medicine Roster",
            command=self.show_medicine_roster,
            bg="#9b59b6",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
        ).grid(row=0, column=4, padx=5, sticky="ew")

        Button(
            control_bar,
            text="👤 Patient Info",
            command=self.show_patient_info,
            bg="#3498db",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
        ).grid(row=0, column=5, padx=5, sticky="ew")

    def start_monitoring(self):
        if self.running:
            self.add_log_entry("Already monitoring", "#ffd700")
            return

        if not self.cap or not self.cap.isOpened():
            messagebox.showwarning(
                "Camera Not Ready",
                "Please turn ON the camera first using 'Camera ON' button",
            )
            return

        self.add_log_entry("Starting monitoring system...", "#00a8ff")
        self.running = True

        self.status_text.set("● MONITORING")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        # Play system start sound
        self.audio_alerts.play_alert("system_start")

        # Reset detection state
        self.state = STATE_MONITOR
        self.prev_cy = None
        self.movement_history = []

        # Start detection thread
        self.thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.thread.start()

        self.add_log_entry(f"Now monitoring: {self.patient_data[1]}", "#00ff88")

    def stop_monitoring(self):
        if not self.running:
            self.add_log_entry("Not currently monitoring", "#ffd700")
            return

        self.add_log_entry("Stopping monitoring...", "#ff4757")
        self.running = False

        self.status_text.set("● STOPPED")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

        # Play system stop sound
        self.audio_alerts.play_alert("system_stop")

        self.add_log_entry("Monitoring stopped", "#a0a0a0")

    def camera_on(self):
        """Turns camera ON without starting monitoring"""
        if self.cap and self.cap.isOpened():
            self.add_log_entry("Camera already ON", "#ffd700")
            return

        try:
            self.add_log_entry("Initializing camera...", "#00a8ff")
            self.cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)

            if not self.cap.isOpened():
                raise Exception("Cannot open camera")

            # Test read
            ret, frame = self.cap.read()
            if not ret:
                raise Exception("Cannot read from camera")

            self.camera_status.set("● Camera: LIVE")
            self.add_log_entry("✓ Camera initialized successfully", "#00ff88")
            messagebox.showinfo("Camera Ready", "Camera is now ON and ready to monitor")

            # Start preview loop
            self.preview_active = True
            self.preview_loop()

        except Exception as e:
            self.add_log_entry(f"✗ Camera error: {str(e)}", "#ff4757")
            messagebox.showerror(
                "Camera Error",
                f"Cannot access camera:\n{str(e)}\n\nMake sure:\n• Camera is connected\n• No other app is using it\n• Drivers are installed",
            )
            if self.cap:
                self.cap.release()
                self.cap = None

    def camera_off(self):
        """Turns camera OFF"""
        if self.running:
            messagebox.showwarning(
                "Stop Monitoring First",
                "Please stop monitoring before turning off the camera",
            )
            return

        if not self.cap:
            self.add_log_entry("Camera already OFF", "#ffd700")
            return

        self.add_log_entry("Turning camera OFF...", "#ff4757")
        self.preview_active = False

        try:
            self.cap.release()
        except:
            pass

        self.cap = None
        self.camera_status.set("● Camera: OFF")
        self.current_frame = None
        self.add_log_entry("✓ Camera turned OFF", "#a0a0a0")
        messagebox.showinfo("Camera Off", "Camera has been turned OFF")

    def preview_loop(self):
        """Shows camera preview when not monitoring"""
        if not self.preview_active or not self.cap or self.running:
            return

        try:
            ret, frame = self.cap.read()
            if ret:
                # Draw preview text
                cv2.putText(
                    frame,
                    "CAMERA PREVIEW - Not Monitoring",
                    (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (255, 255, 0),
                    2,
                )
                self.current_frame = frame
        except:
            pass

        self.after(50, self.preview_loop)

    def detection_loop(self):
        """Main detection loop with full fall detection logic"""
        self.add_log_entry("Detection loop started", "#00a8ff")

        while self.running and self.cap:
            ret, frame = self.cap.read()
            if not ret:
                self.add_log_entry("Frame read failed", "#ff4757")
                time.sleep(0.1)
                continue

            # Add to video buffer
            try:
                self.video_recorder.add_frame(frame)
            except Exception as e:
                pass

            # FPS calculation
            self.frame_count += 1
            if self.frame_count >= 30:
                elapsed = time.time() - self.fps_timer
                if elapsed > 0:
                    self.fps = self.frame_count / elapsed
                    self.fps_text.set(f"FPS: {self.fps:.1f}")
                self.frame_count = 0
                self.fps_timer = time.time()

            # YOLO Detection
            try:
                results = self.model.predict(
                    frame, device=DEVICE, classes=[0], conf=0.35, verbose=False
                )
                boxes = results[0].boxes
                best = choose_largest_box(boxes)
            except Exception as e:
                best = None

            if best:
                x1, y1, x2, y2, conf = best
                self.last_confidence = conf
                self.confidence_text.set(f"Confidence: {conf * 100:.1f}%")

                w, h = max(1, x2 - x1), max(1, y2 - y1)
                ar = w / float(h)
                cx, cy = center_of_box(x1, y1, x2, y2)
                drop = cy - self.prev_cy if self.prev_cy is not None else 0

                self.movement_history.append(cy)
                if len(self.movement_history) > 10:
                    self.movement_history.pop(0)

                avg_movement = (
                    max(self.movement_history) - min(self.movement_history)
                    if len(self.movement_history) > 1
                    else 0
                )

                # Box color based on state
                box_color = {
                    STATE_MONITOR: (0, 255, 0),
                    STATE_POSSIBLE_FALL: (0, 255, 255),
                    STATE_IMPACT_PHASE: (0, 255, 255),
                    STATE_STILLNESS_PHASE: (0, 165, 255),
                    STATE_CONFIRMED_FALL: (0, 0, 255),
                }.get(self.state, (0, 255, 0))

                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)

                # ===== FALL DETECTION STATE MACHINE =====
                if self.state == STATE_MONITOR:
                    if (
                        drop > CONFIG["drop_speed_threshold"]
                        and ar > CONFIG["aspect_ratio_threshold"]
                    ):
                        self.fall_time = time.time()
                        self.fall_start_time = datetime.now()
                        self.state = STATE_POSSIBLE_FALL

                        # Save snapshot
                        self.snapshot_path = os.path.join(
                            SNAP_DIR, f"fall_{now_str()}.jpg"
                        )
                        cv2.imwrite(self.snapshot_path, frame)

                        # Start video recording
                        if CONFIG.get("auto_record_video", True):
                            try:
                                self.video_path = self.video_recorder.save_clip(
                                    post_event_seconds=5
                                )
                            except Exception:
                                self.video_path = None

                        # Audio alert
                        self.audio_alerts.play_alert("possible_fall")

                        self.status_text.set("⚠ POSSIBLE FALL")
                        self.add_log_entry(
                            "⚠ POSSIBLE FALL DETECTED - Analyzing...", "#ffd700"
                        )

                        if self.alerts_enabled.get():
                            try:
                                send_telegram_alert(
                                    f"⚠ POSSIBLE FALL DETECTED\n"
                                    f"Patient: {self.patient_data[1]}\n"
                                    f"Bed: {self.patient_data[5]}\n"
                                    f"Time: {datetime.now().strftime('%H:%M:%S')}"
                                )
                            except Exception as e:
                                self.add_log_entry(
                                    f"Telegram alert failed: {e}", "#ff4757"
                                )

                        # Update snapshot display
                        try:
                            img = Image.open(self.snapshot_path)
                            img = img.resize((480, 320))
                            imgtk = ImageTk.PhotoImage(image=img)
                            self.snapshot_label.imgtk = imgtk
                            self.snapshot_label.configure(image=imgtk, text="")
                        except Exception:
                            pass

                elif self.state == STATE_POSSIBLE_FALL:
                    if time.time() - self.fall_time > 0.2:
                        self.impact_start = time.time()
                        self.state = STATE_IMPACT_PHASE
                        self.add_log_entry(
                            "Impact phase - monitoring movement", "#00a8ff"
                        )

                elif self.state == STATE_IMPACT_PHASE:
                    if time.time() - self.impact_start > CONFIG["impact_movement_time"]:
                        self.still_start = time.time()
                        self.state = STATE_STILLNESS_PHASE
                        self.add_log_entry("Checking for stillness...", "#00a8ff")

                elif self.state == STATE_STILLNESS_PHASE:
                    if avg_movement < CONFIG["min_movement_threshold"]:
                        if time.time() - self.still_start > CONFIG["stillness_time"]:
                            self.state = STATE_CONFIRMED_FALL

                            if time.time() - self.last_alert > CONFIG["cooldown_time"]:
                                response_time = (
                                    int(
                                        (
                                            datetime.now() - self.fall_start_time
                                        ).total_seconds()
                                    )
                                    if self.fall_start_time
                                    else 0
                                )

                                # Audio alert
                                self.audio_alerts.play_alert("confirmed_fall")

                                self.status_text.set("❗ CONFIRMED FALL")
                                self.add_log_entry(
                                    "❗ CONFIRMED FALL - EMERGENCY!", "#ff4757"
                                )

                                if self.alerts_enabled.get():
                                    try:
                                        send_telegram_alert(
                                            f"❗ CONFIRMED FALL - EMERGENCY!\n"
                                            f"Patient: {self.patient_data[1]}\n"
                                            f"Bed: {self.patient_data[5]}\n"
                                            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                            f"Response time: {response_time}s\n"
                                            f"IMMEDIATE ASSISTANCE REQUIRED!"
                                        )
                                    except Exception as e:
                                        self.add_log_entry(
                                            f"Telegram alert failed: {e}", "#ff4757"
                                        )

                                self.last_alert = time.time()

                                # Log to database
                                try:
                                    incident_data = {
                                        "patient_id": self.patient_data[0],
                                        "incident_time": self.fall_start_time.strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                        "incident_type": "Confirmed Fall",
                                        "snapshot_path": self.snapshot_path,
                                        "video_path": self.video_path,
                                        "response_time": response_time,
                                        "notes": f"AI detected. Response: {response_time}s",
                                    }
                                    self.db.log_fall_incident(incident_data)
                                    self.add_log_entry(
                                        "Incident logged to database", "#00ff88"
                                    )
                                except Exception as e:
                                    self.add_log_entry(f"DB log failed: {e}", "#ff4757")
                    else:
                        self.state = STATE_MONITOR
                        self.status_text.set("● MONITORING")
                        self.add_log_entry(
                            "False alarm - patient moving normally", "#00ff88"
                        )

                        # Log as cancelled
                        if self.fall_start_time:
                            try:
                                incident_data = {
                                    "patient_id": self.patient_data[0],
                                    "incident_time": self.fall_start_time.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    "incident_type": "Fall Cancelled",
                                    "snapshot_path": self.snapshot_path,
                                    "video_path": None,
                                    "response_time": 0,
                                    "notes": "Patient movement detected - false alarm",
                                }
                                self.db.log_fall_incident(incident_data)
                            except Exception:
                                pass

                elif self.state == STATE_CONFIRMED_FALL:
                    if drop < -20:
                        self.state = STATE_MONITOR
                        self.status_text.set("● MONITORING")
                        self.add_log_entry(
                            "Patient recovered - system reset", "#00ff88"
                        )

                self.prev_cy = cy
            else:
                self.prev_cy = None
                self.confidence_text.set("Confidence: 0%")

            # Draw state overlay
            state_text = {
                STATE_MONITOR: "MONITORING",
                STATE_POSSIBLE_FALL: "POSSIBLE FALL",
                STATE_IMPACT_PHASE: "IMPACT PHASE",
                STATE_STILLNESS_PHASE: "STILLNESS CHECK",
                STATE_CONFIRMED_FALL: "CONFIRMED FALL",
            }.get(self.state, "UNKNOWN")

            cv2.putText(
                frame,
                state_text,
                (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 255, 255),
                3,
            )

            self.current_frame = frame
            time.sleep(0.01)

        self.add_log_entry("Detection loop ended", "#a0a0a0")

    def update_gui_frame(self):
        """Updates GUI with current camera frame - RESPONSIVE"""
        if self.current_frame is not None:
            try:
                # Get current video label size
                label_width = self.video_label.winfo_width()
                label_height = self.video_label.winfo_height()

                # Only resize if label has valid dimensions
                if label_width > 1 and label_height > 1:
                    frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)

                    # Maintain aspect ratio
                    img_ratio = img.width / img.height
                    label_ratio = label_width / label_height

                    if img_ratio > label_ratio:
                        new_width = label_width
                        new_height = int(label_width / img_ratio)
                    else:
                        new_height = label_height
                        new_width = int(label_height * img_ratio)

                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.video_label.imgtk = imgtk
                    self.video_label.configure(image=imgtk, text="")
            except Exception as e:
                pass

        self.after(30, self.update_gui_frame)

    def cleanup(self):
        """Clean up resources before closing"""
        try:
            # Stop monitoring
            if self.running:
                self.running = False
                self.preview_active = False

                # Wait for thread to finish
                if self.thread and self.thread.is_alive():
                    self.thread.join(timeout=2)

            # Release camera
            if self.cap:
                try:
                    self.cap.release()
                except:
                    pass
                self.cap = None

            self.add_log_entry("Resources cleaned up", "#a0a0a0")
        except:
            pass


# MAIN APPLICATION WINDOW
class SafeGuardProEnhanced:
    """Single-window application with notebook tabs"""

    def __init__(self, root):
        self.root = root
        root.title("SafeGuard Vision Pro - Hospital Patient Monitoring")
        root.geometry("1800x920")
        root.resizable(True, True)
        root.minsize(1400, 800)
        root.configure(bg="#1a1a1a")

        # Initialize components
        self.db = PatientDatabase()
        self.video_recorder = VideoRecorder(
            buffer_seconds=CONFIG.get("video_buffer_seconds", 5)
        )
        self.audio_alerts = AudioAlerts()
        self.current_patient = None
        self.monitoring_view = None

        # Build UI
        self.build_header()
        self.build_notebook()

        # IMPORTANT: Bind close event
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_header(self):
        """Main application header"""
        header = Frame(self.root, bg="#2d2d2d", height=70)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)

        Label(
            header,
            text="SafeGuard Vision Pro",
            font=("Arial", 22, "bold"),
            bg="#2d2d2d",
            fg="#00a8ff",
        ).pack(side=tk.LEFT, padx=25, pady=15)

        Label(
            header,
            text="Hospital Patient Monitoring System",
            font=("Arial", 11),
            bg="#2d2d2d",
            fg="#a0a0a0",
        ).place(x=25, y=45)

        # EXIT BUTTON - Added
        Button(
            header,
            text="✕ EXIT",
            command=self.on_close,
            bg="#ff4757",
            fg="#ffffff",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=8,
            cursor="hand2",
            relief=tk.FLAT,
        ).pack(side=tk.RIGHT, padx=15, pady=12)

        # Time
        time_label = Label(
            header, text="", font=("Arial", 11), bg="#2d2d2d", fg="#ffffff"
        )
        time_label.pack(side=tk.RIGHT, padx=15)

        def update_time():
            time_label.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
            self.root.after(1000, update_time)

        update_time()

    def build_notebook(self):
        """Create tabbed interface"""
        # Configure notebook style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.TNotebook",
            background="#1a1a1a",
            borderwidth=0,
            tabmargins=[5, 5, 5, 0],
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background="#2d2d2d",
            foreground="#ffffff",
            padding=[20, 12],
            font=("Arial", 11, "bold"),
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[("selected", "#00a8ff")],
            foreground=[("selected", "#000000")],
        )

        self.notebook = ttk.Notebook(self.root, style="Custom.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Patient List
        self.patient_list_view = PatientListView(
            self.notebook, self.db, self.on_patient_selected
        )
        self.notebook.add(self.patient_list_view, text="📋 Patient List")

        # Tab 2: New Patient
        self.new_patient_form = NewPatientForm(
            self.notebook, self.db, self.on_patient_added
        )
        self.notebook.add(self.new_patient_form, text="➕ New Patient")

        # Tab 3: Settings
        self.settings_panel = SettingsPanel(self.notebook, CONFIG)
        self.notebook.add(self.settings_panel, text="⚙ Settings")

        # Tab 4: Monitoring (initially disabled)
        self.monitoring_tab = Frame(self.notebook, bg="#1a1a1a")
        Label(
            self.monitoring_tab,
            text="Select a patient to start monitoring",
            font=("Arial", 16),
            bg="#1a1a1a",
            fg="#666666",
        ).pack(expand=True)
        self.notebook.add(self.monitoring_tab, text="📹 Monitoring", state="disabled")

    def on_patient_selected(self, patient_data):
        """Called when a patient is selected"""
        self.current_patient = patient_data

        # Stop previous monitoring if active
        if self.monitoring_view and hasattr(self.monitoring_view, "cleanup"):
            self.monitoring_view.cleanup()

        # Remove old monitoring view
        try:
            self.notebook.forget(self.monitoring_view)
        except:
            pass

        # Create new monitoring view
        self.monitoring_view = MonitoringView(
            self.notebook, patient_data, self.db, self.video_recorder, self.audio_alerts
        )

        # Add and select monitoring tab
        self.notebook.add(self.monitoring_view, text="📹 Monitoring")
        self.notebook.select(self.monitoring_view)

        messagebox.showinfo(
            "Patient Selected",
            f"✓ Ready to monitor:\n\n{patient_data[1]}\nBed: {patient_data[5]}",
        )

    def on_patient_added(self):
        """Called when a new patient is added"""
        self.patient_list_view.refresh_list()
        self.notebook.select(0)

    def on_close(self):
        """Cleanup on exit"""
        try:
            # Cleanup monitoring view
            if self.monitoring_view and hasattr(self.monitoring_view, "cleanup"):
                self.monitoring_view.cleanup()

            # Close database
            try:
                self.db.close()
            except:
                pass

            # Destroy window
            self.root.destroy()

            # Force exit
            import sys

            sys.exit(0)

        except Exception as e:
            print(f"Error during close: {e}")
            import sys

            sys.exit(0)


# RUN APPLICATION
if __name__ == "__main__":
    root = Tk()
    app = SafeGuardProEnhanced(root)

    # Force close handler
    def force_close():
        try:
            app.on_close()
        except:
            pass
        finally:
            try:
                root.quit()
                root.destroy()
            except:
                pass
            import sys

            sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", force_close)
    root.mainloop()