# words/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Family, UserProfile, Word, UserWord, DailyStats, 
    FamilyTask, TaskProgress, GameProgress, PDFWordList
)
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# 取消默认注册，重新注册以自定义
admin.site.unregister(User)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'first_name', 'is_staff', 'date_joined']
    list_filter = ['is_staff', 'date_joined']
    search_fields = ['username', 'first_name']
    list_per_page = 20

# 自定义 Admin 站点标题
admin.site.site_header = '📚 词趣家庭'
admin.site.site_title = '词趣家庭'
admin.site.index_title = '欢迎使用词趣家庭管理系统'


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ['name', 'invite_code', 'created_at', 'member_count']
    search_fields = ['name', 'invite_code']
    
    @admin.display(description='成员数')
    def member_count(self, obj):
        return UserProfile.objects.filter(family=obj).count()


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'nickname', 'role', 'family', 'grade', 'daily_goal', 'current_streak']
    list_filter = ['role', 'family']
    search_fields = ['user__username', 'nickname']
    list_editable = ['daily_goal']


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ['word', 'pronunciation', 'category', 'difficulty', 'definition_preview']
    list_filter = ['category', 'difficulty']
    search_fields = ['word', 'definition']
    list_per_page = 20
    
    @admin.display(description='释义')
    def definition_preview(self, obj):
        if len(obj.definition) > 30:
            return obj.definition[:30] + '...'
        return obj.definition


@admin.register(UserWord)
class UserWordAdmin(admin.ModelAdmin):
    list_display = ['user', 'word', 'status', 'next_review', 'correct_count', 'wrong_count', 'ease_factor']
    list_filter = ['status', 'next_review']
    search_fields = ['user__username', 'word__word']
    date_hierarchy = 'next_review'


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'words_learned', 'words_reviewed']
    list_filter = ['date']
    search_fields = ['user__username']
    date_hierarchy = 'date'


@admin.register(FamilyTask)
class FamilyTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'parent', 'child', 'due_date', 'is_active', 'word_count']
    list_filter = ['is_active', 'due_date']
    filter_horizontal = ['words']
    
    @admin.display(description='单词数')
    def word_count(self, obj):
        return obj.words.count()


@admin.register(GameProgress)
class GameProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_level', 'total_score', 'max_combo']
    search_fields = ['user__username']


@admin.register(PDFWordList)
class PDFWordListAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'family', 'uploaded_by', 'words_extracted', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['file_name']
