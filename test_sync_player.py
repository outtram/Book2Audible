#!/usr/bin/env python3
"""
Test script for the synchronized audio player features
Tests database schema, API endpoints, and basic functionality
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.chunk_database import ChunkDatabase
from src.core.enhanced_fal_tts_client import EnhancedFalTTSClient
import json
import tempfile


def test_database_schema():
    """Test that the database schema includes new tables and columns"""
    print("🔍 Testing database schema...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = ChunkDatabase(Path(db_path))
        
        # Test that new tables exist
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['projects', 'chapters', 'chunks', 'audio_versions', 'word_timings', 'chapter_words']
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                return False
            
            # Test that chunks table has new columns
            cursor = conn.execute("PRAGMA table_info(chunks)")
            columns = [row[1] for row in cursor.fetchall()]
            
            expected_columns = ['orpheus_temperature', 'orpheus_voice', 'orpheus_speed', 'sequence_in_chapter']
            missing_columns = [c for c in expected_columns if c not in columns]
            
            if missing_columns:
                print(f"❌ Missing columns in chunks table: {missing_columns}")
                return False
        
        print("✅ Database schema is correct")
        return True
        
    finally:
        # Cleanup
        os.unlink(db_path)


def test_audio_version_tracking():
    """Test audio version tracking functionality"""
    print("🔍 Testing audio version tracking...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = ChunkDatabase(Path(db_path))
        
        # Create test project and chapter
        project_id = db.create_project("Test Book", "test.txt")
        chapter_id = db.create_chapter(
            project_id=project_id,
            chapter_number=1,
            title="Test Chapter",
            original_text="Hello world. This is a test.",
            cleaned_text="Hello world. This is a test.",
            chunks_directory="/tmp/test"
        )
        
        # Create test chunk
        chunk_id = db.create_chunk(
            chapter_id=chapter_id,
            chunk_number=1,
            position_start=0,
            position_end=27,
            original_text="Hello world. This is a test.",
            cleaned_text="Hello world. This is a test.",
            text_file_path="/tmp/test_chunk.txt"
        )
        
        # Test creating audio versions
        orpheus_params1 = {"voice": "tara", "temperature": 0.7, "speed": 1.0}
        version_id1 = db.create_audio_version(chunk_id, "/tmp/audio_v1.wav", orpheus_params1)
        
        orpheus_params2 = {"voice": "tara", "temperature": 0.5, "speed": 1.2}
        version_id2 = db.create_audio_version(chunk_id, "/tmp/audio_v2.wav", orpheus_params2)
        
        # Test getting versions
        versions = db.get_audio_versions(chunk_id)
        if len(versions) != 2:
            print(f"❌ Expected 2 versions, got {len(versions)}")
            return False
        
        # Test active version
        active_version = db.get_active_audio_version(chunk_id)
        if not active_version or active_version['version_number'] != 2:
            print(f"❌ Expected active version 2, got {active_version}")
            return False
        
        # Test word timings
        word_timings = [
            {"word": "Hello", "start": 0.0, "end": 0.5, "word_index": 0},
            {"word": "world", "start": 0.5, "end": 1.0, "word_index": 1},
            {"word": "This", "start": 1.5, "end": 1.8, "word_index": 2},
            {"word": "is", "start": 1.8, "end": 2.0, "word_index": 3},
            {"word": "a", "start": 2.0, "end": 2.1, "word_index": 4},
            {"word": "test", "start": 2.1, "end": 2.5, "word_index": 5}
        ]
        
        db.store_word_timings(version_id2, word_timings)
        
        # Test retrieving word timings
        retrieved_timings = db.get_word_timings(version_id2)
        if len(retrieved_timings) != 6:
            print(f"❌ Expected 6 word timings, got {len(retrieved_timings)}")
            return False
        
        print("✅ Audio version tracking works correctly")
        return True
        
    finally:
        os.unlink(db_path)


def test_chunk_database_methods():
    """Test new chunk database methods"""
    print("🔍 Testing chunk database methods...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = ChunkDatabase(Path(db_path))
        
        # Create test data
        project_id = db.create_project("Test Book", "test.txt")
        chapter_id = db.create_chapter(
            project_id=project_id,
            chapter_number=1,
            title="Test Chapter",
            original_text="Hello world. This is a test sentence.",
            cleaned_text="Hello world. This is a test sentence.",
            chunks_directory="/tmp/test"
        )
        
        chunk_id = db.create_chunk(
            chapter_id=chapter_id,
            chunk_number=1,
            position_start=0,
            position_end=36,
            original_text="Hello world. This is a test sentence.",
            cleaned_text="Hello world. This is a test sentence.",
            text_file_path="/tmp/test_chunk.txt"
        )
        
        # Test updating Orpheus parameters
        db.update_chunk_orpheus_params(chunk_id, temperature=0.8, voice="dan", speed=1.1)
        
        chunk = db.get_chunk(chunk_id)
        if not hasattr(chunk, 'orpheus_temperature') or chunk.orpheus_temperature != 0.8:
            print("❌ Orpheus parameters not updated correctly")
            return False
        
        # Test chapter words storage
        words_data = [
            {"word_index": 0, "word": "Hello", "chunk_id": chunk_id, "char_start": 0, "char_end": 5, "audio_start_time": 0.0, "audio_end_time": 0.5},
            {"word_index": 1, "word": "world", "chunk_id": chunk_id, "char_start": 6, "char_end": 11, "audio_start_time": 0.5, "audio_end_time": 1.0},
            {"word_index": 2, "word": "This", "chunk_id": chunk_id, "char_start": 13, "char_end": 17, "audio_start_time": 1.5, "audio_end_time": 1.8}
        ]
        
        db.store_chapter_words(chapter_id, words_data)
        
        # Test retrieving chapter words
        chapter_words = db.get_chapter_words(chapter_id)
        if len(chapter_words) != 3:
            print(f"❌ Expected 3 chapter words, got {len(chapter_words)}")
            return False
        
        print("✅ Chunk database methods work correctly")
        return True
        
    finally:
        os.unlink(db_path)


def test_api_endpoints():
    """Test that API endpoints are properly defined"""
    print("🔍 Testing API endpoint definitions...")
    
    try:
        # Import web_api to check if endpoints are defined
        import web_api
        
        # Check if the new endpoints exist
        app = web_api.app
        
        # Get all route paths
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"Found {len(routes)} routes")  # Debug info
        
        expected_endpoints = [
            '/api/chapters/{chapter_id}/audio-sync-data',
            '/api/chapters/{chapter_id}/stitched-audio', 
            '/api/chunks/{chunk_id}/orpheus-params',
            '/api/chapters/{chapter_id}/word-timings',
        ]
        
        missing_endpoints = []
        for endpoint in expected_endpoints:
            # More flexible matching
            pattern = endpoint.replace('{chapter_id}', '').replace('{chunk_id}', '')
            base_pattern = pattern.replace('//', '/')  # Clean up any double slashes
            
            found = False
            for route in routes:
                if base_pattern.replace('/', '') in route.replace('/', ''):
                    found = True
                    break
            
            if not found:
                missing_endpoints.append(endpoint)
        
        if missing_endpoints:
            print(f"❌ Missing API endpoints: {missing_endpoints}")
            print(f"Available routes: {routes[:10]}...")  # Show first 10 routes for debugging
            return False
        
        print("✅ API endpoints are properly defined")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import web_api: {e}")
        return False


def test_enhanced_tts_client():
    """Test enhanced TTS client (without actually calling APIs)"""
    print("🔍 Testing enhanced TTS client...")
    
    try:
        # Test that enhanced client can be imported and initialized
        # Mock the missing dependencies first
        import sys
        from unittest.mock import MagicMock
        
        # Mock fal_client if not available
        sys.modules['fal_client'] = MagicMock()
        
        # Mock config if needed
        if 'src.core.config' not in sys.modules:
            mock_config = MagicMock()
            mock_config.config.fal_config = {"api_key": "test", "timeout": 120}
            sys.modules['src.core.config'] = mock_config
        
        client = EnhancedFalTTSClient()
        
        # Test tokenization
        text = "Hello world. This is a test sentence."
        words = client.tokenize_text(text)
        
        if len(words) < 6:  # Should have at least Hello, world, This, is, a, test, sentence
            print(f"❌ Tokenization failed, got {len(words)} words")
            return False
        
        # Test word matching
        if not client.words_match("hello", "Hello"):
            print("❌ Word matching failed for case difference")
            return False
        
        if not client.words_match("test", "test"):
            print("❌ Word matching failed for exact match")
            return False
        
        print("✅ Enhanced TTS client works correctly")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced TTS client failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Starting synchronized audio player tests...\n")
    
    tests = [
        test_database_schema,
        test_audio_version_tracking,
        test_chunk_database_methods,
        test_enhanced_tts_client,
        test_api_endpoints,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Synchronized audio player is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    exit(main())