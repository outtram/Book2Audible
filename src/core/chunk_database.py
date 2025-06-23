"""
Chunk-level database management for Book2Audible
Enables individual chunk reprocessing, insertion, and management
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

@dataclass
class BookProject:
    """Represents a book processing project"""
    id: Optional[int]
    title: str
    original_file: str
    created_at: str
    status: str  # 'active', 'completed', 'failed'
    total_chapters: int
    metadata: Dict[str, Any]

@dataclass
class ChapterRecord:
    """Represents a chapter within a book project"""
    id: Optional[int]
    project_id: int
    chapter_number: int
    title: str
    original_text: str
    cleaned_text: str
    chunks_directory: str
    total_chunks: int
    completed_chunks: int
    status: str  # 'pending', 'processing', 'completed', 'failed'
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]

@dataclass
class ChunkRecord:
    """Represents an individual text chunk"""
    id: Optional[int]
    chapter_id: int
    chunk_number: int
    position_start: int  # Character position in chapter text
    position_end: int
    original_text: str
    cleaned_text: str
    text_file_path: str
    audio_file_path: Optional[str]
    transcription_file_path: Optional[str]
    diff_file_path: Optional[str]
    status: str  # 'pending', 'processing', 'completed', 'failed', 'needs_reprocess'
    verification_score: Optional[float]
    processing_time: Optional[float]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    orpheus_temperature: Optional[float] = 0.7
    orpheus_voice: Optional[str] = 'tara'
    orpheus_speed: Optional[float] = 1.0
    sequence_in_chapter: Optional[int] = None

class ChunkDatabase:
    """Database manager for chunk-level operations"""
    
    def __init__(self, db_path: Path = None):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path or Path("data/chunk_database.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    original_file TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    total_chapters INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    chapter_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    cleaned_text TEXT NOT NULL,
                    chunks_directory TEXT NOT NULL,
                    total_chunks INTEGER DEFAULT 0,
                    completed_chunks INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (project_id) REFERENCES projects (id),
                    UNIQUE(project_id, chapter_number)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL,
                    chunk_number INTEGER NOT NULL,
                    position_start INTEGER NOT NULL,
                    position_end INTEGER NOT NULL,
                    original_text TEXT NOT NULL,
                    cleaned_text TEXT NOT NULL,
                    text_file_path TEXT NOT NULL,
                    audio_file_path TEXT,
                    transcription_file_path TEXT,
                    diff_file_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    verification_score REAL,
                    processing_time REAL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    orpheus_temperature REAL DEFAULT 0.7,
                    orpheus_voice TEXT DEFAULT 'tara',
                    orpheus_speed REAL DEFAULT 1.0,
                    sequence_in_chapter INTEGER,
                    FOREIGN KEY (chapter_id) REFERENCES chapters (id),
                    UNIQUE(chapter_id, chunk_number)
                )
            """)
            
            # Audio versions table for tracking reprocessed audio files
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audio_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    audio_file_path TEXT NOT NULL,
                    orpheus_params TEXT,
                    created_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    processing_time REAL,
                    file_size_bytes INTEGER,
                    duration_seconds REAL,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id),
                    UNIQUE(chunk_id, version_number)
                )
            """)
            
            # Word-level timing data for synchronized playback
            conn.execute("""
                CREATE TABLE IF NOT EXISTS word_timings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audio_version_id INTEGER NOT NULL,
                    word_index INTEGER NOT NULL,
                    word_text TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    character_start INTEGER,
                    character_end INTEGER,
                    FOREIGN KEY (audio_version_id) REFERENCES audio_versions(id)
                )
            """)
            
            # Chapter-level word mapping for text highlighting
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL,
                    word_index INTEGER NOT NULL,
                    word_text TEXT NOT NULL,
                    chunk_id INTEGER,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    audio_start_time REAL,
                    audio_end_time REAL,
                    FOREIGN KEY (chapter_id) REFERENCES chapters(id),
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id)
                )
            """)
            
            # Chapter-level stitched audio versions for entire chapters
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_audio_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    audio_file_path TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    duration_seconds REAL,
                    created_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    stitched_from_chunks TEXT,  -- JSON list of chunk IDs used
                    excluded_chunks TEXT,       -- JSON list of excluded chunk IDs
                    processing_log TEXT,        -- Detailed stitching log
                    file_checksum TEXT,         -- MD5 or SHA256 for integrity
                    FOREIGN KEY (chapter_id) REFERENCES chapters(id),
                    UNIQUE(chapter_id, version_number)
                )
            """)
            
            # Chapter custom metadata and settings
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL UNIQUE,
                    custom_title TEXT,           -- User-defined chapter title
                    display_order INTEGER,       -- Custom chapter ordering
                    is_hidden BOOLEAN DEFAULT FALSE,
                    notes TEXT,                  -- User notes about the chapter
                    tags TEXT,                   -- JSON array of tags
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (chapter_id) REFERENCES chapters(id)
                )
            """)
            
            # Create indexes for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapters_project ON chapters(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_chapter ON chunks(chapter_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audio_versions_chunk ON audio_versions(chunk_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_word_timings_version ON word_timings(audio_version_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_word_timings_time ON word_timings(start_time, end_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_words_chapter ON chapter_words(chapter_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_words_chunk ON chapter_words(chunk_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_audio_versions_chapter ON chapter_audio_versions(chapter_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_audio_versions_active ON chapter_audio_versions(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_settings_chapter ON chapter_settings(chapter_id)")
            
            # Add new columns to existing chunks table if they don't exist (migration)
            self._migrate_chunks_table(conn)
            
            self.logger.info(f"Database initialized at {self.db_path}")
    
    def _migrate_chunks_table(self, conn):
        """Add new columns to existing chunks table if needed"""
        try:
            # Check if new columns exist
            cursor = conn.execute("PRAGMA table_info(chunks)")
            columns = [row[1] for row in cursor.fetchall()]
            
            new_columns = [
                ("orpheus_temperature", "REAL DEFAULT 0.7"),
                ("orpheus_voice", "TEXT DEFAULT 'tara'"),
                ("orpheus_speed", "REAL DEFAULT 1.0"),
                ("sequence_in_chapter", "INTEGER")
            ]
            
            for column_name, column_def in new_columns:
                if column_name not in columns:
                    conn.execute(f"ALTER TABLE chunks ADD COLUMN {column_name} {column_def}")
                    self.logger.info(f"Added column {column_name} to chunks table")
                    
        except Exception as e:
            self.logger.warning(f"Migration warning: {e}")
    
    def create_project(self, title: str, original_file: str, metadata: Dict[str, Any] = None) -> int:
        """Create a new book project"""
        project = BookProject(
            id=None,
            title=title,
            original_file=original_file,
            created_at=datetime.now().isoformat(),
            status='active',
            total_chapters=0,
            metadata=metadata or {}
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO projects (title, original_file, created_at, status, total_chapters, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (project.title, project.original_file, project.created_at, 
                  project.status, project.total_chapters, json.dumps(project.metadata)))
            
            project_id = cursor.lastrowid
            self.logger.info(f"Created project {project_id}: {title}")
            return project_id
    
    def create_chapter(self, project_id: int, chapter_number: int, title: str, 
                      original_text: str, cleaned_text: str, chunks_directory: str,
                      metadata: Dict[str, Any] = None) -> int:
        """Create a new chapter record"""
        chapter = ChapterRecord(
            id=None,
            project_id=project_id,
            chapter_number=chapter_number,
            title=title,
            original_text=original_text,
            cleaned_text=cleaned_text,
            chunks_directory=chunks_directory,
            total_chunks=0,
            completed_chunks=0,
            status='pending',
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO chapters (project_id, chapter_number, title, original_text, 
                                    cleaned_text, chunks_directory, total_chunks, completed_chunks,
                                    status, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (chapter.project_id, chapter.chapter_number, chapter.title, 
                  chapter.original_text, chapter.cleaned_text, chapter.chunks_directory,
                  chapter.total_chunks, chapter.completed_chunks, chapter.status,
                  chapter.created_at, chapter.updated_at, json.dumps(chapter.metadata)))
            
            chapter_id = cursor.lastrowid
            self.logger.info(f"Created chapter {chapter_id}: {title}")
            return chapter_id
    
    def create_chunk(self, chapter_id: int, chunk_number: int, position_start: int,
                    position_end: int, original_text: str, cleaned_text: str,
                    text_file_path: str, metadata: Dict[str, Any] = None) -> int:
        """Create a new chunk record"""
        chunk = ChunkRecord(
            id=None,
            chapter_id=chapter_id,
            chunk_number=chunk_number,
            position_start=position_start,
            position_end=position_end,
            original_text=original_text,
            cleaned_text=cleaned_text,
            text_file_path=text_file_path,
            audio_file_path=None,
            transcription_file_path=None,
            diff_file_path=None,
            status='pending',
            verification_score=None,
            processing_time=None,
            error_message=None,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO chunks (chapter_id, chunk_number, position_start, position_end,
                                  original_text, cleaned_text, text_file_path, status,
                                  created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (chunk.chapter_id, chunk.chunk_number, chunk.position_start, chunk.position_end,
                  chunk.original_text, chunk.cleaned_text, chunk.text_file_path, chunk.status,
                  chunk.created_at, chunk.updated_at, json.dumps(chunk.metadata)))
            
            chunk_id = cursor.lastrowid
            self.logger.info(f"Created chunk {chunk_id}: Chapter {chapter_id}, Chunk {chunk_number}")
            return chunk_id
    
    def update_chunk_status(self, chunk_id: int, status: str, 
                           audio_file_path: str = None, transcription_file_path: str = None,
                           diff_file_path: str = None, verification_score: float = None,
                           processing_time: float = None, error_message: str = None):
        """Update chunk processing status and results"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE chunks 
                SET status = ?, audio_file_path = ?, transcription_file_path = ?,
                    diff_file_path = ?, verification_score = ?, processing_time = ?,
                    error_message = ?, updated_at = ?
                WHERE id = ?
            """, (status, audio_file_path, transcription_file_path, diff_file_path,
                  verification_score, processing_time, error_message, 
                  datetime.now().isoformat(), chunk_id))
    
    def get_project(self, project_id: int) -> Optional[BookProject]:
        """Get project by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            
            if row:
                return BookProject(
                    id=row[0], title=row[1], original_file=row[2], created_at=row[3],
                    status=row[4], total_chapters=row[5], metadata=json.loads(row[6])
                )
        return None
    
    def get_chapter(self, chapter_id: int) -> Optional[ChapterRecord]:
        """Get chapter by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
            row = cursor.fetchone()
            
            if row:
                return ChapterRecord(
                    id=row[0], project_id=row[1], chapter_number=row[2], title=row[3],
                    original_text=row[4], cleaned_text=row[5], chunks_directory=row[6],
                    total_chunks=row[7], completed_chunks=row[8], status=row[9],
                    created_at=row[10], updated_at=row[11], metadata=json.loads(row[12])
                )
        return None
    
    def get_chunks_by_chapter(self, chapter_id: int) -> List[ChunkRecord]:
        """Get all chunks for a chapter"""
        chunks = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM chunks WHERE chapter_id = ? ORDER BY chunk_number
            """, (chapter_id,))
            
            for row in cursor.fetchall():
                chunks.append(ChunkRecord(
                    id=row[0], chapter_id=row[1], chunk_number=row[2], 
                    position_start=row[3], position_end=row[4], original_text=row[5],
                    cleaned_text=row[6], text_file_path=row[7], audio_file_path=row[8],
                    transcription_file_path=row[9], diff_file_path=row[10], status=row[11],
                    verification_score=row[12], processing_time=row[13], error_message=row[14],
                    created_at=row[15], updated_at=row[16], metadata=json.loads(row[17])
                ))
        return chunks
    
    def get_chunk(self, chunk_id: int) -> Optional[ChunkRecord]:
        """Get specific chunk by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            
            if row:
                # Handle both old and new schema
                base_record = ChunkRecord(
                    id=row[0], chapter_id=row[1], chunk_number=row[2], 
                    position_start=row[3], position_end=row[4], original_text=row[5],
                    cleaned_text=row[6], text_file_path=row[7], audio_file_path=row[8],
                    transcription_file_path=row[9], diff_file_path=row[10], status=row[11],
                    verification_score=row[12], processing_time=row[13], error_message=row[14],
                    created_at=row[15], updated_at=row[16], metadata=json.loads(row[17])
                )
                
                # Add new fields if they exist
                if len(row) > 18:
                    base_record.orpheus_temperature = row[18]
                    base_record.orpheus_voice = row[19] if len(row) > 19 else 'tara'
                    base_record.orpheus_speed = row[20] if len(row) > 20 else 1.0
                    base_record.sequence_in_chapter = row[21] if len(row) > 21 else None
                
                return base_record
        return None
    
    def find_project_by_file(self, original_file: str) -> Optional[BookProject]:
        """Find project by original file path"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM projects WHERE original_file = ?", (original_file,))
            row = cursor.fetchone()
            
            if row:
                return BookProject(
                    id=row[0], title=row[1], original_file=row[2], created_at=row[3],
                    status=row[4], total_chapters=row[5], metadata=json.loads(row[6])
                )
        return None
    
    def find_chapter(self, project_id: int, chapter_number: int) -> Optional[ChapterRecord]:
        """Find chapter by project ID and chapter number"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM chapters WHERE project_id = ? AND chapter_number = ?
            """, (project_id, chapter_number))
            row = cursor.fetchone()
            
            if row:
                return ChapterRecord(
                    id=row[0], project_id=row[1], chapter_number=row[2], title=row[3],
                    original_text=row[4], cleaned_text=row[5], chunks_directory=row[6],
                    total_chunks=row[7], completed_chunks=row[8], status=row[9],
                    created_at=row[10], updated_at=row[11], metadata=json.loads(row[12])
                )
        return None
    def update_chapter(self, chapter_id: int, chapter_number: Optional[int] = None,
                      title: Optional[str] = None) -> bool:
        """Update chapter number and/or title"""
        updates = []
        params = []
        
        if chapter_number is not None:
            updates.append("chapter_number = ?")
            params.append(chapter_number)
            
        if title is not None:
            updates.append("title = ?")
            params.append(title)
            
        if not updates:
            return False
            
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(chapter_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                UPDATE chapters 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            
            success = cursor.rowcount > 0
            
        if success:
            update_info = []
            if chapter_number is not None:
                update_info.append(f"number={chapter_number}")
            if title is not None:
                update_info.append(f"title='{title}'")
            self.logger.info(f"Updated chapter {chapter_id}: {', '.join(update_info)}")
        else:
            self.logger.warning(f"Failed to update chapter {chapter_id} - chapter not found")
            
        return success
    
    def mark_chunk_for_reprocessing(self, chunk_id: int, reason: str = "Manual reprocess"):
        """Mark a chunk to be reprocessed"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE chunks 
                SET status = 'needs_reprocess', error_message = ?, updated_at = ?
                WHERE id = ?
            """, (reason, datetime.now().isoformat(), chunk_id))
            
        self.logger.info(f"Marked chunk {chunk_id} for reprocessing: {reason}")
    
    def insert_chunk_at_position(self, chapter_id: int, position: int, new_text: str) -> int:
        """Insert a new chunk at a specific position within a chapter"""
        # First, shift all existing chunks after the position
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE chunks 
                SET chunk_number = chunk_number + 1
                WHERE chapter_id = ? AND chunk_number >= ?
            """, (chapter_id, position))
            
            # Create the new chunk
            chunk_id = self.create_chunk(
                chapter_id=chapter_id,
                chunk_number=position,
                position_start=0,  # Will be calculated properly
                position_end=len(new_text),
                original_text=new_text,
                cleaned_text=new_text,
                text_file_path="",  # Will be set when files are created
                metadata={"inserted": True, "inserted_at": datetime.now().isoformat()}
            )
            
        self.logger.info(f"Inserted new chunk {chunk_id} at position {position}")
        return chunk_id
    
    def get_chapter_summary(self, chapter_id: int) -> Dict[str, Any]:
        """Get summary statistics for a chapter"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_chunks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_chunks,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_chunks,
                    SUM(CASE WHEN status = 'needs_reprocess' THEN 1 ELSE 0 END) as reprocess_chunks,
                    AVG(verification_score) as avg_verification_score,
                    SUM(processing_time) as total_processing_time
                FROM chunks WHERE chapter_id = ?
            """, (chapter_id,))
            
            row = cursor.fetchone()
            return {
                'total_chunks': row[0],
                'completed_chunks': row[1],
                'failed_chunks': row[2],
                'reprocess_chunks': row[3],
                'avg_verification_score': row[4],
                'total_processing_time': row[5]
            }
    
    def get_chunks_needing_reprocessing(self, chapter_id: int = None) -> List[ChunkRecord]:
        """Get all chunks that need reprocessing"""
        chunks = []
        with sqlite3.connect(self.db_path) as conn:
            if chapter_id:
                cursor = conn.execute("""
                    SELECT * FROM chunks WHERE chapter_id = ? AND status = 'needs_reprocess'
                    ORDER BY chunk_number
                """, (chapter_id,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM chunks WHERE status = 'needs_reprocess'
                    ORDER BY chapter_id, chunk_number
                """)
            
            for row in cursor.fetchall():
                chunks.append(ChunkRecord(
                    id=row[0], chapter_id=row[1], chunk_number=row[2], 
                    position_start=row[3], position_end=row[4], original_text=row[5],
                    cleaned_text=row[6], text_file_path=row[7], audio_file_path=row[8],
                    transcription_file_path=row[9], diff_file_path=row[10], status=row[11],
                    verification_score=row[12], processing_time=row[13], error_message=row[14],
                    created_at=row[15], updated_at=row[16], metadata=json.loads(row[17])
                ))
        return chunks
    
    # Audio version tracking methods
    def create_audio_version(self, chunk_id: int, audio_file_path: str, orpheus_params: Dict[str, Any] = None) -> int:
        """Create a new audio version for a chunk"""
        with sqlite3.connect(self.db_path) as conn:
            # Get next version number
            cursor = conn.execute("SELECT MAX(version_number) FROM audio_versions WHERE chunk_id = ?", (chunk_id,))
            max_version = cursor.fetchone()[0]
            version_number = (max_version or 0) + 1
            
            # Get file stats if possible
            file_size_bytes = None
            duration_seconds = None
            try:
                from pathlib import Path
                audio_path = Path(audio_file_path)
                if audio_path.exists():
                    file_size_bytes = audio_path.stat().st_size
                    
                    # Get duration using librosa or similar
                    try:
                        import librosa
                        duration_seconds = librosa.get_duration(filename=str(audio_path))
                    except ImportError:
                        pass
            except Exception:
                pass
            
            cursor = conn.execute("""
                INSERT INTO audio_versions (chunk_id, version_number, audio_file_path, orpheus_params, 
                                          created_at, is_active, file_size_bytes, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (chunk_id, version_number, audio_file_path, json.dumps(orpheus_params or {}),
                  datetime.now().isoformat(), True, file_size_bytes, duration_seconds))
            
            version_id = cursor.lastrowid
            
            # Deactivate previous versions
            conn.execute("""
                UPDATE audio_versions SET is_active = FALSE 
                WHERE chunk_id = ? AND id != ?
            """, (chunk_id, version_id))
            
            self.logger.info(f"Created audio version {version_id} for chunk {chunk_id}")
            return version_id
    
    def store_word_timings(self, audio_version_id: int, word_timings: List[Dict[str, Any]]):
        """Store word-level timing data for an audio version"""
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing timings for this version
            conn.execute("DELETE FROM word_timings WHERE audio_version_id = ?", (audio_version_id,))
            
            # Insert new timings
            for timing in word_timings:
                conn.execute("""
                    INSERT INTO word_timings (audio_version_id, word_index, word_text, start_time, 
                                            end_time, confidence, character_start, character_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (audio_version_id, timing.get('word_index', 0), timing['word'],
                      timing['start'], timing['end'], timing.get('confidence', 1.0),
                      timing.get('char_start'), timing.get('char_end')))
            
            self.logger.info(f"Stored {len(word_timings)} word timings for audio version {audio_version_id}")
    
    def get_audio_versions(self, chunk_id: int) -> List[Dict[str, Any]]:
        """Get all audio versions for a chunk"""
        versions = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, version_number, audio_file_path, orpheus_params, created_at, 
                       is_active, processing_time, file_size_bytes, duration_seconds
                FROM audio_versions WHERE chunk_id = ? ORDER BY version_number DESC
            """, (chunk_id,))
            
            for row in cursor.fetchall():
                versions.append({
                    'id': row[0],
                    'version_number': row[1],
                    'audio_file_path': row[2],
                    'orpheus_params': json.loads(row[3]) if row[3] else {},
                    'created_at': row[4],
                    'is_active': bool(row[5]),
                    'processing_time': row[6],
                    'file_size_bytes': row[7],
                    'duration_seconds': row[8]
                })
        return versions
    
    def get_active_audio_version(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get the currently active audio version for a chunk"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, version_number, audio_file_path, orpheus_params, created_at, 
                       processing_time, file_size_bytes, duration_seconds
                FROM audio_versions WHERE chunk_id = ? AND is_active = TRUE
            """, (chunk_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'version_number': row[1],
                    'audio_file_path': row[2],
                    'orpheus_params': json.loads(row[3]) if row[3] else {},
                    'created_at': row[4],
                    'processing_time': row[5],
                    'file_size_bytes': row[6],
                    'duration_seconds': row[7]
                }
        return None
    
    def get_word_timings(self, audio_version_id: int) -> List[Dict[str, Any]]:
        """Get word timings for an audio version"""
        timings = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT word_index, word_text, start_time, end_time, confidence, character_start, character_end
                FROM word_timings WHERE audio_version_id = ? ORDER BY word_index
            """, (audio_version_id,))
            
            for row in cursor.fetchall():
                timings.append({
                    'word_index': row[0],
                    'word': row[1],
                    'start': row[2],
                    'end': row[3],
                    'confidence': row[4],
                    'char_start': row[5],
                    'char_end': row[6]
                })
        return timings
    
    def store_chapter_words(self, chapter_id: int, words_data: List[Dict[str, Any]]):
        """Store chapter-level word mapping for text highlighting"""
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing data
            conn.execute("DELETE FROM chapter_words WHERE chapter_id = ?", (chapter_id,))
            
            # Insert new word mapping
            for word_data in words_data:
                conn.execute("""
                    INSERT INTO chapter_words (chapter_id, word_index, word_text, chunk_id, 
                                             char_start, char_end, audio_start_time, audio_end_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (chapter_id, word_data['word_index'], word_data['word'],
                      word_data.get('chunk_id'), word_data['char_start'], word_data['char_end'],
                      word_data.get('audio_start_time'), word_data.get('audio_end_time')))
            
            self.logger.info(f"Stored {len(words_data)} word mappings for chapter {chapter_id}")
    
    def get_chapter_words(self, chapter_id: int) -> List[Dict[str, Any]]:
        """Get word mapping for a chapter"""
        words = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT word_index, word_text, chunk_id, char_start, char_end, audio_start_time, audio_end_time
                FROM chapter_words WHERE chapter_id = ? ORDER BY word_index
            """, (chapter_id,))
            
            for row in cursor.fetchall():
                words.append({
                    'word_index': row[0],
                    'word': row[1],
                    'chunk_id': row[2],
                    'char_start': row[3],
                    'char_end': row[4],
                    'audio_start_time': row[5],
                    'audio_end_time': row[6]
                })
        return words
    
    def update_chunk_orpheus_params(self, chunk_id: int, temperature: float = None, 
                                   voice: str = None, speed: float = None):
        """Update Orpheus parameters for a chunk"""
        with sqlite3.connect(self.db_path) as conn:
            updates = []
            params = []
            
            if temperature is not None:
                updates.append("orpheus_temperature = ?")
                params.append(temperature)
            if voice is not None:
                updates.append("orpheus_voice = ?")
                params.append(voice)
            if speed is not None:
                updates.append("orpheus_speed = ?")
                params.append(speed)
            
            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(chunk_id)
                
                query = f"UPDATE chunks SET {', '.join(updates)} WHERE id = ?"
                conn.execute(query, params)
    
    # ===== CHAPTER AUDIO VERSION MANAGEMENT =====
    
    def create_chapter_audio_version(self, chapter_id: int, audio_file_path: str, 
                                   stitched_from_chunks: List[int] = None,
                                   excluded_chunks: List[int] = None,
                                   processing_log: str = None) -> int:
        """Create a new stitched audio version for a chapter"""
        import os
        import hashlib
        import wave
        
        # Calculate file metadata
        file_size = os.path.getsize(audio_file_path) if os.path.exists(audio_file_path) else 0
        duration = 0
        checksum = None
        
        # Get duration from WAV file
        if os.path.exists(audio_file_path):
            try:
                with wave.open(audio_file_path, 'r') as wav_file:
                    frame_count = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    duration = frame_count / sample_rate
            except:
                pass
            
            # Calculate MD5 checksum for integrity
            try:
                with open(audio_file_path, 'rb') as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
            except:
                pass
        
        with sqlite3.connect(self.db_path) as conn:
            # Deactivate previous versions
            conn.execute("""
                UPDATE chapter_audio_versions 
                SET is_active = FALSE 
                WHERE chapter_id = ?
            """, (chapter_id,))
            
            # Get next version number
            cursor = conn.execute("""
                SELECT COALESCE(MAX(version_number), 0) + 1 
                FROM chapter_audio_versions 
                WHERE chapter_id = ?
            """, (chapter_id,))
            version_number = cursor.fetchone()[0]
            
            # Create new version
            cursor = conn.execute("""
                INSERT INTO chapter_audio_versions (
                    chapter_id, version_number, audio_file_path, file_size_bytes,
                    duration_seconds, created_at, is_active, stitched_from_chunks,
                    excluded_chunks, processing_log, file_checksum
                ) VALUES (?, ?, ?, ?, ?, ?, TRUE, ?, ?, ?, ?)
            """, (
                chapter_id, version_number, audio_file_path, file_size, duration,
                datetime.now().isoformat(),
                json.dumps(stitched_from_chunks or []),
                json.dumps(excluded_chunks or []),
                processing_log or "",
                checksum
            ))
            
            version_id = cursor.lastrowid
            self.logger.info(f"Created chapter audio version {version_number} for chapter {chapter_id}: {audio_file_path}")
            return version_id
    
    def get_active_chapter_audio(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        """Get the active stitched audio version for a chapter"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, version_number, audio_file_path, file_size_bytes,
                       duration_seconds, created_at, stitched_from_chunks,
                       excluded_chunks, processing_log, file_checksum
                FROM chapter_audio_versions
                WHERE chapter_id = ? AND is_active = TRUE
                ORDER BY version_number DESC
                LIMIT 1
            """, (chapter_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'version_number': row[1],
                    'audio_file_path': row[2],
                    'file_size_bytes': row[3],
                    'duration_seconds': row[4],
                    'created_at': row[5],
                    'stitched_from_chunks': json.loads(row[6] or '[]'),
                    'excluded_chunks': json.loads(row[7] or '[]'),
                    'processing_log': row[8],
                    'file_checksum': row[9]
                }
        return None
    
    def list_chapter_audio_versions(self, chapter_id: int) -> List[Dict[str, Any]]:
        """List all audio versions for a chapter"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, version_number, audio_file_path, file_size_bytes,
                       duration_seconds, created_at, is_active, stitched_from_chunks,
                       excluded_chunks, processing_log, file_checksum
                FROM chapter_audio_versions
                WHERE chapter_id = ?
                ORDER BY version_number DESC
            """, (chapter_id,))
            
            versions = []
            for row in cursor.fetchall():
                versions.append({
                    'id': row[0],
                    'version_number': row[1],
                    'audio_file_path': row[2],
                    'file_size_bytes': row[3],
                    'duration_seconds': row[4],
                    'created_at': row[5],
                    'is_active': row[6],
                    'stitched_from_chunks': json.loads(row[7] or '[]'),
                    'excluded_chunks': json.loads(row[8] or '[]'),
                    'processing_log': row[9],
                    'file_checksum': row[10]
                })
            return versions
    
    # ===== CHAPTER SETTINGS MANAGEMENT =====
    
    def set_chapter_custom_title(self, chapter_id: int, custom_title: str):
        """Set a custom title for a chapter"""
        with sqlite3.connect(self.db_path) as conn:
            # Upsert chapter settings
            conn.execute("""
                INSERT INTO chapter_settings (chapter_id, custom_title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chapter_id) DO UPDATE SET
                    custom_title = excluded.custom_title,
                    updated_at = excluded.updated_at
            """, (chapter_id, custom_title, datetime.now().isoformat(), datetime.now().isoformat()))
            
            self.logger.info(f"Set custom title for chapter {chapter_id}: {custom_title}")
    
    def get_chapter_display_info(self, chapter_id: int) -> Dict[str, Any]:
        """Get chapter display information including custom title"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT c.id, c.chapter_number, c.title, c.status,
                       cs.custom_title, cs.display_order, cs.is_hidden, cs.notes, cs.tags
                FROM chapters c
                LEFT JOIN chapter_settings cs ON c.id = cs.chapter_id
                WHERE c.id = ?
            """, (chapter_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'chapter_number': row[1],
                    'original_title': row[2],
                    'status': row[3],
                    'custom_title': row[4],
                    'display_title': row[4] or row[2],  # Use custom title if available
                    'display_order': row[5],
                    'is_hidden': row[6],
                    'notes': row[7],
                    'tags': json.loads(row[8] or '[]')
                }
        return None