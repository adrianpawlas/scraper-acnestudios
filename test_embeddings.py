#!/usr/bin/env python3

import os
os.environ['USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
os.environ['EMBEDDINGS_MODEL'] = 'google/siglip-large-patch16-384'

from scraper.embeddings import get_image_embedding

def test_embeddings():
    print("Testing SigLIP embeddings...")

    # Test with a simple fashion image
    test_url = 'https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=400'

    embedding = get_image_embedding(test_url)

    if embedding:
        print("SUCCESS!")
        print(f"   Embedding dimension: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        print(".3f")
    else:
        print("FAILED to generate embedding")

if __name__ == "__main__":
    test_embeddings()
