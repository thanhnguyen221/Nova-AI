# 🤖 Nova AI - Intelligent Chatbot & Content Generation Platform

![Django](https://img.shields.io/badge/-Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![SQLite](https://img.shields.io/badge/-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Google Gemini](https://img.shields.io/badge/-Gemini%20AI-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Selenium](https://img.shields.io/badge/-Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![WebSocket](https://img.shields.io/badge/-WebSocket-010101?style=for-the-badge&logo=socket.io&logoColor=white)

An AI-powered chatbot platform built with Django, featuring multi-turn conversations with Google Gemini, Notebook LLM system for knowledge-grounded AI responses, interactive mindmap generation, artifact preview panels, and automated slide creation with PayOS payment integration.

## 📺 Video Demo
Experience the real-time chat and video calling features in action:

> [!TIP]
> **Coming Soon** - Demo video showcasing AI chatbot, mindmap generation, and slide creation features.

---

## ✨ Key Features

* **AI Chatbot with Streaming:** Multi-turn conversations using Google Gemini API with Server-Sent Events (SSE) for real-time streaming responses and file attachment support (PDF, TXT, DOCX).
* **Notebook LLM System:** Import URLs and documents to create knowledge bases; Selenium WebDriver scrapes JavaScript-heavy websites with auto-pagination and screenshot capture for AI context.
* **Mindmap AI Generator:** Transform imported sources into interactive SVG mindmaps with zoom/pan controls and node editing capabilities.
* **Artifacts Panel:** Live code/content preview (Claude AI-style) with split-view mode, fullscreen toggle, and real-time editing capabilities.
* **Slide Generation Module:** Create professional presentations using python-pptx and Playwright, supporting 10+ layouts and 6 customizable themes with PPTX/PDF export.
* **Pro Subscription System:** PayOS payment gateway integration with webhook handling and automated expiry tracking via Django signals.

---

## ⚙️ Architecture & How It Works

**1. AI Conversation Layer**
Multi-turn chat system powered by Google Gemini API:
- **Streaming Responses:** Server-Sent Events (SSE) deliver tokens in real-time for fluid conversation experience
- **File Attachments:** Support for PDF, TXT, DOCX documents with context extraction
- **Context Memory:** Maintains conversation history across multiple turns for coherent responses
- **Citation System:** Automatic source referencing for AI-generated content

**2. Notebook LLM System**
Knowledge-grounded AI responses through content import:
- **Web Scraping:** Selenium WebDriver handles JavaScript-heavy sites with deep scrolling and auto-click pagination
- **Document Processing:** Extract text from PDF, TXT, DOCX files for AI context
- **Screenshot Capture:** Visual context preservation from web sources
- **Source Management:** Organize and manage multiple knowledge sources per conversation

**3. Mindmap Generation Engine**
Interactive visualization of AI-generated knowledge structures:
- **SVG Rendering:** Scalable vector graphics with zoom/pan controls
- **Node Editing:** Add, remove, and modify mindmap nodes dynamically
- **Auto-Layout:** AI-powered hierarchical organization of concepts
- **Export Options:** Save as SVG or PNG for sharing

**4. Artifacts Panel System**
Live content preview inspired by Claude AI:
- **Split-View Mode:** Side-by-side code and preview panels
- **Fullscreen Toggle:** Focus mode for distraction-free viewing
- **Real-time Rendering:** Instant preview updates as code changes
- **Multi-format Support:** HTML, CSS, JavaScript, and markdown rendering

**5. Slide Generation Pipeline**
Automated presentation creation with python-pptx:
- **Layout Templates:** 10+ pre-designed slide layouts
- **Theme System:** 6 customizable color themes
- **Export Formats:** PPTX and PDF output via Playwright
- **AI Content:** Automatic content structuring from conversation context

**6. Payment & Subscription Layer**
PayOS integration for Pro tier management:
- **Webhook Handling:** Automated payment status updates
- **Expiry Tracking:** Django signals monitor subscription validity
- **Feature Gating:** Route-level decorators restrict Pro features
- **Payment Links:** Dynamic checkout URL generation

---

## 🛠 Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | Django, Django REST Framework, Django Signals |
| **Database** | SQLite (relational data storage) |
| **Real-Time** | Server-Sent Events (SSE), WebSocket |
| **AI & APIs** | Google Gemini API, DeepSeek-R1 API, PayOS Payment API |
| **Web Scraping** | Selenium WebDriver, Playwright |
| **Document Processing** | python-pptx, python-docx, PyPDF2 |
| **Security** | Django Auth, CSRF Protection, python-dotenv |
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla), Tailwind CSS |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Google Gemini API Key
- PayOS Account (for payment integration)
- Chrome/Chromium (for Selenium WebDriver)

