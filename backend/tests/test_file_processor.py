"""
Tests for file_processor module.
"""

from config import Config
from data_processing.file_processor import FileProcessor, create_file_processor


class TestFileProcessor:

    def test_create_file_processor(self):
        """Test file processor creation"""
        processor = create_file_processor()
        assert isinstance(processor, FileProcessor)
        assert processor.max_file_size == 50 * 1024 * 1024  # 50MB default

    def test_create_file_processor_custom_size(self):
        """Test file processor creation with custom max size"""
        config = Config(max_file_size_mb=10.0)  # 10MB
        processor = create_file_processor(config)
        assert processor.max_file_size == 10 * 1024 * 1024

    def test_process_text_file(self, sample_text_file):
        """Test processing a text file"""
        processor = FileProcessor()
        result = processor.process_file(sample_text_file)

        assert result.success is True
        assert result.file_type == "text"
        assert len(result.content) > 0
        assert "sample text file" in result.content
        # Use Path.resolve() for consistent path comparison
        from pathlib import Path
        assert Path(result.file_path).resolve() == Path(sample_text_file).resolve()
        assert result.metadata["file_extension"] == ".txt"

    def test_process_markdown_file(self, sample_markdown_file):
        """Test processing a markdown file"""
        processor = FileProcessor()
        result = processor.process_file(sample_markdown_file)

        assert result.success is True
        assert result.file_type == "markdown"
        assert "# Sample Markdown" in result.content
        assert "**sample**" in result.content

    def test_process_nonexistent_file(self):
        """Test processing a file that doesn't exist"""
        processor = FileProcessor()
        result = processor.process_file("nonexistent.txt")

        assert result.success is False
        assert result.error == "File not found"
        assert result.content == ""

    def test_process_large_file(self, temp_dir):
        """Test processing a file that's too large"""
        # Create small max size processor
        processor = FileProcessor(max_file_size=100)  # 100 bytes

        # Create file larger than limit
        large_file = temp_dir / "large.txt"
        with open(large_file, "w") as f:
            f.write("x" * 200)  # 200 bytes

        result = processor.process_file(str(large_file))

        assert result.success is False
        assert "File too large" in result.error

    def test_process_folder(self, temp_dir):
        """Test processing a folder with multiple files"""
        # Create multiple test files
        (temp_dir / "file1.txt").write_text("Content of file 1")
        (temp_dir / "file2.md").write_text("# Content of file 2")
        (temp_dir / "file3.py").write_text("print('Content of file 3')")
        (temp_dir / "unsupported.bin").write_bytes(b"binary content")

        processor = FileProcessor()
        results = list(processor.process_folder(str(temp_dir), recursive=False))

        # Should have processed 3 supported files, skipped 1 unsupported
        successful_results = [r for r in results if r.success]
        assert len(successful_results) == 3

        file_types = {r.file_type for r in successful_results}
        assert "text" in file_types
        assert "markdown" in file_types
        assert "code" in file_types

    def test_get_supported_extensions(self):
        """Test getting supported extensions"""
        processor = FileProcessor()
        extensions = processor.get_supported_extensions()

        assert ".txt" in extensions
        assert ".md" in extensions
        assert ".pdf" in extensions
        assert ".docx" in extensions
        assert len(extensions) > 0

    def test_is_supported_file(self):
        """Test checking if file is supported"""
        processor = FileProcessor()

        assert processor.is_supported_file("document.pdf") is True
        assert processor.is_supported_file("text.txt") is True
        assert processor.is_supported_file("readme.md") is True
        assert processor.is_supported_file("binary.exe") is False
        assert processor.is_supported_file("image.jpg") is False

    def test_process_empty_file(self, temp_dir):
        """Test processing an empty file"""
        empty_file = temp_dir / "empty.txt"
        empty_file.write_text("")

        processor = FileProcessor()
        result = processor.process_file(str(empty_file))

        assert result.success is False
        assert result.error == "No content extracted from file"
