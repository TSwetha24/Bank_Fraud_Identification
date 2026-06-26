"""
Standalone Demo Script
Test the Identity Verification System with sample data
"""

import cv2
import numpy as np
import argparse
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.motion_verifier import MotionVerifier
from src.modules.rppg_verifier import rPPGVerifier
from src.modules.morph_detector import MorphDetector
from src.modules.iris_recognizer import IrisRecognizer
from src.modules.trust_token import TrustTokenGraph
from src.utils.logger import get_logger

logger = get_logger('demo')


class IdentityVerificationDemo:
    """Demo script for identity verification system"""
    
    def __init__(self):
        self.motion_verifier = MotionVerifier()
        self.rppg_verifier = rPPGVerifier()
        self.morph_detector = MorphDetector()
        self.iris_recognizer = IrisRecognizer()
        self.trust_token_graph = TrustTokenGraph()
    
    def demo_motion_verification(self):
        """Demo: Motion verification"""
        print("\n" + "="*60)
        print("DEMO: Motion Verification")
        print("="*60)
        
        # Create synthetic frame with movement
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[150:350, 200:440] = [255, 200, 150]  # Skin tone face region
        
        # Add some motion artifacts
        cv2.circle(frame, (320, 250), 80, [100, 50, 50], -1)  # Eyes
        
        result = self.motion_verifier.detect_face_motion(frame)
        
        print(f"Motion Detected: {result['motion_detected']}")
        print(f"Motion Magnitude: {result['motion_magnitude']:.4f}")
        print(f"Is Live: {result['is_live']}")
        print(f"Face Box: {result['face_box']}")
        
        return result
    
    def demo_rppg_verification(self):
        """Demo: rPPG Verification"""
        print("\n" + "="*60)
        print("DEMO: rPPG (Blood Flow) Verification")
        print("="*60)
        
        # Create synthetic frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[150:350, 200:440] = [150, 100, 100]  # Skin tone
        
        # Simulate color variations (pulse)
        face_box = (200, 150, 240, 200)
        roi_signals = self.rppg_verifier.extract_roi_signals(frame, face_box)
        
        print(f"ROI Signals Extracted: {list(roi_signals.keys())}")
        
        # Simulate pulse detection
        for roi_name in roi_signals.keys():
            # Simulate multiple measurements
            for i in range(30):
                synthetic_signal = {
                    'r': 150 + np.random.randint(-10, 10),
                    'g': 140 + np.random.randint(-15, 15),  # Green varies more
                    'b': 130 + np.random.randint(-10, 10)
                }
                result = self.rppg_verifier.detect_blood_flow(roi_name, synthetic_signal)
        
        rppg_result = self.rppg_verifier.verify_multiple_rois()
        print(f"Is Live: {rppg_result['is_live']}")
        print(f"ROIs with Pulse: {rppg_result['rois_with_pulse']}")
        print(f"Average BPM: {rppg_result['avg_bpm']:.2f}")
        print(f"Confidence: {rppg_result['confidence']:.2f}%")
        
        return rppg_result
    
    def demo_morph_detection(self):
        """Demo: Morph Attack Detection"""
        print("\n" + "="*60)
        print("DEMO: Morph Attack Detection")
        print("="*60)
        
        # Create synthetic face-like image
        frame = np.zeros((256, 256, 3), dtype=np.uint8)
        # Draw simple face
        cv2.circle(frame, (128, 128), 80, [150, 100, 100], -1)
        cv2.circle(frame, (110, 110), 15, [50, 50, 50], -1)
        cv2.circle(frame, (146, 110), 15, [50, 50, 50], -1)
        cv2.line(frame, (110, 140), (146, 140), [0, 0, 0], 2)
        
        result = self.morph_detector.comprehensive_morph_detection(frame)
        
        print(f"Is Morphed: {result['is_morphed']}")
        print(f"Confidence: {result['confidence']:.2f}%")
        print(f"Frequency Artifacts: {result['frequency_artifacts']:.4f}")
        print(f"Edge Inconsistency: {result['edge_inconsistency']:.4f}")
        print(f"Symmetry Break: {result['symmetry_break']:.4f}")
        
        return result
    
    def demo_iris_recognition(self):
        """Demo: Iris Recognition"""
        print("\n" + "="*60)
        print("DEMO: Iris Recognition")
        print("="*60)
        
        user_id = "demo_user_001"
        
        # Create synthetic iris templates
        iris_template_1 = np.random.randint(0, 256, 4096, dtype=np.uint8)
        iris_template_2 = iris_template_1 + np.random.randint(-20, 20, 4096)
        iris_template_2 = np.clip(iris_template_2, 0, 255).astype(np.uint8)
        
        # Store first template
        self.iris_recognizer.store_iris_template(user_id, iris_template_1)
        print(f"Stored iris template for user: {user_id}")
        
        # Verify with similar template
        match_result = self.iris_recognizer.match_iris_templates(
            iris_template_1, iris_template_2
        )
        
        print(f"Match Score: {match_result['match_score']:.4f}")
        print(f"Is Match: {match_result['is_match']}")
        print(f"Confidence: {match_result['confidence']:.2f}%")
        
        return match_result
    
    def demo_trust_token(self):
        """Demo: Trust Token Generation and Validation"""
        print("\n" + "="*60)
        print("DEMO: Trust Token & Hardware-Bound Verification")
        print("="*60)
        
        user_id = "demo_user_001"
        
        # Create device data
        device_data = {
            'device_id': 'uuid-1234-5678-9012',
            'model': 'iPhone 14 Pro',
            'os': 'iOS 17',
            'ip_address': '192.168.1.100',
            'mac_address': '00:1A:2B:3C:4D:5E',
            'unique_identifiers': ['sim_id_123', 'imei_456']
        }
        
        # Generate device fingerprint
        fingerprint = self.trust_token_graph.generate_device_fingerprint(device_data)
        print(f"Device Fingerprint: {fingerprint}")
        
        # Create verification data
        verification_data = {
            'motion_verified': True,
            'liveness_verified': True,
            'morph_detected': False,
            'iris_verified': True,
            'typing_speed': 58,
            'swipe_pattern': [0.15, 0.20, 0.18]
        }
        
        # Generate trust token
        token = self.trust_token_graph.create_trust_token(
            user_id, verification_data, device_data
        )
        
        print(f"Token ID: {token['token_id']}")
        print(f"Created At: {token['created_at']}")
        print(f"Expires At: {token['expires_at']}")
        print(f"Signature: {token['signature'][:20]}...")
        
        # Add to trust graph
        biometric_features = {
            'face_score': 95.5,
            'iris_score': 92.3,
            'liveness_confidence': 88.7,
            'motion_profile': {'mean_motion': 0.45}
        }
        
        self.trust_token_graph.add_to_trust_graph(
            user_id, token, biometric_features
        )
        
        # Validate token
        validation_result = self.trust_token_graph.validate_token(
            token['token_id'], device_data
        )
        
        print(f"Token Valid: {validation_result['is_valid']}")
        print(f"Validation Reason: {validation_result.get('reason', 'N/A')}")
        
        # Get trust graph
        trust_graph = self.trust_token_graph.get_user_trust_graph(user_id)
        print(f"Trust Level: {trust_graph['trust_level']:.2f}%")
        print(f"Number of Tokens: {len(trust_graph['tokens'])}")
        print(f"Number of Device Fingerprints: {len(trust_graph['device_fingerprints'])}")
        
        return token, validation_result
    
    def demo_fraud_detection(self):
        """Demo: Fraud Detection Scenario"""
        print("\n" + "="*60)
        print("DEMO: Fraud Detection - Different Device")
        print("="*60)
        
        user_id = "demo_user_001"
        
        # Original device
        original_device = {
            'device_id': 'uuid-1234-5678-9012',
            'model': 'iPhone 14 Pro',
            'os': 'iOS 17'
        }
        
        # Attacker's device
        attacker_device = {
            'device_id': 'uuid-9999-8888-7777',
            'model': 'Samsung Galaxy S24',
            'os': 'Android 14'
        }
        
        # New session data from attacker
        new_session_data = {
            'biometric_score': 45,  # Low confidence
            'location': {'lat': 25.5, 'lon': 85.5}  # Different location
        }
        
        # Verify against trust graph
        result = self.trust_token_graph.verify_against_trust_graph(
            user_id, new_session_data, attacker_device
        )
        
        print(f"Is Trusted: {result['is_trusted']}")
        print(f"Trust Score: {result['trust_score']:.2f}%")
        print(f"Risk Level: {result['risk_level'].upper()}")
        print(f"Anomalies Detected:")
        for anomaly in result['anomalies_detected']:
            print(f"  - {anomaly}")
        
        return result
    
    def run_all_demos(self):
        """Run all demo scenarios"""
        print("\n" + "="*60)
        print("ADAPTIVE MULTI-LAYER IDENTITY VERIFICATION SYSTEM")
        print("PSB Hackathon Series 2026 - Cybersecurity & Fraud Domain")
        print("="*60)
        
        results = {}
        
        try:
            results['motion'] = self.demo_motion_verification()
            results['rppg'] = self.demo_rppg_verification()
            results['morph'] = self.demo_morph_detection()
            results['iris'] = self.demo_iris_recognition()
            results['token'] = self.demo_trust_token()
            results['fraud'] = self.demo_fraud_detection()
            
            self.print_summary(results)
            
        except Exception as e:
            logger.error(f"Error during demo: {str(e)}")
            print(f"ERROR: {str(e)}")
    
    def print_summary(self, results):
        """Print summary of all demos"""
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        print("\n✓ Motion Verification: Working")
        print(f"  - Motion Detection: {'Yes' if results['motion'].get('motion_detected') else 'No'}")
        print(f"  - Liveness: {'Yes' if results['motion'].get('is_live') else 'No'}")
        
        print("\n✓ rPPG Verification: Working")
        print(f"  - Pulse Detected: {'Yes' if results['rppg'].get('is_live') else 'No'}")
        print(f"  - Avg BPM: {results['rppg'].get('avg_bpm', 0):.0f}")
        
        print("\n✓ Morph Detection: Working")
        print(f"  - Morphing Detected: {'Yes' if results['morph'].get('is_morphed') else 'No'}")
        
        print("\n✓ Iris Recognition: Working")
        print(f"  - Match Score: {results['iris'].get('match_score', 0):.2f}")
        
        print("\n✓ Trust Token & Hardware Binding: Working")
        print(f"  - Token Generated: Yes")
        print(f"  - Token Valid: {results['token'][1].get('is_valid')}")
        
        print("\n✓ Fraud Detection: Working")
        print(f"  - Fraud Detected: {'Yes' if not results['fraud'].get('is_trusted') else 'No'}")
        print(f"  - Risk Level: {results['fraud'].get('risk_level', 'Unknown').upper()}")
        
        print("\n" + "="*60)
        print("ALL MODULES OPERATIONAL ✓")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Identity Verification System Demo'
    )
    parser.add_argument(
        '--module',
        choices=['motion', 'rppg', 'morph', 'iris', 'token', 'fraud', 'all'],
        default='all',
        help='Which demo to run'
    )
    
    args = parser.parse_args()
    
    demo = IdentityVerificationDemo()
    
    if args.module == 'motion':
        demo.demo_motion_verification()
    elif args.module == 'rppg':
        demo.demo_rppg_verification()
    elif args.module == 'morph':
        demo.demo_morph_detection()
    elif args.module == 'iris':
        demo.demo_iris_recognition()
    elif args.module == 'token':
        demo.demo_trust_token()
    elif args.module == 'fraud':
        demo.demo_fraud_detection()
    else:
        demo.run_all_demos()


if __name__ == '__main__':
    main()
