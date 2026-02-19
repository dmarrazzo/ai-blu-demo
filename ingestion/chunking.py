import os
import json
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# PVC_MOUNT is where your Elyra pipeline stores data between steps
PVC_MOUNT = Path(os.getenv("PVC_MOUNT", "/mnt/data"))

def chunk_text(text, max_chars=800, overlap=150):
    chunks = []
    start = 0
    if len(text) <= max_chars:
        return [text.strip()] if len(text.strip()) > 20 else []
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            last_space = text.rfind(" ", start, end)
            if last_space != -1: end = last_space
        chunk = text[start:end].strip()
        if len(chunk) > 20: chunks.append(chunk)
        start = end - overlap
        if start >= end: start = end + 1
    return chunks

def run_conversion(input_folder: str):
    pdf_options = PdfPipelineOptions(do_ocr=False)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
    )
    
    pdf_files = list(Path(input_folder).glob("*.pdf"))
    for pdf in pdf_files:
        print(f"📄 Processing {pdf.name}...")
        result = converter.convert(str(pdf))
        markdown_content = result.document.export_to_markdown()
        chunks = chunk_text(markdown_content)
        
        # Save chunks to a JSON file on the PVC for Stage 2
        output_file = PVC_MOUNT / "staging" / f"{pdf.stem}_chunks.json"
        with open(output_file, "w") as f:
            json.dump({"file_name": pdf.name, "chunks": chunks}, f)
        print(f"✅ Saved {len(chunks)} chunks to {output_file}")

if __name__ == "__main__":
    # In a pipeline, 'inputs' would be your source directory
    run_conversion(f"{PVC_MOUNT}/inputs")