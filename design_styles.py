"""Supported visual vocabulary and explainable, local recommendation rubric."""
import html
import re


def style(name, explanation, characteristics, uses, downside, tags, compatible):
    return dict(name=name, explanation=explanation, characteristics=characteristics,
                use_cases=uses, downside=downside, tags=tags, compatible=compatible)


STYLES = {
 'Minimalism': style('Minimalism','Let the essential content do the work.','Open space, few colours, clear type and quiet decoration.','Tools, portfolios, product pages.','Too little hierarchy or content can feel empty.', ['clear','calm','accessible','professional'], ['Bento UI','Editorial Design','Glassmorphism','Material Design','Flat Design']),
 'Maximalism': style('Maximalism','Layer colour, type and imagery with deliberate abundance.','Dense composition, expressive patterns and multiple focal points.','Art, music, expressive brands.','Needs disciplined hierarchy; can overwhelm readers and small screens.', ['art','bold','expressive','dense'], ['Retro Design','Y2K Design']),
 'Glassmorphism': style('Glassmorphism','Use translucent layers to suggest depth.','Blurred panels, translucent edges and a visible backdrop.','Technology showcases and compact overlays.','Contrast and rendering cost need care; avoid using it behind long text.', ['technology','futuristic','layered'], ['Minimalism','Bento UI']),
 'Neumorphism': style('Neumorphism','Make controls appear pressed into a soft surface.','Same-colour surfaces, paired shadows and shallow depth.','Small experimental control panels.','Weak boundaries and subtle states often reduce accessibility.', ['soft','tactile','experimental'], ['Minimalism']),
 'Claymorphism': style('Claymorphism','Give a few elements a rounded, soft clay-like appearance.','Padded shapes, warm colour and gentle dimensional shading.','Playful learning and friendly introductions.','Can feel childish or consume space in dense workflows.', ['playful','education','friendly'], ['Material Design']),
 'Brutalism': style('Brutalism','Expose structure with a deliberately raw visual voice.','Plain type, hard edges, exposed grids and few embellishments.','Artist portfolios and experimental publishing.','Unfamiliar navigation or weak polish can frustrate visitors.', ['raw','art','experimental'], ['Editorial Design']),
 'Neo-Brutalism': style('Neo-Brutalism','Combine bold graphic colour with hard, obvious boundaries.','Heavy outlines, offset shadows and blunt typography.','Independent products and bold creative brands.','High visual intensity can tire users in long sessions.', ['bold','independent','playful'], ['Flat Design']),
 'Skeuomorphism': style('Skeuomorphism','Borrow recognisable shapes from physical objects.','Material cues, realistic controls and familiar object metaphors.','Audio tools, instrument panels and tactile experiences.','Detailed assets and object metaphors can scale poorly.', ['tactile','audio','familiar'], ['Retro Design']),
 'Flat Design': style('Flat Design','Communicate with simple two-dimensional shapes.','Solid fills, crisp icons, clean edges and little depth.','Mobile interfaces, simple tools and navigation.','Clickable elements still need clear borders and interaction states.', ['mobile','clear','simple'], ['Material Design','Minimalism','Neo-Brutalism']),
 'Material Design': style('Material Design','Use predictable hierarchy and consistent interaction states.','Structured spacing, clear controls and restrained elevation.','Dashboards, education and complex interactive tools.','Can feel conventional without a distinct brand voice.', ['dashboard','accessible','interaction','education'], ['Flat Design','Minimalism','Bento UI']),
 'Bento UI': style('Bento UI','Group related content into a deliberate grid of different sizes.','Modular panels, clear grouping and varied emphasis.','Dashboards, feature summaries and developer tools.','A grid of unrelated boxes makes reading order confusing.', ['dashboard','developer','dense','organised'], ['Minimalism','Material Design','Cyberpunk','Glassmorphism']),
 'Y2K Design': style('Y2K Design','Reference the playful digital culture of the early 2000s.','Chrome-like details, bright colour and expressive digital type.','Music, fashion and nostalgic creative projects.','Novelty can compete with reading and age quickly.', ['nostalgia','fashion','playful'], ['Maximalism','Retro Design']),
 'Retro Design': style('Retro Design','Choose a specific earlier era as a visual reference.','Era-specific type, print-like colour or pixel motifs.','Cultural projects, games and nostalgic brands.','Mixing unrelated eras can become a costume rather than a coherent system.', ['nostalgia','games','warm'], ['Editorial Design','Skeuomorphism','Y2K Design','Maximalism']),
 'Cyberpunk': style('Cyberpunk','Use a restrained high-contrast futuristic visual language.','Dark grounds, bright signals, angular structure and technical type.','Games and expressive technology showcases.','Neon, tiny type and motion can make routine work harder.', ['futuristic','technology','games','bold'], ['Bento UI']),
 'Editorial Design': style('Editorial Design','Arrange content with the rhythm of a well-edited publication.','Strong type hierarchy, varied columns and thoughtful reading order.','Magazines, blogs and storytelling portfolios.','Dramatic type and columns must adapt carefully to phones.', ['reading','portfolio','magazine','story'], ['Minimalism','Brutalism','Retro Design']),
}

