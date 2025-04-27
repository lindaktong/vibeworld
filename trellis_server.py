#!/usr/bin/env python
"""Trellis API server for generating 3D models from text prompts."""

import os
from pathlib import Path
import tempfile
import shutil
import uuid
import structlog

# Configuration for the Trellis backends.
os.environ["ATTN_BACKEND"] = "flash-attn"  # Can be 'flash-attn' or 'xformers'.
os.environ["SPCONV_ALGO"] = "native"  # Can be 'native' or 'auto', default is 'auto'.
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import imageio
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

# Import Trellis modules - adjust these paths as needed based on your setup
from third_party.TRELLIS.trellis.pipelines import (
    TrellisImageTo3DPipeline,
    TrellisTextTo3DPipeline,
)
from third_party.TRELLIS.trellis.utils import postprocessing_utils, render_utils

# Initialize logger
logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Trellis API", description="API for generating 3D models from text or images")

# Initialize pipelines
text_pipeline = None
image_pipeline = None

# Define output directory
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Request model for text input
class TextPromptRequest(BaseModel):
    prompt: str
    seed: int = 1
    save_additional_files: bool = False

# Load text pipeline
def load_text_pipeline():
    global text_pipeline
    if text_pipeline is None:
        logger.info("Loading text-to-3D pipeline...")
        text_pipeline = TrellisTextTo3DPipeline.from_pretrained("JeffreyXiang/TRELLIS-text-xlarge")
        text_pipeline.cuda()
        logger.info("Text-to-3D pipeline loaded successfully")

# Load image pipeline
def load_image_pipeline():
    global image_pipeline
    if image_pipeline is None:
        logger.info("Loading image-to-3D pipeline...")
        image_pipeline = TrellisImageTo3DPipeline.from_pretrained("JeffreyXiang/TRELLIS-image-large")
        image_pipeline.cuda()
        logger.info("Image-to-3D pipeline loaded successfully")

# Define endpoints
@app.post("/generate/text")
async def generate_from_text(request: TextPromptRequest):
    """Generate a 3D model from text prompt."""
    # Load the pipeline on demand
    load_text_pipeline()
    
    if text_pipeline is None:
        raise HTTPException(status_code=503, detail="Failed to load text-to-3D pipeline")
    
    # Create a unique ID for this request
    request_id = str(uuid.uuid4())
    output_path = OUTPUT_DIR / request_id
    output_path.mkdir(exist_ok=True)
    
    try:
        logger.info("Processing text prompt", 
                   text_prompt=request.prompt, 
                   seed=request.seed, 
                   request_id=request_id)
        
        # Run the pipeline
        outputs = text_pipeline.run(
            request.prompt,
            seed=request.seed,
        )
        
        # Process outputs
        glb_path = output_path / "model.glb"
        
        # Save GLB file
        glb = postprocessing_utils.to_glb(
            outputs["gaussian"][0],
            outputs["mesh"][0],
            simplify=0.95,
            texture_size=1024,
        )
        glb.export(glb_path)
        
        # Optionally save additional files
        if request.save_additional_files:
            # Render and save videos
            video = render_utils.render_video(outputs["gaussian"][0])["color"]
            imageio.mimsave(output_path / "gaussian.mp4", video, fps=30)
            
            video = render_utils.render_video(outputs["radiance_field"][0])["color"]
            imageio.mimsave(output_path / "radiance_field.mp4", video, fps=30)
            
            video = render_utils.render_video(outputs["mesh"][0])["normal"]
            imageio.mimsave(output_path / "mesh.mp4", video, fps=30)
            
            # Save PLY file
            outputs["gaussian"][0].save_ply(output_path / "model.ply")
        
        logger.info("Processing complete", request_id=request_id)
        
        # Return the GLB file
        return FileResponse(
            path=glb_path,
            filename="model.glb",
            media_type="model/gltf-binary"
        )
        
    except Exception as e:
        logger.error("Error processing request", error=str(e), request_id=request_id)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/generate/image")
async def generate_from_image(
    file: UploadFile = File(...),
    seed: int = Form(1),
    save_additional_files: bool = Form(False)
):
    """Generate a 3D model from an image."""
    # Load the pipeline on demand
    load_image_pipeline()
    
    if image_pipeline is None:
        raise HTTPException(status_code=503, detail="Failed to load image-to-3D pipeline")
    
    # Create a unique ID for this request
    request_id = str(uuid.uuid4())
    output_path = OUTPUT_DIR / request_id
    output_path.mkdir(exist_ok=True)
    
    # Save uploaded image
    temp_file = output_path / file.filename
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        logger.info("Processing image prompt", 
                   image_file=file.filename, 
                   seed=seed, 
                   request_id=request_id)
        
        # Load image
        image = Image.open(temp_file)
        
        # Run the pipeline
        outputs = image_pipeline.run(image, seed=seed)
        
        # Process outputs
        glb_path = output_path / "model.glb"
        
        # Save GLB file
        glb = postprocessing_utils.to_glb(
            outputs["gaussian"][0],
            outputs["mesh"][0],
            simplify=0.95,
            texture_size=1024,
        )
        glb.export(glb_path)
        
        # Optionally save additional files
        if save_additional_files:
            # Render and save videos
            video = render_utils.render_video(outputs["gaussian"][0])["color"]
            imageio.mimsave(output_path / "gaussian.mp4", video, fps=30)
            
            video = render_utils.render_video(outputs["radiance_field"][0])["color"]
            imageio.mimsave(output_path / "radiance_field.mp4", video, fps=30)
            
            video = render_utils.render_video(outputs["mesh"][0])["normal"]
            imageio.mimsave(output_path / "mesh.mp4", video, fps=30)
            
            # Save PLY file
            outputs["gaussian"][0].save_ply(output_path / "model.ply")
        
        logger.info("Processing complete", request_id=request_id)
        
        # Return the GLB file
        return FileResponse(
            path=glb_path,
            filename="model.glb",
            media_type="model/gltf-binary"
        )
        
    except Exception as e:
        logger.error("Error processing request", error=str(e), request_id=request_id)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Check if the service is healthy."""
    return {
        "status": "healthy",
        "text_pipeline_loaded": text_pipeline is not None,
        "image_pipeline_loaded": image_pipeline is not None
    }

# Run the server
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the Trellis API server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--preload-models", action="store_true", help="Preload models at startup")
    
    args = parser.parse_args()
    
    # Optionally preload models
    if args.preload_models:
        load_text_pipeline()
        # load_image_pipeline()
    
    print(f"Starting Trellis API server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
