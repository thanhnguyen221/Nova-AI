# Nova AI - Hướng Dẫn Sử Dụng

## 🚀 Giới Thiệu

Nova AI là chatbot AI đa chức năng tích hợp **Notebook LLM** và **Slide Deck**.  
Hỗ trợ chat với nhiều mô hình Gemini, quản lý sources, và tạo presentation.

---

## 💬 Chat Cơ Bản

### Bắt đầu Chat
1. Vào trang chủ - tự động tạo chat mới
2. Nhập tin nhắn ở ô chat bên dưới
3. Chọn model AI từ dropdown (Gemini Flash, Pro, 2.0...)
4. Gửi tin nhắn - AI sẽ trả lời real-time

### Quản Lý Conversation
- **Tạo chat mới**: Click "New Chat" hoặc icon + ở sidebar
- **Chuyển chat**: Click tên chat trong sidebar
- **Xóa chat**: Click × bên cạnh tên chat
- **Tự động đặt tên**: Sau tin nhắn đầu tiên, AI tự đặt tên chat

### Tính Năng Chat
- **Streaming**: Xem AI trả lời từng chữ
- **Stop**: Bấm ⏹ để dừng AI đang trả lời
- **Regenerate**: Bấm 🔄 để AI viết lại câu trả lời
- **Edit**: Bấm ✏️ để sửa và gửi lại

---

## 📚 Notebook LLM

Notebook LLM cho phép import nguồn dữ liệu để AI tham khảo khi trả lời.

### Import URL Trực Tiếp
1. Ở panel **Notebook LLM** bên phải, tìm mục "Import Link"
2. Dán URL vào ô nhập (ví dụ: `https://...`)
3. Click "Import" hoặc bấm Enter
4. Chờ loading spinner xong - link sẽ vào "Đã Import"
5. Nếu có link liên quan, modal sẽ hiện để chọn import thêm

### Search Và Import
1. Nhập từ khóa ở ô "Tìm Kiếm Thông Minh"
2. Bấm 🔍 hoặc Enter
3. Kết quả chia 2 nhóm:
   - **Trong Notebook**: Sources đã có
   - **Từ Web**: Kết quả tìm từ DuckDuckGo
4. Click "+ Import" để import link từ web
5. Link sẽ tự động lưu vào Notebook

### Quản Lý Sources
- **Xem sources**: Panel "Đã Import" liệt kê tất cả
- **Xóa source**: Click 🗑️ bên cạnh source
- **Attach vào chat**: Click checkbox bên cạnh source

### Flow Import
```
Import URL → Cào dữ liệu → Lưu Notebook → Hiện link liên quan (optional)
```

---

## 🎨 Slide Deck (Presentation)

Tạo slide presentation từ AI.

### Tạo Slide Deck
1. Click **"Slide Deck"** ở menu
2. Chọn **"Tạo từ prompt"** hoặc **"Mở Slide Editor"**
3. Nhập chủ đề (ví dụ: "Marketing Plan 2024")
4. Chọn theme và aspect ratio
5. Click "Tạo" - AI sẽ tạo slides tự động

### Chỉnh Sửa Slides
- **Thêm slide**: Click "+"
- **Xóa slide**: Click 🗑️
- **Đổi layout**: Chọn từ dropdown (Title, Content, Two Column...)
- **Đổi theme**: Chọn theme ở dropdown trên
- **Sửa nội dung**: Click vào text để edit

### Layouts Có Sẵn
| Layout | Mô tả |
|--------|-------|
| Title | Slide tiêu đề |
| Content | Nội dung chính |
| Two Column | 2 cột nội dung |
| Image + Text | Ảnh bên trái, text bên phải |
| Text + Image | Text bên trái, ảnh bên phải |
| Full Image | Toàn màn hình ảnh |
| Quote | Trích dẫn |
| Data | Biểu đồ/dữ liệu |
| Section | Phân cách chương |

### Themes
- **Modern Dark**: Nền tối, accent tím
- **Clean Light**: Trắng sáng, xanh dương
- **Gradient Pop**: Gradient tím-vàng
- **Minimal White**: Tối giản trắng
- **Corporate Blue**: Xanh công ty
- **Creative Purple**: Tím sáng tạo

### Export
1. Ở slide editor, click "Export"
2. Chọn format: PPTX, PDF, HTML, Images
3. Chờ xử lý và tải về

---

## 🔧 Tính Năng Khác

### Image Search (cho Slides)
- Trong slide editor, click "🔍 Tìm ảnh"
- Nhập từ khóa, chọn ảnh phù hợp
- Ảnh tự động vào slide

### File Upload
- Kéo file vào chat hoặc click icon 📎
- Hỗ trợ: PDF, DOCX, TXT, v.v.
- File được xử lý và thêm vào Notebook

### Model Settings
- **Gemini 1.5 Flash**: Nhanh, miễn phí, giới hạn 1500 req/ngày
- **Gemini 1.5 Pro**: Chất lượng cao, 50 req/ngày
- **Gemini 2.0**: Mới nhất, 1000 req/ngày
- **Experimental**: Đang thử nghiệm

---

## ⚡ Tips

1. **Chat hiệu quả**: Import nguồn vào Notebook trước khi hỏi về nội dung đó
2. **Slide đẹp**: Chọn theme phù hợp mục đích (Corporate cho công việc, Creative cho thiết kế)
3. **Tiết kiệm quota**: Dùng Flash cho chat thường, Pro cho yêu cầu phức tạp
4. **Tổ chức**: Đặt tên chat rõ ràng để dễ tìm sau này

---

## 🐛 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| Import URL không được | Kiểm tra URL bắt đầu bằng http:// hoặc https:// |
| Search không ra kết quả | Thử từ khóa khác hoặc chế độ tìm kiếm |
| AI không trả lời | Kiểm tra API key hoặc quota |
| Slide không export được | Thử format khác hoặc refresh trang |

---

## 📝 Changelog

- **v1.0**: Chat cơ bản với Gemini
- **v1.5**: Thêm Notebook LLM, import URLs
- **v2.0**: Thêm Slide Deck, templates, export
- **v2.1**: Cải thiện UI, fix import flow
