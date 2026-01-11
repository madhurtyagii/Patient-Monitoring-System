import os
import threading

# Try to import winsound (Windows only)
try:
    import winsound
    AUDIO_AVAILABLE = True
except ImportError:
    winsound = None
    AUDIO_AVAILABLE = False
    print("[AudioAlerts] winsound not available (Windows only). Audio alerts disabled.")

class AudioAlerts:
    def __init__(self):
        self.enabled = True
        self.alert_sound = "static/alert_sound.wav"
        
        # Create default beep sound if not exists
        if not os.path.exists(self.alert_sound):
            self._create_default_sound()
    
    def _create_default_sound(self):
        """Create a simple beep sound using numpy and scipy"""
        try:
            import numpy as np
            from scipy.io import wavfile
            
            duration = 1.0  # seconds
            frequency = 800  # Hz
            sample_rate = 44100
            
            t = np.linspace(0, duration, int(sample_rate * duration))
            wave = np.sin(2 * np.pi * frequency * t)
            wave = (wave * 32767).astype(np.int16)
            
            os.makedirs("static", exist_ok=True)
            wavfile.write(self.alert_sound, sample_rate, wave)
            print(f"[AudioAlerts] Created default alert sound")
        except Exception as e:
            print(f"[AudioAlerts] Could not create sound: {e}")
    
    def play_alert(self, alert_type="fall"):
        """Play alert sound in background thread"""
        if not self.enabled or not AUDIO_AVAILABLE:
            return
        
        if not os.path.exists(self.alert_sound):
            return
        
        thread = threading.Thread(target=self._play_sound, daemon=True)
        thread.start()
    
    def _play_sound(self):
        try:
            if AUDIO_AVAILABLE and os.path.exists(self.alert_sound):
                # Try to play WAV file using winsound
                winsound.PlaySound(self.alert_sound, winsound.SND_FILENAME)
            else:
                # Fallback: play system beep (frequency in Hz, duration in ms)
                winsound.Beep(1000, 500)  # 1000 Hz for 500ms
        except Exception as e:
            print(f"[AudioAlerts] Error playing sound: {e}")
    
    def set_enabled(self, enabled):
        self.enabled = enabled