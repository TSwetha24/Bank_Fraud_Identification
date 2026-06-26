"""
Trust Token Graph Management Module
Hardware-bound trust tokens for session comparison and fraud detection
"""

import json
import hashlib
import hmac
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TrustTokenGraph:
    """
    Manages hardware-bound trust token graphs for each user
    Stores device fingerprints and behavioral profiles
    """
    
    def __init__(self):
        self.token_store = {}
        self.trust_graphs = {}
        self.device_fingerprints = {}
        
    def generate_device_fingerprint(self, device_data: Dict) -> str:
        """
        Generate unique device fingerprint from hardware data
        """
        fingerprint_data = {
            'device_id': device_data.get('device_id', ''),
            'device_model': device_data.get('model', ''),
            'os': device_data.get('os', ''),
            'unique_identifiers': device_data.get('unique_identifiers', [])
        }
        
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_str.encode()).hexdigest()
        
        return fingerprint_hash
    
    def create_trust_token(self, user_id: str, verification_data: Dict, 
                          device_data: Dict) -> Dict:
        """
        Create hardware-bound trust token
        """
        token_id = str(uuid.uuid4())
        device_fingerprint = self.generate_device_fingerprint(device_data)
        
        token = {
            'token_id': token_id,
            'user_id': user_id,
            'device_fingerprint': device_fingerprint,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(days=365)).isoformat(),
            'verification_data': {
                'motion_verified': verification_data.get('motion_verified', False),
                'liveness_verified': verification_data.get('liveness_verified', False),
                'morph_detected': verification_data.get('morph_detected', False),
                'iris_verified': verification_data.get('iris_verified', False),
            },
            'hardware_features': {
                'device_id': device_data.get('device_id'),
                'model': device_data.get('model'),
                'os': device_data.get('os'),
                'ip_address': device_data.get('ip_address'),
                'mac_address': device_data.get('mac_address')
            },
            'behavioral_profile': {
                'average_typing_speed': verification_data.get('typing_speed', 0),
                'average_swipe_pattern': verification_data.get('swipe_pattern', []),
                'location': device_data.get('location'),
            }
        }
        
        # Generate HMAC signature
        token_str = json.dumps({k: v for k, v in token.items() if k != 'signature'}, 
                              sort_keys=True)
        token['signature'] = hmac.new(
            device_fingerprint.encode(),
            token_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        self.token_store[token_id] = token
        
        return token
    
    def add_to_trust_graph(self, user_id: str, token: Dict, 
                          biometric_features: Dict) -> None:
        """
        Add token and biometric features to user's trust graph
        """
        if user_id not in self.trust_graphs:
            self.trust_graphs[user_id] = {
                'user_id': user_id,
                'created_at': datetime.utcnow().isoformat(),
                'tokens': [],
                'biometric_profiles': [],
                'device_fingerprints': [],
                'trust_level': 0.0
            }
        
        graph = self.trust_graphs[user_id]
        
        # Add token
        graph['tokens'].append({
            'token_id': token['token_id'],
            'created_at': token['created_at'],
            'device_fingerprint': token['device_fingerprint']
        })
        
        # Add biometric profile
        graph['biometric_profiles'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'face_recognition_score': biometric_features.get('face_score', 0),
            'iris_recognition_score': biometric_features.get('iris_score', 0),
            'liveness_confidence': biometric_features.get('liveness_confidence', 0),
            'motion_profile': biometric_features.get('motion_profile', {}),
            'blood_flow_pattern': biometric_features.get('blood_flow_pattern', {})
        })
        
        # Add device fingerprint
        if token['device_fingerprint'] not in graph['device_fingerprints']:
            graph['device_fingerprints'].append(token['device_fingerprint'])
        
        # Calculate trust level (0-100)
        trust_level = self._calculate_trust_level(graph)
        graph['trust_level'] = trust_level
    
    def _calculate_trust_level(self, graph: Dict) -> float:
        """
        Calculate trust level based on token history and profiles
        """
        trust_level = 0.0
        
        # Base trust from verified biometrics
        if graph['biometric_profiles']:
            latest_profile = graph['biometric_profiles'][-1]
            avg_confidence = (
                latest_profile.get('face_recognition_score', 0) +
                latest_profile.get('iris_recognition_score', 0) +
                latest_profile.get('liveness_confidence', 0)
            ) / 3
            trust_level = avg_confidence
        
        # Bonus for consistent device fingerprints
        if len(graph['device_fingerprints']) == 1:
            trust_level *= 1.1  # 10% bonus for single device
        
        # Penalty for multiple different devices
        elif len(graph['device_fingerprints']) > 3:
            trust_level *= 0.8  # 20% penalty
        
        return min(trust_level, 100.0)
    
    def verify_against_trust_graph(self, user_id: str, 
                                  new_session_data: Dict,
                                  device_data: Dict) -> Dict:
        """
        Verify new session data against stored trust graph
        """
        result = {
            'is_trusted': False,
            'trust_score': 0.0,
            'anomalies_detected': [],
            'risk_level': 'high'
        }
        
        if user_id not in self.trust_graphs:
            result['anomalies_detected'].append('No trust history for user')
            return result
        
        graph = self.trust_graphs[user_id]
        
        # Check device fingerprint
        new_fingerprint = self.generate_device_fingerprint(device_data)
        device_mismatch = new_fingerprint not in graph['device_fingerprints']
        
        if device_mismatch:
            result['anomalies_detected'].append('Unknown device fingerprint')
        
        # Check biometric consistency
        biometric_score = new_session_data.get('biometric_score', 0)
        
        if biometric_score < 50:
            result['anomalies_detected'].append('Low biometric confidence')
        
        # Check for suspicious patterns
        if new_session_data.get('location') != graph['biometric_profiles'][-1].get('location'):
            result['anomalies_detected'].append('Location change detected')
        
        # Calculate final trust score
        base_trust = graph['trust_level']
        
        if device_mismatch:
            base_trust *= 0.7  # 30% penalty for new device
        
        if biometric_score > 0:
            base_trust = (base_trust + biometric_score) / 2
        
        result['trust_score'] = min(base_trust, 100.0)
        
        # Determine risk level
        if result['trust_score'] > 80:
            result['risk_level'] = 'low'
            result['is_trusted'] = True
        elif result['trust_score'] > 60:
            result['risk_level'] = 'medium'
        else:
            result['risk_level'] = 'high'
        
        return result
    
    def validate_token(self, token_id: str, device_data: Dict) -> Dict:
        """
        Validate trust token
        """
        result = {
            'is_valid': False,
            'token_id': token_id,
            'reason': ''
        }
        
        if token_id not in self.token_store:
            result['reason'] = 'Token not found'
            return result
        
        token = self.token_store[token_id]
        
        # Check expiration
        expires_at = datetime.fromisoformat(token['expires_at'])
        if datetime.utcnow() > expires_at:
            result['reason'] = 'Token expired'
            return result
        
        # Verify device fingerprint
        current_fingerprint = self.generate_device_fingerprint(device_data)
        if current_fingerprint != token['device_fingerprint']:
            result['reason'] = 'Device fingerprint mismatch'
            return result
        
        # Verify signature
        token_copy = {k: v for k, v in token.items() if k != 'signature'}
        token_str = json.dumps(token_copy, sort_keys=True)
        expected_sig = hmac.new(
            token['device_fingerprint'].encode(),
            token_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if token['signature'] != expected_sig:
            result['reason'] = 'Invalid token signature'
            return result
        
        result['is_valid'] = True
        return result
    
    def get_user_trust_graph(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve user's trust graph
        """
        return self.trust_graphs.get(user_id)
    
    def reset_user_trust(self, user_id: str) -> bool:
        """
        Reset user's trust graph (e.g., after suspicious activity)
        """
        try:
            if user_id in self.trust_graphs:
                del self.trust_graphs[user_id]
            # Also remove associated tokens
            self.token_store = {
                tid: token for tid, token in self.token_store.items()
                if token['user_id'] != user_id
            }
            return True
        except Exception as e:
            logger.error(f"Failed to reset trust: {e}")
            return False
