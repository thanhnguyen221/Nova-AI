from django.urls import path
from . import views
from . import slide_views
from . import payment_views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/<int:conversation_id>/', views.chat_view, name='chat_view'),
    path('chat/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('chat/<int:conversation_id>/update-title/', views.update_conversation_title, name='update_conversation_title'),
    path('stream/', views.stream_response, name='stream_response'),
    path('auto-title/', views.auto_title, name='auto_title'),
    path('create-chat/', views.create_conversation, name='create_conversation'),
    path('api/get-gemini-models/', views.get_gemini_models, name='get_gemini_models'),
    path('api/check-model-status/', views.check_model_status, name='check_model_status'),
    # File upload endpoints
    path('api/chat/upload/', views.upload_chat_file, name='upload_chat_file'),
    path('media/chat/<str:filename>/', views.serve_chat_file, name='serve_chat_file'),
    # Notebook LLM API endpoints
    path('api/notebook/upload/', views.upload_notebook_sources, name='upload_notebook_sources'),
    path('api/notebook/sources/', views.get_notebook_sources, name='get_notebook_sources'),
    path('api/notebook/source/<int:index>/', views.delete_notebook_source, name='delete_notebook_source'),
    path('api/notebook/clear/', views.clear_notebook_sources, name='clear_notebook_sources'),
    path('api/notebook/status/', views.query_with_notebooks, name='query_with_notebooks'),
    path('api/notebook/search/', views.search_documents, name='search_documents'),
    path('api/file/content/', views.get_file_content, name='get_file_content'),
    # Real-Time Web Agent & Notebook LLM endpoints
    path('api/url/scrape/', views.scrape_and_import_url, name='scrape_and_import_url'),
    path('api/url/import/', views.process_import_urls_tag, name='process_import_urls_tag'),
    path('api/conversation/<int:conversation_id>/notebook/', views.get_conversation_notebook, name='get_conversation_notebook'),
    path('api/conversation/<int:conversation_id>/notebook/update/', views.update_conversation_notebook, name='update_conversation_notebook'),
    # Mindmap AI API
    path('api/mindmap/generate/', views.generate_mindmap, name='generate_mindmap'),
    
    # ============== SLIDE PRESENTATION SYSTEM ==============
    # Page Views
    path('slides/', slide_views.slide_dashboard, name='slide_dashboard'),
    path('slides/editor/<int:deck_id>/', slide_views.slide_editor, name='slide_editor'),
    path('slides/present/<int:deck_id>/', slide_views.slide_present, name='slide_present'),
    
    # Deck API
    path('api/slides/decks/', slide_views.get_decks, name='get_decks'),
    path('api/slides/decks/create/', slide_views.create_deck, name='create_deck'),
    path('api/slides/decks/<int:deck_id>/', slide_views.get_deck, name='get_deck'),
    path('api/slides/decks/<int:deck_id>/update/', slide_views.update_deck, name='update_deck'),
    path('api/slides/decks/<int:deck_id>/delete/', slide_views.delete_deck, name='delete_deck'),
    path('api/slides/decks/<int:deck_id>/duplicate/', slide_views.duplicate_deck, name='duplicate_deck'),
    
    # Slide API
    path('api/slides/decks/<int:deck_id>/slides/create/', slide_views.create_slide, name='create_slide'),
    path('api/slides/decks/<int:deck_id>/slides/<int:slide_id>/update/', slide_views.update_slide, name='update_slide'),
    path('api/slides/decks/<int:deck_id>/slides/<int:slide_id>/delete/', slide_views.delete_slide, name='delete_slide'),
    path('api/slides/decks/<int:deck_id>/slides/<int:slide_id>/duplicate/', slide_views.duplicate_slide, name='duplicate_slide'),
    path('api/slides/decks/<int:deck_id>/slides/reorder/', slide_views.reorder_slides, name='reorder_slides'),
    
    # Export API
    path('api/slides/decks/<int:deck_id>/export/<str:format_type>/', slide_views.export_deck, name='export_deck'),
    
    # Export Pages (for template links)
    path('slides/export/<int:deck_id>/pptx/', slide_views.export_deck, {'format_type': 'pptx'}, name='export_pptx'),
    path('slides/export/<int:deck_id>/pdf/', slide_views.export_deck, {'format_type': 'pdf'}, name='export_pdf'),
    
    # Present Mode
    path('slides/present/<int:deck_id>/', slide_views.slide_present, name='present_deck'),
    
    # AI Generation
    path('api/slides/generate-from-chat/', slide_views.generate_slides_from_chat, name='generate_slides_from_chat'),
    
    # AI Assistant in Editor
    path('api/slides/ai/chat/', slide_views.ai_chat, name='ai_chat'),
    path('api/slides/search-image/', slide_views.search_image, name='search_image'),
    path('api/slides/search-unsplash/', slide_views.search_unsplash, name='search_unsplash'),
    
    # Preview
    path('api/slides/preview/<int:slide_id>/', slide_views.render_slide_preview, name='render_slide_preview'),

    # ============== PRO SUBSCRIPTION & PAYMENT ==============
    # Payment API
    path('api/payment/create/', payment_views.create_payment, name='create_payment'),
    path('api/payment/status/', payment_views.check_pro_status, name='check_pro_status'),

    # Payment Return/Cancel Pages
    path('payment/return/', payment_views.payment_return, name='payment_return'),
    path('payment/cancel/', payment_views.payment_cancel, name='payment_cancel'),

    # Payment Webhook (for PayOS server callbacks)
    path('api/payment/webhook/', payment_views.payment_webhook, name='payment_webhook'),
]
