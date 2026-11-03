"""A local creative playground, separated from real projects and inference."""
import html
import streamlit as st
from project_store import list_runs
from text_safety import markdown_text
from web_documents import preview_frame_html
from studio_examples import EXAMPLES, STYLES, example_html
from canvas_story import render_story

SAMPLE = example_html('Photographer portfolio')

def choose_example(name):
    st.session_state['demo_example']=name
    st.session_state['studio_idea']=EXAMPLES[name]['idea']

def frame(document, title, width='Fit'):
    size={'Fit':'100%', 'Desktop':'1280px', 'Tablet':'768px', 'Mobile':'390px'}[width]
    st.markdown('<div class="demo-scroll"><div style="width:'+size+'">'+preview_frame_html(document,title)+'</div></div>', unsafe_allow_html=True)

def render_welcome(pages):
    with st.container(horizontal=True, key='studio-header'):
        st.html('<div class="studio-wordmark"><span aria-hidden="true">[↗</span> Synthetix</div>')
        st.markdown('[How it works](#how-it-works)')
        if st.session_state.get('run_folder'):st.page_link(pages['workspace'],label='Open workspace ↗')
        st.page_link(pages['host'],label='Import HTML')
    st.html('<div class="studio-hero"><p class="studio-kicker">AN IDEA IS A GOOD PLACE TO START / 01</p><h1><span class="hero-mask"><span>Make something</span></span><span class="hero-mask"><em>worth opening.</em></span></h1><p>Turn a small idea into a website you can shape, test, and refine.</p></div>')
    name=st.session_state.get('demo_example','Photographer portfolio')
    item=EXAMPLES[name]
    if 'studio_idea' not in st.session_state:st.session_state['studio_idea']=item['idea']
    left,right=st.columns([1,1.7],gap='large')
    with left,st.container(key='studio-intro'):
        idea=st.text_area('WHAT ARE WE MAKING?',key='studio_idea',persist_state='session',height=150,max_chars=3800,placeholder='A portfolio for a photographer who loves bold type and quiet landscapes.')
        st.caption('Try a prebuilt example · no AI call')
        for example in EXAMPLES:
            st.button(example,key='example-'+example,on_click=choose_example,args=(example,),width='stretch',type='secondary')
        if st.button('Start this project ↗',type='primary',width='stretch'):
            if not idea.strip():st.warning('Describe your idea or choose an example first.')
            else:
                st.session_state['planning_seed']=idea
                for key in ('run_folder','design_plan','design_interview_id'):st.session_state.pop(key,None)
                st.query_params.pop('interview',None)
                st.switch_page(pages['build'])
        st.page_link(pages['host'],label='Import HTML',icon=':material/code:')
        st.page_link(pages['repair'],label='Test and repair code',icon=':material/build:')
        st.caption('Real projects begin with planning. You approve the editable brief before generation.')
    with right,st.container(key='studio-demo',border=True):
        st.html('<div class="hero-planes" aria-hidden="true"><i></i><i></i></div>')
        st.html('<div class="demo-toolbar"><strong>'+html.escape(item['name'])+' / index.html</strong><span class="sample-label">Interactive demo · Prebuilt examples</span></div>')
        width=st.radio('Demo preview width',['Fit','Desktop','Tablet','Mobile'],horizontal=True,key='demo_width')
        style=st.session_state.get('demo_style','Editorial')
        preview,code,checks=st.tabs(['Preview','Code','Checks'])
        document=example_html(name,style)
        with preview:frame(document,'Prebuilt '+name,width)
        with code:st.code(document,language='html')
        with checks:st.info('Not tested in your project. This prebuilt example is separate from real project reports. The walkthrough below uses explicitly simulated evidence.')
        style=st.radio('Starting direction',STYLES,horizontal=True,key='demo_style')
        miniatures = '<div class="style-miniatures" aria-hidden="true"><div><b>Aa</b><i></i><small>Editorial / asymmetry + serif</small></div><div><b>MAKE<br>IT BIG.</b><i></i><small>Bold grid / dark + type</small></div><div><b>Less, considered.</b><i></i><small>Quiet minimal / stacked + space</small></div></div>'
        selected_index = STYLES.index(style)
        parts = miniatures.split('<div>')
        miniatures = '<div>'.join(parts[:selected_index+1]) + '<div class="preview-selected">' + '<div>'.join(parts[selected_index+1:])
        st.html(miniatures)
        st.html('<span class="style-selection-label">Selected direction · '+html.escape(style)+'</span>')
        st.html('<div class="sample-brief"><strong>Selected sample brief</strong><br><b>Audience:</b> '+html.escape(item['audience'])+'<br><b>Structure:</b> '+html.escape(item['structure'])+'<br><b>Interaction:</b> '+html.escape(item['interaction'])+'<br><b>Direction:</b> '+html.escape(style)+'</div>')
    st.html(render_story())
    if st.button('Start your project ↗', key='story-start', type='primary'):
        st.session_state['planning_seed']=st.session_state.get('studio_idea','')
        for key in ('run_folder','design_plan','design_interview_id'):st.session_state.pop(key,None)
        st.query_params.pop('interview',None)
        st.switch_page(pages['build'])
    st.divider()
    st.subheader('Keep making.')
    runs=list_runs()
    if not runs:st.caption('No saved projects yet. Start with your idea above, or import HTML.')
    for item in runs[:3]:
        with st.expander(markdown_text(item['title'])+' · '+str(len(item['versions']))+' version(s)'):
            st.caption(item['mode'])
            if st.button('Open project ↗',key='welcome-'+item['folder'].name):
                st.session_state['run_folder']=str(item['folder']);st.switch_page(pages['workspace'])
