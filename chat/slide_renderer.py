"""
Slide Renderer - Convert slide JSON content to HTML
Modern, beautiful slide rendering with Tailwind CSS
"""
import markdown
import re
from html import escape


def render_slide_to_html(slide_obj, theme_config=None):
    """
    Render a single slide to HTML
    slide_obj can be a Slide model instance or a dict with content, layout, and deck
    """
    # Handle both model instances and dicts
    if hasattr(slide_obj, 'deck'):
        # Model instance
        if theme_config is None:
            theme_config = slide_obj.deck.get_theme_config()
        content = slide_obj.content or {}
        layout = slide_obj.layout
    else:
        # Dict format (for export service)
        if theme_config is None:
            theme_config = slide_obj.get('theme_config', {})
        content = slide_obj.get('content', {})
        layout = slide_obj.get('layout', 'content')
    
    # Layout dispatch
    renderers = {
        'title': render_title_slide,
        'content': render_content_slide,
        'two-column': render_two_column_slide,
        'image-text': render_image_text_slide,
        'text-image': render_text_image_slide,
        'full-image': render_full_image_slide,
        'quote': render_quote_slide,
        'data': render_data_slide,
        'section': render_section_slide,
        'blank': render_blank_slide,
    }
    
    renderer = renderers.get(layout, render_content_slide)
    return renderer(content, theme_config, slide_obj)


def markdown_to_html(text):
    """Convert markdown to HTML"""
    if not text:
        return ''
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code'])


def render_title_slide(content, theme, slide):
    """Title slide layout"""
    title = escape(content.get('title', ''))
    subtitle = escape(content.get('subtitle', ''))
    author = escape(content.get('author', ''))
    date = escape(content.get('date', ''))
    
    bg_style = get_background_style(content.get('background'), theme)
    
    text_color = theme['text']
    return f'''
    <div class="slide-title flex flex-col items-center justify-center text-center p-16 h-full" style="{bg_style}">
        <div class="max-w-4xl">
            <h1 class="text-6xl font-bold mb-6 leading-tight" style="color: {text_color}">
                {title or 'Untitled Presentation'}
            </h1>
            {f'<p class="text-2xl mb-8 opacity-80" style="color: ' + text_color + '">' + subtitle + '</p>' if subtitle else ''}
            <div class="mt-12 flex items-center justify-center gap-8 text-lg opacity-60" style="color: {text_color}">
                {f'<span>{author}</span>' if author else ''}
                {f'<span>•</span><span>{date}</span>' if date else ''}
            </div>
        </div>
    </div>
    '''


def render_content_slide(content, theme, slide):
    """Standard content slide"""
    title = escape(content.get('title', ''))
    body_content = content.get('content', '')
    bullets = content.get('bullets', [])
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    # Build content HTML
    body_html = ''
    if body_content:
        body_html = f'<div class="prose prose-lg max-w-none" style="color: {text_color}">{markdown_to_html(body_content)}</div>'
    
    bullets_html = ''
    if bullets:
        bullets_list = ''.join([f'<li class="mb-3 text-xl flex items-start gap-3"><span class="inline-block w-2 h-2 rounded-full mt-2.5 flex-shrink-0" style="background: {accent_color}"></span><span>{escape(b)}</span></li>' for b in bullets])
        bullets_html = f'<ul class="list-none mt-6 space-y-2">{bullets_list}</ul>'
    
    title_html = f'<h2 class="text-4xl font-bold mb-8" style="color: {text_color}">{title}</h2>' if title else ''
    
    return f'''
    <div class="slide-content flex flex-col p-16 h-full" style="{bg_style}">
        {title_html}
        <div class="flex-1">
            {body_html}
            {bullets_html}
        </div>
    </div>
    '''


def render_two_column_slide(content, theme, slide):
    """Two column layout"""
    title = escape(content.get('title', ''))
    left_content = content.get('left_content', '')
    right_content = content.get('right_content', '')
    left_bullets = content.get('left_bullets', [])
    right_bullets = content.get('right_bullets', [])
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    def build_column(content_text, bullets, side):
        html = ''
        if content_text:
            html += f'<div class="prose" style="color: {text_color}">{markdown_to_html(content_text)}</div>'
        if bullets:
            bullets_list = ''.join([f'<li class="mb-2 flex items-start gap-2"><span class="inline-block w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0" style="background: {accent_color}"></span><span>{escape(b)}</span></li>' for b in bullets])
            html += f'<ul class="list-none mt-4 space-y-1">{bullets_list}</ul>'
        return html or f'<p class="text-gray-400 italic">Click to edit {side} content...</p>'
    
    title_html = f'<h2 class="text-4xl font-bold mb-8" style="color: {text_color}">{title}</h2>' if title else ''
    
    return f'''
    <div class="slide-two-column flex flex-col p-16 h-full" style="{bg_style}">
        {title_html}
        <div class="flex-1 grid grid-cols-2 gap-12">
            <div class="left-column">{build_column(left_content, left_bullets, 'left')}</div>
            <div class="right-column">{build_column(right_content, right_bullets, 'right')}</div>
        </div>
    </div>
    '''


