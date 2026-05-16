"""
家庭背单词应用URL路由
"""
from django.urls import path
from . import views

urlpatterns = [
    # 首页和登录
    path('', views.login_page, name='home'),
    path('login/', views.login_page, name='login'),

    # 认证相关
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/register/', views.parent_register, name='parent_register'),
    path('child/login/', views.child_login, name='child_login'),
    path('child/register/', views.child_register, name='child_register'),
    path('logout/', views.logout_view, name='logout'),

    # 家长功能
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/children/', views.child_management, name='child_management'),
    path('parent/words/', views.word_management, name='word_management'),
    path('parent/words/add/', views.add_word, name='add_word'),
    path('parent/words/bulk-add/', views.bulk_add_words, name='bulk_add_words'),
    path('parent/words/edit/<int:word_id>/', views.edit_word, name='edit_word'),
    path('parent/words/delete/<int:word_id>/', views.delete_word, name='delete_word'),
    path('parent/pdf-import/', views.pdf_import, name='pdf_import'),
    path('parent/tasks/', views.task_management, name='task_management'),
    path('parent/tasks/create/', views.create_task, name='create_task'),

    # 孩子功能
    path('child/', views.child_dashboard, name='child_dashboard'),
    path('dashboard/', views.child_dashboard, name='dashboard'),  # 兼容旧链接
    path('study/', views.study, name='study'),
    path('review/', views.review, name='review'),
    path('answer/<int:word_id>/', views.answer, name='answer'),
    path('training/', views.training, name='training'),
    path('training/challenge/', views.training_challenge, name='training_challenge'),
    path('training/answer/', views.training_answer, name='training_answer'),

    # 游戏功能
    path('game/', views.game_study, name='game_study'),
    path('game/challenge/', views.game_challenge, name='game_challenge'),
    path('game/answer/', views.game_answer, name='game_answer'),
    path('snake/', views.snake_game, name='snake_game'),
    path('snake/word-bank/', views.snake_word_bank, name='snake_word_bank'),
    path('snake/answer/', views.snake_answer, name='snake_answer'),

    # 联机对战
    path('snake/mp/create/', views.mp_create_room, name='mp_create_room'),
    path('snake/mp/join/', views.mp_join_room, name='mp_join_room'),
    path('snake/mp/status/', views.mp_room_status, name='mp_room_status'),
    path('snake/mp/sync/', views.mp_sync_score, name='mp_sync_score'),
    path('snake/mp/leave/', views.mp_leave_room, name='mp_leave_room'),

    # 密码修改
    path('change-password/', views.change_password, name='change_password'),
]
