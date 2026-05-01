from django.contrib import admin
from .models import Conversation, Message, SlideDeck, Slide, SlideExport

class MessageInline(admin.TabularInline):
    model = Message
    extra = 1

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'notebook_count')
    list_filter = ('user', 'created_at')
    search_fields = ('title', 'user__username')
    readonly_fields = ('notebook_files_preview', 'created_at', 'updated_at')
    fields = ('title', 'user', 'notebook_files_preview', 'created_at', 'updated_at')
    inlines = [MessageInline]

    def notebook_count(self, obj):
        return len(obj.notebook_files) if obj.notebook_files else 0
    notebook_count.short_description = 'Sources'

    def notebook_files_preview(self, obj):
        if not obj.notebook_files:
            return "Chưa có sources"
        
        html = '<div style="background:#1e293b;padding:10px;border-radius:5px;max-height:400px;overflow:auto;">'
        html += f'<h3 style="color:#fff;margin:0 0 10px 0;">{len(obj.notebook_files)} sources:</h3>'
        
        for i, item in enumerate(obj.notebook_files, 1):
            item_type = item.get('type', 'unknown')
            if item_type == 'url':
                url = item.get('url', '')
                title = item.get('title', 'Không có tiêu đề')
                content = item.get('content', '')[:100] + '...' if item.get('content') else ''
                html += f'''
                <div style="background:#334155;margin:5px 0;padding:8px;border-radius:3px;">
                    <b style="color:#60a5fa;">#{i} 🔗 URL:</b> 
                    <a href="{url}" target="_blank" style="color:#93c5fd;">{title}</a><br>
                    <small style="color:#94a3b8;">{url}</small><br>
                    <small style="color:#cbd5e1;">{content}</small>
                </div>
                '''
            else:
                name = item.get('name', 'Không có tên')
                path = item.get('path', '')
                html += f'''
                <div style="background:#334155;margin:5px 0;padding:8px;border-radius:3px;">
                    <b style="color:#4ade80;">#{i} 📄 File:</b> {name}<br>
                    <small style="color:#94a3b8;">{path}</small>
                </div>
                '''
        html += '</div>'
        return html
    notebook_files_preview.short_description = 'Notebook Sources'
    notebook_files_preview.allow_tags = True

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'created_at')
    list_filter = ('role', 'created_at')

class SlideInline(admin.TabularInline):
    model = Slide
    extra = 0

@admin.register(SlideDeck)
class SlideDeckAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'slide_count', 'theme', 'created_at')
    list_filter = ('theme', 'created_at')
    search_fields = ('title', 'user__username')
    inlines = [SlideInline]

@admin.register(Slide)
class SlideAdmin(admin.ModelAdmin):
    list_display = ('deck', 'order', 'layout', 'created_at')
    list_filter = ('layout', 'created_at')
    search_fields = ('deck__title',)

@admin.register(SlideExport)
class SlideExportAdmin(admin.ModelAdmin):
    list_display = ('deck', 'format', 'file_size', 'download_count', 'created_at')
    list_filter = ('format', 'created_at')
    search_fields = ('deck__title',)
