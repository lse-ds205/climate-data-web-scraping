-- Create documents table
-- Stores metadata and content for all scraped documents (NDCs, BTRs, LTS, etc.)

CREATE TABLE documents (
    doc_id UUID PRIMARY KEY,
    scraped_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    last_download_attempt TIMESTAMPTZ,
    download_error TEXT,
    download_attempts INTEGER,
    country TEXT REFERENCES countries(id) ON DELETE CASCADE,
    title TEXT,
    url TEXT,
    language TEXT,
    submission_date DATE,
    file_path TEXT,
    file_size DOUBLE PRECISION,
    extracted_text TEXT,
    chunks JSONB,
    document_type TEXT,  -- Type of document: NDC, BTR, LTS, Law, Policy, etc.
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- Create lookup table for standardized document types
-- This allows analysts to add new types while maintaining consistency
CREATE TABLE document_types (
    type_id SERIAL PRIMARY KEY,
    type_name TEXT UNIQUE NOT NULL,
    description TEXT,
    project TEXT,  -- Which project this type is primarily used for
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert standard document types
INSERT INTO document_types (type_name, description, project) VALUES
    ('NDC', 'Nationally Determined Contribution', 'ASCOR'),
    ('BTR', 'Biennial Transparency Report', 'ASCOR'),
    ('LTS', 'Long-Term Strategy', 'ASCOR'),
    ('Law', 'Climate-related legislation', 'ASCOR'),
    ('Policy', 'Climate policy document', 'ASCOR'),
    ('Sustainability Report', 'Corporate sustainability report', 'Banking'),
    ('Annual Report', 'Company annual report', 'Banking'),
    ('Climate Report', 'Standalone climate disclosure', 'Banking'),
    ('TCFD Report', 'TCFD-aligned climate disclosure', 'Banking'),
    ('CDP Response', 'CDP questionnaire response', 'CP'),
    ('ESG Report', 'ESG disclosure report', 'CP')
ON CONFLICT (type_name) DO NOTHING;

-- Create indexes for commonly queried columns
CREATE INDEX IF NOT EXISTS idx_documents_country ON documents(country);
CREATE INDEX IF NOT EXISTS idx_documents_submission_date ON documents(submission_date);
CREATE INDEX IF NOT EXISTS idx_documents_language ON documents(language);
CREATE INDEX IF NOT EXISTS idx_documents_processed_at ON documents(processed_at);
CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_document_types_project ON document_types(project);

-- Add table and column comments
COMMENT ON TABLE documents IS 'Stores metadata and extracted content for all scraped documents';
COMMENT ON TABLE document_types IS 'Standardized document types that can be used across projects. Analysts can add new types as needed.';
COMMENT ON COLUMN documents.doc_id IS 'Unique identifier for the document';
COMMENT ON COLUMN documents.country IS 'Country that submitted the document (references countries table)';
COMMENT ON COLUMN documents.submission_date IS 'Date when the document was submitted';
COMMENT ON COLUMN documents.chunks IS 'JSONB array of document chunks for vector search';
COMMENT ON COLUMN documents.document_type IS 'Type of document: NDC, BTR, LTS, Law, Policy, Sustainability Report, Annual Report, etc. Should match values in document_types.type_name for consistency.';
COMMENT ON COLUMN document_types.type_name IS 'Standardized name for the document type';
COMMENT ON COLUMN document_types.project IS 'Which project this type is primarily used for (ASCOR, Banking, CP, etc.)';