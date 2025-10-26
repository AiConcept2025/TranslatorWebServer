"""
Encoding utilities for handling various text encoding issues.
"""

import re
from typing import Optional, Union, Any
import logging

logger = logging.getLogger("translator.encoding_utils")


def safe_decode_text(text: Union[str, bytes], source_encoding: Optional[str] = None) -> str:
    """
    Safely decode text from various encodings to UTF-8.
    
    Args:
        text: Text to decode (str or bytes)
        source_encoding: Hint about the source encoding
        
    Returns:
        Properly decoded UTF-8 string
    """
    if isinstance(text, str):
        # Already a string, but might have encoding issues
        return fix_string_encoding(text)
    
    if isinstance(text, bytes):
        # Try to decode bytes
        return decode_bytes_safely(text, source_encoding)
    
    # Other types, convert to string
    return str(text)


def decode_bytes_safely(data: bytes, hint_encoding: Optional[str] = None) -> str:
    """
    Safely decode bytes using multiple encoding attempts.
    
    Args:
        data: Bytes to decode
        hint_encoding: Optional encoding hint
        
    Returns:
        Decoded string
    """
    if not data:
        return ""
    
    # Build encoding list with hint first if provided
    encodings = []
    if hint_encoding:
        encodings.append(hint_encoding)
    
    # Add common encodings
    encodings.extend(['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1'])
    
    # Remove duplicates while preserving order
    seen = set()
    encodings = [enc for enc in encodings if not (enc in seen or seen.add(enc))]
    
    for encoding in encodings:
        try:
            decoded = data.decode(encoding)
            
            # For UTF-8, check for replacement characters
            if encoding == 'utf-8' and '\ufffd' in decoded:
                continue
                
            logger.debug(f"Successfully decoded using {encoding}")
            return decoded
            
        except UnicodeDecodeError as e:
            logger.debug(f"Failed to decode with {encoding}: {e}")
            continue
    
    # If all fail, use utf-8 with error replacement
    result = data.decode('utf-8', errors='replace')
    logger.warning(f"Used replacement characters for {len(data)} bytes")
    return result


def fix_string_encoding(text: str) -> str:
    """
    Fix common encoding issues in strings.
    
    Args:
        text: String that may have encoding issues
        
    Returns:
        Fixed string
    """
    if not text:
        return text
    
    # Common Windows-1252 characters that appear in UTF-8 contexts
    replacements = {
        '\u0092': "'",      # Right single quotation mark -> apostrophe
        '\u0093': '"',      # Left double quotation mark
        '\u0094': '"',      # Right double quotation mark
        '\u0096': '–',      # En dash
        '\u0097': '—',      # Em dash
        '\u0091': "'",      # Left single quotation mark -> apostrophe
        '\u0085': '...',    # Next line -> ellipsis
        '\u0080': '€',      # Euro sign
        '\ufffd': '?'       # Replacement character -> question mark
    }
    
    fixed_text = text
    for bad_char, good_char in replacements.items():
        if bad_char in fixed_text:
            fixed_text = fixed_text.replace(bad_char, good_char)
            logger.debug(f"Replaced '{bad_char}' with '{good_char}'")
    
    return fixed_text


def validate_utf8_text(text: str) -> tuple[bool, Optional[str]]:
    """
    Validate that text is properly encoded UTF-8.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Try to encode and decode to verify UTF-8 compatibility
        encoded = text.encode('utf-8')
        decoded = encoded.decode('utf-8')
        
        if decoded != text:
            return False, "Text contains non-UTF-8 characters"
        
        # Check for replacement characters
        if '\ufffd' in text:
            return False, "Text contains Unicode replacement characters"
        
        # Check for common problematic characters
        problematic_chars = ['\u0092', '\u0093', '\u0094', '\u0096', '\u0097']
        for char in problematic_chars:
            if char in text:
                return False, f"Text contains problematic character: {repr(char)}"
        
        return True, None
        
    except UnicodeEncodeError as e:
        return False, f"Unicode encoding error: {e}"


def clean_text_for_json(text: str) -> str:
    """
    Clean text to ensure it's safe for JSON serialization.
    
    Args:
        text: Text to clean
        
    Returns:
        JSON-safe text
    """
    # Fix encoding issues
    cleaned = fix_string_encoding(text)
    
    # Remove or replace control characters except common whitespace
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    
    # Ensure valid UTF-8
    cleaned = cleaned.encode('utf-8', errors='replace').decode('utf-8')
    
    return cleaned


def detect_encoding_issues(text: str) -> list[str]:
    """
    Detect potential encoding issues in text.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of detected issues
    """
    issues = []
    
    # Check for replacement characters
    if '\ufffd' in text:
        issues.append("Contains Unicode replacement characters")
    
    # Check for common Windows-1252 issues
    windows_1252_chars = {
        '\u0092': "Right single quotation mark (0x92)",
        '\u0093': "Left double quotation mark (0x93)",
        '\u0094': "Right double quotation mark (0x94)",
        '\u0096': "En dash (0x96)",
        '\u0097': "Em dash (0x97)"
    }
    
    for char, description in windows_1252_chars.items():
        if char in text:
            issues.append(f"Contains {description}")
    
    # Check for control characters
    control_chars = re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', text)
    if control_chars:
        issues.append(f"Contains control characters: {[hex(ord(c)) for c in set(control_chars)]}")
    
    return issues


class EncodingValidator:
    """Validator class for checking and fixing encoding issues."""
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator.
        
        Args:
            strict: If True, reject text with encoding issues instead of fixing
        """
        self.strict = strict
    
    def validate_and_fix(self, value: Any) -> str:
        """
        Validate and optionally fix encoding issues in a value.
        
        Args:
            value: Value to validate and fix
            
        Returns:
            Fixed string value
            
        Raises:
            ValueError: If strict mode and encoding issues found
        """
        if value is None:
            return ""
        
        # Convert to string if needed
        if isinstance(value, bytes):
            text = decode_bytes_safely(value)
        else:
            text = str(value)
        
        # Detect issues
        issues = detect_encoding_issues(text)
        
        if issues and self.strict:
            raise ValueError(f"Text encoding issues detected: {', '.join(issues)}")
        
        if issues:
            logger.warning(f"Fixing encoding issues: {', '.join(issues)}")
            text = fix_string_encoding(text)
            text = clean_text_for_json(text)
        
        return text


# Convenience functions for Pydantic validators
def encoding_validator(strict: bool = False):
    """
    Create a Pydantic validator for encoding issues.
    
    Args:
        strict: If True, reject invalid encoding instead of fixing
        
    Returns:
        Validator function
    """
    validator = EncodingValidator(strict=strict)
    
    def validate(cls, v):
        return validator.validate_and_fix(v)
    
    return validate


# Example usage in Pydantic models:
"""
from pydantic import BaseModel, validator
from app.utils.encoding_utils import encoding_validator

class MyModel(BaseModel):
    text: str
    
    # Add encoding validation
    _validate_text = validator('text', allow_reuse=True)(encoding_validator(strict=False))
"""