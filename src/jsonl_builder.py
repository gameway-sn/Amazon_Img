import os
import glob
import json

def get_target_scenes(target_scene_dir):
    """
    Returns a sorted list of image file paths from the target scene directory.
    """
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    images = []
    if not os.path.exists(target_scene_dir):
        return images
        
    for item in os.listdir(target_scene_dir):
        ext = os.path.splitext(item)[1].lower()
        if ext in valid_exts:
            # Try to sort numerically if possible, else alphabetically
            images.append(os.path.join(target_scene_dir, item))
            
    def sort_key(filepath):
        basename = os.path.basename(filepath)
        name_no_ext = os.path.splitext(basename)[0]
        if name_no_ext.isdigit():
            return (0, int(name_no_ext))
        return (1, basename)
        
    images.sort(key=sort_key)
    return images

def get_product_references(product_folder):
    """
    Returns a sorted list of all valid reference images found.
    Prioritizes 'main' or 'hero', then '1.*', then alphabetical.
    """
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    images = []
    
    for item in os.listdir(product_folder):
        ext = os.path.splitext(item)[1].lower()
        if ext in valid_exts:
            images.append(item)
            
    if not images:
        return []
        
    def score(img):
        lower_name = img.lower()
        if 'main' in lower_name or 'hero' in lower_name:
            return 0
        if img.startswith('1.'):
            return 1
        return 2

    # sort by score then alphabetically
    images.sort(key=lambda img: (score(img), img))
    return [os.path.join(product_folder, img) for img in images]

def build_local_job_pairs(target_scene_dir, jewelry_ref_dir, output_base_dir=None):
    """
    Scans the directories and pairs up target scenes with product references.
    If output_base_dir is provided, skips pairs where the output image already exists.
    Returns: list of dicts with 'key', 'target_path', 'ref_path'
    """
    scenes = get_target_scenes(target_scene_dir)
    if not scenes:
        return []
        
    pairs = []
    if os.path.exists(jewelry_ref_dir):
        for product_name in os.listdir(jewelry_ref_dir):
            product_folder = os.path.join(jewelry_ref_dir, product_name)
            if os.path.isdir(product_folder):
                ref_paths = get_product_references(product_folder)
                if not ref_paths:
                    continue
                    
                # Pair with each target scene
                for idx, scene_path in enumerate(scenes, start=1):
                    # We can use the actual integer or the scene name
                    scene_name = os.path.splitext(os.path.basename(scene_path))[0]
                    
                    if output_base_dir:
                        expected_output = os.path.join(output_base_dir, product_name, f"{scene_name}.jpg")
                        if os.path.exists(expected_output):
                            continue
                            
                    key = f"{product_name}_{scene_name}"
                    
                    pairs.append({
                        "key": key,
                        "product_name": product_name,
                        "scene_name": scene_name,
                        "target_path": scene_path,
                        "ref_paths": ref_paths
                    })
    return pairs

def generate_jsonl_line(key, target_uri, target_mime, refs_info, prompt_text, model="gemini-1.5-pro", aspect_ratio="1:1", is_2k=False, use_target_scene=True):
    """
    Given the Gemini File URIs, generates the Batch API JSONL line for one request.
    refs_info: list of dicts [{'uri': uri, 'mime': mime}]
    use_target_scene: when False, the target scene image is omitted and only the
    reference jewelry + prompt are sent (target_uri/target_mime are ignored).
    """
    parts = []
    if use_target_scene:
        parts.append({"text": "target scene image:"})
        parts.append({"fileData": {"mimeType": target_mime, "fileUri": target_uri}})

    for i, ref in enumerate(refs_info, start=1):
        label = "reference jewelry image:" if len(refs_info) == 1 else f"reference jewelry image {i}:"
        parts.append({"text": label})
        parts.append({"fileData": {"mimeType": ref['mime'], "fileUri": ref['uri']}})
        
    parts.append({"text": prompt_text})

    generation_config = {
        "responseModalities": ["IMAGE"],
        "imageConfig": {
            "aspectRatio": aspect_ratio
        }
    }
    if is_2k:
        generation_config["imageConfig"]["imageSize"] = "2K"

    model_str = model if model.startswith("models/") else f"models/{model}"
    request_obj = {
        "key": key,
        "request": {
            "model": model_str,
            "contents": [{
                "role": "user",
                "parts": parts
            }],
            "generationConfig": generation_config
        }
    }
    return json.dumps(request_obj)
