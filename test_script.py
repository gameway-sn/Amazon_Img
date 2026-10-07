import base64
from PIL import Image
import io
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.converter import process_results_jsonl

def main():
    img = Image.new('RGB', (10, 10), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    response_obj = {
        "key": "ProductA__scene_1",
        "response": {
            "candidates": [{
                "content": {"parts": [{"inlineData": {"data": b64, "mimeType": "image/jpeg"}}]}
            }]
        }
    }
    
    test_jsonl_path = os.path.join(os.path.dirname(__file__), "test_output.jsonl")
    with open(test_jsonl_path, "w") as f:
        f.write(json.dumps(response_obj) + "\n")
        
    print(f"Created {test_jsonl_path}")
    process_results_jsonl(test_jsonl_path, "outputs")

if __name__ == "__main__":
    main()
