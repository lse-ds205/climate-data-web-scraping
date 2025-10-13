# Contributing to Climate Policy Extractor

This guide will help you set up your development environment to work on the Climate Policy Extractor project.

> **Note**: Before starting development, please check [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for known bugs and planned improvements. This will help you avoid duplicate work and understand current limitations.

## 1. Install Python dependencies

First, clone the repository and navigate to the project directory:

```bash
# Calling it ds205-ps2 (or the like) will make it easier for you
git clone https://github.com/Nayrbnat/rag-fact-sheets-4.git custom-folder-name
cd custom-folder-name
```

Create a virtual environment using Python's built-in `venv` module:

```bash
# Create a virtual environment. 
# This time, let's just simply call it venv to avoid confusion
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

Verify that you're using the Python interpreter from the virtual environment:

```bash
which python  # On macOS/Linux
where python  # On Windows
```

This should output a path that includes your virtual environment directory. **If it doesn't, contact instructors via Slack. Something is wrong.**

Install the required dependencies:

```bash
pip install -r requirements/requirements.txt
```

**Importantly**, install the `NLTK` downloads:

## 1.1 Install Tesseract OCR

The project uses Optical Character Recognition (OCR) capabilities through the `unstructured` library for PDF text extraction. You need to install Tesseract OCR:

### On Windows:
1. Download the Tesseract installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer and follow the instructions
3. Add Tesseract to your PATH environment variable (the installer should offer this option)
4. Verify installation: `tesseract --version`

### On macOS:
```bash
brew install tesseract
```

### On Linux:
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install libtesseract-dev
```

Verify installation:
```bash
tesseract --version
```

## 2. Set up the Database

The project uses PostgreSQL with the pgvector extension for vector search capabilities. You have two options for setting up the database:

### Option A: Using Docker Compose (Recommended)

#### 2.1 Install Docker

If you don't have Docker installed, you can download it from the [Docker website](https://www.docker.com/products/docker-desktop/).

For macOS users, you can also install it using Homebrew:

```bash
brew install --cask docker
```

#### 2.2 Using Docker Compose

Run the containers using Docker Compose:

```bash
docker-compose up -d
```

To stop the containers:

```bash
docker-compose down
```

To view logs:

```bash
docker-compose logs
```

This method automatically sets up all required services defined in the `docker-compose.yml` file.

### Option B: Using Docker Manually

#### 2.3 Run PostgreSQL with pgvector

Start a PostgreSQL container with the pgvector extension:

```bash
docker run -d \
    --name group-4-postgres \
    -e POSTGRES_USER=climate \
    -e POSTGRES_PASSWORD=climate \
    -e POSTGRES_DB=climate \
    -p 5432:5432 \
    -v postgres_data:/var/lib/postgresql/data \
    pgvector/pgvector:0.7.1-pg16
```

Verify that the container is running:

```bash
docker ps -a
```

The STATUS of the container should be "Up".

### 2.4 Setting up the Database
```bash
python manual/setup_database.py 
```

### 2.5 Installing the Embedding Models

```bash
python manual/install_models.py 
```

## 3. Create .env file
Create a `.env` file in the project root directory with the following content:

```plaintext
# Database settings
DATABASE_URL=postgresql://climate:climate@localhost:5432/climate

# Embedding model settings
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
EMBEDDING_DIMENSION=768

# File storage settings
DOWNLOAD_DIR=data/pdfs
PROCESSED_DIR=data/processed

# OpenAI API settings
AI_BASE_URL=[Your OpenAI API base URL, e.g., https://api.openai.com/v1]
AI_API_KEY=[Your OpenAI API key]

LLM_MODEL=[Your LLM model, e.g., gpt-3.5-turbo]
LLM_TEMPERATURE=0.2 # Decrease this for more deterministic responses
LLM_MAX_TOKENS=4096 # Increase this to accommodate longer responses
```

## 4. Running the Spider

To run the NDC spider and collect documents:

```bash
# Make sure you're in the project root directory
cd climate-policy-extractor
# Run the spider
scrapy crawl ndc_spider
```


## 5. Checking Cyclomatic Complexity of the database
To analyze the cyclomatic complexity of the codebase, you can use the `cyclomatic_complexity` module. This will help you identify complex functions that may need refactoring.
To run the cyclomatic complexity analysis, execute the following command:

```bash
python cyclomatic_complexity/analysis.py entrypoints
```

To run the analysis on the `entrypoints` folder for example, use:

```bash
python cyclomatic_complexity/analysis.py entrypoints
```
