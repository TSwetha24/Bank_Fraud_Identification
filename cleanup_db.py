#!/usr/bin/env python3
"""
Clean up database by removing all biometric and user data
(keeps demo users for testing)
"""

import os
from src.utils.database import DatabaseManager, User, BiometricProfile, VerificationSession, TrustToken
from src.utils.database import AnomalyLog, MorphAttackLog, IrisVerificationLog, RiskAssessment

def cleanup_database():
    """Clear all user biometric data from database"""
    
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Delete all biometric/verification data
        print("Clearing biometric profiles...")
        session.query(BiometricProfile).delete()
        
        print("Clearing verification sessions...")
        session.query(VerificationSession).delete()
        
        print("Clearing trust tokens...")
        session.query(TrustToken).delete()
        
        print("Clearing anomaly logs...")
        session.query(AnomalyLog).delete()
        
        print("Clearing morph attack logs...")
        session.query(MorphAttackLog).delete()
        
        print("Clearing iris verification logs...")
        session.query(IrisVerificationLog).delete()
        
        print("Clearing risk assessments...")
        session.query(RiskAssessment).delete()
        
        # Delete all users EXCEPT demo users
        print("Clearing non-demo users...")
        session.query(User).filter(
            ~User.user_id.in_(['demo_user_001', 'demo_user_002'])
        ).delete()
        
        session.commit()
        print("\n✅ Database cleaned successfully!")
        print("Demo users preserved for testing.")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")
        session.rollback()
    finally:
        session.close()

def cleanup_db_file():
    """Remove the SQLite database file entirely"""
    db_file = "bank_fraud.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Deleted {db_file}")
    else:
        print(f"ℹ️  No {db_file} found")

if __name__ == "__main__":
    print("🗑️  Cleaning up database...\n")
    
    # Option 1: Clear data but keep schema
    cleanup_database()
    
    print("\n" + "="*60)
    print("Ready to push to GitHub!")
    print("="*60)
