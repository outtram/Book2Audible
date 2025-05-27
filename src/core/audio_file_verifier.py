"""
Audio file verification system to ensure all WAV files are created successfully
"""
import wave
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from pydub import AudioSegment
import hashlib

class AudioFileVerifier:
    """Comprehensive audio file verification system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def verify_audio_file(self, audio_path: Path) -> Dict[str, Any]:
        """Comprehensive verification of a single audio file"""
        result = {
            'file_path': str(audio_path),
            'exists': False,
            'is_valid_wav': False,
            'is_readable': False,
            'has_audio_data': False,
            'duration_ms': 0,
            'file_size_bytes': 0,
            'sample_rate': 0,
            'channels': 0,
            'bit_depth': 0,
            'is_corrupted': False,
            'error_messages': [],
            'checksum': None,
            'overall_status': 'FAILED'
        }
        
        try:
            # Check if file exists
            if not audio_path.exists():
                result['error_messages'].append(f"File does not exist: {audio_path}")
                return result
            
            result['exists'] = True
            result['file_size_bytes'] = audio_path.stat().st_size
            
            # Check if file is empty
            if result['file_size_bytes'] == 0:
                result['error_messages'].append("File is empty (0 bytes)")
                return result
            
            # Generate file checksum for integrity
            with open(audio_path, 'rb') as f:
                file_hash = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    file_hash.update(chunk)
                result['checksum'] = file_hash.hexdigest()
            
            # Try to read as WAV using wave module (strict check)
            try:
                with wave.open(str(audio_path), 'rb') as wav_file:
                    result['is_valid_wav'] = True
                    result['sample_rate'] = wav_file.getframerate()
                    result['channels'] = wav_file.getnchannels()
                    result['bit_depth'] = wav_file.getsampwidth() * 8
                    frames = wav_file.getnframes()
                    if frames > 0:
                        result['duration_ms'] = int((frames / result['sample_rate']) * 1000)
                        result['has_audio_data'] = True
            except Exception as e:
                result['error_messages'].append(f"WAV format validation failed: {str(e)}")
            
            # Try to read with pydub (more permissive)
            if not result['is_valid_wav']:
                try:
                    audio = AudioSegment.from_wav(str(audio_path))
                    result['is_readable'] = True
                    result['duration_ms'] = len(audio)
                    result['sample_rate'] = audio.frame_rate
                    result['channels'] = audio.channels
                    result['bit_depth'] = audio.sample_width * 8
                    
                    if result['duration_ms'] > 0:
                        result['has_audio_data'] = True
                        
                except Exception as e:
                    result['error_messages'].append(f"Pydub reading failed: {str(e)}")
                    result['is_corrupted'] = True
            
            # Overall status determination
            if result['has_audio_data'] and result['duration_ms'] > 100:  # At least 100ms
                result['overall_status'] = 'PASSED'
            elif result['exists'] and result['file_size_bytes'] > 0:
                result['overall_status'] = 'WARNING'
            else:
                result['overall_status'] = 'FAILED'
                
        except Exception as e:
            result['error_messages'].append(f"Verification failed: {str(e)}")
            self.logger.error(f"Audio verification error for {audio_path}: {e}")
        
        return result
    
    def verify_chunk_directory(self, chunks_dir: Path, base_name: str, expected_chunk_count: int) -> Dict[str, Any]:
        """Verify all chunk files in a directory"""
        
        self.logger.info(f"Verifying chunks in: {chunks_dir}")
        
        verification_results = {
            'chunks_directory': str(chunks_dir),
            'base_name': base_name,
            'expected_chunk_count': expected_chunk_count,
            'found_text_files': 0,
            'found_audio_files': 0,
            'valid_audio_files': 0,
            'total_duration_ms': 0,
            'total_file_size_bytes': 0,
            'chunk_verifications': [],
            'missing_chunks': [],
            'corrupted_chunks': [],
            'summary_status': 'UNKNOWN'
        }
        
        # Check each expected chunk
        for chunk_num in range(1, expected_chunk_count + 1):
            chunk_verification = {
                'chunk_number': chunk_num,
                'text_file_status': 'MISSING',
                'audio_file_status': 'MISSING',
                'text_file_path': None,
                'audio_file_path': None,
                'text_content_length': 0,
                'audio_verification': None
            }
            
            # Check text file
            text_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.txt"
            if text_file.exists():
                chunk_verification['text_file_status'] = 'EXISTS'
                chunk_verification['text_file_path'] = str(text_file)
                verification_results['found_text_files'] += 1
                
                # Read text content
                try:
                    with open(text_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        chunk_verification['text_content_length'] = len(content)
                        if len(content.strip()) > 0:
                            chunk_verification['text_file_status'] = 'VALID'
                except Exception as e:
                    chunk_verification['text_file_status'] = f'ERROR: {e}'
            
            # Check audio file
            audio_file = chunks_dir / f"{base_name}_chunk_{chunk_num:03d}.wav"
            if audio_file.exists():
                chunk_verification['audio_file_path'] = str(audio_file)
                verification_results['found_audio_files'] += 1
                
                # Verify audio file
                audio_result = self.verify_audio_file(audio_file)
                chunk_verification['audio_verification'] = audio_result
                
                if audio_result['overall_status'] == 'PASSED':
                    chunk_verification['audio_file_status'] = 'VALID'
                    verification_results['valid_audio_files'] += 1
                    verification_results['total_duration_ms'] += audio_result['duration_ms']
                    verification_results['total_file_size_bytes'] += audio_result['file_size_bytes']
                elif audio_result['overall_status'] == 'WARNING':
                    chunk_verification['audio_file_status'] = 'WARNING'
                else:
                    chunk_verification['audio_file_status'] = 'CORRUPTED'
                    verification_results['corrupted_chunks'].append(chunk_num)
            else:
                verification_results['missing_chunks'].append(chunk_num)
            
            verification_results['chunk_verifications'].append(chunk_verification)
        
        # Calculate summary status
        if verification_results['valid_audio_files'] == expected_chunk_count:
            verification_results['summary_status'] = 'ALL_VALID'
        elif verification_results['valid_audio_files'] >= expected_chunk_count * 0.9:  # 90% threshold
            verification_results['summary_status'] = 'MOSTLY_VALID'
        elif verification_results['valid_audio_files'] > 0:
            verification_results['summary_status'] = 'PARTIALLY_VALID'
        else:
            verification_results['summary_status'] = 'FAILED'
        
        # Log summary
        self.logger.info(f"Chunk verification complete:")
        self.logger.info(f"  Expected chunks: {expected_chunk_count}")
        self.logger.info(f"  Found text files: {verification_results['found_text_files']}")
        self.logger.info(f"  Found audio files: {verification_results['found_audio_files']}")
        self.logger.info(f"  Valid audio files: {verification_results['valid_audio_files']}")
        self.logger.info(f"  Total duration: {verification_results['total_duration_ms']/1000:.1f} seconds")
        self.logger.info(f"  Status: {verification_results['summary_status']}")
        
        if verification_results['missing_chunks']:
            self.logger.warning(f"Missing chunks: {verification_results['missing_chunks']}")
        if verification_results['corrupted_chunks']:
            self.logger.error(f"Corrupted chunks: {verification_results['corrupted_chunks']}")
        
        return verification_results
    
    def save_verification_report(self, verification_results: Dict[str, Any], output_file: Path):
        """Save detailed verification report to file"""
        
        try:
            # Save JSON report
            json_file = output_file.with_suffix('.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(verification_results, f, indent=2, default=str)
            
            # Save human-readable report
            txt_file = output_file.with_suffix('.txt')
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("AUDIO FILE VERIFICATION REPORT\n")
                f.write("=" * 80 + "\n\n")
                
                f.write(f"Directory: {verification_results['chunks_directory']}\n")
                f.write(f"Base Name: {verification_results['base_name']}\n")
                f.write(f"Expected Chunks: {verification_results['expected_chunk_count']}\n")
                f.write(f"Status: {verification_results['summary_status']}\n\n")
                
                f.write("SUMMARY:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Text Files Found: {verification_results['found_text_files']}/{verification_results['expected_chunk_count']}\n")
                f.write(f"Audio Files Found: {verification_results['found_audio_files']}/{verification_results['expected_chunk_count']}\n")
                f.write(f"Valid Audio Files: {verification_results['valid_audio_files']}/{verification_results['expected_chunk_count']}\n")
                f.write(f"Total Duration: {verification_results['total_duration_ms']/1000:.1f} seconds\n")
                f.write(f"Total File Size: {verification_results['total_file_size_bytes']/1024/1024:.1f} MB\n\n")
                
                if verification_results['missing_chunks']:
                    f.write(f"MISSING CHUNKS: {verification_results['missing_chunks']}\n\n")
                
                if verification_results['corrupted_chunks']:
                    f.write(f"CORRUPTED CHUNKS: {verification_results['corrupted_chunks']}\n\n")
                
                f.write("DETAILED CHUNK VERIFICATION:\n")
                f.write("-" * 40 + "\n")
                
                for chunk_info in verification_results['chunk_verifications']:
                    chunk_num = chunk_info['chunk_number']
                    f.write(f"Chunk {chunk_num:03d}:\n")
                    f.write(f"  Text File: {chunk_info['text_file_status']}\n")
                    f.write(f"  Audio File: {chunk_info['audio_file_status']}\n")
                    
                    if chunk_info['audio_verification']:
                        av = chunk_info['audio_verification']
                        f.write(f"    Duration: {av['duration_ms']/1000:.1f}s\n")
                        f.write(f"    File Size: {av['file_size_bytes']/1024:.1f} KB\n")
                        f.write(f"    Sample Rate: {av['sample_rate']} Hz\n")
                        f.write(f"    Channels: {av['channels']}\n")
                        f.write(f"    Bit Depth: {av['bit_depth']} bits\n")
                        
                        if av['error_messages']:
                            f.write(f"    Errors: {'; '.join(av['error_messages'])}\n")
                    
                    f.write("\n")
            
            self.logger.info(f"Verification report saved: {json_file} and {txt_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save verification report: {e}")
    
    def quick_verify_final_audio(self, final_audio_path: Path, expected_min_duration_ms: int = 1000) -> bool:
        """Quick verification of final stitched audio file"""
        
        if not final_audio_path.exists():
            self.logger.error(f"Final audio file does not exist: {final_audio_path}")
            return False
        
        try:
            verification = self.verify_audio_file(final_audio_path)
            
            if verification['overall_status'] != 'PASSED':
                self.logger.error(f"Final audio verification failed: {verification['error_messages']}")
                return False
            
            if verification['duration_ms'] < expected_min_duration_ms:
                self.logger.warning(f"Final audio duration ({verification['duration_ms']}ms) below expected minimum ({expected_min_duration_ms}ms)")
                return False
            
            self.logger.info(f"Final audio verification PASSED: {verification['duration_ms']/1000:.1f}s, {verification['file_size_bytes']/1024/1024:.1f}MB")
            return True
            
        except Exception as e:
            self.logger.error(f"Final audio verification error: {e}")
            return False