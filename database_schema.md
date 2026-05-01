# Tài Liệu Thiết Kế Cơ Sở Dữ Liệu - Nova AI Project

## Tổng Quan

Cơ sở dữ liệu của dự án Nova AI được thiết kế trên Django ORM với SQLite (phát triển) và hỗ trợ PostgreSQL (production). Gồm 6 bảng chính phân thành 3 nhóm chức năng:

1. **Nhóm Chat AI**: Quản lý hội thoại và tin nhắn
2. **Nhóm Slide/Presentation**: Quản lý bài thuyết trình và slide
3. **Nhóm User Management**: Quản lý người dùng và subscription

---

## 1. Bảng Conversation (Cuộc Hội Thoại)

### Ý Nghĩa
Lưu trữ các cuộc hội thoại chat giữa người dùng và AI. Mỗi conversation chứa nhiều messages.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | Khóa chính |
| user_id | INTEGER | FOREIGN KEY → User (nullable) | Người dùng sở hữu |
| title | VARCHAR(255) | DEFAULT='New Chat' | Tiêu đề cuộc hội thoại |
| notebook_files | JSON | NULL, DEFAULT=[] | Danh sách files/URLs trong Notebook LLM |
| created_at | DATETIME | AUTO_ADD | Thời gian tạo |
| updated_at | DATETIME | AUTO_UPDATE | Thời gian cập nhật cuối |

### Mối Quan Hệ
- **1-n với Message**: Một conversation có nhiều messages
- **n-1 với User**: Nhiều conversation thuộc về một user

---

## 2. Bảng Message (Tin Nhắn)

### Ý Nghĩa
Lưu trữ từng tin nhắn trong cuộc hội thoại, bao gồm nội dung từ user và phản hồi từ AI.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY | Khóa chính |
| conversation_id | INTEGER | FOREIGN KEY → Conversation, CASCADE | Thuộc về conversation |
| role | VARCHAR(10) | CHOICE('user', 'model') | Vai trò (người dùng/AI) |
| content | TEXT | NOT NULL | Nội dung tin nhắn |
| thinking_process | TEXT | NULL | Quá trình suy nghĩ của AI (reasoning) |
| sources | TEXT | NULL | Nguồn tham khảo |
| attachments | JSON | DEFAULT=[] | File đính kèm |
| created_at | DATETIME | AUTO_ADD | Thời gian gửi |

### Mối Quan Hệ
- **n-1 với Conversation**: Nhiều messages thuộc về một conversation
- **related_name='messages'**: Truy cập ngược từ Conversation

---

## 3. Bảng SlideDeck (Bài Thuyết Trình)

### Ý Nghĩa
Container cho các bài thuyết trình/presentation. Lưu thông tin tổng thể về theme, tỷ lệ khung hình.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY | Khóa chính |
| user_id | INTEGER | FOREIGN KEY → User, CASCADE | Người sở hữu |
| title | VARCHAR(255) | DEFAULT='Untitled' | Tên bài thuyết trình |
| description | TEXT | NULL | Mô tả |
| theme | VARCHAR(20) | CHOICE(modern, light, gradient, minimal, corporate, creative) | Giao diện theme |
| aspect_ratio | VARCHAR(10) | DEFAULT='16:9', CHOICE(16:9, 4:3, 21:9) | Tỷ lệ màn hình |
| is_public | BOOLEAN | DEFAULT=False | Công khai hay riêng tư |
| created_at | DATETIME | AUTO_ADD | Ngày tạo |
| updated_at | DATETIME | AUTO_UPDATE | Ngày cập nhật |

### Mối Quan Hệ
- **n-1 với User**: Nhiều decks thuộc về một user
- **1-n với Slide**: Một deck chứa nhiều slides
- **1-n với SlideExport**: Một deck có nhiều lịch sử xuất file

---

## 4. Bảng Slide (Slide Trong Deck)

