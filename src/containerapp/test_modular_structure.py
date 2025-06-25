#!/usr/bin/env python3
"""
Test script to validate the modular ARGUS backend structure
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported successfully"""
    try:
        print("Testing imports...")
        
        # Test individual modules
        import models
        print("✅ models.py imported successfully")
        
        import dependencies
        print("✅ dependencies.py imported successfully")
        
        import logic_app_manager
        print("✅ logic_app_manager.py imported successfully")
        
        import blob_processing
        print("✅ blob_processing.py imported successfully")
        
        import api_routes
        print("✅ api_routes.py imported successfully")
        
        # Test main app
        import main
        print("✅ main.py imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_app_structure():
    """Test that the FastAPI app has the expected structure"""
    try:
        import main
        app = main.app
        
        # Check app configuration
        assert app.title == "ARGUS Backend"
        assert app.version == "1.0.0"
        print("✅ App configuration correct")
        
        # Check routes
        routes = [route for route in app.routes if hasattr(route, 'path')]
        expected_routes = [
            '/',
            '/health',
            '/api/blob-created',
            '/api/process-blob',
            '/api/process-file',
            '/api/configuration',
            '/api/concurrency',
            '/api/workflow-definition',
            '/api/concurrency-full',
            '/api/concurrency/diagnostics',
            '/api/openai-settings',
            '/api/chat'
        ]
        
        route_paths = [route.path for route in routes if not route.path.startswith('/docs') and not route.path.startswith('/openapi')]
        
        for expected_route in expected_routes:
            if expected_route in route_paths:
                print(f"✅ Route {expected_route} found")
            else:
                print(f"❌ Route {expected_route} missing")
                return False
        
        print(f"✅ All {len(expected_routes)} expected routes found")
        return True
        
    except Exception as e:
        print(f"❌ App structure test failed: {e}")
        return False

def test_class_availability():
    """Test that key classes are available"""
    try:
        from models import EventGridEvent, BlobInputStream
        print("✅ EventGridEvent and BlobInputStream classes available")
        
        from logic_app_manager import LogicAppManager
        print("✅ LogicAppManager class available")
        
        return True
    except Exception as e:
        print(f"❌ Class availability test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing ARGUS Backend Modular Structure")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("App Structure Test", test_app_structure),
        ("Class Availability Test", test_class_availability)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            print(f"✅ {test_name} PASSED")
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"🏆 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The modular structure is working correctly.")
        return 0
    else:
        print("🔧 Some tests failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
