# Gemini Image Batch Gen Tool

A desktop tool (Python + Tkinter) for generating Amazon-ready images at scale using Gemini Image models via Batch API.

## Folder Structure

- `Target Scene/`: Target scene images (e.g. 1.jpg, 2.jpg)
- `Jewelry Reference/`: Subfolders for different products containing reference images.
- `outputs/`: Output folder where the generated images will be saved.
- `data/`: Contains `jobs.json` to store job tracking.
- `config/`: Contains configuration files like `prompts.json`.
- `src/`: Python source code.
