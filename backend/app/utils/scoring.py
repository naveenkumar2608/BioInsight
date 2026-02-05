def calculate_confidence(matches: list) -> dict:
    """
    Calculate confidence score based on 4 core factors:
    1. Evidence Type Score (ETS) - Clinical phase evidence
    2. Evidence Count Score (ECS) - Source diversity
    3. Evidence Quality Score (EQS) - Data curation quality
    4. Consistency Score (CS) - Mechanism agreement
    
    Enhanced with weighted combination and non-linear scaling
    """
    if not matches:
        return {
            "score": 0.0,
            "max_phase": 0,
            "evidence_count": 0,
            "source_count": 0,
            "evidence_types": [],
            "reasoning": "No evidence found",
            "factors": {}
        }

    # ========================================
    # 1. Evidence Type Score (ETS) - 40% weight
    # ========================================
    max_phase = 0
    mechanism_of_action = None
    
    for m in matches:
        phase = m.get("phase", 0) or 0
        if phase > max_phase:
            max_phase = phase
            mechanism_of_action = m.get("mechanismOfAction", "")
    
    # Non-linear phase scoring (bigger gaps between phases)
    if max_phase == 4:
        ets = 1.0  # Approved / Post-marketing
    elif max_phase == 3:
        ets = 0.85  # Phase 3
    elif max_phase == 2:
        ets = 0.65  # Phase 2
    elif max_phase == 1:
        ets = 0.45  # Phase 1
    elif max_phase == 0.5:
        ets = 0.35  # Early clinical trials
    else:
        # Check source for preclinical vs literature
        has_preclinical = any(
            str(m.get("source", "")).lower() in ["animal", "preclinical", "in_vivo"] 
            for m in matches
        )
        ets = 0.25 if has_preclinical else 0.15

    # ========================================
    # 2. Evidence Count Score (ECS) - 25% weight
    # ========================================
    unique_sources = set()
    source_types = {"expert": 0, "database": 0, "text_mining": 0}
    
    # CRITICAL FIX: Collect sources from BOTH evidence-level AND reference-level
    for m in matches:
        # Check evidence-level source (datasourceId, etc.)
        evidence_source = m.get("datasourceId") or m.get("source") or m.get("drugType")
        if evidence_source:
            unique_sources.add(str(evidence_source))
            
            # Categorize evidence-level source
            src_lower = str(evidence_source).lower()
            if any(x in src_lower for x in ["chembl", "fda", "drugbank", "ttd"]):
                source_types["expert"] += 1
            elif any(x in src_lower for x in ["europepmc", "pubmed", "mining", "literature"]):
                source_types["text_mining"] += 1
            else:
                source_types["database"] += 1
        
        # Check reference-level sources
        refs = m.get("references", []) or []
        for r in refs:
            source = r.get("source", "")
            if source:
                unique_sources.add(source)
                
                # Categorize reference source
                src_lower = source.lower()
                if any(x in src_lower for x in ["chembl", "fda", "drugbank", "ttd", "dailymed"]):
                    source_types["expert"] += 1
                elif any(x in src_lower for x in ["europepmc", "pubmed", "mining", "literature"]):
                    source_types["text_mining"] += 1
                else:
                    source_types["database"] += 1
    
    source_count = len(unique_sources)
    
    # Handle zero sources gracefully
    if source_count == 0:
        ecs = 0.10  # Very low score for missing data
        source_count = 0
    elif source_count >= 10:
        ecs = 1.0
    elif source_count >= 7:
        ecs = 0.95
    elif source_count >= 5:
        ecs = 0.85
    elif source_count >= 3:
        ecs = 0.70
    elif source_count == 2:
        ecs = 0.50
    else:  # source_count == 1
        ecs = 0.30

    # ========================================
    # 3. Evidence Quality Score (EQS) - 20% weight
    # ========================================
    quality_scores = []
    
    # Collect quality from both evidence-level and reference-level sources
    for m in matches:
        # Check evidence-level source
        evidence_source = m.get("datasourceId") or m.get("source") or m.get("drugType")
        if evidence_source:
            src_lower = str(evidence_source).lower()
            if any(x in src_lower for x in ["chembl", "fda", "expert", "curated_manual", "drugbank", "dailymed"]):
                quality_scores.append(1.0)
            elif any(x in src_lower for x in ["europepmc", "pubmed", "mining", "automated", "literature"]):
                quality_scores.append(0.5)
            else:
                quality_scores.append(0.75)
        
        # Check reference-level sources
        refs = m.get("references", []) or []
        for r in refs:
            src = str(r.get("source", "")).lower()
            if any(x in src for x in ["chembl", "fda", "expert", "curated_manual", "drugbank", "dailymed"]):
                quality_scores.append(1.0)
            elif any(x in src for x in ["europepmc", "pubmed", "mining", "automated", "literature"]):
                quality_scores.append(0.5)
            else:
                quality_scores.append(0.75)
    
    if quality_scores:
        # Blend max and average quality
        max_quality = max(quality_scores)
        avg_quality = sum(quality_scores) / len(quality_scores)
        eqs = (max_quality * 0.6) + (avg_quality * 0.4)
    else:
        # No quality data
        eqs = 0.50
    
    # Apply penalty if only text mining sources exist
    if source_types["text_mining"] > 0 and source_types["expert"] == 0 and source_types["database"] == 0:
        eqs *= 0.7  # 30% penalty for text-mining only

    # ========================================
    # 4. Consistency Score (CS) - 15% weight
    # ========================================
    mechanisms = []
    for m in matches:
        moa = m.get("mechanismOfAction", "")
        if moa:
            mechanisms.append(moa.lower().strip())
    
    unique_mechanisms = set(mechanisms)
    
    # Non-linear consistency penalties
    if len(unique_mechanisms) <= 1:
        cs = 1.0  # All sources agree or only one source
    elif len(unique_mechanisms) == 2:
        cs = 0.80  # Minor variation
    elif len(unique_mechanisms) == 3:
        cs = 0.55  # Moderate conflict
    else:
        cs = 0.30  # Major inconsistency

    # ========================================
    # WEIGHTED COMBINATION (not simple average)
    # ========================================
    # Weights: ETS=40%, ECS=25%, EQS=20%, CS=15%
    weighted_score = (
        ets * 0.40 +  # Clinical evidence is most important
        ecs * 0.25 +  # Source diversity is second
        eqs * 0.20 +  # Quality matters
        cs * 0.15     # Consistency is nice-to-have
    )
    
    # Convert to 0-100 scale
    final_score = weighted_score * 100
    
    # Apply evidence depth bonus (multiplier, not additive)
    evidence_count = len(matches)
    if evidence_count >= 20:
        final_score *= 1.05  # 5% bonus
    elif evidence_count >= 10:
        final_score *= 1.03  # 3% bonus
    elif evidence_count >= 5:
        final_score *= 1.01  # 1% bonus
    
    # Cap at 100
    final_score = min(final_score, 100.0)

    # ========================================
    # REASONING GENERATION
    # ========================================
    reasoning_parts = []
    
    # Primary evidence tier
    if max_phase == 4:
        reasoning_parts.append("FDA approved with strong clinical evidence")
    elif max_phase == 3:
        reasoning_parts.append("Late-stage clinical trials (Phase 3)")
    elif max_phase == 2:
        reasoning_parts.append("Mid-stage clinical trials (Phase 2)")
    elif max_phase == 1:
        reasoning_parts.append("Early-stage clinical trials (Phase 1)")
    else:
        if any(str(m.get("source", "")).lower() in ["animal", "preclinical"] for m in matches):
            reasoning_parts.append("Preclinical evidence only")
        else:
            reasoning_parts.append("Literature-based evidence only")
    
    # Source diversity
    if source_count >= 7:
        reasoning_parts.append(f"highly replicated ({source_count} independent sources)")
    elif source_count >= 4:
        reasoning_parts.append(f"well-supported ({source_count} sources)")
    elif source_count == 1:
        reasoning_parts.append("⚠ single source")
    elif source_count == 0:
        reasoning_parts.append("⚠ no source information")
    else:
        reasoning_parts.append(f"{source_count} sources")
    
    # Quality flags
    if source_types["expert"] > 0:
        reasoning_parts.append("expert-curated")
    elif source_types["text_mining"] == sum(source_types.values()) and source_types["text_mining"] > 0:
        reasoning_parts.append("⚠ text-mining only")
    
    # Consistency warnings
    if len(unique_mechanisms) > 2:
        reasoning_parts.append(f"⚠ {len(unique_mechanisms)} different mechanisms reported")
    
    # Add mechanism if available
    if mechanism_of_action and len(unique_mechanisms) == 1:
        reasoning_parts.append(f"(via {mechanism_of_action})")

    return {
        "score": round(final_score, 1),
        "max_phase": max_phase,
        "evidence_count": evidence_count,
        "source_count": source_count,
        "mechanism": mechanism_of_action,
        "evidence_types": sorted(list(unique_sources)),
        "reasoning": " • ".join(reasoning_parts),
        "factors": {
            "ets": round(ets, 3),
            "ecs": round(ecs, 3),
            "eqs": round(eqs, 3),
            "cs": round(cs, 3),
            "weighted_score": round(weighted_score, 3),
            "source_breakdown": source_types
        }
    }


