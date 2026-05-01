from django.shortcuts import render, get_object_or_404, redirect
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings
from django.utils import timezone
from .models import Conversation, Message
from .ai_service import (
    generate_stream_response, generate_conversation_title,
    scrape_url_content, simple_scrape_url, extract_urls_from_text, parse_import_urls_tag,
    AI_SERVICE
)
from .notebook_service import process_uploaded_files_for_notebook, notebook_service
import google.generativeai as genai
import json
import re
import os


def get_available_gemini_models():
    """Fetch available Gemini models from Google API."""
    if not settings.GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not configured"
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        models = genai.list_models()
        
        gemini_models = []
        priority_models = []  # gemini-1.5 models go here
        other_models = []     # everything else
        
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name.lower():
                # Extract model ID (remove 'models/' prefix if present)
                model_id = m.name.replace('models/', '')
                # Create display name
                display_name = model_id.replace('-', ' ').replace('gemini ', 'Gemini ').title()
                
                # Determine model tier and limits based on model ID
                tier = 'free'
                has_limit = False
                limit_info = None
                expires_at = None
                
                if 'gemini-1.5-flash' in model_id:
                    tier = 'free'
                    has_limit = True
                    limit_info = {'requests_per_minute': 15, 'requests_per_day': 1500}
                    # Flash models typically have generous free tier
                elif 'gemini-1.5-pro' in model_id:
                    tier = 'pro'
                    has_limit = True
                    limit_info = {'requests_per_minute': 2, 'requests_per_day': 50}
                elif 'gemini-2.0' in model_id or 'gemini-2.5' in model_id:
                    tier = 'advanced'
                    has_limit = True
                    limit_info = {'requests_per_minute': 10, 'requests_per_day': 1000}
                elif 'exp' in model_id or 'experimental' in model_id.lower():
                    tier = 'experimental'
                    has_limit = True
                    limit_info = {'requests_per_minute': 5, 'requests_per_day': 100}
                    # Experimental models often have limited availability
                    from datetime import datetime, timedelta
                    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
                
                model_data = {
                    'id': model_id,
                    'name': display_name,
                    'version': getattr(m, 'version', 'v1'),
                    'tier': tier,
                    'has_limit': has_limit,
                    'limit_info': limit_info,
                    'expires_at': expires_at
                }
                
                # Prioritize Gemini 1.5 models
                if 'gemini-1.5-flash' in model_id:
                    priority_models.insert(0, model_data)  # flash at the very top
                elif 'gemini-1.5-pro' in model_id:
                    priority_models.append(model_data)     # pro after flash
                else:
                    other_models.append(model_data)
        
        # Combine: priority first, then others sorted by name
        other_models.sort(key=lambda x: x['name'])
        gemini_models = priority_models + other_models
        
        if not gemini_models:
            return None, "No Gemini models available"
        
        return gemini_models, None
        
    except Exception as e:
        error_msg = str(e)
        if "API key not valid" in error_msg or "invalid" in error_msg.lower():
            return None, "Invalid API key"
        elif "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
            return None, "API quota exhausted"
        else:
            return None, f"API Error: {error_msg}"


def index(request):
    if request.user.is_authenticated:
        # Only show conversations that have at least one message (no ghost chats)
        conversations = Conversation.objects.filter(
            user=request.user,
            messages__isnull=False
        ).distinct().order_by('-updated_at')
        return render(request, 'chat/index.html', {'conversations': conversations})
    return render(request, 'chat/index.html')

@login_required
def chat_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    # Only show conversations with messages
    conversations = Conversation.objects.filter(
        user=request.user,
        messages__isnull=False
    ).distinct().order_by('-updated_at')
    messages = conversation.messages.all().order_by('created_at')
    return render(request, 'chat/index.html', {
        'conversation': conversation,
        'messages': messages,
        'conversations': conversations
    })