### Ý Nghĩa
Lưu trữ từng slide riêng lẻ với layout và nội dung JSON. Hỗ trợ nhiều loại layout khác nhau.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY | Khóa chính |
| deck_id | INTEGER | FOREIGN KEY → SlideDeck, CASCADE | Thuộc về deck |
| order | INTEGER | DEFAULT=0 | Thứ tự hiển thị |
| layout | VARCHAR(20) | CHOICE(title, content, two-column, image-text, text-image, full-image, quote, data, section, blank) | Kiểu bố cục |
| content | JSON | DEFAULT={} | Nội dung slide (text, hình ảnh, bullets...) |
| custom_css | TEXT | NULL | CSS tùy chỉnh |
| created_at | DATETIME | AUTO_ADD | Ngày tạo |
| updated_at | DATETIME | AUTO_UPDATE | Ngày cập nhật |

### Index và Ràng Buộc
- **Ordering**: `['order']` - Sắp xếp theo thứ tự
- **Unique**: Không có, nhưng `order` trong cùng deck nên duy nhất

### Mối Quan Hệ
- **n-1 với SlideDeck**: Nhiều slides thuộc về một deck
- **related_name='slides'**: Truy cập từ SlideDeck

---

## 5. Bảng SlideExport (Lịch Sử Xuất File)

### Ý Nghĩa
Theo dõi lịch sử xuất file (PPTX, PDF) của từng deck.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY | Khóa chính |
| deck_id | INTEGER | FOREIGN KEY → SlideDeck, CASCADE | Thuộc về deck |
| format | VARCHAR(10) | CHOICE(pptx, pdf, html, images) | Định dạng xuất |
| file | FILE | upload_to='slide_exports/' | File đã xuất |
| file_size | INTEGER | NOT NULL | Kích thước file (bytes) |
| download_count | INTEGER | DEFAULT=0 | Số lần tải |
| created_at | DATETIME | AUTO_ADD | Ngày xuất |

### Mối Quan Hệ
- **n-1 với SlideDeck**: Nhiều exports thuộc về một deck
- **related_name='exports'**: Truy cập từ SlideDeck

---

## 6. Bảng UserProfile (Hồ Sơ Người Dùng)

### Ý Nghĩa
Mở rộng thông tin User mặc định của Django, quản lý subscription Pro.

### Các Trường
| Tên Trường | Kiểu Dữ Liệu | Ràng Buộc | Mô Tả |
|------------|--------------|-----------|-------|
| id | INTEGER | PRIMARY KEY | Khóa chính |
| user_id | INTEGER | FOREIGN KEY → User, CASCADE, UNIQUE | One-to-one với User |
| is_pro | BOOLEAN | DEFAULT=False | Có phải Pro không |
| pro_expiry_date | DATETIME | NULL | Ngày hết hạn Pro |
| updated_at | DATETIME | AUTO_UPDATE | Cập nhật cuối |

### Mối Quan Hệ
- **1-1 với User**: Mỗi user có một profile
- **related_name='profile'**: Truy cập từ User

---

## Tóm Tắt Mối Quan Hệ

```
User (1) ────< (n) Conversation
     │
     ├───< (1) UserProfile (One-to-One)
     │
     └───< (n) SlideDeck
                  │
                  ├───< (n) Slide
                  │
                  └───< (n) SlideExport

Conversation (1) ────< (n) Message
```

## Biểu Đồ ER (Tóm Tắt)

| Bảng | Loại | Mối Quan Hệ Chính |
|------|------|-------------------|
| User | Hệ thống | 1-n Conversation, 1-n SlideDeck, 1-1 UserProfile |
| Conversation | Chat | n-1 User, 1-n Message |
| Message | Chat | n-1 Conversation |
| SlideDeck | Slide | n-1 User, 1-n Slide, 1-n SlideExport |
| Slide | Slide | n-1 SlideDeck |
| SlideExport | Slide | n-1 SlideDeck |
| UserProfile | User | 1-1 User |

---

## Lưu Ý Kỹ Thuật

1. **JSON Fields**: `content`, `notebook_files`, `attachments` lưu dạng JSON linh hoạt
2. **CASCADE Delete**: Xóa User/Deck sẽ xóa các records liên quan
3. **Auto Timestamps**: `created_at`, `updated_at` tự động cập nhật
4. **File Uploads**: `thumbnail`, `file` lưu trong thư mục media/
5. **Soft Delete**: Không có, xóa là xóa thật (CASCADE)