# ========================================
# DEBUGGING HELPER
# ========================================
def debug_confidence_calculation(matches: list, drug_name: str = "", target_name: str = ""):
    """
    Debug helper to see exactly what's being calculated.
    """
    print(f"\n{'='*80}")
    print(f"DEBUG: Confidence Calculation for {drug_name} → {target_name}")
    print(f"{'='*80}")
    
    if not matches:
        print("❌ No evidence items provided!")
        return
    
    print(f"\n📊 Evidence Items: {len(matches)}")
    print("-" * 80)
    
    for i, m in enumerate(matches, 1):
        print(f"\nEvidence #{i}:")
        print(f"  Phase: {m.get('phase', 'N/A')}")
        print(f"  Mechanism: {m.get('mechanismOfAction', 'N/A')}")
        print(f"  Evidence Source: {m.get('source') or m.get('datasourceId') or m.get('drugType') or 'N/A'}")
        
        refs = m.get("references", [])
        if refs:
            print(f"  References ({len(refs)}):")
            for j, r in enumerate(refs[:10], 1):
                print(f"    {j}. {r.get('source', 'N/A')}")
            if len(refs) > 10:
                print(f"    ... and {len(refs) - 10} more")
        else:
            print(f"  ⚠ No references found!")
    
    # Count unique sources
    unique_sources = set()
    for m in matches:
        evidence_source = m.get("datasourceId") or m.get("source") or m.get("drugType")
        if evidence_source:
            unique_sources.add(str(evidence_source))
        for r in m.get("references", []):
            if r.get("source"):
                unique_sources.add(r.get("source"))
    
    print(f"\n📈 Summary:")
    print(f"  Total Evidence Items: {len(matches)}")
    print(f"  Unique Sources: {len(unique_sources)}")
    print(f"  Sources: {sorted(list(unique_sources))}")
    
    print(f"\n{'='*80}\n")
