import os
import hashlib
from fastapi import FastAPI, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from image_processor import resize_image, ResizeMode
from s3_operations import S3Config, get_s3_client, download_image_from_s3

# Configuration class
class ImageProcessingConfig(BaseModel):
    max_file_size: int = 20 * 1024 * 1024  # 20MB
    allowed_formats: list = ["jpg", "jpeg", "png", "webp"]

# FastAPI app
app = FastAPI()

@app.get("/favicon.ico", status_code=status.HTTP_204_NO_CONTENT)
async def favicon():
    return Response(content=b"")

@app.get("/resize/{image_key}")
async def resize_image_endpoint(
    image_key: str,
    p: Optional[int] = Query(None, ge=1, le=1000, description="Percentage for proportional scaling"),
    w: Optional[int] = Query(None, gt=0, description="Target width"),
    h: Optional[int] = Query(None, gt=0, description="Target height"),
    m: Optional[ResizeMode] = Query(ResizeMode.LFIT, description="Resize mode")
):
    s3_config = S3Config()
    s3_client = get_s3_client()

    # Download image from S3
    image_data = download_image_from_s3(s3_client, s3_config.bucket_name, image_key)

    # Prepare resize parameters
    resize_params = {
        "p": p,
        "w": w,
        "h": h,
        "m": m
    }
    resize_params = {k: v for k, v in resize_params.items() if v is not None}

    # Resize image
    resized_image_data = resize_image(image_data, resize_params)

    # Determine content type based on file extension
    _, file_extension = os.path.splitext(image_key)
    content_type = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp'
    }.get(file_extension.lower(), 'application/octet-stream')

    # Generate ETag
    etag = hashlib.md5(resized_image_data).hexdigest()

    # Set cache control (1 hour)
    cache_control = "public, max-age=3600"

    # Return the resized image data with caching headers
    return Response(
        content=resized_image_data,
        media_type=content_type,
        headers={
            "Cache-Control": cache_control,
            "ETag": etag
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
