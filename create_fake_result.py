import base64
import json
import sys
import os

def create_fake_result(image_path, run_id="2950a230"):
    if not os.path.exists(image_path):
        print(f"Error: Could not find image at {image_path}")
        return
        
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"
    
    # Read the image and convert it to base64
    with open(image_path, "rb") as f:
        b64_string = base64.b64encode(f.read()).decode('utf-8')
        
    # Build the fake Gemini response payload exactly as the API returns it
    payload = {
        "key": "MyOwnProduct__scene_custom", 
        "response": {
            "candidates": [{
                "content": {
                    "parts": [{
                        "inlineData": {
                            "mimeType": mime_type, 
                            "data": b64_string
                        }
                    }]
                }
            }]
        }
    }
    
    # Overwrite the existing test results file
    os.makedirs("data", exist_ok=True)
    out_file = os.path.join("data", f"results_{run_id}.jsonl")
    with open(out_file, "w") as f:
        f.write(json.dumps(payload) + "\n")
        
    print(f"Successfully folded your image into a fake API payload!")
    print(f"Saved to: {out_file}")
    print("Go back to the UI and click 'Convert' on Run_01 (ID: 2950a230) to test!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_fake_result.py <path_to_your_image.jpg>")
    else:
        create_fake_result(sys.argv[1])
