"""
Face recognition helper for enrollment and stored-photo matching.
"""

import cv2
import numpy as np
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class FaceRecognizer:
    """Basic face vector extraction and matching for prototype use."""

    def __init__(self, size: Tuple[int, int] = (16, 16), hist_bins: int = 32, match_threshold: float = 0.92):
        self.size = size
        self.hist_bins = hist_bins
        self.match_threshold = match_threshold

    def extract_face_vector(self, frame: np.ndarray, face_box: Tuple[int, int, int, int]) -> Optional[list]:
        x, y, w, h = face_box
        if w <= 0 or h <= 0:
            return None

        face_roi = frame[max(0, y):max(0, y + h), max(0, x):max(0, x + w)]
        if face_roi.size == 0:
            return None

        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.size)

        # Normalize pixel intensities
        norm_pixels = resized.astype(np.float32) / 255.0
        pixel_features = norm_pixels.flatten()

        # Histogram of intensities for robustness
        hist = cv2.calcHist([resized], [0], None, [self.hist_bins], [0, 256]).flatten()
        hist = hist / (np.sum(hist) + 1e-6)

        vector = np.concatenate([pixel_features, hist])
        if np.linalg.norm(vector) == 0:
            return None

        normalized = vector / np.linalg.norm(vector)
        return normalized.tolist()

    def match_face_vectors(self, stored_vector: list, probe_vector: list) -> Dict:
        result = {
            'match_score': 0.0,
            'is_match': False,
            'confidence': 0.0
        }

        if stored_vector is None or probe_vector is None:
            return result

        v1 = np.array(stored_vector, dtype=np.float32)
        v2 = np.array(probe_vector, dtype=np.float32)

        if v1.size == 0 or v2.size == 0:
            return result

        dot = float(np.dot(v1, v2))
        norm1 = float(np.linalg.norm(v1))
        norm2 = float(np.linalg.norm(v2))

        if norm1 == 0 or norm2 == 0:
            return result

        similarity = dot / (norm1 * norm2)
        result['match_score'] = float(similarity)

        if similarity > self.match_threshold:
            result['is_match'] = True
            result['confidence'] = min((similarity - self.match_threshold) / (1 - self.match_threshold) * 100, 100.0)

        return result
