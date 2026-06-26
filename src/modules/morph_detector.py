"""
Morph Detection Module
Detects face morphing attacks using Frequency-Domain analysis
"""

import cv2
import numpy as np
from scipy import ndimage
from scipy.fft import fft2, fftshift
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class MorphDetector:
    """
    Detects face morphing attacks using Fourier Transform
    Identifies blending artifacts and texture inconsistencies
    """
    
    def __init__(self):
        self.reference_frequencies = None
        self.artifacts_threshold = 0.3
        self.edge_inconsistency_threshold = 100.0  # Relaxed from default for real webcam video
        self.boundary_blur_threshold = 0.5  # Relaxed threshold
        self.symmetry_break_threshold = 0.3  # Relaxed from 0.15
        
    def preprocess_face(self, face_image: np.ndarray) -> np.ndarray:
        """
        Preprocess face image for morph detection
        """
        # Convert to grayscale if needed
        if len(face_image.shape) == 3:
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # Resize to standard size
        face_image = cv2.resize(face_image, (256, 256))
        
        # Normalize
        face_image = face_image.astype(np.float32) / 255.0
        
        return face_image
    
    def detect_frequency_artifacts(self, face_image: np.ndarray) -> Dict:
        """
        Detect morphing artifacts in frequency domain using Fourier Transform
        """
        face_image = self.preprocess_face(face_image)
        
        # Compute FFT
        fft_image = fft2(face_image)
        fft_shifted = fftshift(fft_image)
        
        # Compute magnitude spectrum
        magnitude_spectrum = np.abs(fft_shifted)
        magnitude_spectrum = np.log(magnitude_spectrum + 1)  # Log scale
        
        result = {
            'is_morphed': False,
            'artifact_score': 0.0,
            'blending_detected': False,
            'texture_inconsistency': 0.0
        }
        
        # Analyze high-frequency components (artifacts are typically high-frequency)
        high_freq = magnitude_spectrum[50:206, 50:206]  # Center region
        
        # Calculate artifact score based on frequency distribution
        mean_high_freq = np.mean(high_freq)
        std_high_freq = np.std(high_freq)
        
        artifact_score = std_high_freq / (mean_high_freq + 1e-6)
        result['artifact_score'] = float(artifact_score)
        
        # Morphed images have different frequency characteristics
        if artifact_score > self.artifacts_threshold:
            result['is_morphed'] = True
            result['blending_detected'] = True
        
        return result, magnitude_spectrum
    
    def detect_edge_inconsistencies(self, face_image: np.ndarray) -> Dict:
        """
        Detect edge and boundary inconsistencies typical of morphing
        """
        face_image = self.preprocess_face(face_image)
        
        # Apply edge detection
        edges = cv2.Canny((face_image * 255).astype(np.uint8), 50, 150)
        
        result = {
            'edge_inconsistency': 0.0,
            'boundary_blur': 0.0,
            'is_morphed': False
        }
        
        # Calculate edge map gradient
        edge_gradient = np.gradient(edges.astype(np.float32))
        edge_variance = np.var(edge_gradient)
        
        result['edge_inconsistency'] = float(edge_variance)
        
        # Check for unnatural blurring at boundaries
        blur_map = cv2.Laplacian(face_image, cv2.CV_32F)
        blur_map = np.abs(blur_map)
        
        # High blur indicates morphing
        boundary_blur = np.mean(blur_map[10:20, :]) + np.mean(blur_map[-20:-10, :])
        result['boundary_blur'] = float(boundary_blur)
        
        # Combined inconsistency check (relaxed for real webcam video)
        if result['edge_inconsistency'] > self.edge_inconsistency_threshold and result['boundary_blur'] > self.boundary_blur_threshold:
            result['is_morphed'] = True
        
        return result
    
    def detect_bilateral_symmetry_break(self, face_image: np.ndarray) -> Dict:
        """
        Detect breaks in facial symmetry (common in morphed faces)
        """
        face_image = self.preprocess_face(face_image)
        
        result = {
            'symmetry_break': 0.0,
            'is_morphed': False
        }
        
        # Split face into left and right halves
        mid_col = face_image.shape[1] // 2
        left_half = face_image[:, :mid_col]
        right_half = np.fliplr(face_image[:, mid_col:])
        
        # Resize right half to match left if sizes differ
        if left_half.shape != right_half.shape:
            right_half = cv2.resize(right_half, (left_half.shape[1], left_half.shape[0]))
        
        # Compute symmetry difference
        symmetry_diff = np.mean(np.abs(left_half - right_half))
        result['symmetry_break'] = float(symmetry_diff)
        
        # High symmetry break indicates morphing
        if symmetry_diff > self.symmetry_break_threshold:
            result['is_morphed'] = True
        
        return result
    
    def comprehensive_morph_detection(self, face_image: np.ndarray) -> Dict:
        """
        Comprehensive morphing detection combining multiple methods
        """
        result_freq, _ = self.detect_frequency_artifacts(face_image)
        result_edge = self.detect_edge_inconsistencies(face_image)
        result_symmetry = self.detect_bilateral_symmetry_break(face_image)
        
        # Combine results
        morphing_indicators = sum([
            result_freq.get('is_morphed', False),
            result_edge.get('is_morphed', False),
            result_symmetry.get('is_morphed', False)
        ])
        
        overall_result = {
            'is_morphed': morphing_indicators >= 2,  # Require at least 2 indicators
            'confidence': (morphing_indicators / 3) * 100,
            'frequency_artifacts': result_freq.get('artifact_score', 0),
            'edge_inconsistency': result_edge.get('edge_inconsistency', 0),
            'symmetry_break': result_symmetry.get('symmetry_break', 0),
            'details': {
                'frequency': result_freq,
                'edge': result_edge,
                'symmetry': result_symmetry
            }
        }
        
        return overall_result
    
    def detect_blending_boundary(self, face_image: np.ndarray) -> np.ndarray:
        """
        Highlight potential blending boundaries (heatmap)
        """
        face_image = self.preprocess_face(face_image)
        
        # Apply Laplacian (detects edges/boundaries)
        laplacian = cv2.Laplacian((face_image * 255).astype(np.uint8), cv2.CV_32F)
        
        # Normalize to 0-255
        boundary_map = np.abs(laplacian)
        boundary_map = (boundary_map - boundary_map.min()) / (boundary_map.max() - boundary_map.min() + 1e-6) * 255
        
        return boundary_map.astype(np.uint8)
