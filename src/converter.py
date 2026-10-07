import json
import base64
import os
import io
from PIL import Image

def process_results_jsonl(jsonl_path, output_base_dir):
    """
    Reads a downloaded batch output JSONL file, decodes base64 images, 
    and saves them to outputs/<product_folder>/<scene>.jpg based on the key.
    """
    if not os.path.exists(jsonl_path):
        print(f"Error: {jsonl_path} not found.")
        return

    os.makedirs(output_base_dir, exist_ok=True)
    success_count = 0
    error_count = 0
    variant_counters = {}

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {line_num}: Failed to parse JSON - {e}")
                continue

            # The user's input request key is simply passed through by standard Gemini Batch API,
            # but sometimes the structure wraps it around depending on the SDK.
            # Assuming the key might be at the root level if passing it or inside a 'request' object.
            key = parsed.get("key", f"unknown_product__scene_unknown_{line_num}")
            
            # Key format: [jewelry reference subfolder name]_[Target Scene Image name]
            if "_" in key:
                parts = key.rsplit("_", 1)
                product_folder = parts[0]
                scene_name = parts[1]
            else:
                product_folder = "Uncategorized"
                scene_name = f"PT_unknown_{line_num}"

            product_dir = os.path.join(output_base_dir, product_folder)
            os.makedirs(product_dir, exist_ok=True)

            if 'error' in parsed:
                print(f"Error in result for {key}: {parsed['error']}")
                error_count += 1
                continue

            if 'response' in parsed and parsed['response']:
                try:
                    candidates = parsed['response']['candidates']
                    if not candidates:
                        print(f"No candidates returned for {key}")
                        error_count += 1
                        continue

                    parts = candidates[0]['content']['parts']
                    image_saved = False
                    for part in parts:
                        inline_data = part.get('inlineData')
                        if inline_data:
                            b64_data = inline_data.get('data')
                            if b64_data:
                                try:
                                    raw_bytes = base64.b64decode(b64_data)
                                    output_filepath = os.path.join(product_dir, f"{scene_name}.jpg")
                                    
                                    with open(output_filepath, "wb") as bf:
                                        bf.write(raw_bytes)
                                        
                                    print(f"Saved: {output_filepath}")
                                    success_count += 1
                                    image_saved = True
                                    break # Assuming 1 image per response
                                except Exception as e:
                                    print(f"Failed to process image for {key}: {e}")
                                    error_count += 1
                    
                    if not image_saved:
                        print(f"No image data found in response for {key}")
                        error_count += 1
                except KeyError as e:
                    print(f"Malformed response for {key}: missing key {e}")
                    error_count += 1

    print(f"\nConversion Complete: {success_count} succeeded, {error_count} failed.")


if __name__ == "__main__":
    # For standalone testing
    import sys
    test_jsonl = sys.argv[1] if len(sys.argv) > 1 else 'test_output.jsonl'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else '../outputs'
    process_results_jsonl(test_jsonl, out_dir)
