# 🏥 Patient Monitoring System

A comprehensive AI-powered patient monitoring system with real-time fall detection, patient management, and automated alerting capabilities built using Python and YOLOv8.

## 🌟 Features

### 🎯 Core Functionality
- **Real-time Fall Detection**: Advanced AI-powered fall detection using YOLOv8 object detection
- **Multi-phase Detection System**: Monitors drop speed, aspect ratio, impact movement, and stillness phases for accurate fall detection
- **Automatic Video Recording**: Captures 5 seconds before and after fall incidents for evidence and analysis
- **Instant Alerts**: Multi-channel alert system with audio beeps and Telegram notifications

### 👥 Patient Management
- **Complete Patient Database**: Store and manage patient records with SQLite
- **Patient Information Tracking**: Name, age, gender, blood group, bed number, emergency contacts, doctor details, and medical conditions
- **Medicine Roster**: Track medications with dosage, frequency, schedules, and status
- **Fall Incident Logging**: Comprehensive incident history with timestamps, snapshots, and video clips
- **Patient Reports**: Generate detailed PDF reports with patient info, incident statistics, and medication lists

### 🖥️ User Interface
- **Modern Tkinter GUI**: Dark-themed, professional interface with intuitive navigation
- **Live Camera Feed**: Real-time video monitoring with detection overlays
- **Patient Dashboard**: Quick access to patient details, incidents, and medicines
- **Search & Filter**: Fast patient lookup and filtering capabilities
- **Settings Panel**: Configurable detection thresholds and system parameters

### 📊 Analytics & Reporting
- **Incident Statistics**: Track total falls, weekly trends, and incident types
- **PDF Report Generation**: Automated comprehensive patient reports
- **Visual Feedback**: Real-time detection status and confidence scores

## 🛠️ Tech Stack

- **Python 3.x** - Core programming language
- **YOLOv8 (Ultralytics)** - AI object detection for person tracking
- **PyTorch** - Deep learning framework (with CUDA support)
- **OpenCV (cv2)** - Computer vision and video processing
- **Tkinter** - GUI framework
- **SQLite3** - Database management
- **Pillow (PIL)** - Image processing
- **FPDF** - PDF report generation
- **Requests** - HTTP requests for Telegram API
- **Winsound** - Audio alert system (Windows)

## 📋 Prerequisites

- Python 3.8 or higher
- Webcam or camera device
- Windows OS (for audio alerts via winsound)
- CUDA-compatible GPU (optional, for faster processing)

## 🚀 Installation

1. **Clone the repository**
```bash
git clone https://github.com/madhurtyagii/Patient-Monitoring-System.git
cd Patient-Monitoring-System
```

2. **Install required dependencies**
```bash
pip install opencv-python torch torchvision ultralytics pillow fpdf requests
```

3. **Set up environment variables** (Optional - for Telegram alerts)
```bash
# Windows
set TELEGRAM_BOT_TOKEN=your_bot_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here

# Linux/Mac
export TELEGRAM_BOT_TOKEN=your_bot_token_here
export TELEGRAM_CHAT_ID=your_chat_id_here
```

## 🎮 Usage

1. **Run the application**
```bash
python safeguard_pro.py
```

2. **Add Patients**
   - Navigate to "Add Patient" section
   - Fill in patient details
   - Save to database

3. **Select Patient & Start Monitoring**
   - Choose a patient from the list
   - Click "Start Monitoring" to activate fall detection
   - System will monitor in real-time

4. **View Incidents & Reports**
   - Access patient dashboard for incident history
   - Generate PDF reports for comprehensive analysis

## 📁 Project Structure

```
Patient-Monitoring-System/
├── safeguard_pro.py          # Main application with GUI and fall detection logic
├── patient_db.py             # Database management (SQLite)
├── video_recorder.py         # Video recording with pre/post event buffering
├── telegram_alert.py         # Telegram notification system
├── audio_alerts.py           # Audio alert system
├── report_generator.py       # PDF report generation
├── yolov8n.pt               # YOLOv8 model weights (auto-downloaded)
├── config.json              # System configuration file
├── patients_data/           # SQLite database directory
├── static/
│   ├── snapshots/           # Fall detection snapshots
│   └── video_clips/         # Recorded video clips
└── reports/                 # Generated PDF reports
```

## ⚙️ Configuration

Modify `config.json` or adjust settings in the GUI:

```json
{
  "drop_speed_threshold": 35,
  "aspect_ratio_threshold": 1.25,
  "impact_movement_time": 0.8,
  "stillness_time": 1.0,
  "cooldown_time": 10,
  "video_buffer_seconds": 5,
  "audio_alerts_enabled": true,
  "auto_record_video": true
}
```

## 🔔 Alert System

### Audio Alerts
- Automatic beep sounds for fall detection events
- Different frequencies for different alert types
- Can be toggled on/off in settings

### Telegram Notifications
- Instant push notifications to configured Telegram chat
- Requires bot token and chat ID setup
- Customizable alert messages

## 🗃️ Database Schema

### Patients Table
Stores patient demographics and medical information

### Medicines Table
Tracks medication schedules with status management

### Fall Incidents Table
Logs all fall detection events with media references

### Vital Signs Table
Optional vital signs tracking (extensible)

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 👨‍💻 Author

**Madhur Tyagi**
- GitHub: [@madhurtyagii](https://github.com/madhurtyagii)

## 🙏 Acknowledgments

- YOLOv8 by Ultralytics for object detection
- OpenCV community for computer vision tools
- Python community for excellent libraries

## 🔮 Future Enhancements

- [ ] Multi-camera support
- [ ] Cloud storage integration
- [ ] Mobile app companion
- [ ] Advanced analytics dashboard
- [ ] Voice alerts
- [ ] Email notification system
- [ ] Vital signs monitoring integration

---

⭐ **If you find this project helpful, please consider giving it a star!**
