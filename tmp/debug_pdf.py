import pdfplumber
import os

file_path = "data/ETHIO_RE_AT_A_GLANCE_2023_24.pdf"
print(f"File exists: {os.path.exists(file_path)}")
print(f"File size: {os.path.getsize(file_path)} bytes")

try:
    with pdfplumber.open(file_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"Page {i+1} text length: {len(text) if text else 0}")
except Exception as e:
    print(f"Error opening PDF: {e}")
