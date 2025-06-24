#!/usr/bin/env python3
"""
Simple test to verify frontend integration
"""

import os
import sys

# Add frontend to path
sys.path.append('frontend')

def test_imports():
    """Test if all required modules can be imported"""
    try:
        print("Testing frontend imports...")
        
        # Test main imports
        import streamlit as st
        print("✅ Streamlit imported successfully")
        
        import backend_client
        print("✅ Backend client imported successfully")
        
        # Test if chat_component exists
        try:
            import document_chat
            print("✅ Document chat component imported successfully")
        except ImportError as e:
            print(f"⚠️ Document chat component import failed: {e}")
            return False
        
        # Test the chat function
        if hasattr(document_chat, 'render_document_chat_tab'):
            print("✅ Chat render function found")
        else:
            print("❌ Chat render function not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 FRONTEND INTEGRATION TEST")
    print("=" * 50)
    
    success = test_imports()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Frontend integration successful!")
        print("Chat component is ready to use.")
    else:
        print("❌ Frontend integration failed.")
        print("Check imports and file paths.")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
