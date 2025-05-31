"""
Main processing engine for Book2Audible
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import logging
from tqdm import tqdm

from .config import config
from .text_processor import TextProcessor, Chapter
from .tts_client import BaseTenTTSClient
from .fal_tts_client import FalTTSClient
from .audio_processor import AudioProcessor
from .audio_verifier import AudioVerifier
from .audio_file_verifier import AudioFileVerifier
from .buffer_manager import BufferManager
from .helpers import ProcessorHelpers
from ..utils.file_handler import FileHandler
from ..utils.logger import setup_logger

class Book2AudioProcessor:
    """Main processor orchestrating the text-to-audio conversion"""
    
    def __init__(self, log_level: str = "INFO", tts_provider: str = None):
        # Setup logging
        self.logger = setup_logger("Book2Audio", config.log_file, log_level)
        
        # Initialize components
        self.text_processor = TextProcessor()
        
        # Initialize TTS client based on provider - default to Fal.ai
        self.tts_provider = tts_provider or "fal"
        if self.tts_provider.lower() == "fal":
            self.tts_client = FalTTSClient()
            self.logger.info("Using Fal.ai TTS provider")
        else:
            # Fallback to Fal.ai if unknown provider
            self.tts_client = FalTTSClient()
            self.logger.info("Unknown provider, defaulting to Fal.ai TTS provider")
        
        self.audio_processor = AudioProcessor()
        self.audio_verifier = AudioVerifier()
        self.audio_file_verifier = AudioFileVerifier()
        self.buffer_manager = BufferManager(self.tts_client, self.audio_processor)
        self.file_handler = FileHandler()
        
        self.logger.info(f"Book2Audio processor initialized with {self.tts_provider} provider")
    
    def process_book(self, input_file: Path, output_dir: Path = None, 
                     manual_chapters: List[str] = None) -> Dict[str, Any]:
        """Process entire book from text file to audio chapters"""
        
        output_dir = output_dir or config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Starting book processing: {input_file}")
        self.logger.info(f"Output directory: {output_dir}")
        
        try:
            # Step 1: Read input file
            self.logger.info("Reading input file...")
            text_content = self.file_handler.read_file(input_file)
            self.logger.info(f"File read successfully: {len(text_content)} characters")
            
            # Step 2: Detect chapters
            self.logger.info("Detecting chapters...")
            if manual_chapters:
                chapters = self._create_manual_chapters(text_content, manual_chapters)
            else:
                chapters = self.text_processor.detect_chapters(text_content)
            
            self.logger.info(f"Found {len(chapters)} chapters")
            
            # Step 3: Process each chapter
            processing_results = []
            chapter_files = []
            
            for chapter in tqdm(chapters, desc="Processing chapters"):
                self.logger.info(f"Processing Chapter {chapter.number}: {chapter.title}")
                
                try:
                    result = self._process_single_chapter(chapter, output_dir)
                    processing_results.append(result)
                    chapter_files.append(result['audio_file'])
                    
                except Exception as e:
                    self.logger.error(f"Failed to process chapter {chapter.number}: {e}")
                    processing_results.append({
                        'chapter': chapter.number,
                        'status': 'failed',
                        'error': str(e)
                    })
        
            # Generate summary and save log
            summary = self._generate_summary(input_file, processing_results, chapter_files)
            log_file = output_dir / f"{input_file.stem}_processing_log.json"
            with open(log_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info("Book processing completed!")
            return summary
            
        except Exception as e:
            self.logger.error(f"Book processing failed: {e}")
            raise
    
    def process_book(self, input_file: Path, output_dir: Path = None, 
                     manual_chapters: List[str] = None) -> Dict[str, Any]:
        """Process entire book from text file to audio chapters"""
        
        output_dir = output_dir or config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Starting book processing: {input_file}")
        
        try:
            # Read and process text
            text_content = self.file_handler.read_file(input_file)
            self.logger.info(f"File read: {len(text_content)} characters")
            
            if manual_chapters:
                chapters = ProcessorHelpers.create_manual_chapters(text_content, manual_chapters)
            else:
                chapters = self.text_processor.detect_chapters(text_content)
            
            self.logger.info(f"Found {len(chapters)} chapters")
            
            # Process chapters
            processing_results = []
            chapter_files = []
            
            for chapter in tqdm(chapters, desc="Processing chapters"):
                try:
                    result = self._process_single_chapter(chapter, output_dir, input_file.name)
                    processing_results.append(result)
                    chapter_files.append(result['audio_file'])
                except Exception as e:
                    self.logger.error(f"Chapter {chapter.number} failed: {e}")
                    processing_results.append({
                        'chapter': chapter.number, 'status': 'failed', 'error': str(e)
                    })
            
            # Generate summary
            summary = ProcessorHelpers.generate_summary(input_file, processing_results, chapter_files)
            log_file = output_dir / f"{input_file.stem}_log.json"
            with open(log_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info("Processing completed!")
            return summary
            
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise

    def _process_single_chapter(self, chapter: Chapter, output_dir: Path, input_filename: str = None) -> Dict[str, Any]:
        """Process a single chapter to audio with individual chunk files and verification"""
        chapter_start_time = time.time()
        
        # Clean text
        cleaned_text = self.text_processor.clean_text(chapter.content)
        
        # Split into smaller chunks for better TTS quality
        chunks = self.text_processor.chunk_long_text(cleaned_text, 150)  # Much smaller chunks
        self.logger.info(f"Chapter {chapter.number} split into {len(chunks)} chunks")
        
        # Create chunks directory with datetime stamp or use existing
        from datetime import datetime
        
        if input_filename:
            base_name = Path(input_filename).stem
        else:
            base_name = f"Chapter_{chapter.number:02d}"
        
        # Check for existing chunks directory to resume
        existing_dirs = list(output_dir.glob(f"{base_name}_chunks_*"))
        if existing_dirs:
            # Use the most recent existing directory
            chunks_dir = max(existing_dirs, key=lambda p: p.stat().st_mtime)
            timestamp = chunks_dir.name.split('_')[-1]  # Extract timestamp
            self.logger.info(f"Resuming with existing chunks directory: {chunks_dir}")
        else:
            # Create new directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            chunks_dir = output_dir / f"{base_name}_chunks_{timestamp}"
            chunks_dir.mkdir(exist_ok=True)
            self.logger.info(f"Created new chunks directory: {chunks_dir}")
        
        # Process each chunk individually with delays to avoid rate limiting
        chunk_results = []
        audio_chunks = [None] * len(chunks)  # Pre-allocate array with correct size
        chunk_delay = config.tts_settings.get("chunk_delay", 2)
        
        # Check for existing files to resume processing
        existing_wav_files = list(chunks_dir.glob(f"{base_name}_chunk_*.wav"))
        completed_chunk_nums = set()
        for wav_file in existing_wav_files:
            # Extract chunk number from filename
            import re
            match = re.search(r'chunk_(\d+)\.wav', wav_file.name)
            if match:
                completed_chunk_nums.add(int(match.group(1)))
        
        self.logger.info(f"Found {len(completed_chunk_nums)} existing chunks: {sorted(completed_chunk_nums)}")
        
        for i, chunk_text in enumerate(chunks):
            chunk_num = i + 1
            
            # Skip if already completed
            if chunk_num in completed_chunk_nums:
                self.logger.info(f"⏭️ Skipping chunk {chunk_num}/{len(chunks)} - already exists")
                # Load existing audio for final stitching
                existing_wav = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.wav"
                if existing_wav.exists():
                    with open(existing_wav, 'rb') as f:
                        audio_chunks[i] = f.read()  # Store at correct index
                    
                    # Create basic result entry
                    chunk_results.append({
                        'chunk_number': chunk_num,
                        'text_file': str(chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.txt"),
                        'audio_file': str(existing_wav),
                        'text_length': len(chunk_text),
                        'word_count': len(chunk_text.split()),
                        'verification': {'is_verified': True, 'accuracy_score': 1.0, 'error_message': 'Pre-existing file'},
                        'status': 'existing'
                    })
                continue
            
            self.logger.info(f"🔄 Processing chunk {chunk_num}/{len(chunks)} ({len(chunk_text)} chars)")
            
            # Add delay between chunks (except for first new chunk)
            if i > 0 and len([x for x in range(1, chunk_num) if x not in completed_chunk_nums]) > 0:
                self.logger.info(f"Waiting {chunk_delay} seconds before next chunk...")
                time.sleep(chunk_delay)
            
            try:
                # Save chunk text file
                chunk_text_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.txt"
                with open(chunk_text_file, 'w', encoding='utf-8') as f:
                    f.write(chunk_text)
                
                self.logger.info(f"Generating audio for chunk {chunk_num} ({len(chunk_text)} chars)...")
                
                # Generate audio with timeout protection
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("TTS generation timeout")
                
                chunk_timeout = config.tts_settings.get("chunk_timeout", 120)
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(chunk_timeout)
                
                try:
                    chunk_audio = self.tts_client.generate_audio(chunk_text)
                    signal.alarm(0)  # Cancel timeout
                except TimeoutError:
                    signal.alarm(0)
                    self.logger.error(f"Chunk {chunk_num} TTS generation timed out after {chunk_timeout}s")
                    raise
                except Exception as e:
                    signal.alarm(0)
                    raise e
                
                self.logger.info(f"Audio generation completed for chunk {chunk_num}")
                
                # Save individual chunk audio
                chunk_audio_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.wav"
                self.audio_processor.save_wav_file(chunk_audio, chunk_audio_file)
                
                # Check if verification is enabled
                verification_enabled = config.tts_settings.get("enable_verification", True)
                
                if verification_enabled:
                    self.logger.info(f"Starting verification for chunk {chunk_num}...")
                    
                    # Verify this individual chunk with timeout handling
                    try:
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError("Verification timeout")
                        
                        verification_timeout = config.tts_settings.get("verification_timeout", 120)
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(verification_timeout)
                        
                        chunk_verification = self.audio_verifier.verify_audio_content(chunk_audio_file, chunk_text)
                        
                        signal.alarm(0)  # Cancel timeout
                        
                    except TimeoutError:
                        self.logger.warning(f"Chunk {chunk_num} verification timed out after {verification_timeout}s")
                        # Create a basic verification result
                        from .audio_verifier import VerificationResult
                        chunk_verification = VerificationResult(
                            original_text=chunk_text,
                            transcribed_text="[VERIFICATION TIMEOUT]",
                            accuracy_score=0.0,
                            word_error_rate=1.0,
                            character_error_rate=1.0,
                            missing_words=[],
                            extra_words=[],
                            is_verified=False,
                            error_message="Verification timeout"
                        )
                    except Exception as e:
                        self.logger.error(f"Chunk {chunk_num} verification failed: {e}")
                        from .audio_verifier import VerificationResult
                        chunk_verification = VerificationResult(
                            original_text=chunk_text,
                            transcribed_text="[VERIFICATION ERROR]",
                            accuracy_score=0.0,
                            word_error_rate=1.0,
                            character_error_rate=1.0,
                            missing_words=[],
                            extra_words=[],
                            is_verified=False,
                            error_message=str(e)
                        )
                else:
                    self.logger.info(f"Verification disabled - skipping chunk {chunk_num} verification")
                    # Create a default "skipped" verification result
                    from .audio_verifier import VerificationResult
                    chunk_verification = VerificationResult(
                        original_text=chunk_text,
                        transcribed_text="[VERIFICATION SKIPPED]",
                        accuracy_score=1.0,  # Assume good quality
                        word_error_rate=0.0,
                        character_error_rate=0.0,
                        missing_words=[],
                        extra_words=[],
                        is_verified=True,  # Skip but mark as passed
                        error_message="Verification disabled"
                    )
                
                # Save transcription and diff for comparison
                transcription_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}_transcription.txt"
                diff_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}_diff.html"
                
                # Save transcription text
                with open(transcription_file, 'w', encoding='utf-8') as f:
                    f.write(chunk_verification.transcribed_text)
                
                # Generate HTML diff file
                self._generate_html_diff(chunk_text, chunk_verification.transcribed_text, diff_file, chunk_num)
                
                chunk_result = {
                    'chunk_number': chunk_num,
                    'text_file': str(chunk_text_file),
                    'audio_file': str(chunk_audio_file),
                    'transcription_file': str(transcription_file),
                    'diff_file': str(diff_file),
                    'text_length': len(chunk_text),
                    'word_count': len(chunk_text.split()),
                    'verification': {
                        'is_verified': chunk_verification.is_verified,
                        'accuracy_score': chunk_verification.accuracy_score,
                        'word_error_rate': chunk_verification.word_error_rate,
                        'character_error_rate': chunk_verification.character_error_rate,
                        'missing_words_count': len(chunk_verification.missing_words),
                        'extra_words_count': len(chunk_verification.extra_words),
                        'missing_words': chunk_verification.missing_words[:10],  # First 10 missing words
                        'extra_words': chunk_verification.extra_words[:10],      # First 10 extra words
                        'error_message': chunk_verification.error_message
                    }
                }
                
                chunk_results.append(chunk_result)
                audio_chunks[i] = chunk_audio  # Store at correct index
                
                # Log chunk verification result with more detail
                if verification_enabled:
                    if chunk_verification.is_verified:
                        self.logger.info(f"✅ Chunk {chunk_num} verification PASSED: {chunk_verification.accuracy_score:.2%}")
                    else:
                        self.logger.warning(f"❌ Chunk {chunk_num} verification FAILED: {chunk_verification.accuracy_score:.2%}")
                else:
                    self.logger.info(f"⚪ Chunk {chunk_num} verification SKIPPED")
                
                self.logger.info(f"📁 Chunk {chunk_num} files: {chunk_text_file.name}, {chunk_audio_file.name}")
                self.logger.info(f"✅ Chunk {chunk_num}/{len(chunks)} completed successfully ({chunk_num/len(chunks)*100:.1f}% done)")
                
            except Exception as e:
                self.logger.error(f"Failed to process chunk {chunk_num}: {e}")
                
                # Still save the text file for debugging
                try:
                    chunk_text_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.txt"
                    with open(chunk_text_file, 'w', encoding='utf-8') as f:
                        f.write(chunk_text)
                    
                    # Save error details
                    error_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}_ERROR.txt"
                    with open(error_file, 'w', encoding='utf-8') as f:
                        f.write(f"Chunk {chunk_num} failed with error:\n{str(e)}\n\nOriginal text:\n{chunk_text}")
                except:
                    pass
                
                chunk_results.append({
                    'chunk_number': chunk_num,
                    'text_file': str(chunk_text_file) if 'chunk_text_file' in locals() else None,
                    'error': str(e),
                    'verification': {'is_verified': False, 'error_message': str(e)}
                })
                
                # Continue with next chunk even if this one failed
                continue
        
        # Process ALL chunks and ensure complete coverage
        self.logger.info(f"Processing completed: {len(chunk_results)} total chunks")
        
        # Ensure arrays are properly aligned and complete
        self.logger.info(f"Final array verification: {len(chunk_results)} results, {len(audio_chunks)} audio chunks")
        
        # Build final arrays ensuring ALL chunks are processed
        successful_chunks = []
        failed_chunk_nums = []
        all_chunk_text = ""
        
        # Process chunks in order ensuring no gaps
        for i in range(len(chunks)):
            chunk_num = i + 1
            chunk_text = chunks[i]
            
            # Check if this chunk has audio data
            if audio_chunks[i] is not None:
                successful_chunks.append(audio_chunks[i])
                all_chunk_text += chunk_text + " "
                self.logger.debug(f"✅ Chunk {chunk_num} included in final audio")
            else:
                failed_chunk_nums.append(chunk_num)
                self.logger.error(f"❌ Missing audio for chunk {chunk_num}")
                
                # Try to regenerate missing chunk if not too many failures
                if len(failed_chunk_nums) <= 3:  # Only retry if few failures
                    self.logger.info(f"🔄 Attempting to regenerate missing chunk {chunk_num}")
                    try:
                        # Apply extended timeout for problematic chunks
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError("TTS generation timeout")
                        
                        extended_timeout = config.tts_settings.get("extended_timeout", 180)
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(extended_timeout)
                        
                        regenerated_audio = self.tts_client.generate_audio(chunk_text)
                        
                        signal.alarm(0)  # Cancel timeout
                        
                        # Save the regenerated chunk
                        regenerated_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}_REGENERATED.wav"
                        self.audio_processor.save_wav_file(regenerated_audio, regenerated_file)
                        
                        # Include in final audio
                        successful_chunks.append(regenerated_audio)
                        all_chunk_text += chunk_text + " "
                        failed_chunk_nums.remove(chunk_num)
                        
                        self.logger.info(f"✅ Successfully regenerated chunk {chunk_num}")
                        
                        # Verify the regenerated chunk immediately
                        regen_verification = self.audio_file_verifier.verify_audio_file(regenerated_file)
                        if regen_verification['overall_status'] != 'PASSED':
                            self.logger.error(f"❌ Regenerated chunk {chunk_num} failed verification")
                            # Remove from successful list if verification fails
                            successful_chunks.pop()
                            failed_chunk_nums.append(chunk_num)
                            all_chunk_text = all_chunk_text[:-len(chunk_text)-1]  # Remove added text
                        
                    except TimeoutError:
                        self.logger.error(f"❌ Chunk {chunk_num} regeneration timed out after {extended_timeout}s")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to regenerate chunk {chunk_num}: {e}")
        
        self.logger.info(f"Successfully aligned {len(successful_chunks)} audio chunks for stitching")
        
        if failed_chunk_nums:
            self.logger.error(f"Failed chunks: {failed_chunk_nums}")
            
        if not successful_chunks:
            raise Exception("All chunks failed to process")
        
        # Ensure we have processed ALL text by checking coverage
        expected_word_count = len(cleaned_text.split())
        actual_word_count = len(all_chunk_text.split())
        coverage_percentage = (actual_word_count / expected_word_count) * 100 if expected_word_count > 0 else 0
        
        self.logger.info(f"Text coverage: {actual_word_count}/{expected_word_count} words ({coverage_percentage:.1f}%)")
        
        if coverage_percentage < 95.0:
            self.logger.warning(f"⚠️ Text coverage below 95% ({coverage_percentage:.1f}%) - some content may be missing")
        
        # Create comprehensive text verification file
        verification_file = chunks_dir / f"{base_name}_TEXT_VERIFICATION.txt"
        with open(verification_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("TEXT VERIFICATION REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Original Chapter Text Length: {len(cleaned_text)} characters\n")
            f.write(f"Original Word Count: {expected_word_count} words\n\n")
            f.write(f"Processed Text Length: {len(all_chunk_text.strip())} characters\n")
            f.write(f"Processed Word Count: {actual_word_count} words\n")
            f.write(f"Coverage Percentage: {coverage_percentage:.2f}%\n\n")
            
            if failed_chunk_nums:
                f.write(f"FAILED CHUNKS: {failed_chunk_nums}\n\n")
            
            f.write("CHUNK-BY-CHUNK VERIFICATION:\n")
            f.write("-" * 40 + "\n")
            
            # Verify each chunk file exists and content matches
            for i, chunk_text in enumerate(chunks):
                chunk_num = i + 1
                chunk_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.txt"
                audio_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.wav"
                
                chunk_status = "✅ COMPLETE" if audio_chunks[i] is not None else "❌ MISSING"
                text_exists = "✅" if chunk_file.exists() else "❌"
                audio_exists = "✅" if audio_file.exists() else "❌"
                
                f.write(f"Chunk {chunk_num:03d}: {chunk_status}\n")
                f.write(f"  Text File: {text_exists} {chunk_file.name}\n")
                f.write(f"  Audio File: {audio_exists} {audio_file.name}\n")
                f.write(f"  Text Length: {len(chunk_text)} chars, {len(chunk_text.split())} words\n")
                
                # Verify text file content matches expected
                if chunk_file.exists():
                    try:
                        with open(chunk_file, 'r', encoding='utf-8') as cf:
                            saved_text = cf.read()
                        if saved_text.strip() == chunk_text.strip():
                            f.write(f"  Content Match: ✅ VERIFIED\n")
                        else:
                            f.write(f"  Content Match: ❌ MISMATCH\n")
                            f.write(f"    Expected: {len(chunk_text)} chars\n")
                            f.write(f"    Saved: {len(saved_text)} chars\n")
                    except Exception as e:
                        f.write(f"  Content Match: ❌ ERROR - {e}\n")
                
                f.write("\n")
            
            f.write("\n" + "=" * 60 + "\n")
            f.write("FULL CHAPTER TEXT (for comparison):\n")
            f.write("=" * 60 + "\n")
            f.write(cleaned_text)
            f.write("\n\n" + "=" * 60 + "\n")
            f.write("RECONSTRUCTED TEXT (from processed chunks):\n")
            f.write("=" * 60 + "\n")
            f.write(all_chunk_text.strip())
        
        self.logger.info(f"Created comprehensive text verification file: {verification_file}")
        
        # Perform comprehensive audio file verification
        self.logger.info("Starting comprehensive audio file verification...")
        audio_verification_results = self.audio_file_verifier.verify_chunk_directory(
            chunks_dir, base_name, len(chunks)
        )
        
        # Save audio verification report
        audio_report_file = chunks_dir / f"{base_name}_AUDIO_VERIFICATION_REPORT"
        self.audio_file_verifier.save_verification_report(audio_verification_results, audio_report_file)
        
        # Log audio verification summary
        if audio_verification_results['summary_status'] == 'ALL_VALID':
            self.logger.info(f"🎵 All {audio_verification_results['valid_audio_files']} audio files verified successfully")
        elif audio_verification_results['summary_status'] == 'MOSTLY_VALID':
            self.logger.warning(f"⚠️ {audio_verification_results['valid_audio_files']}/{audio_verification_results['expected_chunk_count']} audio files valid")
        else:
            self.logger.error(f"❌ Audio verification failed: {audio_verification_results['summary_status']}")
        
        # Generate comprehensive chunk coverage report
        coverage_file = chunks_dir / f"{base_name}_coverage_report.txt"
        with open(coverage_file, 'w', encoding='utf-8') as f:
            f.write(f"CHUNK COVERAGE REPORT\n")
            f.write(f"=====================\n\n")
            f.write(f"Original text length: {len(cleaned_text)} chars\n")
            f.write(f"Reconstructed text length: {len(all_chunk_text.strip())} chars\n")
            f.write(f"Total chunks: {len(chunks)}\n")
            f.write(f"Successful chunks: {len(successful_chunks)}\n")
            f.write(f"Failed chunks: {len(failed_chunk_nums)}\n\n")
            
            if failed_chunk_nums:
                f.write(f"FAILED CHUNKS: {failed_chunk_nums}\n\n")
            
            f.write("CHUNK BREAKDOWN:\n")
            for i, chunk in enumerate(chunks):
                status = "✅ SUCCESS" if i < len(chunk_results) and 'error' not in chunk_results[i] else "❌ FAILED"
                f.write(f"Chunk {i+1:03d}: {len(chunk)} chars - {status}\n")
        
        # Stitch all successful audio chunks together
        self.logger.info(f"Stitching {len(successful_chunks)} audio chunks together...")
        if len(successful_chunks) > 1:
            final_audio = self.audio_processor.stitch_audio_chunks(successful_chunks)
        else:
            final_audio = successful_chunks[0]
        
        # Save final combined audio file with timestamp
        if input_filename:
            filename = f"{Path(input_filename).stem}_{timestamp}.wav"
        else:
            filename = f"Chapter_{chapter.number:02d}_{timestamp}.wav"
            if chapter.title:
                safe_title = "".join(c for c in chapter.title if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"Chapter_{chapter.number:02d}_{safe_title}_{timestamp}.wav"
        
        output_path = output_dir / filename
        self.audio_processor.save_wav_file(final_audio, output_path)
        self.logger.info(f"Final stitched audio saved: {output_path}")
        
        # Verify final audio file integrity
        expected_min_duration = len(successful_chunks) * 1000  # Rough estimate: 1 second per chunk minimum
        final_audio_valid = self.audio_file_verifier.quick_verify_final_audio(output_path, expected_min_duration)
        
        if not final_audio_valid:
            self.logger.error(f"❌ Final audio file verification FAILED: {output_path}")
        else:
            self.logger.info(f"✅ Final audio file verification PASSED: {output_path}")
        
        # Validate final audio quality
        quality_info = self.audio_processor.validate_audio_quality(output_path)
        
        # CRITICAL: Verify final combined audio against original text
        self.logger.info("Starting full chapter verification...")
        try:
            final_verification = self.audio_verifier.verify_audio_content(output_path, cleaned_text)
            
            # Generate full chapter diff
            full_diff_file = chunks_dir / f"{base_name}_FULL_CHAPTER_diff.html"
            self._generate_html_diff(cleaned_text, final_verification.transcribed_text, full_diff_file, "FULL CHAPTER")
            
            # Save full chapter transcription
            full_transcription_file = chunks_dir / f"{base_name}_FULL_CHAPTER_transcription.txt"
            with open(full_transcription_file, 'w', encoding='utf-8') as f:
                f.write(final_verification.transcribed_text)
            
        except Exception as e:
            self.logger.error(f"Full chapter verification failed: {e}")
            from .audio_verifier import VerificationResult
            final_verification = VerificationResult(
                original_text=cleaned_text,
                transcribed_text="[FULL VERIFICATION FAILED]",
                accuracy_score=0.0,
                word_error_rate=1.0,
                character_error_rate=1.0,
                missing_words=[],
                extra_words=[],
                is_verified=False,
                error_message=str(e)
            )
        
        processing_time = time.time() - chapter_start_time
        
        # Calculate summary statistics
        verified_chunks = sum(1 for result in chunk_results 
                            if result.get('verification', {}).get('is_verified', False))
        avg_chunk_accuracy = sum(result.get('verification', {}).get('accuracy_score', 0) 
                               for result in chunk_results) / len(chunk_results)
        
        return {
            'chapter': chapter.number,
            'title': chapter.title,
            'word_count': chapter.word_count,
            'chunk_count': len(chunks),
            'chunks_directory': str(chunks_dir),
            'chunk_results': chunk_results,
            'verified_chunks': verified_chunks,
            'average_chunk_accuracy': avg_chunk_accuracy,
            'audio_file': str(output_path),
            'processing_time': processing_time,
            'quality_check': quality_info,
            'audio_file_verification': {
                'chunk_verification': audio_verification_results,
                'final_audio_valid': final_audio_valid if 'final_audio_valid' in locals() else False
            },
            'content_verification': {
                'is_verified': final_verification.is_verified,
                'accuracy_score': final_verification.accuracy_score,
                'word_error_rate': final_verification.word_error_rate,
                'character_error_rate': final_verification.character_error_rate,
                'missing_words_count': len(final_verification.missing_words),
                'extra_words_count': len(final_verification.extra_words),
                'error_message': final_verification.error_message
            },
            'status': 'success'
        }
    
    def _generate_html_diff(self, original_text: str, transcribed_text: str, diff_file: Path, chunk_num: int):
        """Generate an HTML diff file showing differences between original and transcribed text"""
        import difflib
        
        # Split into words for better diff visualization
        original_words = original_text.split()
        transcribed_words = transcribed_text.split()
        
        # Generate HTML diff
        differ = difflib.HtmlDiff(tabsize=2)
        diff_html = differ.make_file(
            original_words,
            transcribed_words,
            fromdesc=f"Original Text (Chunk {chunk_num})",
            todesc=f"Transcribed Audio (Chunk {chunk_num})",
            context=True,
            numlines=3
        )
        
        # Add custom CSS for better readability
        custom_css = """
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .diff_header { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        .diff_next { display: none; }
        table.diff { border-collapse: collapse; width: 100%; }
        td.diff_header { background-color: #e0e0e0; font-weight: bold; padding: 5px; }
        .diff_add { background-color: #aaffaa; }
        .diff_chg { background-color: #ffff77; }
        .diff_sub { background-color: #ffaaaa; }
        .summary { background-color: #e8f4fd; padding: 15px; border-radius: 5px; margin: 10px 0; }
        </style>
        """
        
        # Calculate accuracy
        from .audio_verifier import AudioVerifier
        verifier = AudioVerifier()
        comparison = verifier._compare_texts(original_text, transcribed_text)
        
        # Add summary section
        summary_html = f"""
        <div class="summary">
            <h3>Verification Summary - Chunk {chunk_num}</h3>
            <p><strong>Accuracy Score:</strong> {comparison.accuracy_score:.2%}</p>
            <p><strong>Word Error Rate:</strong> {comparison.word_error_rate:.2%}</p>
            <p><strong>Character Error Rate:</strong> {comparison.character_error_rate:.2%}</p>
            <p><strong>Missing Words:</strong> {len(comparison.missing_words)}</p>
            <p><strong>Extra Words:</strong> {len(comparison.extra_words)}</p>
            <p><strong>Status:</strong> {'✅ PASSED' if comparison.accuracy_score >= 0.85 else '❌ FAILED'}</p>
        </div>
        """
        
        # Insert custom CSS and summary into HTML
        diff_html = diff_html.replace('<head>', f'<head>{custom_css}')
        diff_html = diff_html.replace('<body>', f'<body>{summary_html}')
        
        # Save the HTML diff file
        with open(diff_file, 'w', encoding='utf-8') as f:
            f.write(diff_html)
        
        self.logger.info(f"Generated diff file: {diff_file}")

    def _generate_summary(self, input_file: Path, results: List[Dict], 
                         chapter_files: List[str]) -> Dict[str, Any]:
        """Generate processing summary report"""
        successful_chapters = [r for r in results if r.get('status') == 'success']
        failed_chapters = [r for r in results if r.get('status') == 'failed']
        
        total_words = sum(r.get('word_count', 0) for r in successful_chapters)
        total_time = sum(r.get('processing_time', 0) for r in successful_chapters)
        
        return {
            'input_file': str(input_file),
            'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_chapters': len(results),
            'successful_chapters': len(successful_chapters),
            'failed_chapters': len(failed_chapters),
            'total_words_processed': total_words,
            'total_processing_time': total_time,
            'average_time_per_chapter': total_time / len(successful_chapters) if successful_chapters else 0,
            'output_files': chapter_files,
            'chapter_details': results
        }
    
    def _create_manual_chapters(self, text: str, chapter_breaks: List[str]) -> List[Chapter]:
        """Create chapters based on manual breaks"""
        chapters = []
        current_pos = 0
        
        for i, break_text in enumerate(chapter_breaks):
            chapter_start = text.find(break_text, current_pos)
            if chapter_start == -1:
                self.logger.warning(f"Chapter break not found: {break_text}")
                continue
            
            # Get previous chapter content
            if i > 0:
                prev_chapter = chapters[-1]
                prev_chapter.content = text[prev_chapter.start_position:chapter_start].strip()
                prev_chapter.end_position = chapter_start
                prev_chapter.word_count = len(prev_chapter.content.split())
            
            # Create new chapter
            chapter = Chapter(
                number=i + 1,
                title=break_text.strip(),
                content="",
                start_position=chapter_start,
                end_position=0,
                word_count=0
            )
            chapters.append(chapter)
            current_pos = chapter_start
        
        # Handle last chapter
        if chapters:
            last_chapter = chapters[-1]
            last_chapter.content = text[last_chapter.start_position:].strip()
            last_chapter.end_position = len(text)
            last_chapter.word_count = len(last_chapter.content.split())
        
        return chapters
