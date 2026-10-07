import json
import os
import time
import mimetypes

try:
    from google import genai
    from google.genai import types
except ImportError:
    # Handle if sdk not installed yet
    genai = None
    types = None

from src.jsonl_builder import build_local_job_pairs, generate_jsonl_line

class GeminiBatchAPI:
    def __init__(self, is_live=False, api_key=None):
        self.is_live = is_live
        if self.is_live:
            if genai is None:
                raise ImportError("google-genai is not installed.")
            if api_key:
                self.client = genai.Client(api_key=api_key)
            else:
                self.client = genai.Client()
        else:
            self.client = None

    def _get_mime_type(self, filepath):
        # basic fallback
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.png': return 'image/png'
        if ext in ['.jpg', '.jpeg']: return 'image/jpeg'
        if ext == '.webp': return 'image/webp'
        return 'application/octet-stream'

    def _resolve_prompt(self, prompts_map, scene_name):
        """
        Returns (prompt_text, aspect_ratio, resolution, use_target_scene) for a scene.
        Supports both the dict format and legacy plain-string prompt entries.
        """
        default_prompt = "Use the reference jewelry image to stylize the scene."
        prompt_data = prompts_map.get(scene_name, {})
        if isinstance(prompt_data, dict):
            return (
                prompt_data.get("prompt", default_prompt),
                prompt_data.get("aspect_ratio", "1:1"),
                prompt_data.get("resolution", "1024x1024"),
                not prompt_data.get("skip_target_scene", False),
            )
        return (str(prompt_data) if prompt_data else default_prompt, "1:1", "1024x1024", True)

    def upload_file_with_poll(self, filepath, display_name=None):
        if not self.is_live:
            print(f"[DRY RUN] Would upload: {filepath}")
            return f"uri://dry-run/{os.path.basename(filepath)}"
            
        mime_type = self._get_mime_type(filepath)
        display_name = display_name or os.path.basename(filepath)
        
        print(f"Uploading {filepath}...")
        uploaded_file = self.client.files.upload(
            file=filepath,
            config={'display_name': display_name, 'mime_type': mime_type}
        )
        
        # Poll briefly
        file_name = uploaded_file.name
        print(f"Uploaded as {file_name}. Polling status...")
        while True:
            file_info = self.client.files.get(name=file_name)
            state = getattr(file_info, 'state', None)
            # Depending on SDK, could be string or enum. Assuming string or .name
            state_str = state.name if hasattr(state, 'name') else str(state)
            
            if 'ACTIVE' in state_str:
                break
            elif 'FAILED' in state_str:
                raise Exception(f"File {file_name} processing failed.")
            time.sleep(2)
            
        # The JSONL needs 'fileUri', but SDK might return a generic name or uri.
        # Assuming uploaded_file.uri or similar. 
        # Fallback if uri isn't present, construct or just use name depending on exact API shape.
        uri = getattr(uploaded_file, 'uri', None)
        if not uri:
            # Sometime SDK users must construct:
            # We will use what is available. For gemini 1.5 fileUri usually looks like:
            pass
        return getattr(uploaded_file, 'uri', f"sys_uri_for_name:{file_name}")

    def create_batch_job(self, target_scene_dir, jewelry_ref_dir, prompts_config, model_name="gemini-3-pro-image-preview", run_name="MyRun", output_base_dir=None):
        """
        Main orchestration:
        1. Build pairs
        2. Upload images
        3. Create JSONL request
        4. Upload JSONL
        5. Start job
        """
        print(f"=== Starting Batch Run: {run_name} (LIVE={self.is_live}) ===")
        pairs = build_local_job_pairs(target_scene_dir, jewelry_ref_dir, output_base_dir)
        if not pairs:
            print("No valid target/reference pairs found. Aborting.")
            return None
            
        # Read prompt mappings
        import json
        prompts_map = {}
        if os.path.exists(prompts_config):
            try:
                with open(prompts_config, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        prompts_map = data
            except Exception as e:
                print(f"Warning: Failed to load prompts config: {e}")
        
        # Upload cache to avoid re-uploading the same file
        uploaded_cache = {}
        
        jsonl_lines = []
        for pair in pairs:
            prompt_text, aspect_ratio, resolution, use_target_scene = self._resolve_prompt(prompts_map, pair['scene_name'])

            # Target image (skipped entirely when the prompt has the target scene deselected)
            t_uri, t_mime = None, None
            if use_target_scene:
                t_path = pair['target_path']
                if t_path not in uploaded_cache:
                    uploaded_cache[t_path] = self.upload_file_with_poll(t_path)
                t_uri = uploaded_cache[t_path]
                t_mime = self._get_mime_type(t_path)

            # Ref images
            refs_info = []
            for r_path in pair['ref_paths']:
                if r_path not in uploaded_cache:
                    uploaded_cache[r_path] = self.upload_file_with_poll(r_path)
                r_uri = uploaded_cache[r_path]
                r_mime = self._get_mime_type(r_path)
                refs_info.append({"uri": r_uri, "mime": r_mime})
            
            # Key
            key = pair['key']

            is_2k = resolution in ["2048x2048", "1792x2400", "2752x1536"]

            json_line = generate_jsonl_line(key, t_uri, t_mime, refs_info, prompt_text, model=model_name, aspect_ratio=aspect_ratio, is_2k=is_2k, use_target_scene=use_target_scene)
            jsonl_lines.append(json_line)
            
        # Save temp JSONL locally
        temp_jsonl = f"temp_batch_{int(time.time())}.jsonl"
        with open(temp_jsonl, "w") as f:
            for line in jsonl_lines:
                f.write(line + "\n")
                
        print(f"Generated JSONL with {len(jsonl_lines)} requests: {temp_jsonl}")
        
        if not self.is_live:
            print(f"[DRY RUN] Would upload {temp_jsonl} and start Batch Job.")
            return "batches/dry_run_job_" + str(int(time.time()))
            
        # LIVE: Upload the JSONL
        uploaded_jsonl = self.client.files.upload(
            file=temp_jsonl,
            config={'display_name': f'batch-req-{run_name}', 'mime_type': 'application/jsonl'}
        )
        print(f"Uploaded JSONL as {uploaded_jsonl.name}")
        
        # Start Batch Job
        # Using string config to avoid crash if types module is missing
        actual_model = model_name if model_name.startswith("models/") else f"models/{model_name}"
        job = self.client.batches.create(
            model=actual_model,
            src=uploaded_jsonl.name,
            config={'display_name': run_name}
        )
        
        print(f"Job Created! {job.name}")
        return job.name

    def run_instant_job(self, target_scene_dir, jewelry_ref_dir, prompts_config, model_name, output_base_dir):
        print(f"=== Starting Instant Run (LIVE={self.is_live}, Model={model_name}) ===")
        pairs = build_local_job_pairs(target_scene_dir, jewelry_ref_dir, output_base_dir)
        if not pairs:
            print("No valid target/reference pairs found. Aborting.")
            return 0, 0
            
        import json
        prompts_map = {}
        if os.path.exists(prompts_config):
            try:
                with open(prompts_config, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        prompts_map = data
            except Exception:
                pass
                
        success_count = 0
        error_count = 0
        variant_counters = {}
        
        try:
            from PIL import Image
            from google.genai import types
        except ImportError:
            print("Please ensure Pillow (PIL) and google-genai are installed.")
            return 0, len(pairs)

        for idx, pair in enumerate(pairs, 1):
            key = pair['key']
            print(f"[{idx}/{len(pairs)}] Processing Instant Generation: {key}")
            
            if not self.is_live:
                print(f"[DRY RUN] Would generate instant item for {key} with model {model_name}")
                success_count += 1
                continue
                
            try:
                prompt_text, aspect_ratio, resolution, use_target_scene = self._resolve_prompt(prompts_map, pair['scene_name'])
                ref_images = [Image.open(rp) for rp in pair['ref_paths']]

                # Target scene deselected -> send only the prompt + reference jewelry
                if use_target_scene:
                    t_img = Image.open(pair['target_path'])
                    contents = [prompt_text, t_img] + ref_images
                else:
                    contents = [prompt_text] + ref_images
                
                # Check mapping for 2K
                is_2k = resolution in ["2048x2048", "1792x2400", "2752x1536"]
                img_config_kwargs = {"aspect_ratio": aspect_ratio}
                if is_2k:
                    img_config_kwargs["image_size"] = "2K"
                    
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(**img_config_kwargs),
                        temperature=0.7
                    )
                )
                
                image_saved = False
                if hasattr(response, 'parts'):
                    for part in response.parts:
                        # Fallback checks since internal representation varies across genai versions
                        if getattr(part, 'inline_data', None) is not None or getattr(part, 'inlineData', None) is not None:
                            try:
                                import io
                                inline_obj = getattr(part, 'inline_data', getattr(part, 'inlineData', None))
                                img_bytes = getattr(inline_obj, 'data', None)
                                
                                if not img_bytes:
                                    continue
                                    
                                product_folder = pair['product_name']
                                product_dir = os.path.join(output_base_dir, product_folder)
                                os.makedirs(product_dir, exist_ok=True)
                                
                                scene_name = pair['scene_name']
                                out_file = os.path.join(product_dir, f"{scene_name}.jpg")
                                
                                # Write raw binary payload BEFORE anything else can crash!
                                with open(out_file, "wb") as bf:
                                    bf.write(img_bytes)
                                
                                print(f"Saved Instant Image: {out_file}")
                                success_count += 1
                                image_saved = True
                                break
                            except Exception as e:
                                print(f"Error saving inline image: {e}")
                                
                if not image_saved:
                    print(f"No image part found in response for {key}.")
                    error_count += 1
                    
            except Exception as e:
                print(f"Instant generation API failed for {key}: {e}")
                error_count += 1
                
        return success_count, error_count

    def check_job_status(self, batch_job_name):
        if not self.is_live:
            return "JOB_STATE_SUCCEEDED"
            
        job = self.client.batches.get(name=batch_job_name)
        # return string state
        state_str = job.state.name if hasattr(job.state, 'name') else str(job.state)
        return state_str

    def download_results(self, job_name, out_filepath):
        if not self.is_live:
            print(f"[DRY RUN] Would download results for {job_name} to {out_filepath}")
            # write an empty file just so it exists
            with open(out_filepath, 'w') as f:
                f.write("")
            return True
            
        job = self.client.batches.get(name=job_name)
        state_str = job.state.name if hasattr(job.state, 'name') else str(job.state)
        if 'SUCCEEDED' not in state_str:
            print(f"Job {job_name} is not succeeded (State: {state_str}).")
            return False
            
        result_file_name = job.dest.file_name
        print(f"Downloading {result_file_name}...")
        file_content_bytes = self.client.files.download(file=result_file_name)
        
        with open(out_filepath, 'wb') as f:
            f.write(file_content_bytes)
        print(f"Saved results to {out_filepath}")
        return True
