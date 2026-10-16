"""Pure, deterministic demo-only quality-gate logic.

The CTQ workbook supplies checklist questions and descriptive tolerances. It does
not establish the demo's universal 'all checks pass to release' requirement.
That release condition is a deliberately explicit, conservative demonstration rule.
"""

def can_inspect_at_stage(initial, active, requested_wc, routes):
    """Never allow an inspection to silently skip earlier unverified stages."""
    route=routes[initial['type']]
    if requested_wc not in route:
        return False
    if active['status'] in ('Scrapped','Hold'):
        # A hold can be investigated/revised at its own stage; scrap is permanent.
        return active['status']=='Hold' and requested_wc==active['wc']
    if active['status']=='Complete' and initial['status']!='Complete':
        return False
    # Historical seeded units may begin their demo mid-route; earlier stages were
    # not observed, and this does NOT certify quality release at those gates.
    return requested_wc==active['wc']


def compute_quality_state(initial,active,check_wc,recorded,routes,rules):
    """Compute status from every result at the active gate rather than latest answer.

    No PASS on a single check can override a FAIL or missing measurement.
    """
    stage_checks=[r['check_id'] for r in rules if r['wc']==check_wc]
    values=[recorded.get(i) for i in stage_checks]
    if 'FAIL' in values:
        if check_wc=='WC1' and initial['type']=='Tank':
            return ('Scrapped',check_wc,active['progress'])
        return ('Hold',check_wc,active['progress'])
    if not stage_checks or any(v!='PASS' for v in values):
        return ('Inspection pending',check_wc,active['progress'])
    route=routes[initial['type']]
    stage=route.index(check_wc)
    if stage==len(route)-1:
        return ('Complete',check_wc,100)
    return ('Ready for next stage',route[stage+1],round((stage+1)*100/len(route)))


def evidence_is_valid_image(data,extension):
    """Decode actual images, not just easily forged extension or magic bytes."""
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    if not 24 <= len(data) <= 6*1024*1024:
        return False
    formats={'png':'PNG','jpg':'JPEG','jpeg':'JPEG','webp':'WEBP'}
    if extension not in formats:
        return False
    try:
        with Image.open(BytesIO(data)) as img:
            if img.format!=formats[extension] or img.width*img.height>20_000_000:
                return False
            img.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return False
