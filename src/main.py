"""
FastAPI Application
Main entry point for the Identity Verification System
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import logging
import os
import tempfile
from typing import Optional
import cv2
import numpy as np
import io
from PIL import Image

from src.utils.config import get_config
from src.utils.logger import get_logger
from src.utils.database import DatabaseManager
from src.modules.motion_verifier import MotionVerifier
from src.modules.rppg_verifier import rPPGVerifier
from src.modules.morph_detector import MorphDetector
from src.modules.iris_recognizer import IrisRecognizer
from src.modules.trust_token import TrustTokenGraph
from src.modules.face_recognizer import FaceRecognizer

# Configuration
config = get_config()
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Identity Trust & Protection System",
    description="Multi-layer biometric verification for banking security",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db_manager = DatabaseManager(config.DATABASE_URL)
motion_verifier = MotionVerifier()
rppg_verifier = rPPGVerifier()
morph_detector = MorphDetector()
iris_recognizer = IrisRecognizer()
face_recognizer = FaceRecognizer()
trust_token_graph = TrustTokenGraph()


def create_pending_user(user_id: str) -> bool:
    """Create a pending user profile for a first-time KYC applicant."""
    if db_manager.get_user(user_id) is not None:
        return False

    placeholder_email = f"{user_id}@pending.local"
    return db_manager.create_user(
        user_id=user_id,
        email=placeholder_email,
        full_name=user_id,
        kyc_status="pending"
    )


def generate_user_id() -> str:
    """Auto-generate a unique user_id."""
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]
    return f"user_{unique_suffix}"


def find_matching_user_in_db(probe_vector: list, match_threshold: float = 0.90) -> Optional[str]:
    """Search database for a user matching the probe face vector.
    Returns matching user_id if found, None otherwise.
    """
    if probe_vector is None:
        return None
    
    all_users = db_manager.list_users()
    best_match = None
    best_score = 0.0
    
    for user in all_users:
        stored_vector = db_manager.get_face_vector(user.user_id)
        if stored_vector is None:
            continue
        
        match_result = face_recognizer.match_face_vectors(stored_vector, probe_vector)
        match_score = match_result['match_score']
        
        if match_score > best_score:
            best_score = match_score
            best_match = user.user_id
    
    # Return match only if above threshold
    if best_score >= match_threshold:
        logger.info(f"Found matching user {best_match} with score {best_score}")
        return best_match
    
    return None


def extract_video_frames(video_bytes: bytes, max_frames: int = 200):
    """Extract a sample of frames from an uploaded video stream."""
    frames = []
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            temp_path = tmp.name

        cap = cv2.VideoCapture(temp_path)
        if not cap.isOpened():
            return frames

        while len(frames) < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return frames


def analyze_video_for_deepfake(frames):
    """Analyze video frames for deepfake, liveness, and morphing signals."""
    if not frames:
        return {
            'deepfake_detected': False,
            'deepfake_score': 0.0,
            'video_frames_analyzed': 0,
            'video_is_live': False,
            'video_rppg_result': {'is_live': False, 'confidence': 0.0},
            'video_morph_score': 0.0,
            'face_frames': 0,
            'motion_votes': 0,
            'morph_votes': 0
        }

    rppg_verifier.reset()
    motion_votes = 0
    face_frames = 0
    morph_votes = 0
    expression_detected = False
    prev_frame = None

    for frame in frames:
        motion_result = motion_verifier.detect_face_motion(frame)
        face_box = motion_result.get('face_box')

        if face_box is not None:
            face_frames += 1
            if motion_result.get('is_live'):
                motion_votes += 1

            roi_signals = rppg_verifier.extract_roi_signals(frame, face_box)
            for roi_name, signal in roi_signals.items():
                if signal and any(value is not None for value in signal.values()):
                    rppg_verifier.detect_blood_flow(roi_name, signal)

        if prev_frame is not None:
            expr_result = rppg_verifier.detect_expression(prev_frame, frame)
            if expr_result.get('expression_detected'):
                expression_detected = True

        morph_result = morph_detector.comprehensive_morph_detection(frame)
        if morph_result.get('is_morphed'):
            morph_votes += 1

        prev_frame = frame

    rppg_result = rppg_verifier.verify_multiple_rois()
    total_frames = len(frames)
    deepfake_score = 0

    # Stricter deepfake detection
    if face_frames / total_frames < 0.5:
        deepfake_score += 2  # Increased weight
    if face_frames > 0 and motion_votes / face_frames < 0.3:  # Stricter: < 0.3 instead of < 0.4
        deepfake_score += 1
    if not rppg_result['is_live']:
        deepfake_score += 2  # Increased weight
    if morph_votes > total_frames / 3:
        deepfake_score += 1
    
    # Additional check: Low motion consistency (deepfakes often have unnatural jitter)
    if face_frames > 0 and motion_votes / face_frames < 0.5:
        deepfake_score += 1  # +1 for inconsistent motion

    return {
        'deepfake_detected': deepfake_score >= 3,  # Require 3 points (more robust detection)
        'deepfake_score': min((deepfake_score / 7) * 100, 100.0),  # Adjusted scale
        'video_frames_analyzed': total_frames,
        'video_is_live': rppg_result['is_live'] or motion_votes > total_frames / 3,
        'video_rppg_result': rppg_result,
        'video_morph_score': morph_votes / total_frames if total_frames else 0.0,
        'face_frames': face_frames,
        'motion_votes': motion_votes,
        'morph_votes': morph_votes,
        'expression_detected': expression_detected
    }


@app.on_event("startup")
async def startup_event():
    """Seed demo users for prototype validation."""
    db_manager.init_db()
    db_manager.create_user(
        user_id="demo_user_001",
        email="demo1@example.com",
        full_name="Demo User 1",
        kyc_status="approved"
    )
    db_manager.create_user(
        user_id="demo_user_002",
        email="demo2@example.com",
        full_name="Demo User 2",
        kyc_status="approved"
    )


# Pydantic Models
class VerificationRequest(BaseModel):
    user_id: str
    verification_type: str  # kyc, login, recovery
    device_data: dict
    location: Optional[dict] = None


class KYCVerificationRequest(VerificationRequest):
    face_image: Optional[str] = None  # base64 encoded
    video_stream: Optional[str] = None


class LivenessResponse(BaseModel):
    is_live: bool
    confidence: float
    motion_detected: bool
    rppg_verified: bool
    expression_detected: bool
    face_detected: bool
    user_exists: bool
    face_enrolled: bool
    face_match_score: float
    face_match_verified: bool


class MorphDetectionResponse(BaseModel):
    is_morphed: bool
    confidence: float
    artifact_score: float
    edge_inconsistency: float
    symmetry_break: float


class IrisVerificationResponse(BaseModel):
    iris_detected: bool
    match_score: float
    is_match: bool
    confidence: float


class VerificationResponse(BaseModel):
    user_id: str
    verification_id: str
    status: str  # approved, rejected, needs_review
    risk_level: str  # low, medium, high, critical
    confidence: float
    details: dict


class EnrollmentResponse(BaseModel):
    user_id: str
    enrolled: bool
    face_match_score: float
    message: str


# Routes

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Identity Trust & Protection System"
    }


@app.get("/api/demo/users")
async def list_demo_users():
    """List seeded demo users for prototype validation"""
    users = db_manager.list_users()
    return [
        {
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "kyc_status": user.kyc_status
        }
        for user in users
    ]


@app.post("/api/enroll/photo", response_model=EnrollmentResponse)
async def enroll_photo(
    user_id: str = Form(...),
    face_image: UploadFile = File(...)
):
    """Enroll a photo for stored-face matching"""
    try:
        if db_manager.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")

        image_data = await face_image.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image format")

        motion_result = motion_verifier.detect_face_motion(frame)
        face_box = motion_result.get('face_box')
        if face_box is None:
            raise HTTPException(status_code=400, detail="Face not detected in enrollment image")

        face_vector = face_recognizer.extract_face_vector(frame, face_box)
        if face_vector is None:
            raise HTTPException(status_code=400, detail="Could not extract face features")

        db_manager.store_face_vector(user_id, face_vector)

        return EnrollmentResponse(
            user_id=user_id,
            enrolled=True,
            face_match_score=1.0,
            message="Photo enrolled successfully"
        )
    except Exception as e:
        logger.error(f"Enrollment error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify/kyc", response_model=VerificationResponse)
async def verify_kyc(
    user_id: Optional[str] = Form(None),
    device_id: str = Form(...),
    device_model: str = Form(...),
    os: str = Form(...),
    face_image: UploadFile = File(None),
    video_stream: UploadFile = File(None),
    gyro_data: Optional[str] = Form(None)
):
    """
    KYC Verification Endpoint - Enhanced with face-based lookup
    If user_id provided: use it (legacy behavior)
    If user_id NOT provided:
      - Extract face vector
      - Search DB for matching face (>90% similarity)
      - If match found: verify that user
      - If no match + real human face: auto-create new user
      - If deepfake: reject without enrolling
    """
    try:
        if not face_image and not video_stream:
            raise HTTPException(status_code=400, detail="Face image or video stream required")

        # READ ALL FILES ONCE
        frame = None
        video_frames = None
        video_analysis = None

        if face_image:
            image_data = await face_image.read()
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                raise HTTPException(status_code=400, detail="Invalid image format")

        if video_stream:
            video_bytes = await video_stream.read()
            video_frames = extract_video_frames(video_bytes)
            if video_frames:
                frame = video_frames[0]
            video_analysis = analyze_video_for_deepfake(video_frames)
            logger.info(f"Video analysis complete - deepfake_detected: {video_analysis['deepfake_detected']}")

        if frame is None:
            raise HTTPException(status_code=400, detail="Unable to decode a valid face image from the submission")

        # FACE-BASED LOOKUP (if user_id not provided)
        if not user_id:
            logger.info("No user_id provided - performing face-based lookup")
            
            # If deepfake detected, reject BEFORE checking face (deepfakes may have no detectable face)
            if video_analysis and video_analysis['deepfake_detected']:
                logger.warning("Rejecting deepfake before enrollment")
                return VerificationResponse(
                    user_id="unknown",
                    verification_id=str(__import__('uuid').uuid4()),
                    status="rejected",
                    risk_level="critical",
                    confidence=0.0,
                    details={
                        'motion_verified': False,
                        'liveness_verified': False,
                        'morph_verified': False,
                        'iris_verified': False,
                        'expression_detected': False,
                        'deepfake_detected': True,
                        'deepfake_score': video_analysis['deepfake_score'],
                        'video_frames_analyzed': video_analysis['video_frames_analyzed'],
                        'video_morph_score': video_analysis['video_morph_score'],
                        'face_box': False,
                        'face_match_verified': False,
                        'face_match_score': 0.0,
                        'user_exists': False,
                        'new_user_created': False,
                        'reason': 'Deepfake detected - enrollment rejected'
                    }
                )
            
            motion_result = motion_verifier.detect_face_motion(frame)
            face_box = motion_result.get('face_box')
            
            if face_box is None:
                raise HTTPException(status_code=400, detail="Face not detected in image/video")
            
            # Extract face vector for matching
            probe_vector = face_recognizer.extract_face_vector(frame, face_box)
            
            # Search for matching user
            matched_user_id = find_matching_user_in_db(probe_vector, match_threshold=0.90)
            
            if matched_user_id:
                user_id = matched_user_id
                logger.info(f"Face matched to existing user: {user_id}")
            else:
                # No match found - auto-create new user if face is real
                if video_analysis and not video_analysis['video_is_live']:
                    logger.warning("New face not detected as live - rejecting")
                    return VerificationResponse(
                        user_id="unknown",
                        verification_id=str(__import__('uuid').uuid4()),
                        status="rejected",
                        risk_level="high",
                        confidence=0.0,
                        details={
                            'motion_verified': False,
                            'liveness_verified': False,
                            'morph_verified': False,
                            'iris_verified': False,
                            'expression_detected': False,
                            'deepfake_detected': False,
                            'deepfake_score': 0.0,
                            'video_frames_analyzed': video_analysis['video_frames_analyzed'] if video_analysis else 0,
                            'video_morph_score': video_analysis['video_morph_score'] if video_analysis else 0.0,
                            'face_box': face_box is not None,
                            'face_match_verified': False,
                            'face_match_score': 0.0,
                            'user_exists': False,
                            'new_user_created': False,
                            'reason': 'No face match found and liveness not verified'
                        }
                    )
                
                # Generate new user_id and create pending profile
                user_id = generate_user_id()
                create_pending_user(user_id)
                logger.info(f"Auto-created new user: {user_id}")
        
        logger.info(f"Starting KYC verification for user {user_id}")

        user = db_manager.get_user(user_id)
        user_exists = user is not None
        new_user_created = False

        if not user_exists:
            new_user_created = create_pending_user(user_id)
            logger.info(f"Created pending profile for first-time user {user_id}")

        # Initialize verification results
        verification_results = {
            'motion_verified': False,
            'liveness_verified': False,
            'morph_verified': False,
            'iris_verified': False,
            'expression_detected': False,
            'deepfake_detected': False,
            'deepfake_score': 0.0,
            'video_frames_analyzed': 0,
            'video_morph_score': 0.0
        }

        # If video was analyzed, populate those results
        if video_analysis:
            verification_results['expression_detected'] = video_analysis['expression_detected']
            verification_results['deepfake_detected'] = video_analysis['deepfake_detected']
            verification_results['deepfake_score'] = video_analysis['deepfake_score']
            verification_results['video_frames_analyzed'] = video_analysis['video_frames_analyzed']
            verification_results['video_morph_score'] = video_analysis['video_morph_score']

        if frame is None:
            raise HTTPException(status_code=400, detail="Unable to decode a valid face image from the submission")

        # 1. Motion Verification
        if config.ENABLE_MOTION_VERIFICATION:
            motion_result = motion_verifier.detect_face_motion(frame)
            verification_results['motion_verified'] = motion_result['is_live']
            verification_results['face_box'] = motion_result.get('face_box') is not None
            logger.info(f"Motion verification: {motion_result['is_live']}")
        else:
            motion_result = {'face_box': None, 'is_live': False}

        # 2. Liveness Detection (rPPG)
        if config.ENABLE_LIVENESS_DETECTION:
            if video_analysis is not None:
                verification_results['liveness_verified'] = video_analysis['video_is_live'] and video_analysis['expression_detected']
                logger.info(
                    f"Video-based liveness detection: {video_analysis['video_is_live']} | challenge blink/eye-close: {video_analysis['expression_detected']}"
                )
            else:
                roi_box = motion_result.get('face_box') or (50, 50, 200, 250)
                roi_signals = rppg_verifier.extract_roi_signals(frame, roi_box)
                liveness = False
                for roi_name, signal in roi_signals.items():
                    if signal:
                        result = rppg_verifier.detect_blood_flow(roi_name, signal)
                        if result.get('pulse_detected'):
                            liveness = True
                verification_results['liveness_verified'] = liveness
                logger.info(f"Liveness detection: {liveness}")

        # 3. Stored Face Match Verification
        face_box = motion_result.get('face_box')
        if face_box is None:
            motion_result = motion_verifier.detect_face_motion(frame)
            face_box = motion_result.get('face_box')

        face_match_score = 0.0
        stored_face_match = False
        if face_box is not None:
            probe_vector = face_recognizer.extract_face_vector(frame, face_box)
            stored_vector = db_manager.get_face_vector(user_id)
            if probe_vector is not None and stored_vector is not None:
                match_result = face_recognizer.match_face_vectors(stored_vector, probe_vector)
                face_match_score = match_result['match_score']
                stored_face_match = match_result['is_match']
                verification_results['face_match_verified'] = stored_face_match
                verification_results['face_match_score'] = face_match_score
                logger.info(f"Stored face match score: {face_match_score}")
            elif probe_vector is not None and stored_vector is None:
                verification_results['face_match_verified'] = False
                verification_results['face_match_score'] = 0.0
                if new_user_created:
                    db_manager.store_face_vector(user_id, probe_vector)
                    verification_results['face_enrolled'] = True
                    logger.info(f"Stored face vector for new user {user_id}")
            else:
                verification_results['face_match_verified'] = False
                verification_results['face_match_score'] = 0.0
        else:
            verification_results['face_match_verified'] = False
            verification_results['face_match_score'] = 0.0
            verification_results['face_enrolled'] = False

        # 4. Morph Detection
        if config.ENABLE_MORPH_DETECTION:
            morph_result = morph_detector.comprehensive_morph_detection(frame)
            verification_results['morph_verified'] = not morph_result['is_morphed']
            verification_results['morph_confidence'] = morph_result['confidence']
            verification_results['artifact_score'] = morph_result['frequency_artifacts']
            verification_results['edge_inconsistency'] = morph_result['edge_inconsistency']
            verification_results['symmetry_break'] = morph_result['symmetry_break']
            logger.info(f"Morph detection: {morph_result}")

        # 5. Iris Recognition
        if config.ENABLE_IRIS_RECOGNITION:
            iris_landmarks = iris_recognizer.detect_iris_landmarks(frame)
            if iris_landmarks['iris_detected']:
                iris_template = iris_recognizer.extract_iris_template(frame, iris_landmarks)
                iris_recognizer.store_iris_template(user_id, iris_template)
                verification_results['iris_verified'] = True
                logger.info("Iris recognition: Verified")

        verification_results['user_exists'] = user_exists
        verification_results['new_user_created'] = new_user_created

        # Calculate final verdict
        passed_checks = sum([
            verification_results['motion_verified'],
            verification_results['liveness_verified'],
            verification_results['morph_verified'],
            verification_results['iris_verified']
        ])
        total_checks = 4

        if video_analysis is not None:
            total_checks += 1
            if verification_results['expression_detected']:
                passed_checks += 1

        if verification_results['deepfake_detected']:
            status = "rejected"
            risk_level = "critical"
            confidence = 0.0
        elif passed_checks >= 3:
            status = "approved"
            risk_level = "low"
            confidence = (passed_checks / total_checks) * 100
        elif passed_checks >= 2:
            status = "needs_review"
            risk_level = "medium"
            confidence = (passed_checks / total_checks) * 100
        else:
            status = "rejected"
            risk_level = "high"
            confidence = (passed_checks / total_checks) * 100

        device_data = {
            'device_id': device_id,
            'model': device_model,
            'os': os
        }

        if config.ENABLE_TRUST_TOKEN:
            token = trust_token_graph.create_trust_token(
                user_id,
                verification_results,
                device_data
            )
            trust_token_graph.add_to_trust_graph(user_id, token, {
                'face_score': confidence,
                'iris_score': 100 if verification_results['iris_verified'] else 0,
                'liveness_confidence': confidence,
                'motion_profile': {}
            })

        logger.info(f"KYC verification completed for {user_id}: {status}")

        return VerificationResponse(
            user_id=user_id,
            verification_id=str(__import__('uuid').uuid4()),
            status=status,
            risk_level=risk_level,
            confidence=confidence,
            details=verification_results
        )
    except Exception as e:
        logger.error(f"KYC verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify/liveness", response_model=LivenessResponse)
async def verify_liveness(
    user_id: str = Form(...),
    face_image: UploadFile = File(...)
):
    """
    Liveness Detection Endpoint
    Verifies using rPPG and motion detection
    """
    try:
        image_data = await face_image.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Motion detection
        motion_result = motion_verifier.detect_face_motion(frame)
        face_box = motion_result.get('face_box')
        face_detected = face_box is not None
        
        # rPPG verification
        if face_detected:
            roi_signals = rppg_verifier.extract_roi_signals(frame, face_box)
            for roi_name, signal in roi_signals.items():
                if signal and any(value is not None for value in signal.values()):
                    rppg_verifier.detect_blood_flow(roi_name, signal)
        else:
            roi_signals = {}
        
        rppg_result = rppg_verifier.verify_multiple_rois()
        
        user_exists = db_manager.get_user(user_id) is not None
        stored_vector = db_manager.get_face_vector(user_id)
        face_enrolled = stored_vector is not None
        
        face_match_score = 0.0
        face_match_verified = False
        if face_detected and face_enrolled:
            probe_vector = face_recognizer.extract_face_vector(frame, face_box)
            if probe_vector is not None:
                match_result = face_recognizer.match_face_vectors(stored_vector, probe_vector)
                face_match_score = match_result['match_score']
                face_match_verified = match_result['is_match']

        is_live = (
            face_detected
            and user_exists
            and face_enrolled
            and face_match_verified
            and (motion_result['is_live'] or rppg_result['is_live'])
        )
        confidence = float(rppg_result['confidence']) if (user_exists and face_match_verified) else 0.0
        
        return LivenessResponse(
            is_live=is_live,
            confidence=confidence,
            motion_detected=motion_result['motion_detected'],
            rppg_verified=rppg_result['is_live'],
            expression_detected=False,
            face_detected=face_detected,
            user_exists=user_exists,
            face_enrolled=face_enrolled,
            face_match_score=face_match_score,
            face_match_verified=face_match_verified
        )
    
    except Exception as e:
        logger.error(f"Liveness verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify/morph-detection", response_model=MorphDetectionResponse)
async def detect_morph(
    user_id: str = Form(...),
    face_image: UploadFile = File(...)
):
    """
    Morph Attack Detection Endpoint
    """
    try:
        image_data = await face_image.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        result = morph_detector.comprehensive_morph_detection(frame)
        
        return MorphDetectionResponse(
            is_morphed=result['is_morphed'],
            confidence=result['confidence'],
            artifact_score=result['frequency_artifacts'],
            edge_inconsistency=result['edge_inconsistency'],
            symmetry_break=result['symmetry_break']
        )
    
    except Exception as e:
        logger.error(f"Morph detection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify/iris", response_model=IrisVerificationResponse)
async def verify_iris(
    user_id: str = Form(...),
    face_image: UploadFile = File(...)
):
    """
    Iris Recognition Endpoint
    """
    try:
        image_data = await face_image.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        iris_landmarks = iris_recognizer.detect_iris_landmarks(frame)
        iris_template = iris_recognizer.extract_iris_template(frame, iris_landmarks)
        
        match_result = iris_recognizer.verify_against_stored(user_id, iris_template)
        
        return IrisVerificationResponse(
            iris_detected=iris_landmarks['iris_detected'],
            match_score=match_result.get('match_score', 0),
            is_match=match_result.get('is_match', False),
            confidence=match_result.get('confidence', 0)
        )
    
    except Exception as e:
        logger.error(f"Iris verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/token/generate")
async def generate_token(request: VerificationRequest):
    """
    Generate hardware-bound trust token
    """
    try:
        verification_data = {
            'motion_verified': True,
            'liveness_verified': True,
            'morph_detected': False,
            'iris_verified': True
        }
        
        token = trust_token_graph.create_trust_token(
            request.user_id,
            verification_data,
            request.device_data
        )
        
        return {
            "token_id": token['token_id'],
            "created_at": token['created_at'],
            "expires_at": token['expires_at']
        }
    
    except Exception as e:
        logger.error(f"Token generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/token/validate")
async def validate_token(
    user_id: str,
    token_id: str,
    device_data: dict
):
    """
    Validate trust token
    """
    try:
        result = trust_token_graph.validate_token(token_id, device_data)
        return result
    
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trust-graph/{user_id}")
async def get_trust_graph(user_id: str):
    """
    Get user's trust graph
    """
    try:
        graph = trust_token_graph.get_user_trust_graph(user_id)
        
        if not graph:
            raise HTTPException(status_code=404, detail="No trust graph found for user")
        
        return graph
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving trust graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Initialize database
    db_manager.init_db()
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower()
    )
