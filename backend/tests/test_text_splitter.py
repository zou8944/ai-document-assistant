"""
Tests for text_splitter module.
"""

import pytest
from data_processing.text_splitter import DocumentProcessor, create_document_processor, DocumentChunk

class TestDocumentProcessor:
    
    def test_create_document_processor(self):
        """Test document processor creation"""
        processor = create_document_processor()
        assert isinstance(processor, DocumentProcessor)
        assert processor.text_splitter.chunk_size == 1000
        assert processor.text_splitter.chunk_overlap == 200
    
    def test_create_document_processor_custom_params(self):
        """Test document processor creation with custom parameters"""
        processor = create_document_processor(chunk_size=500, chunk_overlap=100)
        assert processor.text_splitter.chunk_size == 500
        assert processor.text_splitter.chunk_overlap == 100
    
    def test_process_text_basic(self):
        """Test basic text processing"""
        processor = DocumentProcessor()
        text = "This is a test document. It has multiple sentences. Each sentence provides some information."
        
        chunks = processor.process_text(text, source="test.txt")
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert chunks[0].source == "test.txt"
        assert chunks[0].content == text  # Short text should be in one chunk
    
    def test_process_long_text(self):
        """Test processing long text that requires splitting"""
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        
        # Create long text
        long_text = " ".join([f"This is sentence number {i}." for i in range(100)])
        
        chunks = processor.process_text(long_text, source="long.txt")
        
        assert len(chunks) > 1  # Should be split into multiple chunks
        assert all(len(chunk.content) <= 150 for chunk in chunks)  # Respect chunk size limit
        assert chunks[0].start_index == 0
        assert chunks[1].start_index > 0  # Second chunk should have non-zero start index
    
    def test_process_empty_text(self):
        """Test processing empty text"""
        processor = DocumentProcessor()
        chunks = processor.process_text("", source="empty.txt")
        
        assert len(chunks) == 0
    
    def test_process_whitespace_only_text(self):
        """Test processing text with only whitespace"""
        processor = DocumentProcessor()
        chunks = processor.process_text("   \n\t  ", source="whitespace.txt")
        
        assert len(chunks) == 0
    
    def test_process_file_content(self):
        """Test processing file content with metadata"""
        processor = DocumentProcessor()
        content = "This is file content for testing."
        file_path = "/path/to/test.pdf"
        
        chunks = processor.process_file_content(file_path, content, "pdf")
        
        assert len(chunks) > 0
        chunk = chunks[0]
        assert chunk.source == file_path
        assert chunk.content == content
        assert chunk.metadata["file_path"] == file_path
        assert chunk.metadata["file_type"] == "pdf"
        assert "processing_timestamp" in chunk.metadata
    
    def test_process_web_content(self):
        """Test processing web content with metadata"""
        processor = DocumentProcessor()
        content = "This is web page content for testing."
        url = "https://example.com/page"
        title = "Example Page"
        
        chunks = processor.process_web_content(url, content, title)
        
        assert len(chunks) > 0
        chunk = chunks[0]
        assert chunk.source == url
        assert chunk.content == content
        assert chunk.metadata["url"] == url
        assert chunk.metadata["page_title"] == title
        assert chunk.metadata["content_type"] == "web_page"
    
    def test_get_chunk_stats_empty(self):
        """Test getting statistics for empty chunk list"""
        processor = DocumentProcessor()
        stats = processor.get_chunk_stats([])
        
        assert stats["total_chunks"] == 0
        assert stats["total_characters"] == 0
        assert stats["sources"] == []
    
    def test_get_chunk_stats_with_chunks(self):
        """Test getting statistics for chunk list"""
        processor = DocumentProcessor()
        
        # Create sample chunks
        chunks = [
            DocumentChunk(
                id="1",
                content="First chunk content",
                source="source1.txt",
                start_index=0,
                metadata={}
            ),
            DocumentChunk(
                id="2", 
                content="Second chunk content is longer",
                source="source2.txt",
                start_index=100,
                metadata={}
            ),
            DocumentChunk(
                id="3",
                content="Third chunk",
                source="source1.txt",  # Same source as first
                start_index=200,
                metadata={}
            )
        ]
        
        stats = processor.get_chunk_stats(chunks)
        
        assert stats["total_chunks"] == 3
        assert stats["total_characters"] == sum(len(c.content) for c in chunks)
        assert stats["unique_sources"] == 2  # Two unique sources
        assert "source1.txt" in stats["sources"]
        assert "source2.txt" in stats["sources"]
        assert stats["average_chunk_size"] > 0
    
    def test_chunk_metadata_preservation(self):
        """Test that metadata is properly preserved in chunks"""
        processor = DocumentProcessor()
        
        additional_metadata = {
            "author": "Test Author",
            "created_date": "2024-01-01",
            "category": "test"
        }
        
        chunks = processor.process_text(
            "Test content",
            source="test.txt",
            additional_metadata=additional_metadata
        )
        
        assert len(chunks) > 0
        chunk = chunks[0]
        
        # Check that additional metadata was preserved
        assert chunk.metadata["author"] == "Test Author"
        assert chunk.metadata["created_date"] == "2024-01-01"
        assert chunk.metadata["category"] == "test"
        assert chunk.metadata["source"] == "test.txt"