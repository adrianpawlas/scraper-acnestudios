"""
Local embeddings module for fashion scraper using SigLIP model.
Generates 1024-dimensional embeddings for product images.
"""

import logging
import requests
from io import BytesIO
from PIL import Image
import torch
from transformers import SiglipProcessor, SiglipModel
import os
from typing import Optional, List
import numpy as np

logger = logging.getLogger(__name__)

class SigLIPEmbeddings:
    def __init__(self, model_name: str = "google/siglip-large-patch16-384"):
        self.model_name = model_name
        self.processor = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

    def load_model(self):
        """Load the SigLIP model and processor."""
        if self.model is None:
            logger.info(f"Loading SigLIP model: {self.model_name}")
            try:
                self.processor = SiglipProcessor.from_pretrained(self.model_name)
                self.model = SiglipModel.from_pretrained(self.model_name)
                self.model.to(self.device)
                self.model.eval()
                logger.info("SigLIP model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load SigLIP model: {e}")
                raise

    def download_image(self, url: str, timeout: int = 30) -> Optional[Image.Image]:
        """Download image from URL and return PIL Image."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content)).convert('RGB')
            return image
        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")
            return None

    def get_image_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate SigLIP embedding for a single image URL.
        Returns 1024-dimensional embedding vector or None if failed.
        """
        if self.model is None:
            self.load_model()

        # Download image
        image = self.download_image(image_url)
        if image is None:
            return None

        try:
            # Process image for SigLIP (vision-language model)
            # SigLIP requires both image and text, so we use a dummy text
            dummy_text = "a photo of a fashion item"
            inputs = self.processor(
                text=[dummy_text],
                images=image,
                return_tensors="pt",
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embedding
            with torch.no_grad():
                outputs = self.model(**inputs)
                # For SigLIP, we can use the image embedding from the vision model
                embedding = outputs.vision_model_output.pooler_output

            # Convert to numpy and normalize
            embedding = embedding.cpu().numpy().flatten()
            # Normalize the embedding
            embedding = embedding / np.linalg.norm(embedding)

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding for {image_url}: {e}")
            return None

    def get_batch_embeddings(self, image_urls: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple images in batch.
        Returns list of embedding vectors (or None for failed images).
        """
        if self.model is None:
            self.load_model()

        embeddings = []
        batch_size = 8  # Process in smaller batches to avoid memory issues

        for i in range(0, len(image_urls), batch_size):
            batch_urls = image_urls[i:i + batch_size]
            batch_images = []

            # Download batch of images
            for url in batch_urls:
                image = self.download_image(url)
                batch_images.append(image)

            # Filter out None images and their corresponding URLs
            valid_images = [(img, url) for img, url in zip(batch_images, batch_urls) if img is not None]

            if not valid_images:
                embeddings.extend([None] * len(batch_urls))
                continue

            images, valid_urls = zip(*valid_images)

            try:
                # Process batch - SigLIP requires text input
                dummy_texts = ["a photo of a fashion item"] * len(images)
                inputs = self.processor(
                    text=dummy_texts,
                    images=list(images),
                    return_tensors="pt",
                    padding=True
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    batch_embeddings = outputs.vision_model_output.pooler_output

                # Convert to numpy and normalize
                batch_embeddings = batch_embeddings.cpu().numpy()
                norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
                batch_embeddings = batch_embeddings / norms

                # Create result list matching original batch size
                batch_results = []
                valid_idx = 0
                for img in batch_images:
                    if img is not None:
                        batch_results.append(batch_embeddings[valid_idx].tolist())
                        valid_idx += 1
                    else:
                        batch_results.append(None)

                embeddings.extend(batch_results)

            except Exception as e:
                logger.error(f"Failed to process batch: {e}")
                embeddings.extend([None] * len(batch_urls))

        return embeddings

# Global instance for reuse
_embeddings_instance = None

def get_image_embedding(image_url: str) -> Optional[List[float]]:
    """Get embedding for a single image URL."""
    global _embeddings_instance
    if _embeddings_instance is None:
        model_name = os.getenv("EMBEDDINGS_MODEL", "google/siglip-large-patch16-384")
        _embeddings_instance = SigLIPEmbeddings(model_name)
    return _embeddings_instance.get_image_embedding(image_url)

def get_batch_embeddings(image_urls: List[str]) -> List[Optional[List[float]]]:
    """Get embeddings for multiple image URLs."""
    global _embeddings_instance
    if _embeddings_instance is None:
        model_name = os.getenv("EMBEDDINGS_MODEL", "google/siglip-large-patch16-384")
        _embeddings_instance = SigLIPEmbeddings(model_name)
    return _embeddings_instance.get_batch_embeddings(image_urls)

if __name__ == "__main__":
    # Test the embeddings
    test_url = 'https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=400'

    print("Testing SigLIP embeddings...")
    embedding = get_image_embedding(test_url)

    if embedding:
        print(f"✅ Success! Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        print(f"Sample embedding value: {embedding[0]:.3f}")
    else:
        print("❌ Failed to generate embedding")
