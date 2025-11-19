import os
import logging
import re
from typing import List, Dict, Any
from unstructured.partition.pdf import partition_pdf
from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)


def merge_short_chunks(elements: List[Dict[str, Any]], min_length: int = 20) -> List[Dict[str, Any]]:
    """
    Merge chunks that are shorter than the minimum length threshold.
    
    Args:
        elements: List of document elements
        min_length: Minimum length threshold for a chunk
        
    Returns:
        List of merged chunks
    """
    if not elements:
        return elements
    
    merged_elements = []
    current_chunk = None
    
    for element in elements:
        text = element.get('text', '')
        
        if current_chunk is None:
            current_chunk = element
        elif len(current_chunk.get('text', '')) < min_length:
            # Merge with current chunk
            current_chunk['text'] = current_chunk.get('text', '') + ' ' + text
            
            # Merge metadata where appropriate
            if 'metadata' in element and 'metadata' in current_chunk:
                # Merge element types
                if 'element_types' in element['metadata'] and 'element_types' in current_chunk['metadata']:
                    for et in element['metadata']['element_types']:
                        if et not in current_chunk['metadata']['element_types']:
                            current_chunk['metadata']['element_types'].append(et)
                
                # Merge paragraph numbers if they exist
                if 'paragraph_numbers' in element['metadata'] and 'paragraph_numbers' in current_chunk['metadata']:
                    for pn in element['metadata']['paragraph_numbers']:
                        if pn not in current_chunk['metadata']['paragraph_numbers']:
                            current_chunk['metadata']['paragraph_numbers'].append(pn)
                
                # Merge paragraph IDs if they exist
                if 'paragraph_ids' in element['metadata'] and 'paragraph_ids' in current_chunk['metadata']:
                    for pid in element['metadata']['paragraph_ids']:
                        if pid not in current_chunk['metadata']['paragraph_ids']:
                            current_chunk['metadata']['paragraph_ids'].append(pid)
        else:
            # Current chunk is long enough, add to results
            merged_elements.append(current_chunk)
            current_chunk = element
    
    # Don't forget the last chunk
    if current_chunk is not None:
        merged_elements.append(current_chunk)
    
    return merged_elements
            
def split_long_chunks(elements: List[Dict[str, Any]], max_length: int = 1000) -> List[Dict[str, Any]]:
    """
    Split chunks that are longer than the maximum length threshold.
    
    Args:
        elements: List of document elements
        max_length: Maximum length threshold for a chunk
        
    Returns:
        List of split chunks
    """
    if not elements:
        return elements
        
    result = []
    chunk_id_counter = 0
    
    for element in elements:
        text = element.get('text', '')
        
        # If the element is short enough, keep it as is
        if len(text) <= max_length:
            result.append(element)
            continue
        
        # If the element has sentences, use those for splitting
        sentences = element.get('sentences', [])
        if not sentences and text:
            # If no sentences are provided but we have text, tokenize it
            sentences = sent_tokenize(text)
        
        if not sentences:
            # If still no sentences, just add the element as is
            result.append(element)
            continue
        
        # Split into multiple chunks
        current_chunk_text = ""
        current_sentences = []
        
        for sentence in sentences:
            # Check if adding this sentence would exceed the max length
            if len(current_chunk_text) + len(sentence) + 1 > max_length and current_chunk_text:
                # Create a new chunk with current content
                new_chunk = {
                    "id": f"chunk_{chunk_id_counter}",
                    "text": current_chunk_text.strip(),
                    "sentences": current_sentences,
                    "metadata": element.get('metadata', {}).copy()  # Copy metadata
                }
                result.append(new_chunk)
                chunk_id_counter += 1
                
                # Reset for next chunk
                current_chunk_text = sentence
                current_sentences = [sentence]
            else:
                # Add to current chunk
                if current_chunk_text:
                    current_chunk_text += " " + sentence
                else:
                    current_chunk_text = sentence
                current_sentences.append(sentence)
        
        # Add the last chunk if there's content
        if current_chunk_text:
            new_chunk = {
                "id": f"chunk_{chunk_id_counter}",
                "text": current_chunk_text.strip(),
                "sentences": current_sentences,
                "metadata": element.get('metadata', {}).copy()
            }
            result.append(new_chunk)
            chunk_id_counter += 1
    
    return result
    
