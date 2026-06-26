"""
Motion Verification Module
Detects face movement using optical flow and gyroscope/accelerometer data
"""

import cv2
import numpy as np
import mediapipe as mp
import importlib
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MotionVerifier:
    def __init__(self):
        # Robust import for MediaPipe face_detection across different installs
        self.use_mediapipe = True
        try:
            face_detection_mod = mp.solutions.face_detection
            self.face_detector = face_detection_mod.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.7
            )
        except Exception:
            # Fall back to OpenCV Haar cascade for environments without MediaPipe
            self.use_mediapipe = False
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        self.prev_gray = None
        self.motion_history = []
        self.gyro_history = []
        
    def detect_face_motion(self, frame: np.ndarray) -> Dict:
        """
        Detect face motion using optical flow
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        motion_data = {
            'motion_detected': False,
            'motion_magnitude': 0.0,
            'flow_vectors': None,
            'face_box': None,
            'is_live': False
        }

        # If the frame size changes, reset optical flow state
        if self.prev_gray is not None and self.prev_gray.shape != gray.shape:
            self.prev_gray = None
        
        # Detect face (MediaPipe if available, otherwise OpenCV cascade)
        face_box = None
        if getattr(self, 'use_mediapipe', False):
            results = self.face_detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results and getattr(results, 'detections', None):
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                face_box = (
                    int(bbox.xmin * w),
                    int(bbox.ymin * h),
                    int(bbox.width * w),
                    int(bbox.height * h)
                )
                motion_data['face_box'] = face_box
        else:
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            if len(faces) > 0:
                x_f, y_f, fw_f, fh_f = faces[0]
                face_box = (x_f, y_f, fw_f, fh_f)
                motion_data['face_box'] = face_box

        # If a face was found by either method, compute optical flow and motion metrics
        if face_box is not None:
            x, y, fw, fh = face_box
            face_roi = gray[max(0, y):min(h, y+fh), max(0, x):min(w, x+fw)]

            # Calculate optical flow
            if self.prev_gray is not None:
                try:
                    flow = cv2.calcOpticalFlowFarneback(
                        self.prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                except cv2.error as e:
                    logger.warning(f"Optical flow failed: {e}")
                    flow = None

                if flow is not None:
                    # Calculate motion magnitude
                    magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    motion_magnitude = np.mean(magnitude)

                    motion_data['motion_magnitude'] = float(motion_magnitude)
                    motion_data['flow_vectors'] = flow

                    # Threshold for motion detection
                    if motion_magnitude > 0.5:
                        motion_data['motion_detected'] = True
                        self.motion_history.append(motion_magnitude)

                        # Check if motion pattern suggests liveness
                        if len(self.motion_history) >= 5:
                            motion_variance = np.var(self.motion_history[-5:])
                            if motion_variance > 0.1:  # Varying motion indicates real person
                                motion_data['is_live'] = True

                # Calculate motion magnitude
                magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_magnitude = np.mean(magnitude)

                motion_data['motion_magnitude'] = float(motion_magnitude)
                motion_data['flow_vectors'] = flow

                # Threshold for motion detection
                if motion_magnitude > 0.5:
                    motion_data['motion_detected'] = True
                    self.motion_history.append(motion_magnitude)

                    # Check if motion pattern suggests liveness
                    if len(self.motion_history) >= 5:
                        motion_variance = np.var(self.motion_history[-5:])
                        if motion_variance > 0.1:  # Varying motion indicates real person
                            motion_data['is_live'] = True

            self.prev_gray = gray.copy()
        
        return motion_data
    
    def verify_gyroscope_motion(self, gyro_data: Dict) -> bool:
        """
        Verify gyroscope and accelerometer data matches face motion
        
        Args:
            gyro_data: Dictionary with 'gyro' and 'accel' readings
        """
        if 'gyro' not in gyro_data or 'accel' not in gyro_data:
            return False
        
        gyro_magnitude = np.linalg.norm(gyro_data['gyro'])
        accel_magnitude = np.linalg.norm(gyro_data['accel'])
        
        self.gyro_history.append({
            'gyro': gyro_magnitude,
            'accel': accel_magnitude
        })
        
        # Verify motion consistency
        if len(self.gyro_history) >= 3:
            recent_motion = self.motion_history[-3:] if self.motion_history else [0]
            recent_gyro = [m['gyro'] for m in self.gyro_history[-3:]]
            
            # Motion correlation check
            motion_avg = np.mean(recent_motion)
            gyro_avg = np.mean(recent_gyro)
            
            # If both show movement or both are still, it's consistent
            if (motion_avg > 0.5 and gyro_avg > 0.1) or (motion_avg < 0.5 and gyro_avg < 0.1):
                return True
        
        return False
    
    def validate_tilt_motion(self, gyro_data: Dict) -> Dict:
        """
        Validate that user is performing tilt/rotation motion
        """
        result = {
            'tilt_detected': False,
            'rotation_detected': False,
            'motion_pattern': 'static'
        }
        
        if 'gyro' not in gyro_data:
            return result
        
        gyro = gyro_data['gyro']
        
        # Check for rotation (around z-axis)
        if abs(gyro[2]) > 0.2:
            result['rotation_detected'] = True
            result['motion_pattern'] = 'rotation'
        
        # Check for tilt (around x/y axes)
        if abs(gyro[0]) > 0.2 or abs(gyro[1]) > 0.2:
            result['tilt_detected'] = True
            result['motion_pattern'] = 'tilt'
        
        if result['tilt_detected'] or result['rotation_detected']:
            self.gyro_history.append(gyro)
        
        return result
    
    def reset(self):
        """Reset state for new verification"""
        self.prev_gray = None
        self.motion_history = []
        self.gyro_history = []
