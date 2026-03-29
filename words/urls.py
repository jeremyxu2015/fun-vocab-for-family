from django.urls import path
from . import views

urlpatterns = [
    # 登录相关
    path('', views.student_login, name='login'),
    path('login/', views.student_login, name='login'),
    path('student-login/', views.student_login, name='student_login'),
    path('student-register/', views.student_register, name='student_register'),
    path('teacher-login/', views.teacher_login, name='teacher_login'),
    path('logout/', views.logout_view, name='logout'),
    path('teacher/codes/generate/', views.generate_registration_code, name='generate_code'),
    path('teacher/codes/', views.registration_code_list, name='registration_code_list'),
    path('teacher/codes/revoke/<int:code_id>/', views.revoke_code, name='revoke_code'),
    path('game/', views.game_study, name='game_study'),
    path('snake/', views.snake_game, name='snake_game'),
    path('snake/word-bank/', views.snake_word_bank, name='snake_word_bank'),
    path('snake/mp/create/', views.mp_create_room, name='mp_create_room'),
    path('snake/mp/join/', views.mp_join_room, name='mp_join_room'),
    path('snake/mp/status/', views.mp_room_status, name='mp_room_status'),
    path('snake/mp/sync/', views.mp_sync_score, name='mp_sync_score'),
    path('snake/mp/leave/', views.mp_leave_room, name='mp_leave_room'),
    path('game/challenge/', views.game_challenge, name='game_challenge'),
    path('game/answer/', views.game_answer, name='game_answer'),
    path('snake/answer/', views.snake_answer, name='snake_answer'),
    
    # 学生学习
    path('dashboard/', views.dashboard, name='dashboard'),
    path('study/', views.study, name='study'),
    path('training/', views.training, name='training'),
    path('training/challenge/', views.training_challenge, name='training_challenge'),
    path('training/answer/', views.training_answer, name='training_answer'),
    path('review/', views.review, name='review'),
    path('answer/<int:word_id>/', views.answer, name='answer'),
    path('ranking/', views.class_ranking, name='ranking'),
    path('change-password/', views.change_password, name='change_password'),
    
    # 教师管理
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/students/', views.student_management, name='student_management'),
    path('teacher/students/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    path('teacher/students/update-class/<int:student_id>/', views.update_student_class, name='update_student_class'),
    path('teacher/students/import/', views.import_students, name='import_students'),
    path('teacher/words/', views.word_management, name='word_management'),
    path('teacher/words/add/', views.add_word, name='add_word'),
    path('teacher/words/bulk-add/', views.bulk_add_words, name='bulk_add_words'),
    path('teacher/homework/', views.homework_management, name='homework_management'),
    path('teacher/homework/create/', views.create_homework, name='create_homework'),
    path('teacher/change-password/', views.teacher_change_password, name='teacher_change_password'),
    path('teacher/classes/', views.class_management, name='class_management'),
    path('teacher/words/edit/<int:word_id>/', views.edit_word, name='edit_word'),
    path('teacher/words/delete/<int:word_id>/', views.delete_word, name='delete_word'),
]
