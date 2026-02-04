# Supported Document Formats

This document describes the document formats supported by the Knowledge Base Management system and their processing methods.

## PDF Documents

### Extraction Methods
- **PyPDF2**: For basic text extraction from PDFs
- **pdfplumber**: For more accurate text extraction with layout preservation
- **PDFMiner**: For advanced PDF processing and layout analysis

### Processing Pipeline
1. **Text Extraction**: Extract raw text content
2. **Metadata Extraction**: Extract title, author, creation date
3. **Page Segmentation**: Split by pages for better organization
4. **OCR Support**: For scanned PDFs (requires Tesseract)

### Limitations
- Complex layouts may not be preserved accurately
- Scanned documents require OCR processing
- Embedded images are not extracted by default

## DOCX Documents

### Extraction Methods
- **python-docx**: Primary library for DOCX processing
- **xml.etree.ElementTree**: For direct XML parsing when needed

### Processing Pipeline
1. **Paragraph Extraction**: Extract text from paragraphs
2. **Style Recognition**: Identify headings, lists, tables
3. **Metadata Extraction**: Document properties
4. **Image Extraction**: Extract embedded images (optional)

### Advantages
- Preserves document structure well
- Easy metadata extraction
- Support for styles and formatting

## TXT Documents

### Processing
- Simple text file reading with UTF-8 encoding
- Automatic encoding detection
- Line ending normalization

### Considerations
- No inherent structure information
- May require manual section detection
- Simple but versatile format

## Markdown Documents

### Processing Pipeline
1. **Parse Markdown Syntax**: Headers, lists, code blocks
2. **Extract Structure**: Use headers for hierarchical organization
3. **Convert to HTML**: For rich content rendering (optional)

### Advantages
- Inherent structure from headers
- Easy to process and analyze
- Supports code blocks and formatting

## HTML Documents

### Extraction Methods
- **BeautifulSoup4**: For HTML parsing and cleaning
- **lxml**: For fast XML/HTML processing

### Processing Pipeline
1. **HTML Cleaning**: Remove scripts, styles, ads
2. **Text Extraction**: Extract main content
3. **Link Extraction**: Extract and preserve hyperlinks
4. **Structure Analysis**: Use heading tags for hierarchy

## Other Formats

### CSV/Excel
- Tabular data extraction
- Schema detection
- Relationship mapping

### PowerPoint (PPTX)
- Slide-by-slide extraction
- Speaker notes extraction
- Image extraction

### Images
- OCR processing required
- Layout analysis for scanned documents
- Quality assessment

## File Type Detection

The system uses multiple methods for file type detection:

1. **File Extension**: Primary detection method
2. **Magic Numbers**: Binary signature detection
3. **Content Analysis**: For ambiguous files

## Processing Configuration

Configure processing options in `config.yaml`:

```yaml
document_processing:
  pdf:
    extractor: "pdfplumber"
    enable_ocr: false
    preserve_layout: true
  docx:
    extract_styles: true
    extract_images: false
  txt:
    encoding: "auto"
    normalize_line_endings: true
  max_file_size_mb: 50
```

## Best Practices

1. **Pre-process Documents**: Clean and normalize before ingestion
2. **Batch Processing**: Process similar documents together
3. **Quality Check**: Verify extraction quality for each format
4. **Fallback Strategies**: Have backup extraction methods
5. **Logging**: Log processing issues for troubleshooting