def render_image_text_slide(content, theme, slide):
    """Image left, text right"""
    title = escape(content.get('title', ''))
    body_content = content.get('content', '')
    image = content.get('image', {})
    bullets = content.get('bullets', [])
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    image_url = image.get('url', '')
    image_html = ''
    if image_url:
        image_html = f'''
        <div class="flex-1 flex items-center justify-center">
            <img src="{escape(image_url)}" alt="Slide image" class="max-w-full max-h-[500px] object-contain rounded-lg shadow-2xl" />
        </div>
        '''
    
    body_html = ''
    if body_content:
        body_html = f'<div class="prose prose-lg" style="color: {text_color}">{markdown_to_html(body_content)}</div>'
    
    bullets_html = ''
    if bullets:
        bullets_list = ''.join([f'<li class="mb-3 text-lg flex items-start gap-3"><span class="inline-block w-2 h-2 rounded-full mt-2 flex-shrink-0" style="background: {accent_color}"></span><span>{escape(b)}</span></li>' for b in bullets])
        bullets_html = f'<ul class="list-none mt-4 space-y-1">{bullets_list}</ul>'
    
    title_html = f'<h2 class="text-3xl font-bold mb-6" style="color: {text_color}">{title}</h2>' if title else ''
    
    return f'''
    <div class="slide-image-text flex flex-col p-16 h-full" style="{bg_style}">
        {title_html}
        <div class="flex-1 grid grid-cols-2 gap-12 items-center">
            {image_html}
            <div>
                {body_html}
                {bullets_html}
            </div>
        </div>
    </div>
    '''


def render_text_image_slide(content, theme, slide):
    """Text left, image right"""
    title = escape(content.get('title', ''))
    body_content = content.get('content', '')
    image = content.get('image', {})
    bullets = content.get('bullets', [])
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    image_url = image.get('url', '')
    image_html = ''
    if image_url:
        image_html = f'<img src="{escape(image_url)}" alt="Slide image" class="max-w-full max-h-[500px] object-contain rounded-lg shadow-2xl" />'
    
    body_html = ''
    if body_content:
        body_html = f'<div class="prose prose-lg" style="color: {text_color}">{markdown_to_html(body_content)}</div>'
    
    bullets_html = ''
    if bullets:
        bullets_list = ''.join([f'<li class="mb-3 text-lg flex items-start gap-3"><span class="inline-block w-2 h-2 rounded-full mt-2 flex-shrink-0" style="background: {accent_color}"></span><span>{escape(b)}</span></li>' for b in bullets])
        bullets_html = f'<ul class="list-none mt-4 space-y-1">{bullets_list}</ul>'
    
    title_html = f'<h2 class="text-3xl font-bold mb-6" style="color: {text_color}">{title}</h2>' if title else ''
    
    return f'''
    <div class="slide-text-image flex flex-col p-16 h-full" style="{bg_style}">
        {title_html}
        <div class="flex-1 grid grid-cols-2 gap-12 items-center">
            <div>
                {body_html}
                {bullets_html}
            </div>
            <div class="flex items-center justify-center">{image_html}</div>
        </div>
    </div>
    '''


def render_full_image_slide(content, theme, slide):
    """Full screen image slide"""
    title = escape(content.get('title', ''))
    subtitle = escape(content.get('subtitle', ''))
    image = content.get('image', {})
    caption = escape(image.get('caption', ''))
    
    image_url = image.get('url', '')
    
    bg_style = get_background_style(content.get('background'), theme)
    
    if image_url:
        title_html = f'<div class="absolute bottom-16 left-16 right-16 text-white"><h2 class="text-4xl font-bold mb-2">{title}</h2>' if title else ''
        subtitle_html = f'<p class="text-xl opacity-80">{subtitle}</p>' if subtitle else ''
        title_close = '</div>' if title else ''
        caption_html = f'<div class="absolute bottom-4 right-16 text-white/60 text-sm italic">{caption}</div>' if caption else ''
        return f'''
        <div class="slide-full-image relative h-full w-full overflow-hidden">
            <img src="{escape(image_url)}" alt="Full screen" class="absolute inset-0 w-full h-full object-cover" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/30"></div>
            {title_html}{subtitle_html}{title_close}
            {caption_html}
        </div>
        '''
    
    return f'''
    <div class="slide-full-image flex items-center justify-center h-full" style="{bg_style}">
        <p class="text-gray-400">No image selected</p>
    </div>
    '''


def render_quote_slide(content, theme, slide):
    """Quote slide"""
    quote = content.get('quote', {})
    quote_text = escape(quote.get('text', content.get('content', '')))
    author = escape(quote.get('author', content.get('author', '')))
    title = escape(content.get('title', ''))
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    title_html = f'<h3 class="text-2xl font-semibold mb-8 opacity-60" style="color: {text_color}">{title}</h3>' if title else ''
    author_html = f'<footer class="text-xl opacity-60" style="color: {text_color}">— {author}</footer>' if author else ''
    
    return f'''
    <div class="slide-quote flex flex-col items-center justify-center p-20 h-full text-center" style="{bg_style}">
        {title_html}
        <blockquote class="max-w-4xl">
            <p class="text-4xl font-light leading-relaxed mb-8" style="color: {text_color}">
                <span class="text-6xl opacity-40" style="color: {accent_color}">"</span>
                {quote_text or 'Add your quote here...'}
                <span class="text-6xl opacity-40" style="color: {accent_color}">"</span>
            </p>
            {author_html}
        </blockquote>
    </div>
    '''


