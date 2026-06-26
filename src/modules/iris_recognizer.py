"""
Iris Recognition Module
Fallback biometric verification for edge cases (identical twins, etc.)
"""

import cv2
import numpy as np
import mediapipe as mp
import importlib
from typing import Dict, Tuple, Optional
from scipy.spatial.distance import euclidean
import logging

logger = logging.getLogger(__name__)


class IrisRecognizer:
    """
    Iris pattern recognition and matching
    Unique even between identical twins
    """
    
    def __init__(self):
        # Robust import for MediaPipe face_mesh across different installs
        self.use_face_mesh = True
        try:
            face_mesh_mod = mp.solutions.face_mesh
            self.face_mesh = face_mesh_mod.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5
            )
        except Exception:
            try:
                face_mesh_mod = importlib.import_module('mediapipe.solutions.face_mesh')
                self.face_mesh = face_mesh_mod.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5
                )
            except Exception:
                # Gracefully disable face_mesh features for demo if MediaPipe isn't usable
                logger.warning('MediaPipe face_mesh unavailable; iris recognition disabled for demo.')
                self.face_mesh = None
                self.use_face_mesh = False
        self.stored_iris_templates = {}
        
    def detect_iris_landmarks(self, frame: np.ndarray) -> Dict:
        """
        Detect iris landmarks using MediaPipe Face Mesh
        """
        result = {
            'left_iris': None,
            'right_iris': None,
            'iris_detected': False
        }

        # If face_mesh is disabled (no MediaPipe), skip detection
        if not getattr(self, 'use_face_mesh', True) or self.face_mesh is None:
            return result

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect face mesh
        mesh_results = self.face_mesh.process(rgb_frame)

        if not mesh_results or not getattr(mesh_results, 'multi_face_landmarks', None):
            return result
        
        landmarks = mesh_results.multi_face_landmarks[0]
        h, w, _ = frame.shape
        
        # Iris landmarks in MediaPipe (approximate centers and boundaries)
        # Left iris: landmarks 468-471 (center + 4 points)
        # Right iris: landmarks 473-476 (center + 4 points)
        
        try:
            # Left iris center
            left_iris_center = landmarks.landmark[468]
            left_iris_pts = [
                (landmarks.landmark[468].x * w, landmarks.landmark[468].y * h),
                (landmarks.landmark[469].x * w, landmarks.landmark[469].y * h),
                (landmarks.landmark[470].x * w, landmarks.landmark[470].y * h),
                (landmarks.landmark[471].x * w, landmarks.landmark[471].y * h)
            ]
            
            # Right iris center
            right_iris_center = landmarks.landmark[473]
            right_iris_pts = [
                (landmarks.landmark[473].x * w, landmarks.landmark[473].y * h),
                (landmarks.landmark[474].x * w, landmarks.landmark[474].y * h),
                (landmarks.landmark[475].x * w, landmarks.landmark[475].y * h),
                (landmarks.landmark[476].x * w, landmarks.landmark[476].y * h)
            ]
            
            result['left_iris'] = {
                'center': (int(left_iris_center.x * w), int(left_iris_center.y * h)),
                'points': left_iris_pts
            }
            
            result['right_iris'] = {
                'center': (int(right_iris_center.x * w), int(right_iris_center.y * h)),
                'points': right_iris_pts
            }
            
            result['iris_detected'] = True
            
        except Exception as e:
            logger.warning(f"Iris detection error: {e}")
        
        return result
    
    def extract_iris_template(self, frame: np.ndarray, 
                             iris_landmarks: Dict) -> Optional[np.ndarray]:
        """
        Extract iris template from detected landmarks
        Creates a binary iris template for matching
        """
        if not iris_landmarks['iris_detected']:
            return None
        
        # Use both irises for template
        templates = []
        
        for side in ['left_iris', 'right_iris']:
            if iris_landmarks[side] is None:
                continue
            
            center = iris_landmarks[side]['center']
            points = iris_landmarks[side]['points']
            
            # Create circular mask around iris center
            mask = np.zeros((64, 64), dtype=np.uint8)
            radius = 15
            cv2.circle(mask, (32, 32), radius, 255, -1)
            
            # Extract iris region from frame
            x, y = center
            iris_roi = frame[max(0, y-radius):min(frame.shape[0], y+radius),
                            max(0, x-radius):min(frame.shape[1], x+radius)]
            
            if iris_roi.shape[0] > 0 and iris_roi.shape[1] > 0:
                # Resize to standard size
                iris_roi = cv2.resize(iris_roi, (64, 64))
                
                # Convert to grayscale
                if len(iris_roi.shape) == 3:
                    iris_roi = cv2.cvtColor(iris_roi, cv2.COLOR_BGR2GRAY)
                
                # Apply mask
                iris_template = cv2.bitwise_and(iris_roi, iris_roi, mask=mask)
                templates.append(iris_template)
        
        if templates:
            # Combine templates
            combined = np.concatenate([t.flatten() for t in templates])
            return combined
        
        return None
    
    def compute_iris_feature_vector(self, iris_template: np.ndarray) -> np.ndarray:
        """
        Compute feature vector from iris template using frequency analysis
        """
        if iris_template is None or len(iris_template) == 0:
            return np.array([])
        
        # Reshape to 2D
        template_2d = iris_template.reshape(64, 64) if iris_template.size == 4096 else iris_template[:4096].reshape(64, 64)
        
        # Extract features
        features = []
        
        # 1. Histogram features
        hist = cv2.calcHist([template_2d], [0], None, [32], [0, 256])
        hist = hist.flatten() / (hist.sum() + 1e-6)
        features.extend(hist)
        
        # 2. Texture features (LBP-like)
        lbp_features = self._compute_lbp(template_2d)
        features.extend(lbp_features)
        
        # 3. Edge features
        edges = cv2.Canny(template_2d.astype(np.uint8), 50, 150)
        edge_hist = cv2.calcHist([edges], [0], None, [16], [0, 256])
        edge_hist = edge_hist.flatten() / (edge_hist.sum() + 1e-6)
        features.extend(edge_hist)
        
        return np.array(features)
    
    def _compute_lbp(self, image: np.ndarray) -> np.ndarray:
        """
        Compute Local Binary Pattern features
        """
        lbp_features = []
        
        for i in range(1, image.shape[0] - 1):
            for j in range(1, image.shape[1] - 1):
                center = image[i, j]
                neighbors = [
                    image[i-1, j-1], image[i-1, j], image[i-1, j+1],
                    image[i, j+1], image[i+1, j+1], image[i+1, j],
                    image[i+1, j-1], image[i, j-1]
                ]
                
                lbp_val = 0
                for k, neighbor in enumerate(neighbors):
                    if neighbor >= center:
                        lbp_val |= (1 << k)
                
                lbp_features.append(lbp_val)
        
        # Compute histogram of LBP values
        hist = np.histogram(lbp_features, bins=256, range=(0, 256))[0]
        hist = hist.astype(np.float32) / (np.sum(hist) + 1e-6)
        
        return hist
    
    def match_iris_templates(self, template1: np.ndarray, 
                            template2: np.ndarray) -> Dict:
        """
        Match two iris templates
        """
        result = {
            'match_score': 0.0,
            'is_match': False,
            'confidence': 0.0
        }
        
        if template1 is None or template2 is None:
            return result
        
        # Compute feature vectors
        features1 = self.compute_iris_feature_vector(template1)
        features2 = self.compute_iris_feature_vector(template2)
        
        if len(features1) == 0 or len(features2) == 0:
            return result
        
        # Compute similarity (cosine similarity)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 > 0 and norm2 > 0:
            similarity = np.dot(features1, features2) / (norm1 * norm2)
            result['match_score'] = float(similarity)
            
            # Threshold for iris matching
            if similarity > 0.7:
                result['is_match'] = True
                result['confidence'] = min((similarity - 0.7) / 0.3 * 100, 100.0)
        
        return result
    
    def store_iris_template(self, user_id: str, iris_template: np.ndarray) -> bool:
        """
        Store iris template for future verification
        """
        try:
            self.stored_iris_templates[user_id] = iris_template
            return True
        except Exception as e:
            logger.error(f"Failed to store iris template: {e}")
            return False
    
    def verify_against_stored(self, user_id: str, iris_template: np.ndarray) -> Dict:
        """
        Verify iris template against stored template
        """
        if user_id not in self.stored_iris_templates:
            return {
                'is_match': False,
                'match_score': 0.0,
                'error': 'No stored iris template for user'
            }
        
        stored_template = self.stored_iris_templates[user_id]
        return self.match_iris_templates(stored_template, iris_template)
