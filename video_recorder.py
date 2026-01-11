import cv2
import os
import threading
from collections import deque
from datetime import datetime

class VideoRecorder:
    def __init__(self, buffer_seconds=5, fps=20):
        self.buffer_seconds = buffer_seconds
        self.fps = fps
        self.buffer_size = buffer_seconds * fps
        self.frame_buffer = deque(maxlen=self.buffer_size)
        self.recording = False
        self.output_dir = "static/video_clips"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def add_frame(self, frame):
        """Add frame to circular buffer"""
        if frame is not None:
            self.frame_buffer.append(frame.copy())
    
    def save_clip(self, post_event_seconds=5):
        """Save clip: 5 seconds before + 5 seconds after event"""
        if self.recording:
            return None
        
        self.recording = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fall_clip_{timestamp}.avi"
        filepath = os.path.join(self.output_dir, filename)
        
        # Start recording thread
        thread = threading.Thread(
            target=self._record_clip,
            args=(filepath, post_event_seconds),
            daemon=True
        )
        thread.start()
        
        return filepath
    
    def _record_clip(self, filepath, post_seconds):
        """Internal method to record clip"""
        try:
            # Get pre-event frames from buffer
            pre_frames = list(self.frame_buffer)
            
            if len(pre_frames) == 0:
                self.recording = False
                return
            
            # Get frame dimensions
            height, width = pre_frames[0].shape[:2]
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(filepath, fourcc, self.fps, (width, height))
            
            # Write pre-event frames
            for frame in pre_frames:
                out.write(frame)
            
            # Continue recording post-event frames
            frames_to_record = post_seconds * self.fps
            frames_recorded = 0
            
            while frames_recorded < frames_to_record and len(self.frame_buffer) > 0:
                frame = self.frame_buffer[-1]
                out.write(frame)
                frames_recorded += 1
                cv2.waitKey(int(1000/self.fps))
            
            out.release()
            print(f"[VideoRecorder] Saved clip: {filepath}")
            
        except Exception as e:
            print(f"[VideoRecorder] Error: {e}")
        finally:
            self.recording = False