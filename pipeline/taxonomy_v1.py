"""CG-specific, transparent multi-label title rules; not official paper tracks."""
import re
TAXONOMY = {
 'Rendering': {
  'Light transport & sampling':r'render|light transport|path trac|ray trac|monte carlo|global illumination|radiosity|sampling',
  'Shading & appearance':r'shad|reflectance|\bbrdf\b|\bbsdf\b|appearance|subsurface|illumination|material',
  'Inverse rendering':r'inverse render|inverse graphics|inverse light|reflectance estimat|material estimat',
 },
 'Geometry & Modeling': {
  'Meshes & geometry processing':r'\bmesh\w*|geometry|geometric|surface|manifold|parametriz|parameteriz|triangulat',
  'Shape modeling & reconstruction':r'\bshape\b|modeling|modelling|reconstruct|point cloud|point set|implicit|signed distance',
  'Procedural & scene modeling':r'procedural|scene (generat|synthes|model)|urban|building|terrain|vegetation',
 },
 'Animation & Simulation': {
  'Character animation & motion':r'animat|character|skeletal|skinning|motion (captur|synthes|generat)|locomotion|avatar',
  'Fluids & physical simulation':r'simulat|fluid|smoke|\bfire\b|liquid|hydrodynamic|particle|rigid.body|physics',
  'Deformation, cloth & hair':r'deform|elastic|cloth|\bhair\b|\bfur\b|garment|fracture',
 },
 'Neural & Generative Graphics': {
  'Neural rendering & radiance fields':r'neural render|radiance field|gaussian splat|\bnerf\b|novel.view',
  'Generative models & diffusion':r'generativ|diffusion|\bgan\b|text.to.|flow.matching',
  'Learning for graphics':r'neural|deep learn|machine learn|learning.based|learned|differentiable|reinforcement learn',
 },
 'Images & Computational Photography': {
  'Image processing & restoration':r'image|photograph|denois|deblur|super.resolution|inpaint|tone.map|retarget',
  'Cameras, optics & displays':r'camera|optic|lens|display|hologra|light.field|light field|high.dynamic',
  'Video & image editing':r'video|image edit|composit|matting|style transfer|image styl',
 },
 'Visualization & Visual Analytics': {
  'Scientific & volume visualization':r'visualiz|visualis|volume|volumetric|scientific|isosurface|flow field',
  'Information visualization':r'\bchart\b|\bgraphs?\b|\bnetwork\b|dashboard|scatterplot|parallel coordinate|treemap',
  'Visual analytics & data exploration':r'visual analy|data explor|sensemak|explainab|interpretab|visual explor',
 },
 'XR & Interaction': {
  'Virtual & augmented reality':r'virtual reality|augmented reality|mixed reality|\bvr\b|\bar\b|\bxr\b|immersive',
  'Interaction & interfaces':r'interact|interface|gesture|touch|sketch|user.input|selection technique',
  'Haptics & embodied experiences':r'haptic|tactile|embodi|telepresence|virtual human',
 },
 'Fabrication & Materials': {
  'Computational fabrication':r'fabricat|3d.print|additive manufactur|laser cut|cnc|manufactur',
  'Material & structure design':r'metamaterial|microstructur|structural design|topology optim|architected|mechanical',
  'Texture & pattern design':r'texture|pattern|weav|knit|mosaic|stippl|halfton',
 },
 'Systems & Real-Time Graphics': {
  'Real-time rendering & engines':r'real.time|game|rasteriz|rasteris|rendering pipeline',
  'GPU & parallel computing':r'\bgpu\b|parallel|hardware|graphics processor|graphics processing',
  'Efficiency & compression':r'efficien|accelerat|compress|level.of.detail|memory|out.of.core|streaming',
 },
 'Perception & Evaluation': {
  'Visual perception':r'percept|perceiv|psychophys|visual attention|salien|gaze|eye.track',
  'User studies & evaluation':r'user stud|evaluat|usability|human.factor|user.experience',
  'Quality, metrics & benchmarks':r'quality|metric|benchmark|dataset|data set|fidelity',
 },
}
PATTERNS={g:{n:re.compile(r,re.I) for n,r in ts.items()} for g,ts in TAXONOMY.items()}
TOPICS=list(TAXONOMY)
SUBTOPICS=[t for ts in TAXONOMY.values() for t in ts]
def classify(title):
    areas,details=[],[]
    for group,patterns in PATTERNS.items():
        found=[n for n,p in patterns.items() if p.search(title)]
        if found: areas.append(group);details.extend(found)
    return areas or ['Other / Unclassified'],details or ['Other / Unclassified']