@login_required
def stream_response(request):
    if request.method == 'POST':
        conversation_id = request.POST.get('conversation_id')
        user_text = request.POST.get('message')
        model_id = request.POST.get('model_id', 'gemini-1.5-flash')
        search_mode = request.POST.get('search_mode', 'false') == 'true'
        
        if not conversation_id:
            # Create a new conversation with temporary title
            conversation = Conversation.objects.create(user=request.user, title="New Chat")
        else:
            conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        
        # Get quick upload files from request
        quick_files_json = request.POST.get('quick_files', '[]')
        try:
            quick_files = json.loads(quick_files_json)
        except:
            quick_files = []
        
        # CRITICAL: Save user message IMMEDIATELY before API call
        # Save ONLY the original user text, not the file content
        # Extract original message from the full message (remove file content sections)
        original_user_text = user_text
        
        # Helper function to extract user text after markers
        def extract_user_text(text):
            result = text
            # Try removing NOTEBOOK section
            if '=== NOTEBOOK LLM SOURCES ===' in result:
                parts = result.split('=== END NOTEBOOK SOURCES ===')
                if len(parts) > 1:
                    result = parts[-1].strip()  # Take part after END marker
            # Try removing FILE section
            if '=== FILE ĐÍNH KÈM ===' in result:
                parts = result.split('=== END FILES ===')
                if len(parts) > 1:
                    result = parts[-1].strip()  # Take part after END marker
            return result
        
        # Apply extraction (handle both orders: FILE+NOTEBOOK or NOTEBOOK+FILE)
        original_user_text = extract_user_text(original_user_text)
        
        # If still contains markers, try once more
        if '===' in original_user_text and ('FILE' in original_user_text or 'NOTEBOOK' in original_user_text):
            original_user_text = extract_user_text(original_user_text)
        
        # If original is empty but there are files, show a placeholder
        if not original_user_text and quick_files:
            original_user_text = f"[Đính kèm {len(quick_files)} file]"
        
        Message.objects.create(
            conversation=conversation, 
            role='user', 
            content=original_user_text,
            attachments=quick_files if quick_files else None
        )
        print(f"[PERSISTENCE] User message saved to conversation {conversation.id} with {len(quick_files)} attachments")

        # Get notebook LLM toggle state from frontend (default: False/OFF)
        notebook_llm_enabled = request.POST.get('notebook_llm_enabled', 'false').lower() == 'true'

        # Get notebook sources from session
        session_key = f'notebook_sources_{request.user.id}'
        notebook_sources = request.session.get(session_key, [])

        # Create notebook context if sources exist AND notebook LLM is enabled
        notebook_context = None
        gemini_files = []  # Store Gemini file URIs to send with message

        # Add quick upload files to gemini_files (these are always sent - user explicitly attached them)
        for qf in quick_files:
            if qf.get('gemini_file_uri'):
                gemini_files.append(qf['gemini_file_uri'])
                print(f"[Quick Upload] Adding file: {qf.get('name')} -> {qf.get('gemini_file_uri')}")

        # Only add notebook sources if Notebook LLM toggle is ON
        if notebook_llm_enabled and notebook_sources:
            notebook_context = notebook_service.create_notebook_context(notebook_sources, user_text)
            # Collect Gemini file URIs from notebook sources
            for source in notebook_sources:
                if source.get('gemini_file_uri'):
                    gemini_files.append(source['gemini_file_uri'])
            print(f"[NOTEBOOK LLM] Enabled - Attached {len(notebook_sources)} sources, {len(gemini_files)} Gemini files total")
        elif notebook_sources:
            print(f"[NOTEBOOK LLM] Disabled - Skipping {len(notebook_sources)} notebook sources")

        stream = generate_stream_response(conversation, user_text, model_id, notebook_context=notebook_context, gemini_files=gemini_files, search_mode=search_mode)
        response = StreamingHttpResponse(stream, content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
@require_POST
def auto_title(request):
    """AJAX endpoint to auto-generate conversation title after first message."""
    data = json.loads(request.body)
    conversation_id = data.get('conversation_id')
    user_text = data.get('message', '')
    model_id = data.get('model_id', 'gemini-1.5-flash')
    
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        # Only update if still has default title
        if conversation.title == "New Chat" or not conversation.title.strip():
            try:
                title = generate_conversation_title(user_text, model_id)
            except Exception as e:
                print(f"[ERROR] Title generation failed: {e}")
                title = "Cuộc hội thoại mới"
            conversation.title = title
            conversation.save()
            return JsonResponse({'title': title, 'conversation_id': conversation_id})
        return JsonResponse({'title': conversation.title, 'conversation_id': conversation_id})
    
    return JsonResponse({'error': 'No conversation_id provided'}, status=400)

@login_required
def create_conversation(request):
    """Create a new conversation and return its ID (SPA behavior)."""
    conversation = Conversation.objects.create(user=request.user, title="New Chat")
    return JsonResponse({
        'conversation_id': conversation.id,
        'title': conversation.title
    })

@login_required
@require_POST
def delete_conversation(request, conversation_id):
    """Delete a conversation and all its messages."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    conversation.delete()
    return JsonResponse({'success': True, 'conversation_id': conversation_id})


@login_required
@require_POST
def update_conversation_title(request, conversation_id):
    """Update conversation title manually."""
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    data = json.loads(request.body)
    new_title = data.get('title', '').strip()

    if not new_title:
        return JsonResponse({'error': 'Title cannot be empty'}, status=400)

    conversation.update_title(new_title)
    return JsonResponse({
        'success': True,
        'conversation_id': conversation_id,
        'title': conversation.title
    })


def get_gemini_models(request):
    """API endpoint to fetch available Gemini models dynamically."""
    models, error = get_available_gemini_models()
    
    if error:
        return JsonResponse({
            'status': 'error',
            'message': error,
            'models': [],
            'api_connected': False
        }, status=503 if 'not configured' in error or 'Invalid' in error else 500)
    
    return JsonResponse({
        'status': 'success',
        'models': models,
        'api_connected': True,
        'count': len(models)
    })


def check_model_status(request):
    """
    Check real-time status of a specific model from Google API.
    Returns deprecation warnings, quota status, and availability.
    """
    model_id = request.GET.get('model_id', '')
    if not model_id:
        return JsonResponse({
            'status': 'error',
            'message': 'model_id parameter required'
        }, status=400)
    
    if not settings.GEMINI_API_KEY:
        return JsonResponse({
            'status': 'error',
            'message': 'API key not configured'
        }, status=503)
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Get model details from list
        models = genai.list_models()
        model_info = None
        for m in models:
            if model_id in m.name or m.name.replace('models/', '') == model_id:
                model_info = m
                break
        
        if not model_info:
            return JsonResponse({
                'status': 'not_found',
                'message': f'Model {model_id} not found in available models',
                'is_deprecated': True,
                'recommendation': 'Please select a different model'
            })
        
        # Check for deprecation based on model info and description
        deprecation_warning = None
        is_deprecated = False
        
        # Check if model description or version indicates deprecation
        description = getattr(model_info, 'description', '').lower()
        if any(word in description for word in ['deprecated', 'legacy', 'old version', 'superseded']):
            is_deprecated = True
            deprecation_warning = 'Model marked as legacy/deprecated in documentation'
        
        # Check model availability through Google's metadata if available
        # Some models have labels that indicate status
        labels = getattr(model_info, 'labels', {}) or {}
        if isinstance(labels, dict):
            if labels.get('status') == 'deprecated' or labels.get('lifecycle') == 'deprecated':
                is_deprecated = True
                deprecation_warning = 'Model status: deprecated'
        
        # Build status response
        status_data = {
            'status': 'active' if not is_deprecated else 'deprecated',
            'model_id': model_id,
            'model_name': getattr(model_info, 'display_name', model_id),
            'version': getattr(model_info, 'version', 'unknown'),
            'description': getattr(model_info, 'description', ''),
            'is_deprecated': is_deprecated,
            'deprecation_warning': deprecation_warning,
            'last_checked': timezone.now().isoformat(),
        }
        
        # Add expiration estimation based on version/name patterns
        # This is heuristic based on Google's typical release patterns
        if 'experimental' in model_id.lower() or 'preview' in model_id.lower() or 'exp' in model_id.lower():
            # Experimental models typically last 3-6 months
            status_data['estimated_lifespan'] = '3-6 months from release'
            status_data['is_experimental'] = True
            
            # Check if model name suggests it's old (v1, 001 patterns)
            version = getattr(model_info, 'version', '')
            if version in ['001', 'v1', '1']:
                status_data['stability'] = 'stable'
            else:
                status_data['stability'] = 'preview'
                
        elif 'latest' in model_id.lower():
            status_data['stability'] = 'unstable'
            status_data['warning'] = 'Using "latest" alias - may change without notice'
        else:
            status_data['stability'] = 'stable'
        
        # If deprecated, suggest alternatives
        if is_deprecated:
            # Find similar stable models
            alternatives = []
            for m in genai.list_models():
                m_id = m.name.replace('models/', '')
                if 'generateContent' in m.supported_generation_methods:
                    if not any(x in m_id.lower() for x in ['experimental', 'preview', 'exp']):
                        if 'gemini-1.5-flash' in m_id or 'gemini-2.0-flash' in m_id:
                            alternatives.append({
                                'id': m_id,
                                'name': getattr(m, 'display_name', m_id)
                            })
            status_data['alternatives'] = alternatives[:3]
        
        return JsonResponse(status_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'model_id': model_id
        }, status=500)


# ============== NOTEBOOK LLM API ENDPOINTS ==============

@login_required
@require_POST
def upload_notebook_sources(request):
    """
    Upload files to create a Notebook LLM source collection
    Similar to adding sources in Google Notebook LLM
    """
    files = request.FILES.getlist('files')
    
    if not files:
        return JsonResponse({
            'status': 'error',
            'message': 'No files provided'
        }, status=400)
    
    try:
        # Process files through Notebook LLM service
        sources = process_uploaded_files_for_notebook(files)
        
        # Store sources in session for this conversation
        session_key = f'notebook_sources_{request.user.id}'
        existing_sources = request.session.get(session_key, [])
        existing_sources.extend(sources)
        request.session[session_key] = existing_sources
        
        return JsonResponse({
            'status': 'success',
            'message': f'Uploaded {len(sources)} sources',
            'sources': [
                {
                    'name': s['name'],
                    'type': s['type'],
                    'size': s['size'],
                    'has_summary': bool(s.get('ai_summary')),
                    'gemini_uri': s.get('gemini_file_uri'),
                    'extracted_text': s.get('extracted_text', '')[:5000],  # First 5000 chars
                    'preview': (s.get('extracted_text', '') or s.get('content_preview', ''))[:200]
                }
                for s in sources
            ]
        })
        
    except Exception as e:
        print(f"[Notebook LLM Upload Error] {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }, status=500)


@login_required
def get_notebook_sources(request):
    """Get current user's notebook sources from session with file/URL分类"""
    session_key = f'notebook_sources_{request.user.id}'
    sources = request.session.get(session_key, [])

    # Categorize sources
    file_sources = []
    url_sources = []

    for s in sources:
        source_type = s.get('type', 'file')
        if source_type == 'url':
            full_content = s.get('extracted_text', '') or s.get('content_preview', '') or s.get('content', '')
            url_sources.append({
                'name': s.get('title', s.get('name', 'Unknown URL')),
                'type': 'url',
                'url': s.get('url', ''),
                'preview': full_content[:200],
                'extracted_text': full_content,  # Return full content for display
                'gemini_file_uri': s.get('gemini_file_uri')
            })
        else:
            file_sources.append({
                'name': s.get('name', 'Unknown File'),
                'type': 'file',
                'size': s.get('size', 0),
                'extracted_text': s.get('extracted_text', ''),
                'preview': (s.get('extracted_text', '') or s.get('content_preview', ''))[:200],
                'gemini_file_uri': s.get('gemini_file_uri')
            })

    return JsonResponse({
        'status': 'success',
        'count': len(sources),
        'file_count': len(file_sources),
        'url_count': len(url_sources),
        'files': file_sources,
        'urls': url_sources,
        'sources': file_sources + url_sources  # Combined for backward compatibility
    })


@login_required
@require_http_methods(["POST", "GET"])
def search_documents(request):
    """
    Search for documents/web content and suggest for import.
    Used by Notebook LLM search feature.
    Returns suggestions immediately for direct import.
    PHASE 2: Enhanced search with notebook sources + web search
    """
    try:
        # Support both POST and GET for flexibility
        if request.method == 'POST':
            data = json.loads(request.body)
            query = data.get('query', '').strip()
            search_mode = data.get('search_mode', 'all')  # 'all', 'web', 'notebook'
            conversation_id = data.get('conversation_id')
        else:
            query = request.GET.get('query', '').strip()
            search_mode = request.GET.get('search_mode', 'all')
            conversation_id = request.GET.get('conversation_id')

        if not query:
            return JsonResponse({
                'status': 'success',
                'query': '',
                'notebook_results': [],
                'web_results': [],
                'suggestions': [],
                'count': 0,
                'message': 'Nhập từ khóa để tìm tài liệu'
            })

        print(f"[SEARCH] Mode: {search_mode}, Query: {query}")

        notebook_results = []
        web_results = []
        query_lower = query.lower()

        # 1. SEARCH WITHIN NOTEBOOK SOURCES (if mode is 'all' or 'notebook')
        if search_mode in ['all', 'notebook']:
            session_key = f'notebook_sources_{request.user.id}'
            notebook_sources = request.session.get(session_key, [])
            
            # Also search in conversation notebook if provided
            conversation_sources = []
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=request.user)
                    conversation_sources = conversation.notebook_files or []
                except Conversation.DoesNotExist:
                    pass
            
            # Combine session and conversation sources
            all_sources = notebook_sources + conversation_sources
            
            # Search through each source
            query_words = [w for w in query_lower.split() if len(w) > 1]  # Split query into words
            
            for idx, source in enumerate(all_sources):
                if not isinstance(source, dict):
                    continue
                    
                source_name = source.get('name', '')
                source_title = source.get('title', '')
                source_url = source.get('url', '')
                source_content = source.get('extracted_text', '') or source.get('content', '') or source.get('content_preview', '')
                
                name_lower = source_name.lower()
                title_lower = source_title.lower()
                url_lower = source_url.lower()
                content_lower = source_content.lower()
                
                # Calculate relevance score
                score = 0
                match_details = []
                
                # 1. Full phrase matches (highest score)
                if query_lower in name_lower:
                    score += 20
                    match_details.append('name_exact')
                if query_lower in title_lower:
                    score += 20
                    match_details.append('title_exact')
                if query_lower in content_lower:
                    score += 15
                    match_details.append('content_exact')
                if query_lower in url_lower:
                    score += 8
                    match_details.append('url_exact')
                
                # 2. Individual word matches (partial credit)
                for word in query_words:
                    if word in name_lower:
                        score += 5
                    if word in title_lower:
                        score += 5
                    if word in content_lower:
                        score += 3
                        # Count occurrences
                        score += content_lower.count(word)
                    if word in url_lower:
                        score += 2
                
                # 3. Bonus for matching multiple different fields
                fields_matched = sum([
                    query_lower in name_lower,
                    query_lower in title_lower,
                    query_lower in content_lower,
                    query_lower in url_lower
                ])
                if fields_matched >= 2:
                    score += 10  # Bonus for cross-field matches
                
                if score > 0:
                    # Find snippet around the match
                    snippet = ''
                    if source_content:
                        idx_match = source_content.lower().find(query_lower)
                        if idx_match >= 0:
                            start = max(0, idx_match - 100)
                            end = min(len(source_content), idx_match + len(query) + 200)
                            snippet = source_content[start:end]
                            if start > 0:
                                snippet = '...' + snippet
                            if end < len(source_content):
                                snippet = snippet + '...'
                    
                    notebook_results.append({
                        'index': idx,
                        'name': source_name or source_title or 'Unknown',
                        'title': source_title or source_name or 'Unknown',
                        'url': source_url,
                        'type': source.get('type', 'file'),
                        'snippet': snippet[:300] if snippet else (source_content[:200] + '...' if len(source_content) > 200 else source_content),
                        'score': score,
                        'match_count': source_content.lower().count(query_lower) if source_content else 0,
                        'source_location': 'notebook'
                    })
            
            # Sort by relevance score
            notebook_results.sort(key=lambda x: x['score'], reverse=True)
            print(f"[SEARCH] Found {len(notebook_results)} matches in notebook sources")

        # 2. WEB SEARCH (if mode is 'all' or 'web')
        if search_mode in ['all', 'web']:
            from .ai_service import perform_web_search
            # Use max_results=15 for better coverage with new multi-strategy search
            web_search_results = perform_web_search(query, max_results=15)

            if web_search_results:
                for result in web_search_results:
                    title = result.get('title', '').strip() or 'Untitled'
                    url = result.get('href', '').strip()
                    body = result.get('body', '').strip()

                    if url:  # Only include if URL exists
                        # Check if already in notebook
                        is_duplicate = any(
                            r.get('url') == url for r in notebook_results
                        )
                        
                        web_results.append({
                            'title': title[:100],
                            'url': url,
                            'snippet': body[:300] + '...' if len(body) > 300 else body,
                            'full_text': body,
                            'type': 'web',
                            'source': 'duckduckgo',
                            'already_in_notebook': is_duplicate
                        })
                
                print(f"[SEARCH] Found {len(web_results)} web results")

        # Combine all results for backward compatibility
        all_suggestions = notebook_results + web_results

        # Build response message
        message_parts = []
        if notebook_results:
            message_parts.append(f"{len(notebook_results)} trong Notebook")
        if web_results:
            message_parts.append(f"{len(web_results)} từ Web")
        
        message = f"Tìm thấy: {', '.join(message_parts)}" if message_parts else "Không tìm thấy kết quả"

        return JsonResponse({
            'status': 'success',
            'query': query,
            'search_mode': search_mode,
            'notebook_results': notebook_results[:20],  # Limit to top 20
            'web_results': web_results[:15],  # Limit to top 15
            'suggestions': all_suggestions[:25],  # Combined for backward compat
            'count': len(all_suggestions),
            'notebook_count': len(notebook_results),
            'web_count': len(web_results),
            'message': message
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format'}, status=400)
    except Exception as e:
        import traceback
        print(f"[SEARCH ERROR] {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': f'Search error: {str(e)}',
            'suggestions': [],
            'count': 0
        }, status=500)


@login_required
@require_POST
def clear_notebook_sources(request):
    """Clear all notebook sources for user"""
    session_key = f'notebook_sources_{request.user.id}'
    request.session[session_key] = []
    
    return JsonResponse({
        'status': 'success',
        'message': 'Notebook sources cleared'
    })


@login_required
def delete_notebook_source(request, index):
    """Delete a single notebook source by index"""
    session_key = f'notebook_sources_{request.user.id}'
    sources = request.session.get(session_key, [])
    
    if request.method == 'DELETE':
        if 0 <= index < len(sources):
            deleted = sources.pop(index)
            request.session[session_key] = sources
            request.session.modified = True
            return JsonResponse({
                'status': 'success',
                'message': f"Deleted {deleted.get('name', 'source')}"
            })
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid index'
        }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed'
    }, status=405)


