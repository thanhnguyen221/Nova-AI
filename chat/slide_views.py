"""
Slide Views - API endpoints for slide deck management
Full CRUD + Export functionality
"""
import json
import re
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile

from .models import SlideDeck, Slide, SlideExport
from .slide_service import SlideService


# ==================== PAGE VIEWS ====================

@login_required
def slide_dashboard(request):
    """Main slide dashboard - list all user's decks"""
    decks = SlideDeck.objects.filter(user=request.user).prefetch_related('slides')

    return render(request, 'chat/slides/dashboard.html', {
        'decks': decks,
    })


@login_required
def slide_editor(request, deck_id):
    """Slide editor interface"""
    import json
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slides_qs = deck.slides.all()

    # Serialize slides to JSON for JavaScript
    slides_data = [{
        'id': s.id,
        'order': s.order,
        'layout': s.layout,
        'content': s.content
    } for s in slides_qs]

    return render(request, 'chat/slides/editor.html', {
        'deck': deck,
        'slides_json': json.dumps(slides_data),
        'theme_config_json': json.dumps(deck.get_theme_config()),
    })


@login_required
def slide_present(request, deck_id):
    """Presentation view - fullscreen slide show"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slides = deck.slides.all()
    
    return render(request, 'chat/slides/present.html', {
        'deck': deck,
        'slides': slides,
        'theme_config': deck.get_theme_config(),
    })


# ==================== API VIEWS ====================

@login_required
@require_POST
def create_deck(request):
    """Create a new slide deck with optional AI generation"""
    try:
        data = json.loads(request.body)
        title = data.get('title') or 'Untitled Presentation'
        description = data.get('description', '')
        theme = data.get('theme', 'modern')
        aspect_ratio = data.get('aspect_ratio', '16:9')
        ai_prompt = data.get('ai_prompt', '').strip()
        
        deck = SlideService.create_deck(
            user=request.user,
            title=title,
            description=description,
            theme=theme,
            aspect_ratio=aspect_ratio
        )
        
        # If AI prompt provided, generate slides
        if ai_prompt:
            try:
                from .ai_service import generate_text_sync
                
                ai_context = f"""Bạn là chuyên gia thiết kế presentation. 
Tạo một bộ slide hoàn chỉnh cho chủ đề: "{title}"

Mô tả/Mục tiêu: {ai_prompt}

YÊU CẦU QUAN TRỌNG:
1. Slide 1 phải là title slide với title chính xác là "{title}"
2. Tạo 4-6 slides với nội dung thực tế, không placeholder
3. Nội dung phải phù hợp với chủ đề và mục tiêu đã nêu
4. Trả về JSON theo format bên dưới

Các layout hỗ trợ: title, content, two-column, quote, section, image-text

JSON FORMAT:
{{"slides": [
  {{"layout": "title", "content": {{"title": "{title}", "subtitle": "Mô tả ngắn gọn"}}}},
  {{"layout": "content", "content": {{"title": "Giới thiệu", "bullets": ["Điểm 1", "Điểm 2", "Điểm 3"]}}}},
  {{"layout": "content", "content": {{"title": "Nội dung chính", "bullets": ["Chi tiết 1", "Chi tiết 2"]}}}},
  {{"layout": "content", "content": {{"title": "Kết luận", "bullets": ["Tóm tắt", "Hành động tiếp theo"]}}}}
]}}"""
                
                ai_response = generate_text_sync(ai_context, model_name='gemini-2.0-flash')
                
                # Try to extract JSON
                import re
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    slide_data = json.loads(json_match.group())
                    slides = slide_data.get('slides', [])
                    
                    for idx, slide_info in enumerate(slides):
                        SlideService.add_slide(
                            deck=deck,
                            layout=slide_info.get('layout', 'content'),
                            order=idx,
                            content=slide_info.get('content', {})
                        )
                else:
                    # Fallback: add default slides
                    _add_default_slides(deck, title, description)
            except Exception as e:
                print(f"AI generation error: {e}")
                _add_default_slides(deck, title, description)
        else:
            # Add default title slide
            _add_default_slides(deck, title, description)
        
        return JsonResponse({
            'status': 'success',
            'deck': {
                'id': deck.id,
                'title': deck.title,
                'theme': deck.theme,
                'aspect_ratio': deck.aspect_ratio,
                'slide_count': deck.slides.count(),
                'created_at': deck.created_at.isoformat(),
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _add_default_slides(deck, title, description):
    """Add default slides to a new deck"""
    SlideService.add_slide(
        deck=deck,
        layout='title',
        order=0,
        content={
            'title': title,
            'subtitle': description or 'Created with Nova AI'
        }
    )
    
    SlideService.add_slide(
        deck=deck,
        layout='content',
        order=1,
        content={
            'title': 'Introduction',
            'bullets': ['Add your content here', 'Click on slides to edit', 'Use the AI assistant for help']
        }
    )


@login_required
def get_decks(request):
    """Get all user's slide decks"""
    decks = SlideDeck.objects.filter(user=request.user).prefetch_related('slides')
    
    data = []
    for deck in decks:
        data.append({
            'id': deck.id,
            'title': deck.title,
            'description': deck.description,
            'theme': deck.theme,
            'aspect_ratio': deck.aspect_ratio,
            'slide_count': deck.slide_count,
            'is_public': deck.is_public,
            'created_at': deck.created_at.isoformat(),
            'updated_at': deck.updated_at.isoformat(),
        })
    
    return JsonResponse({
        'status': 'success',
        'decks': data
    })