def render_data_slide(content, theme, slide):
    """Data/chart slide"""
    title = escape(content.get('title', ''))
    chart = content.get('chart', {})
    data_points = content.get('data_points', [])
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    # Build simple bar chart visualization
    chart_html = ''
    if data_points:
        max_val = max([d.get('value', 0) for d in data_points]) if data_points else 1
        bars = ''
        for d in data_points:
            label = escape(d.get('label', ''))
            value = d.get('value', 0)
            height_pct = (value / max_val * 100) if max_val > 0 else 0
            bars += f'''
            <div class="flex flex-col items-center gap-2">
                <div class="w-16 bg-gradient-to-t rounded-t-lg relative group cursor-pointer" style="height: {height_pct * 3}px; background: {accent_color}">
                    <span class="absolute -top-8 left-1/2 -translate-x-1/2 text-sm font-bold opacity-0 group-hover:opacity-100 transition-opacity" style="color: {text_color}">{value}</span>
                </div>
                <span class="text-sm opacity-70" style="color: {text_color}">{label}</span>
            </div>
            '''
        chart_html = f'<div class="flex items-end justify-center gap-8 h-64 mt-8">{bars}</div>'
    
    return f'''
    <div class="slide-data flex flex-col p-16 h-full" style="{bg_style}">
        <h2 class="text-4xl font-bold mb-8" style="color: {text_color}">{title or 'Data Visualization'}</h2>
        <div class="flex-1 flex flex-col justify-center">
            {chart_html}
        </div>
    </div>
    '''


def render_section_slide(content, theme, slide):
    """Section divider slide"""
    title = escape(content.get('title', ''))
    subtitle = escape(content.get('subtitle', ''))
    section_number = content.get('section_number', '')
    
    bg_style = get_background_style(content.get('background'), theme)
    text_color = theme['text']
    accent_color = theme['accent']
    
    section_num_html = f'<span class="text-8xl font-bold opacity-20 mb-4" style="color: {accent_color}">{section_number}</span>' if section_number else ''
    subtitle_html = f'<p class="text-2xl opacity-70" style="color: {text_color}">{subtitle}</p>' if subtitle else ''
    
    return f'''
    <div class="slide-section flex flex-col items-center justify-center p-16 h-full text-center" style="{bg_style}">
        {section_num_html}
        <h1 class="text-5xl font-bold mb-4" style="color: {text_color}">{title or 'Section Title'}</h1>
        {subtitle_html}
        <div class="mt-12 w-24 h-1 rounded-full" style="background: {accent_color}"></div>
    </div>
    '''


def render_blank_slide(content, theme, slide):
    """Blank slide"""
    bg_style = get_background_style(content.get('background'), theme)
    custom_html = content.get('custom_html', '')
    
    if custom_html:
        return f'<div class="slide-blank h-full" style="{bg_style}">{custom_html}</div>'
    
    return f'''
    <div class="slide-blank flex items-center justify-center h-full" style="{bg_style}">
        <p class="text-gray-400 italic">Blank slide - click to edit</p>
    </div>
    '''


def get_background_style(background, theme):
    """Generate background CSS style"""
    if not background:
        return f"background: {theme['bg']}"
    
    bg_type = background.get('type', 'color')
    value = background.get('value', '')
    
    if bg_type == 'color':
        return f"background: {value or theme['bg']}"
    elif bg_type == 'gradient':
        return f"background: {value or theme['bg']}"
    elif bg_type == 'image':
        return f"background-image: url({value}); background-size: cover; background-position: center;"
    
    return f"background: {theme['bg']}"


def render_deck_to_html(deck, slides):
    """Render entire deck to single HTML for export"""
    theme = deck.get_theme_config() if hasattr(deck, 'get_theme_config') else deck.get('theme_config', {})
    
    slides_html = ''
    for slide in slides:
        slide_dict = {
            'content': slide.content if hasattr(slide, 'content') else slide.get('content', {}),
            'layout': slide.layout if hasattr(slide, 'layout') else slide.get('layout', 'content'),
            'theme_config': theme
        }
        slide_html = render_slide_to_html(slide_dict, theme)
        slides_html += f'''
        <div class="slide-page" style="page-break-after: always; width: 100%; height: 100vh; overflow: hidden;">
            {slide_html}
        </div>
        '''
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{deck.title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @page {{ size: {'297mm 210mm' if deck.aspect_ratio == '16:9' else '297mm 223mm'}; margin: 0; }}
        body {{ margin: 0; font-family: system-ui, -apple-system, sans-serif; }}
        .slide-page {{ page-break-after: always; }}
    </style>
</head>
<body class="bg-white">
    {slides_html}
</body>
</html>'''