@login_required
def query_with_notebooks(request):
    """
    Query using Notebook LLM sources
    GET endpoint to check if notebooks are attached
    """
    session_key = f'notebook_sources_{request.user.id}'
    sources = request.session.get(session_key, [])
    
    if not sources:
        return JsonResponse({
            'status': 'no_sources',
            'message': 'No notebook sources attached'
        })
    
    return JsonResponse({
        'status': 'has_sources',
        'count': len(sources),
        'source_names': [s['name'] for s in sources]
    })


@login_required
def get_file_content(request):
    """
    Get file content for preview
    Query param: file_path - path to the uploaded file
    """
    file_path = request.GET.get('file_path')
    file_name = request.GET.get('file_name', 'unknown')
    
    if not file_path:
        return JsonResponse({
            'status': 'error',
            'message': 'No file path provided'
        }, status=400)
    
    # Security: only allow accessing files in MEDIA_ROOT
    import os
    from django.conf import settings
    
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    # Ensure the path is within MEDIA_ROOT (prevent directory traversal)
    real_full_path = os.path.realpath(full_path)
    real_media_root = os.path.realpath(settings.MEDIA_ROOT)
    
    if not real_full_path.startswith(real_media_root):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid file path'
        }, status=403)
    
    if not os.path.exists(real_full_path):
        return JsonResponse({
            'status': 'error',
            'message': 'File not found'
        }, status=404)
    
    try:
        # Read file content based on type
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if file_ext in ['.txt', '.md', '.csv', '.json', '.py', '.js', '.html', '.css', '.cpp', '.c', '.h']:
            with open(real_full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        elif file_ext in ['.pdf']:
            # For PDF, return a preview message
            content = f'[PDF Document: {file_name}]\n\nFile size: {os.path.getsize(real_full_path)} bytes\n\nNote: PDF content is extracted for AI processing but raw preview is limited.'
        elif file_ext in ['.doc', '.docx']:
            # For Word docs, return a preview message
            content = f'[Word Document: {file_name}]\n\nFile size: {os.path.getsize(real_full_path)} bytes\n\nNote: Document content is extracted for AI processing but raw preview is limited.'
        else:
            content = f'[File: {file_name}]\n\nFile size: {os.path.getsize(real_full_path)} bytes\n\nBinary file - preview not available.'
        
        return JsonResponse({
            'status': 'success',
            'file_name': file_name,
            'file_type': file_ext,
            'content': content
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error reading file: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@login_required
def upload_chat_file(request):
    """
    Upload a file for chat attachments and save to media folder.
    Returns the file URL and metadata.
    For images: uses Gemini Vision to extract text and content.
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No file provided'
            }, status=400)

        uploaded_file = request.FILES['file']
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        file_type = uploaded_file.content_type or 'application/octet-stream'

        # Generate unique filename
        import uuid
        ext = os.path.splitext(file_name)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"

        # Save to media/chat/ folder
        chat_dir = os.path.join(settings.MEDIA_ROOT, 'chat')
        os.makedirs(chat_dir, exist_ok=True)

        file_path = os.path.join(chat_dir, unique_name)

        # Save file
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Build URL
        file_url = f"{settings.MEDIA_URL}chat/{unique_name}"

        # Extract content based on file type
        extracted_text = None
        image_analysis = None

        # Text files
        text_extensions = ['.txt', '.md', '.csv', '.json', '.py', '.js', '.html', '.css']
        if ext in text_extensions:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    extracted_text = f.read()
            except:
                pass

        # Image files - use Gemini Vision
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        if ext in image_extensions or file_type.startswith('image/'):
            try:
                import base64

                # Read image and encode to base64
                with open(file_path, 'rb') as img_file:
                    image_data = img_file.read()
                    image_b64 = base64.b64encode(image_data).decode('utf-8')

                # Check if AI_SERVICE is available
                if not AI_SERVICE:
                    raise Exception("AI_SERVICE not initialized")

                # Use Gemini Vision to analyze image
                vision_prompt = """
                Phân tích chi tiết hình ảnh này và trích xuất TẤT CẢ thông tin có thể:
                1. Text/OCR: Đọc toàn bộ text trong ảnh (biển hiệu, văn bản, số, ký tự...)
                2. Mô tả: Mô tả chi tiết nội dung hình ảnh
                3. Đối tượng: Liệt kê các đối tượng, người, vật thể trong ảnh
                4. Ngữ cảnh: Giải thích ngữ cảnh/ý nghĩa của ảnh nếu có
                5. Dữ liệu: Nếu là biểu đồ, bảng số liệu, hãy trích xuất dữ liệu

                Format trả về:
                [TEXT OCR]: ...
                [MÔ TẢ]: ...
                [ĐỐI TƯỢNG]: ...
                [NGỮ CẢNH]: ...
                [DỮ LIỆU]: ... (nếu có)
                """

                # Call Gemini Vision API
                analysis = AI_SERVICE.process_image_with_vision(image_b64, vision_prompt)
                image_analysis = analysis
                extracted_text = f"[IMAGE ANALYSIS]\n{analysis}\n\n[IMAGE URL] {file_url}"

                print(f"[Image Upload] Gemini Vision analysis: {len(analysis)} chars")

            except Exception as e:
                print(f"[Image Upload] Vision analysis failed: {e}")
                import traceback
                traceback.print_exc()
                extracted_text = f"[Hình ảnh đã upload - không thể phân tích: {str(e)}]\nURL: {file_url}"

        return JsonResponse({
            'status': 'success',
            'file_name': file_name,
            'file_type': file_type,
            'file_size': file_size,
            'file_url': file_url,
            'extracted_text': extracted_text,
            'image_analysis': image_analysis,
            'is_image': ext in image_extensions or file_type.startswith('image/')
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error uploading file: {str(e)}'
        }, status=500)


@login_required
def serve_chat_file(request, filename):
    """
    Serve chat uploaded files securely.
    """
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, 'chat', filename)
        
        if not os.path.exists(file_path):
            return JsonResponse({
                'status': 'error',
                'message': 'File not found'
            }, status=404)
        
        # Check if file is within media directory (security)
        real_path = os.path.realpath(file_path)
        media_path = os.path.realpath(settings.MEDIA_ROOT)
        if not real_path.startswith(media_path):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid file path'
            }, status=403)
        
        # Guess content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error serving file: {str(e)}'
        }, status=500)


# ============================================================================
# REAL-TIME WEB AGENT & NOTEBOOK LLM API ENDPOINTS
# ============================================================================

@login_required
@require_POST
def scrape_and_import_url(request):
    """
    API endpoint to scrape a URL and add it to the conversation's notebook.
    PHASE 2: Enhanced with better error handling and fallback methods.
    """
    import traceback
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        conversation_id = data.get('conversation_id')

        if not url:
            return JsonResponse({'status': 'error', 'message': 'URL is required'}, status=400)

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            return JsonResponse({'status': 'error', 'message': 'Invalid URL format. URL must start with http:// or https://'}, status=400)
        
        # Validate URL format more thoroughly
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc:
                return JsonResponse({'status': 'error', 'message': 'Invalid URL: no domain found'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid URL: {str(e)}'}, status=400)

        print(f"[URL IMPORT] Scraping URL: {url}")

        # PHASE 2: Try multiple scraping methods with fallbacks
        result = None
        scrape_error = None
        
        # Method 1: Try full scrape with Selenium (may timeout/fail)
        try:
            result = scrape_url_content(url)
            if result.get('success') and len(result.get('content', '')) > 100:
                print(f"[URL IMPORT] Full scrape successful: {len(result['content'])} chars")
            else:
                print(f"[URL IMPORT] Full scrape returned insufficient content: {result.get('content', '')[:100]}...")
                result = None
        except Exception as e:
            scrape_error = str(e)
            print(f"[URL IMPORT] Full scrape failed: {e}")
            traceback.print_exc()
        
        # Method 2: Fallback to simple HTTP scrape if full scrape failed
        if not result:
            print("[URL IMPORT] Trying simple HTTP fallback...")
            try:
                result = simple_scrape_url(url)
                if result.get('success'):
                    print(f"[URL IMPORT] Simple scrape successful: {len(result['content'])} chars")
                else:
                    result = None
            except Exception as e:
                print(f"[URL IMPORT] Simple scrape also failed: {e}")
        
        # If all methods failed, return error with details
        if not result or not result.get('success'):
            error_msg = result.get('error', 'Unknown error') if result else scrape_error
            
            # Special handling for 403 errors
            if '403' in str(error_msg):
                return JsonResponse({
                    'status': 'error',
                    'error_type': '403_forbidden',
                    'message': f"Website đang chặn truy cập tự động (403 Forbidden).\n\nGợi ý:\n• Thử tìm kiếm thông tin từ nguồn khác\n• Copy-paste nội dung trực tiếp vào chat\n• Một số website như Glints, LinkedIn có chống bot nghiêm ngặt",
                    'url': url
                }, status=403)
            
            return JsonResponse({
                'status': 'error',
                'message': f"Không thể tải nội dung từ URL. Lỗi: {error_msg}"
            }, status=500)

        # Get or create conversation
        conversation = None
        created_new = False
        
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            except Conversation.DoesNotExist:
                pass
        
        # If no conversation, create a new one with auto title from URL
        if not conversation:
            title = result['title'][:50] if result['title'] else f"Notebook: {url[:40]}"
            conversation = Conversation.objects.create(
                user=request.user,
                title=title
            )
            created_new = True
            print(f"[URL IMPORT] Created new conversation {conversation.id} with title: {title}")
        
        # Add to notebook
        file_info = {
            'type': 'url',
            'url': url,
            'title': result['title'],
            'content': result['content'][:5000],  # Store preview
            'added_at': timezone.now().isoformat()
        }
        added = conversation.add_notebook_file(file_info)

        # Also add to session for immediate use
        session_key = f'notebook_sources_{request.user.id}'
        notebook_sources = request.session.get(session_key, [])

        # Check if already in session
        existing = [s for s in notebook_sources if s.get('url') == url]
        if not existing:
            notebook_sources.append({
                'type': 'url',
                'url': url,
                'title': result['title'],
                'extracted_text': result['content'],  # Use extracted_text for consistency
                'content_preview': result['content'][:500] if len(result['content']) > 500 else result['content'],
                'added_at': timezone.now().isoformat()
            })
            request.session[session_key] = notebook_sources

        return JsonResponse({
            'status': 'success',
            'url': url,
            'title': result['title'],
            'content_preview': result['content'][:500] + '...' if len(result['content']) > 500 else result['content'],
            'content_length': len(result['content']),
            'already_exists': not added,
            'conversation_id': conversation.id,
            'created_new_conversation': created_new,
            'notebook_count': len(conversation.notebook_files) if conversation.notebook_files else 0,
            'extracted_links': result.get('extracted_links', []),
            'scraping_metadata': result.get('scraping_metadata', {}),
            'screenshot_base64': result.get('screenshot_base64'),
            'has_screenshot': result.get('has_screenshot', False)
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"[URL IMPORT ERROR] {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def process_import_urls_tag(request):
    """
    Backend interceptor for [IMPORT_URLS: ...] tag.
    Called by frontend when AI outputs this tag.
    """
    try:
        data = json.loads(request.body)
        ai_response = data.get('ai_response', '')
        conversation_id = data.get('conversation_id')

        # Parse the IMPORT_URLS tag
        urls, match = parse_import_urls_tag(ai_response)

        if not urls:
            return JsonResponse({
                'status': 'no_action',
                'message': 'No IMPORT_URLS tag found'
            })

        print(f"[IMPORT_URLS] Found {len(urls)} URLs to import: {urls}")

        # Scrape each URL
        imported = []
        failed = []

        for url in urls:
            result = scrape_url_content(url)
            if result['success']:
                imported.append({
                    'url': url,
                    'title': result['title'],
                    'content': result['content'][:5000]
                })
            else:
                failed.append({'url': url, 'error': result.get('error', 'Unknown error')})

        # Add to conversation notebook if provided
        if conversation_id and imported:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
                for item in imported:
                    file_info = {
                        'type': 'url',
                        'url': item['url'],
                        'title': item['title'],
                        'content': item['content'],
                        'added_at': timezone.now().isoformat(),
                        'source': 'ai_import'
                    }
                    conversation.add_notebook_file(file_info)

                # Update session
                session_key = f'notebook_sources_{request.user.id}'
                notebook_sources = request.session.get(session_key, [])
                for item in imported:
                    existing = [s for s in notebook_sources if s.get('url') == item['url']]
                    if not existing:
                        notebook_sources.append({
                            'type': 'url',
                            'url': item['url'],
                            'title': item['title'],
                            'content': item['content'],
                            'added_at': timezone.now().isoformat()
                        })
                request.session[session_key] = notebook_sources

            except Conversation.DoesNotExist:
                pass

        # Return cleaned response (with tag removed)
        cleaned_response = re.sub(r'\[IMPORT_URLS:[^\]]+\]', '', ai_response).strip()

        return JsonResponse({
            'status': 'success',
            'imported_count': len(imported),
            'failed_count': len(failed),
            'imported': imported,
            'failed': failed,
            'cleaned_response': cleaned_response,
            'tag_removed': True
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"[IMPORT_URLS ERROR] {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def get_conversation_notebook(request, conversation_id):
    """Get all notebook files for a conversation."""
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        notebook_files = conversation.notebook_files or []

        return JsonResponse({
            'status': 'success',
            'conversation_id': conversation_id,
            'notebook_files': notebook_files,
            'count': len(notebook_files)
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Conversation not found'}, status=404)


@login_required
@require_POST
def update_conversation_notebook(request, conversation_id):
    """Update notebook files for a conversation."""
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        data = json.loads(request.body)
        notebook_files = data.get('notebook_files', [])

        conversation.notebook_files = notebook_files
        conversation.save(update_fields=['notebook_files', 'updated_at'])

        # Update session
        session_key = f'notebook_sources_{request.user.id}'
        request.session[session_key] = notebook_files

        return JsonResponse({
            'status': 'success',
            'conversation_id': conversation_id,
            'count': len(notebook_files)
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Conversation not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)


@login_required
@require_POST
def generate_mindmap(request):
    """Generate mindmap structure from file content using Gemini AI."""
    import traceback
    import google.generativeai as genai
    import re

    try:
        data = json.loads(request.body)
        content = data.get('content', '')
        file_names = data.get('file_names', [])
        selected_model = data.get('model', 'gemini-2.5-flash')  # Get model from frontend
        is_modification = data.get('is_modification', False)  # Check if this is a modification request

        if not content:
            return JsonResponse({
                'status': 'error',
                'message': 'No content provided'
            }, status=400)

        # Check API key
        if not getattr(settings, 'GEMINI_API_KEY', None):
            # Fallback without AI
            mindmap_data = generate_fallback_mindmap(file_names, content)
            return JsonResponse({
                'status': 'success',
                'mindmap_data': mindmap_data,
                'files_analyzed': len(file_names),
                'note': 'Generated without AI (no API key)'
            })

        try:
            # Configure Gemini
            genai.configure(api_key=settings.GEMINI_API_KEY)

            # List of models to try in order (user's choice first, then fallbacks)
            models_to_try = [
                selected_model,  # User selected model first
                'gemini-2.5-flash',
                'gemini-2.5-pro',
                'gemini-2.0-flash',
                'gemini-1.5-flash',
                'gemini-2.0-pro'
            ]

            # Create prompt based on request type
            files_info = ', '.join(file_names) if file_names else 'Unknown files'

            if is_modification:
                # Modification request - content already contains both original and modification context
                prompt = f"""Bạn là chuyên gia tạo SƠ ĐỒ TƯ DUY (Mind Map). Bạn đang SỬA ĐỔI mindmap dựa trên yêu cầu của người dùng.

YÊU CẦU TỪ NGƯỜI DÙNG:
{content[:12000]}

NHIỆM VỤ:
1. Phân tích nội dung file GỐC
2. Áp dụng các yêu cầu sửa đổi cụ thể (thêm, bớt, sửa các node)
3. Tạo mindmap mới với cấu trúc 3 tầng:
   - Tầng 1 (Root): Chủ đề chính
   - Tầng 2 (Branches): Các ý chính
   - Tầng 3 (Sub-branches): Chi tiết

QUY TẮC:
1. Giữ nguyên các phần không bị yêu cầu sửa
2. Thực hiện chính xác các thay đổi được yêu cầu
3. Tiêu đề ngắn gọn (3-6 từ), tiếng Việt có dấu
4. Sắp xếp logic, 4-6 nhánh chính

ĐỊNH DẠNG JSON:
{{
  "title": "Chủ đề chính",
  "children": [
    {{"title": "Ý chính 1", "children": [{{"title": "Chi tiết 1.1"}}]}},
    {{"title": "Ý chính 2", "children": [{{"title": "Chi tiết 2.1"}}]}}
  ]
}}

CHỈ trả về JSON."""
            else:
                # Original generation request
                prompt = f"""Bạn là chuyên gia tạo SƠ ĐỒ TƯ DUY (Mind Map). Hãy phân tích nội dung file và tạo sơ đồ tư duy CHÍNH XÁC, BÁM SÁT nội dung.

THÔNG TIN FILE: {files_info}

NỘI DUNG FILE:
{content[:10000]}

NHIỆM VỤ:
Tạo sơ đồ tư duy với cấu trúc 3 tầng:
- Tầng 1 (Root): Chủ đề chính = Tên file hoặc chủ đề cốt lõi của nội dung
- Tầng 2 (Branches): Các ý chính, khái niệm, hoặc chủ đề lớn trong nội dung
- Tầng 3 (Sub-branches): Chi tiết, ví dụ, hoặc khái niệm con của mỗi ý chính

QUY TẮC QUAN TRỌNG:
1. BẮT BUỘC: Chỉ sử dụng thông tin CÓ TRONG FILE, không thêm ý tưởng bên ngoài
2. Tiêu đề phải là từ khóa/ngắn gọn (3-6 từ), không phải câu dài
3. Sắp xếp theo thứ tự logic xuất hiện trong file
4. Số lượng: 4-6 nhánh chính (tầng 2), mỗi nhánh có 2-4 chi tiết (tầng 3)
5. Ngôn ngữ: Tiếng Việt có dấu, đúng chính tả

ĐỊNH DẠNG TRẢ VỀ (JSON):
{{
  "title": "Tên chủ đề chính",
  "children": [
    {{
      "title": "Ý chính 1",
      "children": [
        {{"title": "Chi tiết 1.1"}},
        {{"title": "Chi tiết 1.2"}}
      ]
    }},
    {{
      "title": "Ý chính 2",
      "children": [
        {{"title": "Chi tiết 2.1"}},
        {{"title": "Chi tiết 2.2"}}
      ]
    }}
  ]
}}

CHỈ trả về JSON, không giải thích, không text thêm."""

            # Generate response with retry logic for quota errors
            mindmap_data = None
            last_error = None

            for attempt, model_name in enumerate(models_to_try):
                if not model_name:
                    continue
                try:
                    print(f"[Mindmap] Attempt {attempt + 1} with model: {model_name}")
                    model = genai.GenerativeModel(model_name=model_name)
                    response = model.generate_content(prompt)
                    response_text = response.text

                    # Extract JSON from response
                    json_match = re.search(r'\{[\s\S]*\}', response_text)

                    if json_match:
                        mindmap_json = json_match.group(0)
                        mindmap_data = json.loads(mindmap_json)
                        print(f"[Mindmap] Success with model: {model_name}")
                        break
                    else:
                        raise Exception("No JSON found in response")

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    # Check for quota/rate limit errors
                    if any(keyword in error_str for keyword in ['quota', 'rate limit', '429', 'exhausted', 'limit exceeded']):
                        print(f"[Mindmap] Quota exceeded for {model_name}, trying next...")
                        continue
                    else:
                        # Other errors - try next model
                        print(f"[Mindmap] Error with {model_name}: {e}")
                        continue

            if not mindmap_data:
                print(f'[Mindmap AI Error] All models failed. Last error: {last_error}')
                mindmap_data = generate_fallback_mindmap(file_names, content)

        except Exception as ai_error:
            # If AI fails completely, use fallback
            print(f'[Mindmap AI Error] {ai_error}')
            mindmap_data = generate_fallback_mindmap(file_names, content)
        
        return JsonResponse({
            'status': 'success',
            'mindmap_data': mindmap_data,
            'files_analyzed': len(file_names)
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        print(f'[Mindmap Error] {traceback.format_exc()}')
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def generate_fallback_mindmap(file_names, content):
    """Generate mindmap structure without AI using keyword extraction."""
    import re
    
    # Extract title from filename
    title = 'Mindmap'
    if file_names:
        fname = file_names[0]
        # Remove extension and clean up
        title = re.sub(r'\.(txt|md|pdf|doc|docx)$', '', fname, flags=re.IGNORECASE)
        title = title.replace('_', ' ').replace('-', ' ')
        title = title[:40]  # Limit length
    
    # Clean content - remove special chars but keep Vietnamese
    content = re.sub(r'[^\w\s\-\.\u00C0-\u1EF9]', ' ', content)
    content = re.sub(r'\s+', ' ', content).strip()
    
    # Split into sentences/segments
    sentences = re.split(r'[.!?\n]+', content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    # Common Vietnamese stop words
    stop_words = {'và', 'của', 'là', 'có', 'được', 'cho', 'trong', 'với', 'các', 'để', 'này', 
                  'không', 'về', 'một', 'đã', 'đến', 'từ', 'theo', 'người', 'năm', 'khi', 'sẽ',
                  'đó', 'tại', 'còn', 'vì', 'nếu', 'nhưng', 'mà', 'thì', 'lại', 'đang', 'rất',
                  'điều', 'sự', 'việc', 'thông', 'tin', 'qua', 'bởi', 'trên', 'dưới', 'trước',
                  'sau', 'trong', 'ngoài', 'giữa', 'cùng', 'vào', 'ra', 'lên', 'xuống'}
    
    # Extract keywords (words with length > 3, not stop words, capitalize first letter)
    def clean_phrase(text):
        words = text.lower().split()
        # Filter out stop words and short words
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        # Take first 3-5 meaningful words
        if keywords:
            return ' '.join(keywords[:5]).title()
        return text[:30].strip()
    
    children = []
    used_titles = set()
    
    # Group content into topics
    chunk_size = max(1, len(sentences) // 6)
    
    for i in range(min(6, len(sentences) // max(1, chunk_size))):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, len(sentences))
        chunk = sentences[start_idx:end_idx]
        
        if not chunk:
            continue
        
        # Topic title from first meaningful sentence
        topic_title = clean_phrase(chunk[0])
        # Ensure unique titles
        counter = 1
        original_title = topic_title
        while topic_title in used_titles:
            topic_title = f"{original_title} {counter}"
            counter += 1
        used_titles.add(topic_title)
        
        # Sub-topics from remaining sentences
        sub_children = []
        sub_used = set()
        
        for sentence in chunk[1:3]:  # Max 2 sub-topics
            sub_title = clean_phrase(sentence)
            if sub_title and sub_title not in sub_used and sub_title != topic_title:
                sub_used.add(sub_title)
                sub_children.append({'title': sub_title[:30]})
        
        if not sub_children:
            # Create generic sub-topic if none extracted
            sub_children = [{'title': f'Nội dung {i+1}'}]
        
        children.append({
            'title': topic_title[:35],
            'children': sub_children
        })
    
    # Ensure at least 2 topics
    if len(children) < 2:
        children = [
            {'title': 'Tổng quan', 'children': [{'title': 'Nội dung chính'}]},
            {'title': 'Chi tiết', 'children': [{'title': 'Thông tin thêm'}]},
        ]
    
    return {
        'title': title,
        'children': children
    }
