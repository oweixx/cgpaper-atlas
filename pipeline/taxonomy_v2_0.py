"""Evidence-based CG labels; evidence strength is not a probability.

Specific title phrases take precedence. Abstract-only labels need repeated
support or a contribution sentence. Venue/author/country/year are never inputs.
"""
import html
import re
import unicodedata
from taxonomy_v1 import TAXONOMY as LEGACY_TAXONOMY

VERSION = 'cg-topics-v2.0'
UNCLASSIFIED = 'Other / Unclassified'
TOPICS = list(LEGACY_TAXONOMY)
SUBTOPICS = [name for children in LEGACY_TAXONOMY.values() for name in children]
TAXONOMY = {group: list(children) for group, children in LEGACY_TAXONOMY.items()}

# Research objects and methods, not isolated generic adjectives. Stable names
# preserve old links; the expressions and decision rules are versioned together.
EXPRESSIONS = {
 'R1': r'\brender(?:ing|er|ers)?\b|\blight transport\b|\bpath trac\w*|\bray trac\w*|\bpath guid\w*|\bradiosity\b|\bglobal illumination\b|\bphoton (?:map\w*|transport|density)|\bcaustic\w*|\bradiance transfer\b|\bnext event estimation\b|\bvisibility (?:comput\w*|cull\w*|algorithm\w*)|\bocclusion cull\w*',
 'R2': r'\bshad(?:ing|ers?|ows?)\b|\breflectance\b|\bbrdf\b|\bbsdf\b|\bbssrdf\b|\bsubsurface scatter\w*|\brelight\w*|\bspecular\b|\bmaterial (?:appearance|attributes?|capture|edit\w*|transform\w*)|\bappearance (?:capture|model\w*|acquisition)|\breflect(?:ion|ive)\b',
 'R3': r'\binverse (?:render\w*|graphics|light\w*)|\b(?:reflectance|material|brdf|lighting|illumination) (?:estimat\w*|recover\w*|reconstruct\w*|acquisition)|\bestimat\w* (?:\w+ ){0,3}(?:reflectance|roughness|brdf)|\bshape and reflectance (?:acquisition|capture)|\bphotometric stereo\b',
 'G1': r'\b(?:mesh\w*|remesh\w*|triangulat\w*|tessellat\w*|parametriz\w*|parameteriz\w*|spline\w*|bezier|nurbs|geodesic\w*|hexahedral|polyline\w*)\b|\b(?:geometry|geometric) (?:process\w*|model\w*|represent\w*|comput\w*)|\b(?:frame|cross|octahedral|direction) fields?\b|\bfunctional maps?\b|\b(?:shape|surface) (?:correspond\w*|registration|matching|symmetr\w*|simplif\w*)|\bsubdivision\b|\b(?:polygon\w*|polyhed\w*)\b|\bimplicit surfaces?\b|\b(?:parametric|kinematic|spline|curved) surface\w*|\bmarching cubes\b|\bwinding numbers?\b|\bspatial indexing\b|\bquadtree\w*',
 'G2': r'\bshapes?\b|\b(?:3d|three dimensional|surface|object|point cloud) (?:reconstruct\w*|model(?:ing|ling)|retriev\w*|complet\w*|generat\w*)|\b(?:geometric|solid|freeform|free form|sketch based|spline) model\w*|\bpoint (?:clouds?|sets?)\b|\bsigned distance\b|\bimplicit (?:surface|function|represent\w*)|\bconstructive solid geometry\b',
 'G3': r'\bprocedural (?:model\w*|scene\w*|generat\w*|terrain\w*)|\bscene (?:generat\w*|synthes\w*|model\w*|layout\w*)|\b(?:terrain|landscape|urban|city|building|vegetation|plant|tree) (?:generat\w*|synthes\w*|model\w*|author\w*|design\w*)|\b(?:terrain|landscape)\b|\barchitectural model\w*',
 'A1': r'\banimat\w*|\b(?:character|skeletal|skeleton) (?:motion|animat\w*|control|rig\w*)|\bskinning\b|\b(?:motion|pose) (?:captur\w*|synthes\w*|generat\w*|edit\w*|retarget\w*|remap\w*|correct\w*|prior\w*|track\w*|interpol\w*)|\blocomo\w*|\bavatar\w*|\bgait\w*|\bblendshape\w*|\bfacial (?:animat\w*|expression\w*|performance)|\bcharacter\w*',
 'A2': r'\bfluid\w*|\b(?:liquid|water|smoke|fire|combustion|rigid body|affine body|physical|physics based|physically based|acoustic|sound|wave|erosion|machining) (?:\w+ ){0,3}(?:simulat\w*|dynamics|propagat\w*)|\b(?:simulat\w*|dynamics) of (?:\w+ ){0,3}(?:water|fluid|liquid|fire|wave|rigid|machining)|\b(?:combustion|hydrodynamic\w*|thermodynamic\w*|navier stokes|elastodynamic\w*|material point method|smoothed particle hydrodynamics)\b|\b(?:affine|rigid) body dynamics\b|\b(?:sound|acoustic) propagation\b|\bfire\b',
 'A3': r'\bcloth\w*|\bhair\b|\bfur\b|\bgarment\w*|\bfractur\w*|\b(?:elastic|inelastic|plastic|soft body|deformable) (?:\w+ ){0,2}(?:simulat\w*|dynamics|solid\w*|bod\w*|deform\w*)|\b(?:elasticity|elastoplastic\w*|hyperelastic\w*)\b',
 'N1': r'\bneural render\w*|\bneural radiance fields?\b|\bnerf\w*|\bgaussian splatt?\w*|\b(?:3d|2d|three dimensional) gaussian\w*|\b(?:neural|learned) (?:\w+ ){0,2}view synthes\w*',
 'N2': r'\bgenerative (?:model\w*|network\w*|adversarial\w*|ai)\b|\bdiffusion (?:model\w*|prior\w*|generat\w*|probabilistic\w*|transformer\w*)|\bdenoising diffusion\b|\bgan\w*\b|\btext (?:to|guided|conditioned) (?:image|video|3d|shape|motion|scene)\w*|\b(?:image|video|3d|shape|scene|motion) generation\b|\bflow matching\b',
 'N3': r'\bneural (?:network\w*|denois\w*|represent\w*|model\w*|process\w*|field\w*|photometr\w*)|\bdeep (?:learn\w*|network\w*|model\w*|feature\w*)|\bmachine learn\w*|\blearning based\b|\blearned (?:\w+ ){0,2}(?:represent\w*|feature\w*|model\w*|prior\w*|compress\w*)|\b(?:reinforcement|supervised|unsupervised|self supervised|contrastive) learn\w*|\blearning (?:to|for|target|shape|based)\b|\b(?:train\w*|learn\w*) (?:\w+ ){0,3}dictionar\w*|\btransformer (?:network\w*|model\w*)',
 'I1': r'\b(?:image|photo\w*) (?:process\w*|restor\w*|reconstruct\w*|denois\w*|deblur\w*|inpaint\w*|segment\w*|vectoriz\w*|color\w*|colour\w*|generat\w*|retarget\w*|resiz\w*|enhanc\w*|analog\w*)|\b(?:denois\w*|deblur\w*|inpaint\w*|super resolution|tone map\w*|superpixel\w*|demosaic\w*|deconvol\w*|dehaz\w*)\b|\b(?:photo|image) collections?\b|\b(?:texture|image) (?:analy\w*|descriptor\w*)|\bvisual (?:object )?tracking\b|\bcompressed sensing\b',
 'I2': r'\bcamera\w*|\b(?:optic\w*|lens\w*|hologra\w*|photometr\w*|lidar|light field|lightfield|coded aperture|time of flight|transient imag\w*|computational photograph\w*)\b|\b(?:head mounted|near eye|autostereoscopic|stereoscopic|light field|off the shelf|holographic) display\w*|\bdisplay (?:design|optics|calibrat\w*|technolog\w*)',
 'I3': r'\b(?:video|image|photo\w*) (?:edit\w*|styl\w*|matt\w*|composit\w*|interpol\w*|inpaint\w*|synthes\w*|coloriz\w*|transfer\w*)|\b(?:styliz\w*|stylis\w*|edit\w*|matt\w*) (?:\w+ ){0,2}(?:video|image|photo\w*)|\b(?:matting|style transfer|image to image translation)\b|\b(?:visual attribute|material attribute) transfer\b',
 'V1': r'\b(?:volume|volumetric|scientific|flow|vector field|tensor field|ensemble|medical|scalar field|molecular) (?:\w+ ){0,2}(?:visuali[sz]\w*|render\w*|analy\w*)|\b(?:flow|vector|tensor|scalar) fields?\b|\b(?:isosurface\w*|streamline\w*|pathline\w*)\b|\bvisuali[sz]\w*.{0,90}\b(?:function dynamics|simulation|ensemble|scientific|volume|volumetric)\b|\brender\w* (?:of )?(?:volume|volumetric)\b',
 'V2': r'\b(?:graph|network|information|data|music|musical) (?:visuali[sz]\w*|draw\w*|layout\w*)|\b(?:chart\w*|dashboard\w*|scatterplot\w*|treemap\w*|parallel coordinates?|node link|visual encodings?)\b|\b(?:readability|visual proofs?|visual certif\w*) (?:\w+ ){0,5}graphs?\b|\bvisuali[sz]\w* (?:\w+ ){0,7}(?:music|musical|relational)\b|\bgraph properties\b',
 'V3': r'\bvisual analy\w*|\bvisual explor\w*|\bsensemak\w*|\binteractive (?:visuali[sz]\w*|data explor\w*)|\bvisual (?:explan\w*|explain\w*|reason\w*)|\b(?:data|model) explor\w*',
 'X1': r'\b(?:virtual|augmented|mixed|extended|cross) reality\b|\b(?:vr|ar|xr|hmd|cave)\b|\bimmersive\b|\bvirtual environments?\b|\bcybersickness\b|\bvection\b|\bredirected walking\b',
 'X2': r'\b(?:user|human computer|hand|touch|gesture|pen|sketch|multimodal|tangible) (?:based )?(?:interact\w*|interface\w*|input\w*|gestur\w*)|\b(?:interface\w*|gesture\w*|freehand|hci)\b|\b(?:sketch|drawing|designer) (?:based|guidance|support|interface|interaction)\b|\binteractiv\w* (?:\w+ ){0,2}(?:author\w*|design\w*|scene synthes\w*|model\w*|transformation)|\b(?:input model|gks input|graphical symbolic commands|target selection technique\w*|object selection technique\w*)\b|\bidea sketch\b|\bterrain authoring\b',
 'X3': r'\b(?:haptic\w*|tactile|telepresence|embodiment|embodied)\b|\b(?:force|touch) feedback\b|\bbody ownership\b',
 'F1': r'\bfabricat\w*|\bmanufactur\w*|\b3d print\w*|\badditive (?:process\w*|manufactur\w*)|\blaser cut\w*|\bcnc\b|\b(?:papercraft|papercut\w*|origami|kirigami|quilts?|quilting|machining|toolpath\w*)\b|\bpaper piec\w*',
 'F2': r'\bmetamaterial\w*|\bmicrostructur\w*|\bstructural design\b|\btopology optimi\w*|\barchitected (?:material|structure)\w*|\b(?:mechanical|elastic) (?:material|structure) (?:design|optimi\w*)|\b(?:compliant mechanisms?|auxetic\w*|lattice structures?)\b',
 'F3': r'\b(?:texture|pattern) (?:synthes\w*|design\w*|generat\w*)|\b(?:textile\w*|weaving|woven|knitting|knitted|knitwear|embroid\w*|quilts?|quilting|mosaic\w*|stippl\w*|halfton\w*|moire)\b',
 'S1': r'\b(?:real time|interactive) (?:\w+ ){0,5}(?:render\w*|animat\w*|ray trac\w*|path trac\w*|graphics)\b|\brasteri[sz]\w*|\b(?:game|render\w*) engines?\b|\brendering pipeline\b|\bscan convers\w*|\bscan convert\w*|\b(?:postscript|phigs|gks|opengl|vulkan)\b|\bgraphics (?:api|language\w*|standard\w*)',
 'S2': r'\bgpus?\b|\bgraphics (?:hardware|processor\w*|processing unit\w*)|\b(?:parallel|distributed) (?:algorithm\w*|comput\w*|render\w*|simulat\w*|volume|architectur\w*)|\b(?:simd|mapreduce|multi gpu|cuda)\b',
 'S3': r'\bcompress(?:ion|ed|ing|or|ors|ible|ibility)\b|\blevel of detail\b|\bout of core\b|\b(?:geometry|texture|mesh|image|video) (?:encod\w*|stream\w*)|\b(?:acceleration|spatial indexing|spatial data) (?:structure\w*|technique\w*)|\b(?:fast|accelerat\w*) (?:\w+ ){0,2}(?:ray trac\w*|render\w*)|\b(?:memory efficient|memory footprint|storage structures?|bvh)\b',
 'P1': r'\bpercept\w*|\bperceived\b|\bpsychophys\w*|\bvisual attention\b|\bsaliency\b|\beye track\w*|\bgaze\b',
 'P2': r'\buser stud(?:y|ies)\b|\bsubjective evaluat\w*|\bhuman factors?\b|\b(?:evaluat\w*|investigat\w*|stud\w*) (?:\w+ ){0,3}(?:user preferences?|user experience|usability)|\b(?:user preference\w*|user experience|usability) (?:stud\w*|evaluat\w*|experiment\w*)',
 'P3': r'\bbenchmark\w*|\bshrec\b|\bquality (?:assessment|metric\w*|prediction)|\b(?:image|perceptual|visual|video) quality (?:assessment|metric\w*|prediction)|\ba (?:new |large scale |novel )?dataset (?:for|of)\b|\bdataset and benchmark\b',
}
RULES = []
for prefix, (group, children) in zip('RGANIVXFSP', TAXONOMY.items()):
    for i, name in enumerate(children, 1):
        code = prefix + str(i)
        RULES.append((code, group, name, re.compile(EXPRESSIONS[code])))

