"""
File handling utilities for Book2Audible
"""
import chardet
from pathlib import Path
from typing import Union, Tuple
import logging
from docx import Document

class FileHandler:
    """Handles reading various file formats and encoding detection"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.supported_formats = ['.txt', '.docx']
    
    def read_file(self, file_path: Union[str, Path]) -> str:
        """Read text content from file, auto-detecting format and encoding"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        self.logger.info(f"Reading file: {file_path}")
        
        try:
            if file_path.suffix.lower() == '.txt':
                return self._read_text_file(file_path)
            elif file_path.suffix.lower() == '.docx':
                return self._read_docx_file(file_path)
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {e}")
            raise
    
    def _read_text_file(self, file_path: Path) -> str:
        """Read text file with encoding detection"""
        # Detect encoding
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        encoding_result = chardet.detect(raw_data)
        encoding = encoding_result['encoding'] or 'utf-8'
        confidence = encoding_result['confidence']
        
        self.logger.debug(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
        
        # Read with detected encoding
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback to utf-8 with error handling
            self.logger.warning(f"Failed to decode with {encoding}, falling back to utf-8")
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        
        return content
    
    def _read_docx_file(self, file_path: Path) -> str:
        """Read DOCX file content"""
        try:
            doc = Document(file_path)
            paragraphs = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    paragraphs.append(paragraph.text)
            
            content = '\n'.join(paragraphs)
            self.logger.info(f"Successfully read DOCX file: {len(content)} characters")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to read DOCX file: {e}")
            raise