### Installation

**1. Clone the repository:**
```bash
git clone https://github.com/thanhnguyen221/nova-ai.git
cd nova-ai
```

**2. Create virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables:**
Create a `.env` file in the root directory (copy from `.env.example`):
```bash
cp .env.example .env
```

Then edit `.env` with your actual API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PAYOS_CLIENT_ID=your_payos_client_id
PAYOS_API_KEY=your_payos_api_key
PAYOS_CHECKSUM_KEY=your_payos_checksum_key
```

**Note:** The `.env` file is in `.gitignore` and will NOT be pushed to GitHub. Only `.env.example` is committed as a template.

**5. Initialize Database:**
Run Django migrations to set up the SQLite database:
```bash
python manage.py migrate
```

**6. Run the application:**
```bash
python manage.py runserver
```

**7. Access the platform:**
Open your browser and navigate to:
```
http://localhost:8000
```

---

## 📱 Core Features Walkthrough

### 🤖 AI Chatbot
- Multi-turn conversations with Google Gemini
- Real-time streaming via Server-Sent Events
- File attachment support (PDF, TXT, DOCX)
- Context memory across conversation turns
- Source citation for AI responses

### � Notebook LLM
- Import URLs for web content extraction
- Document upload (PDF, TXT, DOCX)
- Selenium-powered deep scraping with pagination
- Screenshot capture for visual context
- Knowledge source management per conversation

### �️ Mindmap AI
- Interactive SVG mindmap generation
- Zoom and pan controls
- Node editing (add, remove, modify)
- AI-powered hierarchical layout
- Export to SVG/PNG formats

### 🎨 Artifacts Panel
- Live code/content preview (Claude-style)
- Split-view and fullscreen modes
- Real-time rendering updates
- Multi-format support (HTML, CSS, JS, Markdown)

### � Slide Generation
- 10+ pre-designed slide layouts
- 6 customizable color themes
- PPTX and PDF export options
- AI-powered content structuring
- Playwright-based PDF rendering

### 💳 Pro Subscription
- PayOS payment gateway integration
- Automated webhook handling
- Subscription expiry tracking
- Feature gating for Pro tier
- Dynamic checkout link generation

---

## 📊 Project Structure

```
nova-ai/
├── chat/                  # AI chatbot application
│   ├── views.py           # Chat views and SSE streaming
│   ├── slide_views.py     # Slide generation API
│   ├── payment_views.py   # PayOS payment handling
│   ├── ai_service.py      # Gemini AI integration
│   ├── slide_service.py   # PPTX generation logic
│   └── models.py          # Conversation, Message, SlideDeck models
├── notebook/              # Notebook LLM application
│   ├── views.py           # Notebook management
│   └── notebook_service.py # Content processing
├── templates/             # HTML templates
│   └── chat/              # Chat interface templates
├── static/                # CSS, JS, images
│   └── css/               # Tailwind CSS output
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
└── README.md            # This file
```

---

## 🔐 Security Features

- **Django Security:** Built-in CSRF protection and XSS prevention
- **API Key Protection:** Environment variables for sensitive credentials
- **Payment Security:** PayOS checksum validation for webhooks
- **Input Validation:** Django forms with strict validation rules
- **SQL Injection Prevention:** Django ORM parameterized queries
- **Session Management:** Django session backend with secure cookies

---

## 🦾 Research Context

This project was developed as part of **Scientific Research at Kien Giang University**, exploring:
- Large Language Model (LLM) integration in web applications
- Knowledge-grounded AI responses through context injection
- Automated content generation (mindmaps, slides) using AI
- Payment gateway integration for SaaS subscription models
- Web scraping techniques for data extraction and processing

---

## 📄 License

This project is licensed under the MIT License.

---



## 👨‍💻 Author

**Thanh Nguyen-Nhut**
- **Role:** Full-Stack Developer / AI Integration Specialist
- **Responsibilities:** Django Backend, Google Gemini AI Integration, Selenium Web Scraping, Slide Generation System, PayOS Payment Integration
- **GitHub:** [@thanhnguyen221](https://github.com/thanhnguyen221)
- **LinkedIn:** [Thanh Nguyen](https://linkedin.com/in/nhut-thanh-nguyen-6041343b2)
- **Email:** thanhfff55@gmail.com
---

<p align="center">
  Made with ❤️ and ☕ | Nova AI 🤖
</p>
