#!/usr/bin/env python3
"""
Script to verify admin IDs are loaded correctly from config
"""

try:
    from config import ADMIN_IDS
    
    print("✅ Admin IDs loaded successfully!")
    print(f"📋 Current Admin IDs: {ADMIN_IDS}")
    print(f"📊 Total Admins: {len(ADMIN_IDS)}")
    
    # Check if the new admin ID is included
    new_admin_id = 7085119805
    if new_admin_id in ADMIN_IDS:
        print(f"✅ New admin ID {new_admin_id} is correctly configured!")
    else:
        print(f"❌ New admin ID {new_admin_id} is NOT found in the config!")
    
    # Check if the original admin ID is still there
    original_admin_id = 1298849354
    if original_admin_id in ADMIN_IDS:
        print(f"✅ Original admin ID {original_admin_id} is still configured!")
    else:
        print(f"❌ Original admin ID {original_admin_id} is NOT found!")
        
except Exception as e:
    print(f"❌ Error loading config: {e}")
