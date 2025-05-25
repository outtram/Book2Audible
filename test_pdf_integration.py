#!/usr/bin/env python3
"""
Integration test for PDF extraction using the actual project PDF
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.core.pdf_extractor import extract_pdf_chapters

def test_pdf_extraction():
    """Test PDF extraction with the actual project PDF"""
    
    # Find the PDF file
    project_root = Path(__file__).parent.parent
    pdf_files = list(project_root.rglob("*.pdf"))
    
    if not pdf_files:
        print("❌ No PDF files found in project")
        return False
    
    pdf_path = pdf_files[0]  # Use first PDF found
    print(f"📄 Testing with PDF: {pdf_path}")
    
    # Create test output directory
    output_dir = project_root / "test_extraction"
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Extract chapters
        stats = extract_pdf_chapters(pdf_path, output_dir, "INFO")
        
        # Validate results
        print(f"✅ Extraction completed!")
        print(f"📊 Chapters: {stats['total_chapters']}")
        print(f"📝 Words: {stats['total_words']:,}")
        print(f"📄 Pages: {stats['total_pages']}")
        
        # Check if we got reasonable results
        if stats['total_chapters'] < 5:
            print("⚠️  Warning: Fewer chapters than expected")
        
        if stats['total_words'] < 10000:
            print("⚠️  Warning: Fewer words than expected")
        
        # List created files
        chapters_dir = output_dir / "chapters"
        if chapters_dir.exists():
            txt_files = list(chapters_dir.glob("*.txt"))
            print(f"\n📁 Created {len(txt_files)} chapter files:")
            for txt_file in sorted(txt_files):
                word_count = len(txt_file.read_text(encoding='utf-8').split())
                print(f"  • {txt_file.name} ({word_count} words)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_pdf_extraction()
    sys.exit(0 if success else 1)
