#!/usr/bin/env python3
"""
Book2Audible - Convert books to audiobooks using Orpheus TTS
"""
import click
import sys
from pathlib import Path
from typing import List, Optional

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.processor import Book2AudioProcessor
from src.core.config import config
from src.core.pdf_extractor import extract_pdf_chapters
from src.utils.logger import setup_logger

@click.command()
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True),
              help='Input text file (.txt or .docx)')
@click.option('--output', '-o', 'output_dir', type=click.Path(),
              help='Output directory for audio files')
@click.option('--voice', '-v', default='tara',
              help='Voice to use for TTS (default: tara)')
@click.option('--manual-chapters', '-m', multiple=True,
              help='Manually specify chapter breaks (can be used multiple times)')
@click.option('--log-level', '-l', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level')
@click.option('--test-connection', is_flag=True,
              help='Test Baseten API connection and exit')
@click.option('--validate-config', is_flag=True,
              help='Validate configuration and exit')
@click.option('--extract-pdf', 'pdf_file', type=click.Path(exists=True),
              help='Extract chapters from PDF file and exit')
def main(input_file: str, output_dir: Optional[str], voice: str,
         manual_chapters: List[str], log_level: str, 
         test_connection: bool, validate_config: bool, pdf_file: Optional[str]):
    """
    Book2Audible - Convert text books to audiobooks using Orpheus TTS
    
    Examples:
        book2audible -i book.txt
        book2audible -i book.docx -o ./audio_output
        book2audible -i book.txt -m "Chapter 1" -m "Chapter 2"
        book2audible --extract-pdf book.pdf -o ./extracted_chapters
        book2audible --test-connection
    """
    
    # Setup logger
    logger = setup_logger("CLI", config.log_file, log_level)
    
    # Banner
    click.echo("🎧 Book2Audible - Text to Audiobook Converter")
    click.echo("=" * 50)
    
    try:
        # Initialize processor
        processor = Book2AudioProcessor(log_level)
        
        # Handle special flags
        if validate_config:
            click.echo("✅ Configuration validation...")
            _validate_configuration()
            return
            
        if test_connection:
            click.echo("🔌 Testing Baseten API connection...")
            if processor.tts_client.test_connection():
                click.echo("✅ Connection successful!")
            else:
                click.echo("❌ Connection failed!")
                sys.exit(1)
            return
        
        if pdf_file:
            click.echo("📄 Extracting chapters from PDF...")
            _extract_pdf_chapters(pdf_file, output_dir, log_level)
            return
        
        # Validate inputs (only required if not using special flags)
        if not input_file:
            click.echo("❌ Error: Missing option '--input' / '-i'. Required when not using --test-connection, --validate-config, or --extract-pdf.")
            sys.exit(1)
            
        input_path = Path(input_file)
        if not input_path.exists():
            click.echo(f"❌ Input file not found: {input_path}")
            sys.exit(1)
        
        # Set output directory
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = config.output_dir
        
        # Display processing info
        click.echo(f"📖 Input: {input_path}")
        click.echo(f"🎵 Output: {output_path}")
        click.echo(f"🗣️ Voice: {voice}")
        
        if manual_chapters:
            click.echo(f"📑 Manual chapters: {len(manual_chapters)}")
        
        click.echo("\n🚀 Starting processing...")
        
        # Process the book
        summary = processor.process_book(
            input_path, 
            output_path, 
            list(manual_chapters) if manual_chapters else None
        )
        
        # Display results
        click.echo("\n" + "=" * 50)
        click.echo("✅ Processing completed!")
        click.echo(f"📊 Chapters processed: {summary['successful_chapters']}/{summary['total_chapters']}")
        click.echo(f"📝 Words processed: {summary['total_words_processed']:,}")
        click.echo(f"⏱️ Total time: {summary['total_processing_time']:.1f}s")
        
        if summary['failed_chapters'] > 0:
            click.echo(f"⚠️ Failed chapters: {summary['failed_chapters']}")
        
        click.echo(f"📁 Audio files saved to: {output_path}")
        
    except KeyboardInterrupt:
        click.echo("\n⏹️ Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        click.echo(f"❌ Error: {e}")
        sys.exit(1)

def _validate_configuration():
    """Validate application configuration"""
    issues = []
    
    # Check API key
    if not config.baseten_api_key or config.baseten_api_key.startswith("${"):
        issues.append("❌ Baseten API key not configured (set BASETEN_API_KEY)")
    else:
        click.echo("✅ Baseten API key configured")
    
    # Check directories
    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        click.echo("✅ Output directory accessible")
    except Exception as e:
        issues.append(f"❌ Output directory issue: {e}")
    
    # Check configuration files
    config_files = [
        config.config_dir / "baseten_config.json",
        config.config_dir / "tts_settings.json"
    ]
    
    for conf_file in config_files:
        if conf_file.exists():
            click.echo(f"✅ {conf_file.name} found")
        else:
            issues.append(f"❌ {conf_file.name} missing")
    
    if issues:
        click.echo("\nConfiguration Issues:")
        for issue in issues:
            click.echo(issue)
        sys.exit(1)
    else:
        click.echo("\n✅ All configuration checks passed!")

def _extract_pdf_chapters(pdf_file: str, output_dir: Optional[str], log_level: str):
    """Extract chapters from PDF file"""
    pdf_path = Path(pdf_file)
    
    # Set output directory
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path.cwd() / "extracted_chapters"
    
    click.echo(f"📄 PDF: {pdf_path}")
    click.echo(f"📁 Output: {output_path}")
    
    try:
        # Extract chapters
        stats = extract_pdf_chapters(pdf_path, output_path, log_level)
        
        # Display results
        click.echo("\n" + "=" * 50)
        click.echo("✅ PDF extraction completed!")
        click.echo(f"📊 Chapters extracted: {stats['total_chapters']}")
        click.echo(f"📝 Total words: {stats['total_words']:,}")
        click.echo(f"📄 Total pages: {stats['total_pages']}")
        click.echo(f"📁 Files saved to: {output_path / 'chapters'}")
        
        # Show chapter breakdown
        click.echo("\n📋 Extracted chapters:")
        for chapter in stats['chapters']:
            click.echo(f"  • {chapter['filename']}.txt ({chapter['word_count']} words)")
            
    except Exception as e:
        click.echo(f"❌ PDF extraction failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
