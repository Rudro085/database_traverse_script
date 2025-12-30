import base64
import re
import logging

logger = logging.getLogger(__name__)

def ultra_forgiving_b64decode(b64_string: str) -> bytes:
    """
    Decode base64 like online tools - extremely forgiving.
    Handles incorrect padding, extra characters, data URLs, etc.
    """
    if not b64_string:
        return b""
    
    # Make a copy to work with
    s = str(b64_string)
    
    logger.debug(f"Original length: {len(s)}")
    
    # 1. Remove data URL prefix if present
    if 'base64,' in s:
        s = s.split('base64,', 1)[1]
        logger.debug("Removed data URL prefix")
    
    # 2. Remove ALL whitespace and control characters
    s = re.sub(r'\s+', '', s)  # Remove spaces, newlines, tabs
    logger.debug(f"After removing whitespace: {len(s)}")
    
    # 3. Remove any non-base64 characters (keep only A-Z, a-z, 0-9, +, /, =)
    # This is what most online tools do
    s = re.sub(r'[^A-Za-z0-9+/=]', '', s)
    logger.debug(f"After removing non-base64 chars: {len(s)}")
    
    # 4. Handle URL-safe base64
    s = s.replace('-', '+').replace('_', '/')
    
    # 5. Check if we have anything left
    if not s:
        raise ValueError("No valid base64 characters found")
    
    # 6. Try different padding strategies
    strategies = [
        # Strategy 1: Try as-is
        lambda x: x,
        
        # Strategy 2: Add padding if length not multiple of 4
        lambda x: x + '=' * (4 - len(x) % 4) if len(x) % 4 else x,
        
        # Strategy 3: Remove all '=' and add correct padding
        lambda x: x.rstrip('=') + '=' * (4 - len(x.rstrip('=')) % 4),
        
        # Strategy 4: Force to multiple of 4 by adding or removing characters
        lambda x: x[:len(x) - (len(x) % 4)] if len(x) % 4 else x,
    ]
    
    for i, strategy in enumerate(strategies):
        try:
            modified = strategy(s)
            logger.debug(f"Strategy {i+1}: Trying length {len(modified)}")
            
            # Try decoding
            decoded = base64.b64decode(modified, validate=False)
            logger.debug(f"Strategy {i+1} succeeded!")
            return decoded
            
        except Exception as e:
            logger.debug(f"Strategy {i+1} failed: {e}")
            continue
    
    # 7. Last resort: Try with the most common fix
    try:
        # Remove all equals, calculate needed padding, add it back
        s_no_eq = s.rstrip('=')
        needed_padding = 4 - (len(s_no_eq) % 4)
        if needed_padding == 4:
            needed_padding = 0
        s_final = s_no_eq + '=' * needed_padding
        
        logger.debug(f"Final attempt: length {len(s_final)}")
        return base64.b64decode(s_final, validate=False)
        
    except Exception as e:
        # Save the problematic string for debugging
        logger.error(f"All decoding attempts failed. String preview: {s[:200]}")
        logger.error(f"String length: {len(s)}")
        logger.error(f"String length mod 4: {len(s) % 4}")
        raise ValueError(f"Cannot decode base64 after all attempts: {e}") from e