# Chunk Management Guide

## Overview

The chunk management system allows you to cost-effectively fix audio glitches by reprocessing individual chunks instead of entire chapters. This saves significant time and API costs.

## Quick Start: Fix Audio Glitches in Chapter 03

### 1. Check Chapter Status
```bash
# List all chapters to find your chapter ID
python chunk_cli.py list-chapters

# Get detailed status of chapter (replace 3 with your chapter ID)
python chunk_cli.py chapter-status 3
```

### 2. Identify Problem Chunks
```bash
# Show chunks that might need reprocessing
python chunk_cli.py show-candidates 3
```

### 3. Reprocess Individual Chunks
```bash
# Reprocess a specific chunk (replace 15 with the problematic chunk ID)
python chunk_cli.py reprocess-chunk 15

# Or reprocess all failed/low-quality chunks at once
python chunk_cli.py reprocess-failed 3
```

### 4. Restitch the Audio
```bash
# Restitch chapter audio (excludes any failed chunks automatically)
python chunk_cli.py restitch 3

# Or exclude specific problematic chunks while keeping others
python chunk_cli.py restitch 3 --exclude 15 22
```

## Advanced Features

### Insert New Text
If you need to add text at a specific location:
```bash
# Insert new chunk at position 10
python chunk_cli.py insert-chunk 3 10 "This is new text to insert." --title "Correction"

# Then process the new chunk
python chunk_cli.py reprocess-chunk <new_chunk_id>

# Finally restitch
python chunk_cli.py restitch 3
```

### Mark Chunks for Later Processing
```bash
# Mark a chunk that needs attention
python chunk_cli.py mark-reprocess 15 --reason "Audio glitch detected"
```

## Integration with Existing Processing

### Option 1: Enable Automatic Tracking (Recommended)
Update your processing to use the enhanced processor:

```python
from src.core.enhanced_processor import EnhancedBook2AudioProcessor

# Replace your existing processor
processor = EnhancedBook2AudioProcessor(enable_chunk_tracking=True)
result = processor.process_book(input_file, output_dir)

# Now you can use chunk management
if result.get('chunk_management', {}).get('chapter_id'):
    chapter_id = result['chunk_management']['chapter_id']
    print(f"Chapter tracked with ID: {chapter_id}")
```

### Option 2: Manual Registration
For existing chapters, manually register them:

```python
from src.core.chunk_manager import ChunkManager

chunk_manager = ChunkManager()

# Register an existing chapter
chapter_id = chunk_manager.register_chapter_processing(
    input_file="your_book.pdf",
    chapter_number=3,
    chapter_title="Chapter 3",
    original_text=chapter_text,
    chunks_directory="/path/to/Chapter_03_chunks_20241201_143022"
)
```

## Cost Savings Example

**Before:** Reprocessing entire Chapter 03 (50 chunks)
- Cost: ~$2.50 (50 chunks × $0.05 per chunk)
- Time: ~15 minutes

**After:** Reprocessing 3 problematic chunks
- Cost: ~$0.15 (3 chunks × $0.05 per chunk)
- Time: ~1 minute

**Savings: 94% cost reduction, 93% time reduction!**

## Troubleshooting

### Database Issues
```bash
# Check if database exists
ls -la data/chunk_database.db

# If missing, it will be created automatically on first use
```

### File Path Issues
```bash
# Verify chunks directory exists
ls -la "data/output/Chapter_03_chunks_*"

# Check specific chunk files
ls -la "data/output/Chapter_03_chunks_20241201_143022/"
```

### Audio Quality Issues
The system automatically identifies chunks needing reprocessing based on:
- Processing failures
- Low verification scores (<85% accuracy)
- Missing audio files
- Manual marking

## Best Practices

1. **Always check candidates first** - Use `show-candidates` to see what needs fixing
2. **Reprocess in small batches** - Don't reprocess everything at once
3. **Verify results** - Check the verification scores after reprocessing
4. **Keep original files** - The system preserves original chunks and creates timestamped versions
5. **Use exclusion for stitching** - If some chunks are problematic, exclude them rather than reprocess everything

## File Organization

The system maintains your existing file structure and adds:
```
Chapter_03_chunks_20241201_143022/
├── Chapter_03_chunk_001.txt          # Original chunk text
├── Chapter_03_chunk_001.wav          # Original audio
├── Chapter_03_chunk_001_REPROCESSED_20241201_150022.wav  # Reprocessed version
├── Chapter_03_chunk_015_REPROCESSED_20241201_150022.wav  # Fixed glitch
└── Chapter_03_RESTITCHED_20241201_151022.wav             # Final stitched audio
```

## Database Schema

The system tracks:
- **Projects** - Your book files
- **Chapters** - Individual chapters within books  
- **Chunks** - Text segments with processing status, verification scores, file paths

All data is stored in `data/chunk_database.db` (SQLite).

## Next Steps

1. Run `python chunk_cli.py list-chapters` to see your existing chapters
2. Use `python chunk_cli.py chapter-status <chapter_id>` to analyze Chapter 03
3. Identify and reprocess problematic chunks
4. Restitch the final audio

The system is designed to be safe - it never modifies your original files and creates timestamped versions for all operations.