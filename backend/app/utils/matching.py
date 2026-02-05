import re

def fuzzy_match_drug(search_term, row_drug_name, search_id, row_drug_id):
    """
    Robust matching logic for drug names.
    """
    # 0. Safety check for None
    if not search_term or not row_drug_name:
        return False
        
    search_term = search_term.lower()
    row_drug_name = row_drug_name.lower()

    # 1. Exact ID match (best)
    if search_id and row_drug_id == search_id:
        return True
    
    # 2. Exact name match (case-insensitive)
    if search_term == row_drug_name:
        return True
    
    # 3. Check if one is a variant/salt of the other
    # Remove common suffixes
    clean_search = re.sub(r'\s+(mesylate|hydrochloride|sulfate|sodium|calcium|anhydrous|monohydrate|trihydrate)$', '', search_term)
    clean_row = re.sub(r'\s+(mesylate|hydrochloride|sulfate|sodium|calcium|anhydrous|monohydrate|trihydrate)$', '', row_drug_name)
    
    if clean_search == clean_row:
        return True
    
    # 4. Only allow substring match if search term is long enough
    if len(search_term) >= 5 and search_term in row_drug_name:
        return True
        
    return False
