# Nova AI - Project Overview

> **Đọc file này để hiểu toàn bộ dự án trong 5 phút**

---

## 🎯 Dự Án Là Gì?

**Nova AI** là web application Django kết hợp:
1. **Chatbot AI** (như ChatGPT) - Chat với Gemini
2. **Notebook LLM** (như NotebookLM) - Import sources để AI tham khảo
3. **Slide Deck** (như Canva) - Tạo presentation

**Use case chính**: Người dùng import tài liệu/tìm kiếm web → Chat với AI về nội dung đó → Tạo presentation từ nội dung.

---

## 🏗️ Kiến Trúc Tổng Quan

```
┌─────────────────────────────────────────────────────────┐
│                      User Interface                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Chat UI   │  │ Notebook UI  │  │  Slide Editor  │  │
│  │             │  │              │  │                │  │
│  │ • Streaming │  │ • Import URL │  │ • Templates   │  │
│  │ • Messages  │  │ • Search     │  │ • Layouts     │  │
│  │ • Markdown  │  │ • Sources    │  │ • Themes      │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘  │
└─────────┼────────────────┼───────────────────┼──────────┘
          │                │                   │
          ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                      Django Backend                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Views     │  │    Models    │  │   Services     │  │
│  │             │  │              │  │                │  │
│  │ • chat_     │  │ • Conver-    │  │ • ai_service   │
│  │ • notebook  │  │   sation     │  │ • notebook_    │
│  │ • slide_    │  │ • Message    │  │   service      │
│  │ • export    │  │ • SlideDeck  │  │ • slide_       │
│  └──────┬──────┘  │ • Slide      │  │   service      │
│         │         └──────┬───────┘  └────────────────┘  │
│         │                │                            │
│         ▼                ▼                            │
│  ┌───────────────────────────────────────────────┐   │
│  │              Database (SQLite)                 │   │
│  │  Conversations, Messages, Slides, Exports   │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                   External Services                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Gemini    │  │  DuckDuckGo  │  │    Selenium    │  │
│  │    API      │  │   Search     │  │   WebDriver    │  │
│  │             │  │              │  │                │  │
│  │ • Chat      │  │ • Web search │  │ • Deep scrape  │  │
│  │ • Generate  │  │ • Images     │  │ • Screenshots │  │
│  │ • Titles    │  │              │  │ • JS exec     │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục Quan Trọng

```
nova_project/                 # Django project settings
    settings.py
    urls.py

chat/                         # Main app (chat + notebook + slides)
    models.py                 # Conversation, Message, SlideDeck, Slide...
    views.py                  # Chat APIs, notebook APIs
    slide_views.py            # Slide editor APIs
    ai_service.py             # Gemini integration, scraping
    notebook_service.py       # File processing
    slide_service.py          # AI slide generation
    slide_renderer.py         # Slide HTML/PPTX/PDF rendering

templates/
    chat/
        index.html            # MAIN UI: chat + notebook panel
        slides/
            editor.html       # Slide editor UI
            list.html         # Slide deck list

static/
    css/                      # Tailwind + custom CSS
    js/                       # JavaScript modules

media/                        # User uploads, exports
    slide_exports/
```

---

## 🔄 Data Flow Chính

### 1. Chat Flow
```
User gửi tin nhắn
    ↓
Frontend gọi POST /chat/ (streaming)
    ↓
Backend lấy conversation + messages history
    ↓
Gọi Gemini API với context
    ↓
Streaming response về frontend
    ↓
Lưu message vào database
```

### 2. Notebook Import Flow
```
User paste URL → Click Import
    ↓
POST /api/url/scrape/
    ↓
Thử scrape: Selenium → HTTP fallback
    ↓
Extract content + links liên quan
    ↓
Lưu vào Conversation.notebook_files (JSON)
    ↓
Trả về: content, links, screenshot
    ↓
Frontend: refresh list → show modal links
```

### 3. Slide Generation Flow
```
User nhập prompt → Click Tạo
    ↓
POST /api/slides/generate/
    ↓
AI service generate content
    ↓
Parse thành slides structure
    ↓
Tạo SlideDeck + Slide objects
    ↓
Redirect đến slide editor
    ↓
User chỉnh sửa → Export
```

---

## 🗄️ Database Schema (Tóm tắt)

```
┌─────────────────┐       ┌─────────────────┐
│  Conversation   │◄──────│     Message     │
├─────────────────┤  1:N  ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ user (FK)       │       │ conversation    │
│ title           │       │ role (user/     │
│ notebook_files  │       │   model)        │
│ created_at      │       │ content         │
└─────────────────┘       │ attachments     │
                          │ sources         │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│   SlideDeck     │◄──────│     Slide       │
├─────────────────┤  1:N  ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ user (FK)       │       │ deck (FK)       │
│ title           │       │ order           │
│ theme           │       │ layout          │
│ aspect_ratio    │       │ content (JSON)  │
└─────────────────┘       └─────────────────┘
```

---

## 🔑 Key Files Hiểu Dự Án

| File | Mục đích |
|------|----------|
| `chat/models.py` | Định nghĩa data structure |
| `chat/views.py` | API endpoints cho chat + notebook |
| `chat/slide_views.py` | API endpoints cho slides |
| `chat/ai_service.py` | Gemini integration + scraping logic |
| `templates/chat/index.html` | Main UI (chat + notebook panel) |
| `templates/chat/slides/editor.html` | Slide editor interface |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.x, Python 3.x |
| Database | SQLite (dev), PostgreSQL (prod-ready) |
| AI | Google Gemini API |
| Frontend | HTML + Tailwind CSS + Vanilla JS |
| Scraping | Selenium + BeautifulSoup |
| Export | python-pptx, Playwright (PDF) |
| Search | DuckDuckGo (ddgs) |

---

## 🚀 Chạy Dự Án

```bash
# 1. Setup environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Environment variables
cp .env.example .env
# Edit .env: GEMINI_API_KEY=your_key

# 4. Database
python manage.py migrate

# 5. Build CSS
./build-css.sh

# 6. Run server
python manage.py runserver
```

**Access**: http://localhost:8000

---

## 📊 Tính Năng Chính (Checklist)

- ✅ Chat với Gemini (streaming)
- ✅ Quản lý nhiều conversations
- ✅ Notebook LLM (import URLs, files)
- ✅ Web search integration
- ✅ Slide Deck tạo presentation
- ✅ Export PPTX/PDF/HTML
- ✅ Image search cho slides
- ✅ Auto-title generation

---

## 🎯 Đối Tượng Người Dùng

1. **Học sinh/Sinh viên**: Import tài liệu → Hỏi AI → Làm slide thuyết trình
2. **Nhân viên văn phòng**: Tìm kiếm thông tin → Tổng hợp → Tạo báo cáo
3. **Content creator**: Nghiên cứu chủ đề → Tạo content

---

**Tóm lại**: Nova AI = Gemini + NotebookLM + Canva trong một ứng dụng Django.

---

*Last Updated: April 2026*