CONFLICTS = {
 frozenset(['Minimalism','Maximalism']): 'One removes visual density while the other celebrates it. Choose which controls the main reading experience.',
 frozenset(['Neumorphism','Neo-Brutalism']): 'Soft low-contrast depth conflicts with strong outlines and hard offset shadows.',
 frozenset(['Neumorphism','Cyberpunk']): 'Soft, subtle surfaces and intense graphic signals pull interaction states in different directions.',
 frozenset(['Brutalism','Glassmorphism']): 'Raw exposed structure and polished translucent layers need separate roles.',
}


def compatibility(selected):
    warnings=[]
    for i, left in enumerate(selected):
        for right in selected[i+1:]:
            pair=frozenset([left,right])
            if pair in CONFLICTS:warnings.append(f'{left} + {right}: {CONFLICTS[pair]}')
            elif right not in STYLES[left]['compatible'] and left not in STYLES[right]['compatible']:
                warnings.append(f'{left} + {right}: not a standard pairing. Define a primary style and limit the other to a specific role.')
    return warnings


def recommend(requirements, initial=''):
    """Rank by explicit preference, content and interaction needs; never claim model inference."""
    text=' '.join(str(v.get('value','')) if isinstance(v,dict) else str(v) for v in requirements.values())+' '+initial
    text=text.lower()
    scores={name:0 for name in STYLES};reasons={name:[] for name in STYLES}
    def add(names, points, why):
        for name in names:scores[name]+=points;reasons[name].append(why)
    groups=[
      (r'dashboard|developer|coding|diagnostic|analytics', ['Bento UI','Material Design','Minimalism'],4,'Organise complex information and keep frequent controls readable.'),
      (r'portfolio|writer|magazine|blog|journal|article', ['Editorial Design','Minimalism'],4,'Give reading order and individual work a strong hierarchy.'),
      (r'future|futuristic|technology|robot', ['Glassmorphism','Minimalism','Cyberpunk'],3,'A technical identity fits, with restrained effects around readable content.'),
      (r'child|playful|learn|education|school', ['Material Design','Claymorphism','Flat Design'],3,'Clear feedback and friendly shapes support learning.'),
      (r'artist|music|bold|expressive', ['Neo-Brutalism','Maximalism','Editorial Design'],3,'A distinctive visual voice suits the requested creative identity.'),
      (r'retro|nostalgi|vintage|1990|1980', ['Retro Design','Y2K Design'],5,'An explicitly nostalgic direction should guide the visual language.'),
      (r'mobile|accessible|accessibility|calm|simple', ['Minimalism','Material Design','Flat Design'],2,'Readable boundaries and predictable controls help mobile and accessible use.'),
      (r'audio|instrument|mixer', ['Skeuomorphism','Material Design'],3,'Familiar controls can make a specialised tool easier to understand.'),
    ]
    for pattern,names,points,why in groups:
        if re.search(pattern,text):
            add(names,points,why)
            add(names[:1],4,why)
    explicit=requirements.get('selected_styles',{}).get('value','')
    for name in STYLES:
        if name.lower() in text:add([name],6,'This style is explicitly mentioned in your requirements.')
        if name in explicit:add([name],20,'This is your selected direction; your preference takes precedence.')
    if not any(scores.values()):add(['Minimalism','Flat Design','Editorial Design'],1,'A readable starting point while the purpose and audience are clarified.')
    order=sorted(STYLES,key=lambda name:(-scores[name],list(STYLES).index(name)))[:3]
    return [dict(name=name, reason=' '.join(dict.fromkeys(reasons[name])), tradeoff=STYLES[name]['downside']) for name in order]


def recommended_combination(ranked):
    first=ranked[0]['name']
    if first in ('Bento UI','Glassmorphism','Editorial Design','Material Design'):
        return [first,'Minimalism']
    return [first]


def preview(name):
    """Authored CSS illustration, not a screenshot or an AI-generated recommendation."""
    slug=list(STYLES).index(name)
    title=html.escape(name)
    return (f'<div class="style-sample sample-{slug}" role="img" aria-label="{title} illustrative composition">'
            '<span class="sample-kicker">FORM / FUNCTION</span><strong>A different<br>point of view.</strong>'
            '<div class="sample-modules"><i></i><i></i><i></i></div><span class="sample-action">Explore →</span></div>')
