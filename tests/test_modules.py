"""
Test Suite for Identity Verification System
"""

import unittest
import numpy as np
import cv2
from src.modules.motion_verifier import MotionVerifier
from src.modules.rppg_verifier import rPPGVerifier
from src.modules.morph_detector import MorphDetector
from src.modules.iris_recognizer import IrisRecognizer
from src.modules.trust_token import TrustTokenGraph


class TestMotionVerifier(unittest.TestCase):
    """Test motion verification module"""
    
    def setUp(self):
        self.verifier = MotionVerifier()
    
    def test_motion_detection(self):
        """Test motion detection capability"""
        # Create test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:200, 100:200] = [255, 255, 255]  # White square
        
        result = self.verifier.detect_face_motion(frame)
        
        self.assertIn('motion_detected', result)
        self.assertIn('motion_magnitude', result)
        self.assertIn('is_live', result)
    
    def test_gyroscope_verification(self):
        """Test gyroscope data verification"""
        gyro_data = {
            'gyro': [0.5, 0.3, 0.1],
            'accel': [0.1, 0.2, 9.8]
        }
        
        result = self.verifier.verify_gyroscope_motion(gyro_data)
        self.assertIsInstance(result, bool)


class TestrPPGVerifier(unittest.TestCase):
    """Test rPPG verification module"""
    
    def setUp(self):
        self.verifier = rPPGVerifier()
    
    def test_roi_signal_extraction(self):
        """Test ROI signal extraction"""
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        face_box = (100, 100, 200, 200)
        
        signals = self.verifier.extract_roi_signals(frame, face_box)
        
        self.assertIn('forehead', signals)
        self.assertIn('cheeks', signals)
        self.assertIn('lips', signals)
        self.assertIn('eyes', signals)
    
    def test_blood_flow_detection(self):
        """Test blood flow detection"""
        color_signal = {'r': 150, 'g': 140, 'b': 130}
        result = self.verifier.detect_blood_flow('forehead', color_signal)
        
        self.assertIn('pulse_detected', result)
        self.assertIn('blood_flow_strength', result)
        self.assertIn('frequency', result)


class TestMorphDetector(unittest.TestCase):
    """Test morph detection module"""
    
    def setUp(self):
        self.detector = MorphDetector()
    
    def test_frequency_artifact_detection(self):
        """Test frequency domain artifact detection"""
        # Create synthetic image
        frame = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
        
        result, spectrum = self.detector.detect_frequency_artifacts(frame)
        
        self.assertIn('is_morphed', result)
        self.assertIn('artifact_score', result)
        self.assertIn('blending_detected', result)
    
    def test_comprehensive_morph_detection(self):
        """Test comprehensive morph detection"""
        frame = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
        
        result = self.detector.comprehensive_morph_detection(frame)
        
        self.assertIn('is_morphed', result)
        self.assertIn('confidence', result)
        self.assertIn('details', result)


class TestIrisRecognizer(unittest.TestCase):
    """Test iris recognition module"""
    
    def setUp(self):
        self.recognizer = IrisRecognizer()
    
    def test_iris_feature_extraction(self):
        """Test iris feature extraction"""
        template = np.random.randint(0, 256, 4096, dtype=np.uint8)
        
        features = self.recognizer.compute_iris_feature_vector(template)
        
        self.assertGreater(len(features), 0)
    
    def test_iris_template_storage(self):
        """Test iris template storage"""
        user_id = "test_user_123"
        template = np.random.randint(0, 256, 4096, dtype=np.uint8)
        
        result = self.recognizer.store_iris_template(user_id, template)
        
        self.assertTrue(result)


class TestTrustTokenGraph(unittest.TestCase):
    """Test trust token graph module"""
    
    def setUp(self):
        self.trust_graph = TrustTokenGraph()
    
    def test_device_fingerprint_generation(self):
        """Test device fingerprint generation"""
        device_data = {
            'device_id': 'device_001',
            'model': 'iPhone 14',
            'os': 'iOS 16',
            'unique_identifiers': ['uid_1', 'uid_2']
        }
        
        fingerprint = self.trust_graph.generate_device_fingerprint(device_data)
        
        self.assertIsInstance(fingerprint, str)
        self.assertEqual(len(fingerprint), 64)  # SHA256 hex length
    
    def test_trust_token_creation(self):
        """Test trust token creation"""
        user_id = "test_user_123"
        verification_data = {
            'motion_verified': True,
            'liveness_verified': True,
            'morph_detected': False,
            'iris_verified': True,
            'typing_speed': 60,
            'swipe_pattern': [0.1, 0.2, 0.3]
        }
        device_data = {
            'device_id': 'device_001',
            'model': 'iPhone 14',
            'os': 'iOS 16',
            'ip_address': '192.168.1.1',
            'mac_address': '00:1A:2B:3C:4D:5E',
            'location': {'lat': 23.1815, 'lon': 79.9864}
        }
        
        token = self.trust_graph.create_trust_token(
            user_id, verification_data, device_data
        )
        
        self.assertIn('token_id', token)
        self.assertIn('device_fingerprint', token)
        self.assertIn('signature', token)
    
    def test_token_validation(self):
        """Test token validation"""
        user_id = "test_user_123"
        verification_data = {
            'motion_verified': True,
            'liveness_verified': True
        }
        device_data = {
            'device_id': 'device_001',
            'model': 'iPhone 14',
            'os': 'iOS 16'
        }
        
        token = self.trust_graph.create_trust_token(
            user_id, verification_data, device_data
        )
        
        result = self.trust_graph.validate_token(token['token_id'], device_data)
        
        self.assertTrue(result['is_valid'])


if __name__ == '__main__':
    unittest.main()
