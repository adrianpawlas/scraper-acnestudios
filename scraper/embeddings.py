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
    def __init__(self, model_name: str = "google/siglip-base-patch16-384"):
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
            # Process image with SigLIP (requires both image and text inputs)
            inputs = self.processor(images=image, text=[""], return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embedding
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use image embeddings (768-dim for SigLIP base)
                embedding = outputs.image_embeds.squeeze()

            # Convert to numpy
            embedding = embedding.cpu().numpy().flatten()

            # Verify dimensions (should be exactly 768 for base model)
            if len(embedding) != 768:
                logger.error(f"Embedding dimension mismatch: got {len(embedding)}, expected 768")
                return None

            # Convert to list and validate values
            embedding_list = embedding.tolist()

            # Check for invalid values that can't be JSON serialized
            if any(not isinstance(x, (int, float)) or str(x).lower() in ('nan', 'inf', '-inf') for x in embedding_list):
                logger.error("Embedding contains invalid values (NaN/inf)")
                return None

            return embedding_list

        except Exception as e:
            logger.error(f"Failed to generate embedding for {image_url}: {e}")
            return None

    def get_text_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate SigLIP text embedding using the same model as image embeddings.
        Returns 768-dimensional embedding vector or None if failed.
        Uses the text encoder so embeddings are in the same space as image_embeds.
        """
        if not text or not str(text).strip():
            return None

        if self.model is None:
            self.load_model()

        try:
            # SigLIP processor tokenizes text; max_length=64 is required for SigLIP
            inputs = self.processor(
                text=[str(text)[:2000]],  # Truncate to avoid token limit
                padding="max_length",
                max_length=64,
                truncation=True,
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                text_out = self.model.get_text_features(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask")
                )
                # Handle both tensor and BaseModelOutputWithPooling
                if hasattr(text_out, 'pooler_output') and text_out.pooler_output is not None:
                    text_embeds = text_out.pooler_output
                elif hasattr(text_out, 'last_hidden_state'):
                    text_embeds = text_out.last_hidden_state[:, 0, :]
                else:
                    text_embeds = text_out

            embedding = text_embeds.squeeze().cpu().numpy().flatten()

            if len(embedding) != 768:
                logger.error(f"Text embedding dimension mismatch: got {len(embedding)}, expected 768")
                return None

            embedding_list = embedding.tolist()
            if any(not isinstance(x, (int, float)) or str(x).lower() in ('nan', 'inf', '-inf') for x in embedding_list):
                logger.error("Text embedding contains invalid values")
                return None

            return embedding_list

        except Exception as e:
            logger.error(f"Failed to generate text embedding: {e}")
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
                # Process batch with SigLIP
                empty_texts = [""] * len(images)
                inputs = self.processor(
                    images=list(images),
                    text=empty_texts,
                    return_tensors="pt"
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    batch_embeddings = outputs.image_embeds.squeeze()

                # Convert to numpy
                batch_embeddings = batch_embeddings.cpu().numpy()

                # Verify dimensions
                if batch_embeddings.shape[-1] != 768:
                    logger.error(f"Batch embedding dimension mismatch: got {batch_embeddings.shape[-1]}, expected 768")
                    return [None] * len(batch_urls)

                # Create result list matching original batch size
                batch_results = []
                valid_idx = 0
                for img in batch_images:
                    if img is not None:
                        embedding_list = batch_embeddings[valid_idx].tolist()
                        # Validate embedding values
                        if any(not isinstance(x, (int, float)) or str(x).lower() in ('nan', 'inf', '-inf') for x in embedding_list):
                            logger.error(f"Batch embedding {valid_idx} contains invalid values")
                            batch_results.append(None)
                        else:
                            batch_results.append(embedding_list)
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
    # Always check if model name has changed (in case env var was updated)
    expected_model = os.getenv("EMBEDDINGS_MODEL", "google/siglip-base-patch16-384")
    if _embeddings_instance is None or _embeddings_instance.model_name != expected_model:
        _embeddings_instance = SigLIPEmbeddings(expected_model)
    return _embeddings_instance.get_image_embedding(image_url)

def get_text_embedding(text: str) -> Optional[List[float]]:
    """Get text embedding for product info using same model as image embeddings."""
    global _embeddings_instance
    expected_model = os.getenv("EMBEDDINGS_MODEL", "google/siglip-base-patch16-384")
    if _embeddings_instance is None or _embeddings_instance.model_name != expected_model:
        _embeddings_instance = SigLIPEmbeddings(expected_model)
    return _embeddings_instance.get_text_embedding(text)


def get_batch_embeddings(image_urls: List[str]) -> List[Optional[List[float]]]:
    """Get embeddings for multiple image URLs."""
    global _embeddings_instance
    # Always check if model name has changed (in case env var was updated)
    expected_model = os.getenv("EMBEDDINGS_MODEL", "google/siglip-base-patch16-384")
    if _embeddings_instance is None or _embeddings_instance.model_name != expected_model:
        _embeddings_instance = SigLIPEmbeddings(expected_model)
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