def remove_gibberish(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove gibberish text from chunks.
    
    This function removes common OCR artifacts and formatting issues.
    
    Args:
        elements: List of document elements
        
    Returns:
        List of cleaned chunks
    """
    if not elements:
        return elements
        
    cleaned_elements = []
    
    for element in elements:
        if 'text' not in element:
            continue
        
        text = element['text']
        
        # Check for severe corruption that should cause chunk rejection
        if is_severely_corrupted(text):
            # Safely truncate text for logging, handling non-ASCII characters
            safe_text = text[:50].encode('ascii', 'replace').decode('ascii')
            logger.warning(f"Rejecting severely corrupted chunk: {safe_text}...")
            continue
        
        # Clean up the text
        text = clean_corrupted_text(text)
        
        # Replace multiple spaces with a single space
        text = ' '.join(text.split())
        
        # Remove common OCR artifacts
        text = text.replace('•', '').replace('|', '').replace('¦', '')
        
        # Remove excessive punctuation
        for char in '.,;:!?':
            text = text.replace(f'{char}{char}{char}', f'{char}')
            text = text.replace(f'{char} {char}', f'{char}')
        
        # Only include elements that have meaningful content
        if len(text.strip()) > 5:  # Arbitrary threshold to filter out tiny fragments
            element['text'] = text.strip()
            cleaned_elements.append(element)
    
    return cleaned_elements

def extract_country_from_filename(pdf_path: str) -> str:
    """
    Extract country name from PDF filename.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Country name or 'Unknown'
    """
    filename = os.path.basename(pdf_path)
    filename_lower = filename.lower()
    
    # Common country name patterns in filenames
    country_patterns = {
        'afghanistan': 'Afghanistan',
        'albania': 'Albania',
        'algeria': 'Algeria',
        'argentina': 'Argentina',
        'australia': 'Australia',
        'austria': 'Austria',
        'bangladesh': 'Bangladesh',
        'belgium': 'Belgium',
        'brazil': 'Brazil',
        'canada': 'Canada',
        'chile': 'Chile',
        'china': 'China',
        'colombia': 'Colombia',
        'costa_rica': 'Costa Rica',
        'egypt': 'Egypt',
        'ethiopia': 'Ethiopia',
        'france': 'France',
        'germany': 'Germany',
        'ghana': 'Ghana',
        'india': 'India',
        'indonesia': 'Indonesia',
        'iran': 'Iran',
        'iraq': 'Iraq',
        'italy': 'Italy',
        'japan': 'Japan',
        'kenya': 'Kenya',
        'madagascar': 'Madagascar',
        'malaysia': 'Malaysia',
        'mexico': 'Mexico',
        'morocco': 'Morocco',
        'nigeria': 'Nigeria',
        'pakistan': 'Pakistan',
        'peru': 'Peru',
        'philippines': 'Philippines',
        'poland': 'Poland',
        'russia': 'Russia',
        'saudi_arabia': 'Saudi Arabia',
        'singapore': 'Singapore',
        'south_africa': 'South Africa',
        'south_korea': 'South Korea',
        'spain': 'Spain',
        'thailand': 'Thailand',
        'turkey': 'Turkey',
        'ukraine': 'Ukraine',
        'united_kingdom': 'United Kingdom',
        'uk': 'United Kingdom',
        'united_states': 'United States',
        'usa': 'United States',
        'vietnam': 'Vietnam',
    }
    
    # Try to find country in filename
    for pattern, country_name in country_patterns.items():
        if pattern in filename_lower:
            return country_name
    
    # If no pattern found, try to extract from first part of filename
    # Many files are named like "country_language_date.pdf"
    filename_parts = filename.replace('.pdf', '').split('_')
    if filename_parts:
        first_part = filename_parts[0].lower()
        # Try exact match first
        for pattern, country_name in country_patterns.items():
            if first_part == pattern:
                return country_name
        
        # If still no match, capitalize the first part as a fallback
        if len(first_part) > 2:
            return first_part.replace('_', ' ').title()

    return 'Unknown'

def has_character_corruption(text: str) -> bool:
    """
    Detect if text contains character encoding corruption typical of PDF extraction issues.
    Improved to reduce false positives with legitimate formatted text.
    
    Args:
        text: Text to check for corruption
        
    Returns:
        True if corruption is detected
    """
    if not text:
        return False
    
    # Check for CID (Character ID) corruption - this is the main indicator
    cid_pattern = r'\(cid:\d+\)'
    cid_matches = len(re.findall(cid_pattern, text))
    
    # If more than 10% of the text appears to be CID references, it's corrupted
    if cid_matches > 0 and (cid_matches * 10) > len(text.split()):
        return True
    
    return False

def retry_with_ocr(pdf_path: str, languages_list: list) -> List[Dict[str, Any]]:
    """
    Retry PDF extraction using OCR when standard extraction fails or produces corruption.
    
    Args:
        pdf_path: Path to PDF file
        languages_list: List of languages for OCR
        
    Returns:
        List of extracted elements using OCR
    """
    try:
        logger.info(f"Attempting OCR extraction for {pdf_path}")
        filename = os.path.basename(pdf_path)
        country = extract_country_from_filename(pdf_path)
        
        # Force OCR extraction
        elements = partition_pdf(
            filename=pdf_path, 
            strategy="ocr_only",
            extract_images_in_pdf=False,
            infer_table_structure=True,
            languages=languages_list        )
        
        processed_elements = []
        
        # Track page-relative paragraph numbering for OCR
        current_page = 0
        page_paragraph_count = 0
        
        for i, element in enumerate(elements):
            text = str(element).strip() if element else ""
            
            # Still check for corruption in OCR results
            if has_character_corruption(text):
                logger.debug(f"OCR element {i} still has corruption, skipping")
                continue
            
            if len(text) < 10:
                continue
                
            # Extract metadata
            metadata = {
                'element_index': i,
                'element_type': type(element).__name__,
                'page_number': 0,
                'paragraph_number': None,
                'extraction_strategy': 'ocr_fallback',
                'filename': filename,
                'country': country,
                'document_title': f"{country} NDC"
            }
            
            # Handle metadata extraction from unstructured elements
            try:
                if hasattr(element, 'metadata') and element.metadata:
                    element_metadata = element.metadata
                    
                    if hasattr(element_metadata, 'page_number'):
                        metadata['page_number'] = element_metadata.page_number
                    elif hasattr(element_metadata, 'to_dict'):
                        meta_dict = element_metadata.to_dict()
                        metadata['page_number'] = meta_dict.get('page_number', 0)
                        
                        # Try to extract paragraph number
                        for key in ['paragraph', 'para', 'element_id', 'order']:
                            if key in meta_dict and isinstance(meta_dict[key], (int, str)):
                                try:
                                    metadata['paragraph_number'] = int(meta_dict[key])
                                    break
                                except (ValueError, TypeError):
                                    continue
                        
            except Exception as meta_error:
                logger.warning(f"Error extracting OCR metadata from element {i}: {meta_error}")
            
            # Check if we moved to a new page and reset paragraph counter
            if metadata['page_number'] != current_page:
                current_page = metadata['page_number']
                page_paragraph_count = 1
            else:
                page_paragraph_count += 1
            
            # If no paragraph number found, use page-relative numbering
            if metadata['paragraph_number'] is None:
                metadata['paragraph_number'] = page_paragraph_count
            
            processed_elements.append({
                'text': text,
                'metadata': metadata
            })

        logger.info(f"OCR extraction completed with {len(processed_elements)} elements")
        return processed_elements
        
    except Exception as e:
        logger.error(f"OCR extraction failed for {pdf_path}: {e}")
        return []
    
def is_severely_corrupted(text: str) -> bool:
    """
    Check if text is so corrupted it should be completely rejected.
    Updated to be less aggressive with legitimate formatted text.
    
    Args:
        text: Text to check
        
    Returns:
        True if text should be rejected
    """
    if not text or len(text) < 10:
        return True
    
    # Count CID references - this is the primary corruption indicator
    cid_count = len(re.findall(r'\(cid:\d+\)', text))
    word_count = len(text.split())
    
    # If more than 30% of "words" are CID references, reject (was 50%)
    if word_count > 0 and (cid_count / word_count) > 0.3:
        return True
    
    # Check for strings that are mostly non-alphabetic, but be more lenient
    # Include accented characters, common punctuation, and major script families
    # This pattern includes: Latin, Cyrillic, Greek, Arabic, Chinese, Japanese, Korean, etc.
    legit_char_pattern = r'[a-zA-Z0-9àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß\u0400-\u04FF\u0500-\u052F\u2DE0-\u2DFF\uA640-\uA69F\u1C80-\u1C88\u1D2B\u1D78\uA69F\u1C80-\u1C88\u1D2B\u1D78\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\u4E00-\u9FFF\u3400-\u4DBF\u20000-\u2A6DF\u2A700-\u2B73F\u2B740-\u2B81F\u2B820-\u2CEAF\uF900-\uFAFF\u2F800-\u2FA1F\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\u0370-\u03FF\u1F00-\u1FFF\s.,;:!?()\-\'"]'
    legit_chars = len(re.findall(legit_char_pattern, text))
    
    # Only apply this check if the text is mostly ASCII/Latin characters
    # For non-Latin scripts, we'll be more lenient
    ascii_ratio = len(re.findall(r'[a-zA-Z0-9\s.,;:!?()\-\'"]', text)) / len(text) if len(text) > 0 else 0
    
    if len(text) > 20:
        if ascii_ratio > 0.8:  # Mostly ASCII/Latin text
            if (legit_chars / len(text)) < 0.4:
                return True
        else:  # Non-Latin script - be more lenient
            if (legit_chars / len(text)) < 0.2:
                return True
    
    # Check for excessive Unicode replacement characters
    if text.count('�') + text.count('\ufffd') > 5:
        return True
    
    return False

def clean_corrupted_text(text: str) -> str:
    """
    Clean text with character corruption issues.
    Updated to preserve legitimate formatting.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return text
    
    # Remove CID references
    text = re.sub(r'\(cid:\d+\)', ' ', text)
    
    # Remove excessive repeated characters, but preserve table of contents dots
    # Only replace if it's not a table of contents pattern
    if not re.match(r'^[^.]*\.{10,}[^.]*$', text):  # Not a table of contents
        text = re.sub(r'(.)\1{10,}', r'\1\1\1', text)  # Reduce excessive repetition
    
    # Remove Unicode replacement characters
    text = text.replace('�', ' ').replace('\ufffd', ' ')
    
    # Remove problematic control characters but preserve normal spaces and newlines
    text = re.sub(r'[\x00-\x08\x0E-\x1F\x7F]', ' ', text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()