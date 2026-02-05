import re
from typing import List, Dict, Optional, Tuple, Set

# 1. Normalization Mappings
ENTITY_MAPPINGS = {
    # Drug Aliases/Typos
    "vergfr2": "VEGFR2",
    "vegf-r2": "VEGFR2",
    "vegfr-2": "VEGFR2",
    "v-egfr": "VEGFR",
    
    # Target Aliases/Typos
    "bcr abl": "BCR-ABL1",
    "bcr-abl": "BCR-ABL1",
    "her2": "ERBB2",
    "her-2": "ERBB2",
    "her 2": "ERBB2",
    "ampk": "PRKAA1",
    "vegfr": "KDR",
    "vegfr2": "KDR",
    "egfr": "EGFR",
    "lipitor": "Atorvastatin",
    "hmg-coa reductase": "HMGCR",
    "hmg coa reductase": "HMGCR",
    "α-synuclein": "SNCA",
    "alpha-synuclein": "SNCA",
    "alpha synuclein": "SNCA",
}

# Expanded stopwords - CRITICAL for filtering out query words
STOPWORDS = {
    'how', 'does', 'with', 'is', 'the', 'and', 'what', 'tell', 'me', 
    'about', 'of', 'on', 'in', 'to', 'for', 'a', 'an', 'are', 'was', 'were',
    'has', 'have', 'had', 'been', 'be', 'by', 'at', 'from', 'this', 'that',
    'which', 'who', 'whom', 'whose', 'its', 'interact', 'interaction', 
    'mechanistically', 'mechanism', 'acts', 'acts on', 'between', 'relationship',
    'drug', 'target', 'explain', 'work', 'works', 'working', 'show', 'shows',
    'affect', 'affects', 'impact', 'impacts', 'influence', 'influences',
    'binding', 'binds', 'bind', 'inhibit', 'inhibits', 'inhibitor', 'inhibition',
    'activate', 'activates', 'activation', 'modulate', 'modulates', 'modulation',
    'relate', 'related', 'relating', 'relation', 'connection', 'connected'
}

def normalize_text(text: str) -> str:
    """
    Apply normalization to the input text before extraction.
    """
    lowered = text.lower()
    for alias, formal in ENTITY_MAPPINGS.items():
        lowered = re.sub(rf'\b{re.escape(alias)}\b', formal.lower(), lowered)
    return lowered

def extract_regex_entities(text: str) -> Dict[str, Optional[str]]:
    """
    Deterministic extraction using Regex.
    """
    entities = {"drug": None, "target": None}
    
    # Pre-clean for common phrases
    text = re.sub(r'\bis\s+associated\s+with\b', 'targets', text, flags=re.I)
    text = re.sub(r'\bhow\s+does\b', '', text, flags=re.I)
    text = re.sub(r'\bmechanistically\b', '', text, flags=re.I)
    
    patterns = [
        (r'interaction\s+between\s+([\w-]+)\s+and\s+([\w-]+)', 1, 2),
        (r'([\w-]+)\s+interacts?\s+with\s+([\w-]+)', 1, 2),
        (r'(?:does\s+)?(?:the\s+drug\s+)?([\w-]+)\s+(?:inhibits?|targets?|binds?|blocks?)\s+(?:to\s+)?(?:the\s+)?(?:protein\s+)?([\w-]+)', 1, 2),
        (r'([\w-]+)\s+and\s+([\w-]+)\s+interaction', 1, 2),
        (r'([\w-]+)\s+targets\s+([\w-]+\s+kinase)', 1, 2),
        (r'when\s+([\w-]+)\s+binds\s+(?:to\s+)?([\w-]+)', 1, 2),
    ]
    
    for pattern, d_grp, t_grp in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            entities["drug"] = match.group(d_grp)
            entities["target"] = match.group(t_grp)
            return entities
    return entities

def generate_smart_candidates(query: str) -> List[str]:
    """
    IMPROVED: Generate candidates with multi-word entity awareness.
    """
    candidates = []
    original_words = re.findall(r"[\w-]+|[^\w\s]", query)
    
    # ============================================================
    # STRATEGY 1: Multi-word Capitalized Phrases
    # ============================================================
    i = 0
    greek_connectors = {'alpha', 'beta', 'gamma', 'delta', 'kappa', 'sigma', 'omega'}
    weak_connectors = {'of', 'and'}
    all_connectors = greek_connectors.union(weak_connectors)

    while i < len(original_words):
        word = original_words[i]
        if word and len(word) > 1 and (word[0].isupper() or '-' in word):
            phrase_parts = [word]
            j = i + 1
            while j < len(original_words):
                next_word = original_words[j]
                if (next_word and len(next_word) > 0 and 
                    (next_word[0].isupper() or 
                     '-' in next_word or
                     next_word in ['-', '–', '—'] or
                     next_word.lower() in all_connectors)):
                    phrase_parts.append(next_word)
                    j += 1
                else:
                    break
            
            # Trim trailing weak connectors (of, and)
            while phrase_parts and phrase_parts[-1].lower() in weak_connectors:
                phrase_parts.pop()
            
            if phrase_parts:
                phrase = ' '.join(phrase_parts)
                clean_phrase = ''.join(char for char in phrase if char.isalnum() or char in [' ', '-']).strip()
                if clean_phrase.lower() not in STOPWORDS and len(clean_phrase) > 1:
                    candidates.append(clean_phrase)
                    no_space = clean_phrase.replace(' ', '')
                    if no_space != clean_phrase and len(no_space) > 3:
                        candidates.append(no_space)
            
            i = j if j > i else i + 1
        else:
            i += 1
    
    # ============================================================
    # STRATEGY 2: Individual Capitalized Words
    # ============================================================
    for word in original_words:
        if word and len(word) > 1 and word[0].isupper():
            clean_word = ''.join(char for char in word if char.isalnum() or char == '-')
            if clean_word.lower() not in STOPWORDS and len(clean_word) > 1:
                if not any(clean_word in candidate for candidate in candidates):
                    candidates.append(clean_word)
    
    # ============================================================
    # STRATEGY 3: Significant Long Words (fallback)
    # ============================================================
    for word in original_words:
        clean_word = ''.join(char for char in word if char.isalnum() or char == '-')
        if (len(clean_word) > 5 and 
            clean_word.lower() not in STOPWORDS and
            not any(clean_word in candidate for candidate in candidates)):
            candidates.append(clean_word)
    
    return sorted(list(set(candidates)), key=lambda x: len(x), reverse=True)

def get_candidates(text: str) -> List[str]:
    """
    Generate candidates from original and normalized text.
    """
    original_candidates = generate_smart_candidates(text)
    normalized_text = normalize_text(text)
    normalized_candidates = []
    if normalized_text != text.lower():
        normalized_candidates = generate_smart_candidates(normalized_text)
    
    all_candidates = list(set(original_candidates + normalized_candidates))
    return sorted(all_candidates, key=lambda x: len(x), reverse=True)
