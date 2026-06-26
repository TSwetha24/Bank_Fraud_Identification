"""
Database Models and Schema
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()


class User(Base):
    """User model for storing user identity information"""
    __tablename__ = "users"
    
    user_id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, index=True)
    full_name = Column(String(255))
    kyc_status = Column(String(50), default='pending')  # pending, approved, rejected
    kyc_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BiometricProfile(Base):
    """Store user biometric profiles"""
    __tablename__ = "biometric_profiles"
    
    profile_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    face_vector = Column(JSON)  # Face embedding
    iris_template = Column(JSON)  # Iris template
    behavioral_signature = Column(JSON)  # Typing speed, swipe patterns, etc.
    motion_profile = Column(JSON)  # Motion patterns
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)


class VerificationSession(Base):
    """Track verification sessions"""
    __tablename__ = "verification_sessions"
    
    session_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    verification_type = Column(String(50))  # kyc, login, recovery, etc.
    motion_verified = Column(Boolean, default=False)
    liveness_verified = Column(Boolean, default=False)
    morph_detected = Column(Boolean, default=False)
    iris_verified = Column(Boolean, default=False)
    final_verdict = Column(String(50))  # approved, rejected, needs_review
    confidence_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    details = Column(JSON)


class TrustToken(Base):
    """Hardware-bound trust tokens"""
    __tablename__ = "trust_tokens"
    
    token_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    device_fingerprint = Column(String(64), index=True)
    device_data = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_used = Column(DateTime, nullable=True)
    signature = Column(String(64))


class AnomalyLog(Base):
    """Log suspicious activities"""
    __tablename__ = "anomaly_logs"
    
    log_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    anomaly_type = Column(String(100))  # device_change, location_change, etc.
    severity = Column(String(20))  # low, medium, high, critical
    details = Column(JSON)
    action_taken = Column(String(100))  # blocked, challenged, allowed
    created_at = Column(DateTime, default=datetime.utcnow)


class MorphAttackLog(Base):
    """Log morph attack detection attempts"""
    __tablename__ = "morph_attack_logs"
    
    log_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=True)
    morph_confidence = Column(Float)
    artifact_score = Column(Float)
    edge_inconsistency = Column(Float)
    symmetry_break = Column(Float)
    is_morphed = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)


class IrisVerificationLog(Base):
    """Log iris verification attempts"""
    __tablename__ = "iris_verification_logs"
    
    log_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    iris_detected = Column(Boolean)
    match_score = Column(Float)
    is_match = Column(Boolean)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAssessment(Base):
    """Overall risk assessment for transactions/logins"""
    __tablename__ = "risk_assessments"
    
    assessment_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), index=True)
    session_id = Column(String(36))
    risk_score = Column(Float)  # 0-100
    risk_level = Column(String(20))  # low, medium, high, critical
    factors = Column(JSON)  # Risk factors detected
    recommendation = Column(String(100))  # allow, challenge, block
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = os.getenv('DATABASE_URL', 'sqlite:///./bank_fraud.db')
        
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    def close_session(self, session):
        """Close database session"""
        session.close()

    def get_user(self, user_id: str):
        """Return a user record if it exists"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.user_id == user_id).first()
        finally:
            self.close_session(session)

    def get_biometric_profile(self, user_id: str):
        """Return a biometric profile for an existing user"""
        session = self.get_session()
        try:
            return session.query(BiometricProfile).filter(BiometricProfile.user_id == user_id).first()
        finally:
            self.close_session(session)

    def store_face_vector(self, user_id: str, face_vector: list):
        """Store a face vector for an enrolled user"""
        session = self.get_session()
        try:
            profile = session.query(BiometricProfile).filter(BiometricProfile.user_id == user_id).first()
            if not profile:
                profile = BiometricProfile(
                    profile_id=str(__import__('uuid').uuid4()),
                    user_id=user_id,
                    face_vector=face_vector,
                    iris_template={},
                    behavioral_signature={},
                    motion_profile={},
                    verified=True
                )
                session.add(profile)
            else:
                profile.face_vector = face_vector
                profile.verified = True
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            self.close_session(session)

    def get_face_vector(self, user_id: str):
        """Return the stored face vector for a user"""
        session = self.get_session()
        try:
            profile = session.query(BiometricProfile).filter(BiometricProfile.user_id == user_id).first()
            return profile.face_vector if profile else None
        finally:
            self.close_session(session)

    def list_users(self):
        """Return all registered users"""
        session = self.get_session()
        try:
            return session.query(User).all()
        finally:
            self.close_session(session)

    def create_user(self, user_id: str, email: str, full_name: str, kyc_status: str = 'approved'):
        """Create a new user if it does not already exist"""
        session = self.get_session()
        try:
            if session.query(User).filter(User.user_id == user_id).first():
                return False
            user = User(
                user_id=user_id,
                email=email,
                full_name=full_name,
                kyc_status=kyc_status
            )
            session.add(user)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            self.close_session(session)

    def create_biometric_profile(self,
                                 user_id: str,
                                 face_vector=None,
                                 iris_template=None,
                                 behavioral_signature=None,
                                 motion_profile=None,
                                 verified: bool = False):
        """Create a biometric profile for a user"""
        session = self.get_session()
        try:
            if not session.query(User).filter(User.user_id == user_id).first():
                return False
            if session.query(BiometricProfile).filter(BiometricProfile.user_id == user_id).first():
                return False
            profile = BiometricProfile(
                profile_id=str(__import__('uuid').uuid4()),
                user_id=user_id,
                face_vector=face_vector or {},
                iris_template=iris_template or {},
                behavioral_signature=behavioral_signature or {},
                motion_profile=motion_profile or {},
                verified=verified
            )
            session.add(profile)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            self.close_session(session)