def normalize(text):
    text = unicodedata.normalize('NFKD', html.unescape(text or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[-\u2010-\u2015\u2212_/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip().lower()

FOCUS = re.compile(r'\b(?:we (?:\w+ ){0,2}(?:present|propose|introduce|develop|design|formulate|describe|investigate|study|conduct)|this (?:paper|work|study) (?:\w+ ){0,2}(?:present|propos|introduc|develop|investigat|focus)|(?:our|the) (?:method|approach|framework|model|algorithm) (?:\w+ ){0,2}(?:uses?|utiliz|learns?|relies)|(?:has|have) (?:also )?been developed)')
BACKGROUND = re.compile(r'\b(?:previous|prior|existing|compared|comparison|unlike|outperforms?|state of the art)\b')

def classify_with_evidence(title, abstract=''):
    title = normalize(title)
    abstract = normalize(abstract)
    abstract = re.sub(r'\be\.g\.', 'for example', abstract)
    abstract = re.sub(r'\bi\.e\.', 'that is', abstract)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?;])\s+', abstract) if s.strip()]
    usable = [s for s in sentences if not BACKGROUND.search(s) or FOCUS.search(s)]
    intro = set(sentences[:3])
    evidence, candidates = [], []
    for code, area, name, pattern in RULES:
        title_hits = list(dict.fromkeys(m.group() for m in pattern.finditer(title)))
        matches = [(s, list(dict.fromkeys(m.group() for m in pattern.finditer(s)))) for s in usable]
        matches = [(s, hits) for s, hits in matches if hits]
        core = [(s, hits) for s, hits in matches if s in intro or FOCUS.search(s)]
        if code == 'G2':
            # A shape/model used as input is not necessarily a modeling contribution.
            matches = [(s,[h for h in hits if h not in {'shape','shapes','3d model','3d models'}]) for s,hits in matches]
            matches = [(s,h) for s,h in matches if h]
            core = [(s,h) for s,h in matches if s in intro or FOCUS.search(s)]
        if code == 'R2' and not re.search(r'\b(?:light\w*|reflectance|brdf|bsdf|shading|specular|material|illumination|render\w*)\b', title+' '+abstract):
            title_hits = [h for h in title_hits if not re.fullmatch(r'shadows?|reflection|appearance model\w*', h)]
            matches = [(s,[h for h in hits if not re.fullmatch(r'shadows?|reflection|appearance model\w*', h)]) for s,hits in matches]
            matches = [(s,h) for s,h in matches if h]
            core = [(s,h) for s,h in matches if s in intro or FOCUS.search(s)]
        if code == 'I1' and re.search(r'\b(?:point cloud|mesh|shape|scene|motion)\w*', title) and not re.search(r'\b(?:image|photo|video)\w*', title):
            title_hits = [h for h in title_hits if not re.fullmatch(r'denois\w*|inpaint\w*|super resolution',h)]
            matches = [(s,[h for h in hits if not re.fullmatch(r'denois\w*|inpaint\w*|super resolution',h)]) for s,hits in matches]
            matches = [(s,h) for s,h in matches if h]
            core = [(s,h) for s,h in matches if s in intro or FOCUS.search(s)]
        # Shared terms can describe different research objects.
        if code == 'R1' and re.search(r'\b(?:sound|audio|acoustic|binaural)\b', title):
            title_hits = []; matches = []; core = []
        if code == 'G2' and re.search(r'\b(?:moire|quilt|patchwork)\b', title):
            title_hits = []; matches = []; core = []
        if code == 'A1' and re.search(r'\b(?:shape|surface|intrinsic)\b', title) and not re.search(r'\b(?:motion|animation|avatar|character)\b', title):
            title_hits = []; matches = []; core = []
        if code == 'N3' and re.search(r'\b(?:nlp|language model|llm|text classification)\w*', title) and any(re.search(r'visual analy|visuali[sz]|visual explanation', s) for s in sentences):
            title_hits = []; matches = []; core = []
        if code in {'P1', 'P2', 'P3'} and not title_hits:
            study_title = re.search(r'percept|readability|evaluat|user preference|visual quality|subjective',title)
            core = [(s,h) for s,h in core if (s in intro or (study_title and FOCUS.search(s))) and re.search(r'\b(?:study|studies|investigat\w*|experiment\w*|benchmark\w*|dataset|perception|perceptual)\b',s)]
        if code == 'S3' and 'compressed sensing' in title:
            title_hits = []; matches = []; core = []
        if code == 'V1' and re.search(r'\b(?:mesh|triangulated|surface)\w*', title) and not re.search(r'\b(?:visuali[sz]\w*|isosurface\w*|render\w*|flow)\b', title):
            title_hits = []; matches = []; core = []
        repeated = len(matches) >= 2 or len({h for _, hits in core for h in hits}) >= 2
        contribution = any(FOCUS.search(s) for s, _ in core)
        if title_hits:
            evidence.append({'area': area, 'subtopic': name, 'basis': 'title', 'terms': title_hits[:4], 'snippet': title[:240]})
        elif core and (repeated or contribution):
            sentence, hits = next(((s,h) for s,h in core if FOCUS.search(s)), core[0])
            evidence.append({'area': area, 'subtopic': name, 'basis': 'abstract', 'terms': hits[:4], 'snippet': sentence[:320]})
        elif core:
            candidates.append(name)
    areas = [area for area in TOPICS if any(e['area'] == area for e in evidence)]
    details = [name for name in SUBTOPICS if any(e['subtopic'] == name for e in evidence)]
    basis = 'abstract-supported' if any(e['basis'] == 'abstract' for e in evidence) else 'title-supported' if evidence else 'needs-review'
    return {'topics': areas or [UNCLASSIFIED], 'subtopics': details or [UNCLASSIFIED],
            'version': VERSION, 'basis': basis, 'evidence': evidence,
            'review_candidates': candidates, 'abstract_available': bool(abstract)}

def classify(title, abstract=''):
    result = classify_with_evidence(title, abstract)
    return result['topics'], result['subtopics']
