-- Migration to add unique index on (source, external_id)
-- Run this if your table doesn't already have the unique constraint

-- Create unique index on (source, external_id) if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'products'
        AND indexname = 'idx_products_source_external_id'
    ) THEN
        CREATE UNIQUE INDEX idx_products_source_external_id
        ON products (source, external_id);
    END IF;
END $$;

-- Add embedding column if it doesn't exist (for SigLIP embeddings)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products'
        AND column_name = 'embedding'
    ) THEN
        ALTER TABLE products ADD COLUMN embedding VECTOR(1024);
    END IF;
END $$;

-- Create vector index for embeddings if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'products'
        AND indexname = 'idx_products_embedding'
    ) THEN
        CREATE INDEX idx_products_embedding
        ON products USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    END IF;
END $$;
