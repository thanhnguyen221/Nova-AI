import google.generativeai as genai
from django.conf import settings
from .models import Message, Conversation
import re


def get_gemini_model():
    """Initialize and return the Gemini model with system instructions."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in settings.")
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    # List available models for debugging
    try:
        print("=== AVAILABLE MODELS ===")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")
        print("========================")
    except Exception as e:
        print(f"Could not list models: {e}")
    
    # EXACT system instruction from SKILLS.md (Phase 5.7: Enhanced search rules)
    system_instruction = (
        "You are an advanced reasoning AI powering Nova AI. "
        "You MUST respond in Vietnamese (Tiếng Việt) unless explicitly asked otherwise. "
        "LUẬT TỐI CAO DÀNH CHO BẠN: "
        "CHO DÙ NGƯỜI DÙNG HỎI BẤT CỨ ĐIỀU GÌ, ĐẶC BIỆT LÀ GỬI CODE HAY NHỜ SỬA CODE, "
        "BẠN BẮT BUỘC PHẢI SUY LUẬN TRƯỚC VÀ ĐẶT SUY LUẬN VÀO TRONG THẺ <thinking>...</thinking>. "
        "Nếu bạn xuất code ra mà không có thẻ <thinking> trước đó, hệ thống sẽ bị lỗi. "
        "1. BÊN TRONG <thinking>: Giải thích vấn đề, tìm lỗi sai của code, lên kế hoạch giải quyết. "
        "2. BÊN NGOÀI <thinking>: Chỉ cung cấp đoạn code hoàn chỉnh đặt trong block Markdown (ví dụ: ```python ... ```), và tóm tắt ngắn gọn. "
        "Không được đặt câu trả lời chính vào trong thẻ thinking. "
        "\n\nQUY TẮC TÌM KIẾM VÀ TRÍCH DẪN NGHIÊM NGẶT (Nếu có tìm kiếm): "
        "- ĐA DẠNG HÓA NGUỒN: Tuyệt đối KHÔNG chỉ lấy từ support.google.com. "
        "- ƯU TIÊN: Báo lớn VN (VnExpress, Tuổi Trẻ, Thanh Niên), diễn đàn (Reddit, StackOverflow, Tinhte), blog chuyên gia. "
        "- KỸ THUẬT: Thay đổi query bằng tiếng Việt và tiếng Anh để có kết quả tốt nhất. "
        "- FORMAT: Nguồn PHẢI đặt trong <sources>[{\"title\": \"...\", \"url\": \"...\"}]</sources> ở ĐẦU câu trả lời. "
        "- CHỈ DÙNG LINK GỐC, không dùng link trung gian Google Search. "
        "- ƯU TIÊN TIN MỚI NHẤT trong 24h nếu là tin thời sự."
    )
    
    # Use gemini-2.0-flash (2026 model standard)
    model_name = 'gemini-2.0-flash'
    print(f"Using model: {model_name}")
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
    )
    return model


def generate_stream_response(conversation, user_text):
    """
    Yield SSE-formatted chunks of the response from Gemini.
    """
    model = get_gemini_model()
    
    # Fetch last 10 messages for context (conversational memory)
    past_messages = conversation.messages.all().order_by('-created_at')[:10]
    past_messages = list(reversed(past_messages))
    
    contents = []
    for msg in past_messages:
        role = 'user' if msg.role == 'user' else 'model'
        
        # When sending context to the model, combine thought and content if present
        text = msg.content
        if msg.thinking_process:
            text = f"<thinking>\n{msg.thinking_process}\n</thinking>\n{text}"
            
        contents.append({"role": role, "parts": [text]})
        
    # Append the current prompt
    contents.append({"role": "user", "parts": [user_text]})
    
    # Save the user message to DB
    Message.objects.create(conversation=conversation, role='user', content=user_text)
    
    # Generate streaming response
    response = model.generate_content(
        contents=contents,
        stream=True
    )
    
    full_response = ""
    for chunk in response:
        if hasattr(chunk, 'text'):
            text = chunk.text
            full_response += text
            # Properly escape newlines for SSE format
            safe_text = text.replace('\n', '\\n').replace('\r', '\\r')
            yield f"data: {safe_text}\n\n"
    
    # Parse <thinking> tags from full_response to save into DB
    think_match = re.search(r'<thinking>(.*?)</thinking>', full_response, flags=re.DOTALL)
    
    thinking_process = ""
    content = full_response
    
    if think_match:
        thinking_process = think_match.group(1).strip()
        # Remove think tags from the final text
        content = re.sub(r'<thinking>.*?</thinking>', '', full_response, flags=re.DOTALL).strip()
        
    # Save the AI response
    Message.objects.create(
        conversation=conversation,
        role='model',
        content=content,
        thinking_process=thinking_process
    )
    
    # Signal end of stream
    yield "data: [DONE]\n\n"


def generate_conversation_title(user_text):
    """Generate a concise 3-word title for a new conversation."""
    if not settings.GEMINI_API_KEY:
        return user_text[:30]
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name='gemini-2.0-flash')
    
    prompt = f'Generate a concise 2-4 word title for a conversation starting with this message. Return ONLY the title, no quotes: "{user_text[:100]}"'
    
    try:
        response = model.generate_content(prompt)
        title = response.text.strip().strip('"').strip("'")
        return title[:50] if title else user_text[:30]
    except:
        return user_text[:30]