@login_required
def get_deck(request, deck_id):
    """Get a single deck with all slides"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slides = deck.slides.all()
    
    return JsonResponse({
        'status': 'success',
        'deck': {
            'id': deck.id,
            'title': deck.title,
            'description': deck.description,
            'theme': deck.theme,
            'aspect_ratio': deck.aspect_ratio,
            'is_public': deck.is_public,
            'theme_config': deck.get_theme_config(),
            'created_at': deck.created_at.isoformat(),
            'updated_at': deck.updated_at.isoformat(),
        },
        'slides': [
            {
                'id': slide.id,
                'order': slide.order,
                'layout': slide.layout,
                'content': slide.content,
                'custom_css': slide.custom_css,
                'created_at': slide.created_at.isoformat(),
            }
            for slide in slides
        ]
    })


@login_required
@require_POST
def update_deck(request, deck_id):
    """Update deck properties"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    
    try:
        data = json.loads(request.body)
        
        if 'title' in data:
            deck.title = data['title'][:255]
        if 'description' in data:
            deck.description = data['description']
        if 'theme' in data:
            deck.theme = data['theme']
        if 'aspect_ratio' in data:
            deck.aspect_ratio = data['aspect_ratio']
        if 'is_public' in data:
            deck.is_public = data['is_public']
        
        deck.save()
        
        return JsonResponse({
            'status': 'success',
            'deck': {
                'id': deck.id,
                'title': deck.title,
                'theme': deck.theme,
                'aspect_ratio': deck.aspect_ratio,
                'theme_config': deck.get_theme_config(),
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_deck(request, deck_id):
    """Delete a deck and all its slides"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    deck.delete()
    
    return JsonResponse({
        'status': 'success',
        'message': 'Deck deleted successfully'
    })


@login_required
@require_POST
def duplicate_deck(request, deck_id):
    """Duplicate a deck with all its slides"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    
    try:
        # Create new deck with "Copy of" prefix
        new_deck = SlideDeck.objects.create(
            user=request.user,
            title=f"Copy of {deck.title}",
            description=deck.description,
            theme=deck.theme,
            aspect_ratio=deck.aspect_ratio,
            is_public=False
        )
        
        # Copy all slides
        slides = deck.slides.all()
        for slide in slides:
            Slide.objects.create(
                deck=new_deck,
                layout=slide.layout,
                order=slide.order,
                content=slide.content.copy() if slide.content else {},
                custom_css=slide.custom_css
            )
        
        return JsonResponse({
            'status': 'success',
            'deck': {
                'id': new_deck.id,
                'title': new_deck.title,
                'theme': new_deck.theme,
                'aspect_ratio': new_deck.aspect_ratio,
                'slide_count': new_deck.slides.count(),
                'created_at': new_deck.created_at.isoformat(),
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ==================== SLIDE API ====================

@login_required
@require_POST
def create_slide(request, deck_id):
    """Add a new slide to deck"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    
    try:
        # Get the next order number
        last_slide = Slide.objects.filter(deck=deck).order_by('-order').first()
        next_order = (last_slide.order + 1) if last_slide else 0
        
        # Create slide directly
        slide = Slide.objects.create(
            deck=deck,
            layout='content',
            order=next_order,
            content={
                'title': 'New Slide',
                'subtitle': 'Add your content here',
                'bullets': ['Point 1', 'Point 2', 'Point 3']
            }
        )
        
        return JsonResponse({
            'status': 'success',
            'slide': {
                'id': slide.id,
                'order': slide.order,
                'layout': slide.layout,
                'content': slide.content,
            }
        })
    except Exception as e:
        import traceback
        print(f"Error creating slide: {e}")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def update_slide(request, deck_id, slide_id):
    """Update slide content or layout"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slide = get_object_or_404(Slide, id=slide_id, deck=deck)
    
    try:
        data = json.loads(request.body)
        
        if 'layout' in data:
            slide.layout = data['layout']
        if 'content' in data:
            slide.content = data['content']
        if 'order' in data:
            slide.order = data['order']
        if 'custom_css' in data:
            slide.custom_css = data['custom_css']
        
        slide.save()
        
        return JsonResponse({
            'status': 'success',
            'slide': {
                'id': slide.id,
                'order': slide.order,
                'layout': slide.layout,
                'content': slide.content,
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE", "POST"])
def delete_slide(request, deck_id, slide_id):
    """Delete a slide"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slide = get_object_or_404(Slide, id=slide_id, deck=deck)
    
    try:
        slide.delete()
        
        # Reorder remaining slides
        remaining_slides = Slide.objects.filter(deck=deck).order_by('order')
        for idx, s in enumerate(remaining_slides):
            s.order = idx
            s.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        import traceback
        print(f"Error deleting slide: {e}")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def reorder_slides(request, deck_id):
    """Reorder slides: expects {slide_orders: [[id, new_order], ...]}"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    
    try:
        data = json.loads(request.body)
        slide_orders = data.get('slide_orders', [])
        
        # Update orders in a transaction-safe way
        for slide_id, new_order in slide_orders:
            Slide.objects.filter(id=slide_id, deck=deck).update(order=new_order)
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def duplicate_slide(request, deck_id, slide_id):
    """Duplicate a slide"""
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    slide = get_object_or_404(Slide, id=slide_id, deck=deck)
    
    try:
        new_slide = SlideService.duplicate_slide(slide)
        return JsonResponse({
            'status': 'success',
            'slide': {
                'id': new_slide.id,
                'order': new_slide.order,
                'layout': new_slide.layout,
                'content': new_slide.content,
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ==================== EXPORT API ====================

@login_required
def export_deck(request, deck_id, format_type):
    """
    Export deck to various formats
    format_type: pptx, pdf, html, images
    """
    deck = get_object_or_404(SlideDeck, id=deck_id, user=request.user)
    
    try:
        filename, buffer = SlideService.export_deck(deck, format_type)
        
        # Determine content type
        content_types = {
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'pdf': 'application/pdf',
            'html': 'text/html',
            'images': 'application/zip',
        }
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type=content_types.get(format_type, 'application/octet-stream')
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Track export
        file_size = len(buffer.getvalue())
        export_record = SlideExport.objects.create(
            deck=deck,
            format=format_type,
            file=ContentFile(buffer.getvalue(), name=filename),
            file_size=file_size
        )
        
        return response
        
    except ImportError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Missing dependency: {str(e)}. Please install required packages.'
        }, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ==================== AI GENERATION ====================

@login_required
@require_POST
def generate_slides_from_chat(request):
    """
    Generate slides from conversation messages using AI
    """
    from .models import Conversation
    from .ai_service import AI_SERVICE
    
    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        prompt = data.get('prompt', '')
        
        if not conversation_id:
            return JsonResponse({'status': 'error', 'message': 'No conversation ID provided'}, status=400)
        
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        
        # Get conversation summary
        messages = conversation.messages.all().order_by('created_at')
        conversation_summary = "\n".join([
            f"{msg.role}: {msg.content[:200]}"
            for msg in messages
        ])
        
        # Build AI prompt for slide generation
        ai_prompt = f"""Bạn là một chuyên gia tạo slide thuyết trình chuyên nghiệp.

Nhiệm vụ: Tạo một bộ slide từ nội dung cuộc trò chuyện sau.

YÊU CẦU BẮT BUỘC:
1. Tạo tối thiểu 5 slide, tối đa 10 slide
2. Slide 1 phải là TITLE slide với tiêu đề chính và subtitle
3. Các slide tiếp theo phải đa dạng layout: content, two-column, quote, section
4. Nội dung phải ngắn gọn, súc tích, dễ đọc trên slide
5. Trả về JSON theo định dạng CHÍNH XÁC sau:

{{
    "title": "Tiêu đề bài thuyết trình",
    "slides": [
        {{
            "layout": "title",
            "content": {{
                "title": "Tiêu đề chính",
                "subtitle": "Tiêu đề phụ",
                "author": "Tác giả"
            }}
        }},
        {{
            "layout": "content",
            "content": {{
                "title": "Tiêu đề slide",
                "bullets": ["Điểm chính 1", "Điểm chính 2", "Điểm chính 3"]
            }}
        }},
        {{
            "layout": "two-column",
            "content": {{
                "title": "So sánh",
                "left_bullets": ["Điểm A", "Điểm B"],
                "right_bullets": ["Điểm C", "Điểm D"]
            }}
        }},
        {{
            "layout": "quote",
            "content": {{
                "quote": {{
                    "text": "Câu trích dẫn quan trọng",
                    "author": "Tác giả"
                }}
            }}
        }},
        {{
            "layout": "section",
            "content": {{
                "title": "Phần mới",
                "subtitle": "Mô tả phần này"
            }}
        }}
    ]
}}

Layout hợp lệ: title, content, two-column, image-text, text-image, quote, section, data

NỘI DUNG CUỘC TRÒ CHUYỆN:
{conversation_summary[:2000]}

YÊU CẦU THÊM TỪ NGƯỜI DÙNG:
{prompt}

CHỈ trả về JSON, không có text khác."""

        # Call AI to generate slides
        response = AI_SERVICE.generate_text(ai_prompt, model='gemini-2.0-flash')
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            slides_data = json.loads(json_match.group())
        else:
            slides_data = json.loads(response)
        
        # Create deck
        deck = SlideService.create_deck(
            user=request.user,
            title=slides_data.get('title', 'AI Generated Presentation'),
            description=f"Generated from conversation #{conversation_id}",
            theme='modern',
            aspect_ratio='16:9'
        )
        
        # Create slides
        for i, slide_data in enumerate(slides_data.get('slides', [])):
            SlideService.add_slide(
                deck=deck,
                layout=slide_data.get('layout', 'content'),
                order=i,
                content=slide_data.get('content', {})
            )
        
        return JsonResponse({
            'status': 'success',
            'deck': {
                'id': deck.id,
                'title': deck.title,
                'slide_count': deck.slides.count(),
            },
            'redirect_url': f'/slides/editor/{deck.id}/'
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'AI response parsing failed: {str(e)}'
        }, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ==================== RENDER PREVIEW ====================

@login_required
def render_slide_preview(request, slide_id):
    """Render a single slide to HTML for preview"""
    from .slide_renderer import render_slide_to_html
    
    slide = get_object_or_404(Slide, id=slide_id)
    deck = slide.deck
    
    # Check permission
    if deck.user != request.user and not deck.is_public:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    theme = deck.get_theme_config()
    html = render_slide_to_html(slide, theme)
    
    return HttpResponse(f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ margin: 0; padding: 20px; background: #1a1a1a; }}
        .slide-preview {{ 
            width: 960px; 
            height: 540px; 
            margin: 0 auto;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            border-radius: 8px;
            overflow: hidden;
        }}
    </style>
</head>
<body>
    <div class="slide-preview">{html}</div>
</body>
</html>''')


# ==================== AI ASSISTANT IN EDITOR ====================

@login_required
@require_POST
def ai_chat(request):
    """
    AI chat endpoint for slide editor assistant
    Uses GeminiChatService from chat app
    """
    try:
        data = json.loads(request.body)
        message = data.get('message', '')
        deck_id = data.get('deck_id')
        current_slide = data.get('current_slide', {})
        conversation = data.get('conversation', [])
        
        # Build context for AI
        system_context = f"""Bạn là AI Assistant trong Slide Editor của Nova AI.

Ngữ cảnh hiện tại:
- Deck ID: {deck_id}
- Slide layout: {current_slide.get('layout', 'content')}
- Slide content hiện tại: {json.dumps(current_slide.get('content', {}), ensure_ascii=False)}

Nhiệm vụ của bạn:
1. Viết/gợi ý nội dung cho slide
2. Tạo kịch bản thuyết trình
3. Đề xuất improvements cho slide hiện tại
4. Trả lời các câu hỏi về cách làm slide

Nếu user yêu cầu tạo/tìm hình ảnh, hãy trả về JSON với search_image=true và search_query.
Nếu user yêu cầu cập nhật nội dung slide, hãy trả về JSON với slide_content.

Format phản hồi:
- Text bình thường cho câu trả lời
- Hoặc JSON: {{"response": "text", "slide_content": {{...}}, "search_image": true, "search_query": "..."}}"""

        # Import generate_text_sync function from ai_service
        from .ai_service import generate_text_sync
        
        # Get active model from request or use default
        active_model = data.get('model', 'gemini-2.0-flash')
        
        # Build full prompt with system context
        full_prompt = system_context + "\n\nUser: " + message
        
        # Call AI service (non-streaming)
        response_text = generate_text_sync(full_prompt, model_name=active_model)
        
        # Try to parse JSON response
        result = {'status': 'success', 'response': response_text}
        
        try:
            # Look for JSON in response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_data = json.loads(json_match.group())
                if 'slide_content' in json_data:
                    result['slide_content'] = json_data['slide_content']
                if 'search_image' in json_data:
                    result['search_image'] = json_data['search_image']
                    result['search_query'] = json_data.get('search_query', '')
                if 'response' in json_data:
                    result['response'] = json_data['response']
        except:
            pass  # Use raw response if not valid JSON
        
        return JsonResponse(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def search_image(request):
    """Search for images using DuckDuckGo"""
    from ddgs import DDGS
    
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'status': 'error', 'message': 'No query provided'}, status=400)
    
    try:
        with DDGS() as ddgs:
            results = ddgs.images(query, max_results=5)
            if results:
                # Return first image
                image = results[0]
                return JsonResponse({
                    'status': 'success',
                    'image_url': image.get('image'),
                    'thumbnail': image.get('thumbnail'),
                    'title': image.get('title'),
                    'source': image.get('source')
                })
            else:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'No images found'
                }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def search_unsplash(request):
    """
    Search for high-quality images using Unsplash API
    Returns multiple images for slide design
    """
    import urllib.request
    import urllib.parse
    
    query = request.GET.get('q', '')
    per_page = min(int(request.GET.get('per_page', 8)), 20)  # Max 20 images
    
    if not query:
        return JsonResponse({'status': 'error', 'message': 'No query provided'}, status=400)
    
    try:
        from django.conf import settings
        access_key = settings.UNSPLASH_API_KEY if hasattr(settings, 'UNSPLASH_API_KEY') else ''
        
        # Use demo API if no key provided (limited to 50 req/hour)
        base_url = "https://api.unsplash.com/search/photos"
        params = {
            'query': query,
            'per_page': per_page,
            'orientation': 'landscape',  # Better for slides
            'order_by': 'relevant'
        }
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'Accept-Version': 'v1',
            'User-Agent': 'Nova-AI-Slide-Editor/1.0'
        }
        
        if access_key:
            headers['Authorization'] = f'Client-ID {access_key}'
        
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            images = []
            for photo in data.get('results', []):
                images.append({
                    'id': photo.get('id'),
                    'url': photo.get('urls', {}).get('regular'),  # 1080px width
                    'thumb': photo.get('urls', {}).get('small'),  # 400px width
                    'full': photo.get('urls', {}).get('full'),
                    'width': photo.get('width'),
                    'height': photo.get('height'),
                    'description': photo.get('description') or photo.get('alt_description'),
                    'author': photo.get('user', {}).get('name'),
                    'author_url': photo.get('user', {}).get('links', {}).get('html'),
                    'download_location': photo.get('links', {}).get('download_location')
                })
            
            return JsonResponse({
                'status': 'success',
                'total': data.get('total', 0),
                'total_pages': data.get('total_pages', 0),
                'images': images,
                'source': 'unsplash',
                'note': 'Images from Unsplash - Please credit photographers when using'
            })
            
    except urllib.error.HTTPError as e:
        # If Unsplash API fails (rate limit or no key), fallback to placeholder
        if e.code == 401 or e.code == 403:
            return JsonResponse({
                'status': 'success',
                'images': get_placeholder_images(query, per_page),
                'source': 'placeholder',
                'note': 'Using placeholder images. Add UNSPLASH_API_KEY to .env for real photos.'
            })
        return JsonResponse({
            'status': 'error',
            'message': f'Unsplash API error: {e.code}'
        }, status=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Fallback to placeholder images
        return JsonResponse({
            'status': 'success',
            'images': get_placeholder_images(query, per_page),
            'source': 'placeholder',
            'note': f'Using placeholder images. Error: {str(e)[:100]}'
        })


def get_placeholder_images(query, count=8):
    """Generate placeholder image URLs as fallback"""
    # Using picsum.photos for reliable placeholder images
    images = []
    keywords = query.split()[:3]  # Use first 3 keywords
    seed = abs(hash(query)) % 10000
    
    for i in range(count):
        img_seed = (seed + i) % 1000
        images.append({
            'id': f'placeholder_{i}',
            'url': f'https://picsum.photos/seed/{img_seed}/800/450',
            'thumb': f'https://picsum.photos/seed/{img_seed}/200/113',
            'full': f'https://picsum.photos/seed/{img_seed}/1920/1080',
            'width': 800,
            'height': 450,
            'description': f'Placeholder image {i+1} for "{query}"',
            'author': 'Placeholder',
            'author_url': '#',
            'download_location': None
        })
    return images
