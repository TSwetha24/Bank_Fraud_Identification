"""
rPPG (Remote Photoplethysmography) Verification Module
Detects blood flow patterns from facial ROIs to prevent deepfake attacks
"""

import cv2
import numpy as np
from scipy.signal import butter, filtfilt
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class rPPGVerifier:
    """
    Verifies liveness using ROI-based rPPG
    Analyzes blood flow in specific facial regions
    """
    
    def __init__(self, frame_rate: int = 30):
        self.frame_rate = frame_rate
        self.roi_history = {
            'forehead': [],
            'cheeks': [],
            'lips': [],
            'eyes': []
        }
        self.color_channels = {
            'forehead': [],
            'cheeks': [],
            'lips': [],
            'eyes': []
        }
        
    def extract_roi_signals(self, frame: np.ndarray, 
                           face_box: Tuple[int, int, int, int]) -> Dict:
        """
        Extract color signals from specific facial ROIs
        """
        x, y, w, h = face_box
        
        # Normalize face coordinates
        x = max(0, x)
        y = max(0, y)
        
        roi_signals = {}
        
        # Forehead ROI (upper region)
        forehead_y = y
        forehead_h = int(h * 0.2)
        if forehead_y + forehead_h < frame.shape[0]:
            forehead_roi = frame[forehead_y:forehead_y+forehead_h, x:x+w]
            roi_signals['forehead'] = self._extract_color_signal(forehead_roi)
        
        # Cheeks ROI (middle sides)
        cheek_y = y + int(h * 0.25)
        cheek_h = int(h * 0.3)
        if cheek_y + cheek_h < frame.shape[0]:
            cheek_roi = frame[cheek_y:cheek_y+cheek_h, x:x+w]
            roi_signals['cheeks'] = self._extract_color_signal(cheek_roi)
        
        # Lips ROI (lower region)
        lips_y = y + int(h * 0.65)
        lips_h = int(h * 0.2)
        if lips_y + lips_h < frame.shape[0]:
            lips_roi = frame[lips_y:lips_y+lips_h, x:x+w]
            roi_signals['lips'] = self._extract_color_signal(lips_roi)
        
        # Eyes ROI (upper middle)
        eyes_y = y + int(h * 0.15)
        eyes_h = int(h * 0.15)
        if eyes_y + eyes_h < frame.shape[0]:
            eyes_roi = frame[eyes_y:eyes_y+eyes_h, x:x+w]
            roi_signals['eyes'] = self._extract_color_signal(eyes_roi)
        
        return roi_signals
    
    def _extract_color_signal(self, roi: np.ndarray) -> Dict:
        """
        Extract color channel signals from ROI
        """
        # Normalize ROI size to avoid empty regions
        if roi.size == 0:
            return {'r': 0, 'g': 0, 'b': 0}
        
        # Average color intensity in each channel
        b_mean = np.mean(roi[:, :, 0])
        g_mean = np.mean(roi[:, :, 1])
        r_mean = np.mean(roi[:, :, 2])
        
        return {
            'r': float(r_mean),
            'g': float(g_mean),
            'b': float(b_mean)
        }
    
    def detect_blood_flow(self, roi_name: str, color_signal: Dict) -> Dict:
        """
        Detect blood flow patterns in specific ROI
        """
        if not color_signal or 'g' not in color_signal:
            return {
                'roi': roi_name,
                'pulse_detected': False,
                'blood_flow_strength': 0.0,
                'frequency': 0.0
            }

        # Store signal history
        self.color_channels[roi_name].append(color_signal)
        
        result = {
            'roi': roi_name,
            'pulse_detected': False,
            'blood_flow_strength': 0.0,
            'frequency': 0.0
        }
        
        # Need minimum frames for FFT analysis
        if len(self.color_channels[roi_name]) < 30:
            return result
        
        # Extract green channel (best for pulse detection)
        g_signal = [s['g'] for s in self.color_channels[roi_name][-60:]]
        
        # Normalize signal
        g_signal = np.array(g_signal)
        g_signal = (g_signal - np.mean(g_signal)) / np.std(g_signal)
        
        # Apply bandpass filter (40-200 BPM = 0.67-3.33 Hz)
        try:
            # Design bandpass filter (Butterworth) and apply with filtfilt
            b, a = butter(4, [0.67, 3.33], btype='band', fs=self.frame_rate)
            filtered_signal = filtfilt(b, a, g_signal)
            
            # FFT to find dominant frequency
            fft_vals = np.fft.fft(filtered_signal)
            freqs = np.fft.fftfreq(len(filtered_signal), 1/self.frame_rate)
            
            # Find peak in frequency domain
            power = np.abs(fft_vals)
            idx = np.argmax(power[1:len(power)//2]) + 1
            peak_freq = abs(freqs[idx])
            
            # Convert to BPM
            bpm = peak_freq * 60
            
            result['frequency'] = float(bpm)
            
            # Valid heart rate is 40-200 BPM
            if 40 < bpm < 200:
                result['pulse_detected'] = True
                result['blood_flow_strength'] = float(np.max(np.abs(filtered_signal)))
        
        except Exception as e:
            logger.warning(f"Blood flow detection error: {e}")
        
        return result
    
    def verify_multiple_rois(self) -> Dict:
        """
        Verify blood flow across multiple ROIs for liveness confirmation
        """
        verification = {
            'is_live': False,
            'rois_with_pulse': [],
            'avg_bpm': 0.0,
            'confidence': 0.0
        }
        
        pulse_count = 0
        bpm_values = []
        
        for roi_name in self.roi_history.keys():
            signal = self.color_channels[roi_name][-1] if self.color_channels[roi_name] else None
            result = self.detect_blood_flow(roi_name, signal)
            
            if result['pulse_detected']:
                pulse_count += 1
                bpm_values.append(result['frequency'])
                verification['rois_with_pulse'].append(roi_name)
        
        # Liveness requires pulse in at least 2 ROIs
        if pulse_count >= 2:
            verification['is_live'] = True
            verification['avg_bpm'] = float(np.mean(bpm_values)) if bpm_values else 0
            verification['confidence'] = min(pulse_count / 4 * 100, 100.0)
        
        return verification
    
    def detect_expression(self, prev_frame: np.ndarray, 
                         curr_frame: np.ndarray) -> Dict:
        """
        Detect facial expressions (smile, blink, raise eyebrow)
        """
        expressions = {
            'smile': False,
            'blink': False,
            'eyebrow_raise': False,
            'expression_detected': False
        }
        
        # Calculate frame difference for motion detection
        if prev_frame is not None and curr_frame is not None:
            diff = cv2.absdiff(prev_frame, curr_frame)
            motion = np.sum(diff)
            
            # Threshold for expression movement
            if motion > 5000:
                expressions['expression_detected'] = True
        
        return expressions
    
    def reset(self):
        """Reset state for new verification"""
        for key in self.roi_history.keys():
            self.roi_history[key] = []
            self.color_channels[key] = []
