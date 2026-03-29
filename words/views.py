from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages
from .models import Word, UserWord, DailyStats, UserProfile, Homework, HomeworkSubmission, GameProgress, RegistrationCode
from .decorators import teacher_required
import random
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
@login_required
@teacher_required
def student_management(request):
    """学生管理 - 显示详细背诵统计"""
    from django.db.models import Count, Case, When, IntegerField, Value
    
    teacher = request.user
    classes = UserProfile.objects.filter(
        is_teacher=False
    ).values_list('class_name', flat=True).distinct()
    
    selected_class = request.GET.get('class', '')
    
    # 增强查询：统计每个学生的单词掌握情况
    qs = User.objects.filter(userprofile__is_teacher=False)
    if selected_class:
        qs = qs.filter(userprofile__class_name=selected_class)
    students = qs.annotate(
        mastered_count=Count('userword', filter=Q(userword__status='mastered')),
        familiar_count=Count('userword', filter=Q(userword__status='familiar')),
        new_count=Count('userword', filter=Q(userword__status='new')),
        total_words=Count('userword'),
        today_learned=Count('dailystats', filter=Q(dailystats__date=timezone.now().date()))
    ).select_related('userprofile')
    
    # 计算班级平均掌握率
    total_mastered = sum(s.mastered_count for s in students)
    total_learned = sum(s.total_words for s in students)
    class_avg = (total_mastered / total_learned * 100) if total_learned > 0 else 0
    
    return render(request, 'words/teacher/student_management.html', {
        'students': students,
        'classes': classes,
        'selected_class': selected_class,
        'class_avg': round(class_avg, 1),
        'total_students': len(students)
    })
@login_required
def snake_game(request):
    """贪吃蛇背单词游戏"""
    return render(request, 'words/snake_game.html')


@login_required
def snake_word_bank(request):
    """AJAX: 返回随机释义列表（用于贪吃蛇干扰项，不创建 UserWord）"""
    words = list(Word.objects.values_list('definition', flat=True))
    random.shuffle(words)
    return JsonResponse({'definitions': words[:30]})


# ——— 贪吃蛇联机对战（内存房间） ———
import string as _string
import time as _time

_MP_ROOMS = {}  # {room_code: {creator, joiner, creator_score, joiner_score, ...}}

def _clean_old_rooms():
    """清理超过 30 分钟的房间"""
    now = _time.time()
    expired = [k for k, v in _MP_ROOMS.items() if now - v.get('created', 0) > 1800]
    for k in expired:
        del _MP_ROOMS[k]

@login_required
@csrf_exempt
def mp_create_room(request):
    """创建联机房间"""
    _clean_old_rooms()
    # 生成 4 位数字房间号
    for _ in range(100):
        code = ''.join(random.choices(_string.digits, k=4))
        if code not in _MP_ROOMS:
            break
    _MP_ROOMS[code] = {
        'creator': request.user.id,
        'creator_name': request.user.first_name or request.user.username,
        'joiner': None,
        'joiner_name': '',
        'started': False,
        'creator_score': 0, 'creator_words': 0, 'creator_lives': 3,
        'joiner_score': 0, 'joiner_words': 0, 'joiner_lives': 3,
        'created': _time.time(),
    }
    return JsonResponse({'room_code': code})

@login_required
@csrf_exempt
def mp_join_room(request):
    """加入联机房间"""
    code = request.POST.get('room_code', '')
    room = _MP_ROOMS.get(code)
    if not room:
        return JsonResponse({'error': '房间不存在'})
    if room['started']:
        return JsonResponse({'error': '房间已开始'})
    if room['joiner']:
        return JsonResponse({'error': '房间已满'})
    room['joiner'] = request.user.id
    room['joiner_name'] = request.user.first_name or request.user.username
    room['started'] = True
    return JsonResponse({'ok': True, 'opponent': room['creator_name']})

@login_required
def mp_room_status(request):
    """查询房间状态（创建者轮询用）"""
    code = request.GET.get('room_code', '')
    room = _MP_ROOMS.get(code)
    if not room:
        return JsonResponse({'error': '房间不存在'})
    return JsonResponse({
        'started': room['started'],
        'opponent': room['joiner_name'] if room['joiner'] else None,
    })

@login_required
@csrf_exempt
def mp_sync_score(request):
    """同步分数"""
    code = request.POST.get('room_code', '')
    room = _MP_ROOMS.get(code)
    if not room:
        return JsonResponse({'error': '房间不存在'})

    uid = request.user.id
    s = int(request.POST.get('score', 0))
    w = int(request.POST.get('words', 0))
    l = int(request.POST.get('lives', 0))

    if uid == room['creator']:
        room['creator_score'] = s
        room['creator_words'] = w
        room['creator_lives'] = l
        return JsonResponse({
            'opponent_score': room['joiner_score'],
            'opponent_words': room['joiner_words'],
            'opponent_lives': room['joiner_lives'],
        })
    else:
        room['joiner_score'] = s
        room['joiner_words'] = w
        room['joiner_lives'] = l
        return JsonResponse({
            'opponent_score': room['creator_score'],
            'opponent_words': room['creator_words'],
            'opponent_lives': room['creator_lives'],
        })

@login_required
@csrf_exempt
def mp_leave_room(request):
    """离开房间"""
    code = request.POST.get('room_code', '')
    if code in _MP_ROOMS:
        del _MP_ROOMS[code]
    return JsonResponse({'ok': True})


@login_required
def game_challenge(request):
    """AJAX 获取挑战单词"""
    user = request.user
    
    # 优先获取待复习的单词
    review_word = UserWord.objects.filter(
        user=user,
        next_review__lte=timezone.now()
    ).select_related('word').first()
    
    if review_word:
        mode = 'review'
        word = review_word.word
        user_word = review_word
    else:
        # 其次获取新单词（未学习）
        learned_ids = UserWord.objects.filter(user=user).values_list('word_id', flat=True)
        new_word = Word.objects.exclude(id__in=learned_ids).first()
        
        if not new_word:
            return JsonResponse({'game_clear': True, 'message': '恭喜！你已学完所有单词！'})
        
        mode = 'new'
        word = new_word
        user_word, _ = UserWord.objects.get_or_create(user=user, word=word)
    
    return JsonResponse({
        'word_id': word.id,
        'word': word.word,
        'pronunciation': word.pronunciation,
        'definition': word.definition,
        'example': word.example,
        'mode': mode,  # 'review' 需要填空，'new' 显示选择
        'status': user_word.status
    })

@login_required
@csrf_exempt
def snake_answer(request):
    """贪吃蛇游戏提交答案"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'})
    
    word_id = request.POST.get('word_id')
    user_input = request.POST.get('user_input', '').strip().lower()
    mode = request.POST.get('mode')  # 'review' 或 'new'
    
    word = get_object_or_404(Word, id=word_id)
    user_word, created = UserWord.objects.get_or_create(user=request.user, word=word)
    
    # 验证逻辑
    import re
    correct = False
    
    def strip_pos(text):
        """去掉词性前缀，如 'n. 苹果' → '苹果'、'adj. 好的' → '好的'"""
        return re.sub(r'^[a-zA-Z]+\.\s*', '', text.strip())
    
    def get_clean_definitions(definition_text):
        """拆分多个释义并去掉词性，返回纯中文列表"""
        parts = re.split(r'[；;，,、]', definition_text)
        return [strip_pos(p).lower() for p in parts if strip_pos(p)]
    
    clean_defs = get_clean_definitions(word.definition)
    
    if mode == 'review':
        # 复习模式：匹配任意一个释义即算对（去掉词性后比较）
        correct = any(
            user_input == d or user_input in d or d in user_input
            for d in clean_defs
        ) or user_input == word.word.lower()
    else:
        # 新学模式：前端传回答案正确与否（基于选择）
        is_correct = request.POST.get('is_correct') == 'true'
        correct = is_correct
    
    # 显示用的释义（不带词性）
    display_defs = '、'.join(get_clean_definitions(word.definition))
    
    if correct:
        # 更新 SM-2
        from .utils import calculate_next_review
        calculate_next_review(user_word, 5)  # 满分
        
        # 奖励
        score = 10 + (user_word.streak * 2 if hasattr(user_word, 'streak') else 0)
        
        return JsonResponse({
            'correct': True,
            'message': '回答正确！继续游戏！',
            'score': score,
            'interval': user_word.interval
        })
    else:
        # 错误惩罚
        user_word.wrong_count += 1
        user_word.save()
        
        return JsonResponse({
            'correct': False,
            'message': f'错误！正确答案是：{display_defs}',
            'game_over': mode == 'review'  # 复习模式错误即游戏结束
        })

@login_required
def game_study(request):
    """游戏模式：闯关背单词"""
    user = request.user
    progress, _ = GameProgress.objects.get_or_create(user=user)
    
    # 每关5个单词，根据等级选择难度
    words_per_level = 5
    difficulty = min(progress.current_level // 5 + 1, 5)  # 每5关升难度
    
    # 获取当前关卡单词（优先作业，其次按难度，最后不限难度）
    words = []
    if hasattr(user, 'userprofile'):
        homework = Homework.objects.filter(
            class_name=user.userprofile.class_name,
            is_active=True,
            due_date__gte=timezone.now().date()
        ).first()
        if homework:
            words = list(homework.words.all()[:words_per_level])
    
    if len(words) < words_per_level:
        # 先尝试按难度获取
        words = list(Word.objects.filter(difficulty=difficulty)[:words_per_level])
    
    if len(words) < words_per_level:
        # 不限难度，随机取够
        words = list(Word.objects.order_by('?')[:words_per_level])
    
    if not words:
        messages.info(request, '还没有导入单词，请联系老师添加单词！')
        return redirect('dashboard')
    
    # 选择出题单词
    word = random.choice(words)
    
    # 生成4个选项（包含正确答案 + 3个干扰项）
    other_words = list(Word.objects.exclude(id=word.id).order_by('?')[:3])
    options = other_words + [word]
    random.shuffle(options)
    
    return render(request, 'words/game.html', {
        'word': word,
        'options': options,
        'progress': progress,
        'level': progress.current_level,
        'lives': '❤️' * progress.lives
    })

@csrf_exempt
@login_required
def game_answer(request):
    """游戏模式答题"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'})
    
    word_id = request.POST.get('word_id')
    selected_id = request.POST.get('selected_id')
    
    word = get_object_or_404(Word, id=word_id)
    user_word, created = UserWord.objects.get_or_create(user=request.user, word=word)
    progress = GameProgress.objects.get(user=request.user)
    
    correct = (str(word_id) == str(selected_id))
    points = 0
    
    if correct:
        # 答对：连击+1，加积分
        progress.combo += 1
        if progress.combo > progress.max_combo:
            progress.max_combo = progress.combo
        points = progress.add_score(10)
        
        # SM-2算法更新
        from .utils import calculate_next_review
        calculate_next_review(user_word, 5)  # 游戏模式默认满分
        
        # 检查通关（每5关一个Boss）
        if progress.combo >= 5:
            progress.current_level += 1
            progress.combo = 0
            progress.lives = min(progress.lives + 1, 5)  # 通关奖励生命
            progress.save()
            return JsonResponse({
                'correct': True,
                'points': points,
                'level_up': True,
                'message': f'🎉 通关！进入第 {progress.current_level} 关！'
            })
    else:
        # 答错：连击中断，扣生命
        progress.combo = 0
        progress.lives -= 1
        progress.save()
        
        if progress.lives <= 0:
            # 生命耗尽，降级或重来
            if progress.current_level > 1:
                progress.current_level -= 1
            progress.lives = 3
            progress.save()
            return JsonResponse({
                'correct': False,
                'game_over': True,
                'message': '💔 生命耗尽，退回上一关！'
            })
    
    progress.save()
    return JsonResponse({
        'correct': correct,
        'points': points if correct else 0,
        'combo': progress.combo,
        'lives': progress.lives,
        'total_score': progress.total_score
    })

# ========== 学生登录（学号+班级） ==========
def student_login(request):
    """学生登录（班级+学号+密码）"""
    # 已登录用户直接跳转
    if request.user.is_authenticated:
        if hasattr(request.user, 'userprofile') and request.user.userprofile.is_teacher:
            return redirect('teacher_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        student_id = request.POST.get('student_id')
        password = request.POST.get('password', '')

        username = f"{class_name}_{student_id}"
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, '❌ 班级、学号或密码错误，请重试')

    return render(request, 'words/student_login.html')


def student_register(request):
    """学生注册（需教师验证码）"""
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        reg_code = request.POST.get('registration_code', '').strip()
        student_id = request.POST.get('student_id')
        real_name = request.POST.get('real_name')

        # 验证注册码
        try:
            code_obj = RegistrationCode.objects.get(
                code=reg_code,
                class_name=class_name,
                is_used=False
            )
            if not code_obj.is_valid():
                if timezone.now() > code_obj.expires_at:
                    messages.error(request, '❌ 验证码已过期，请联系老师重新获取')
                else:
                    messages.error(request, '❌ 验证码使用次数已达上限')
                return render(request, 'words/student_register.html')
        except RegistrationCode.DoesNotExist:
            messages.error(request, '❌ 验证码无效，请确认：1.班级选择正确 2.输入无误')
            return render(request, 'words/student_register.html')

        # 创建账号
        username = f"{class_name}_{student_id}"
        if User.objects.filter(username=username).exists():
            messages.error(request, '❌ 该班级学号已被注册，请直接登录')
            return render(request, 'words/student_register.html')

        try:
            user = User.objects.create_user(
                username=username,
                password=student_id,  # 初始密码=学号
                first_name=real_name
            )
            UserProfile.objects.create(
                user=user,
                student_id=student_id,
                class_name=class_name,
                real_name=real_name
            )
            code_obj.use(user)
            messages.success(request, f'🎉 注册成功！班级：{class_name}，学号：{student_id}，初始密码为学号，请登录后修改密码')
            return redirect('student_login')
        except Exception:
            messages.error(request, '❌ 注册失败，请重试')

    return render(request, 'words/student_register.html')
@login_required
@teacher_required
def generate_registration_code(request):
    """教师生成注册验证码"""
    if request.method == 'POST':
        class_name = request.POST.get('class_name')
        valid_minutes = int(request.POST.get('valid_minutes', 15))
        max_uses = int(request.POST.get('max_uses', 1))
        
        if not class_name:
            messages.error(request, '请选择班级')
            return redirect('generate_registration_code')
        
        code_obj = RegistrationCode.generate_code(
            class_name=class_name,
            teacher=request.user,
            max_uses=max_uses,
            valid_minutes=valid_minutes
        )
        
        messages.success(request, 
            f'✅ 验证码已生成：【{code_obj.code}】，有效期{valid_minutes}分钟，可使用{max_uses}次')
        return redirect('registration_code_list')
    
    # 获取教师管理的班级（从现有学生班级中提取）
    classes = UserProfile.objects.filter(
        is_teacher=False
    ).values_list('class_name', flat=True).distinct()
    
    return render(request, 'words/teacher/generate_code.html', {
        'classes': classes
    })

@login_required
@teacher_required
def registration_code_list(request):
    """查看验证码列表"""
    codes = RegistrationCode.objects.filter(
        teacher=request.user
    ).order_by('-created_at')[:50]
    
    return render(request, 'words/teacher/code_list.html', {
        'codes': codes
    })

@login_required
@teacher_required
def revoke_code(request, code_id):
    """作废验证码"""
    code = get_object_or_404(RegistrationCode, id=code_id, teacher=request.user)
    code.is_used = True  # 强制标记为已使用
    code.save()
    messages.success(request, f'验证码 {code.code} 已作废')
    return redirect('registration_code_list')

def teacher_login(request):
    """教师用传统方式登录"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and hasattr(user, 'userprofile') and user.userprofile.is_teacher:
            login(request, user)
            return redirect('teacher_dashboard')
        else:
            messages.error(request, '教师账号或密码错误')
    
    return render(request, 'words/teacher_login.html')

def logout_view(request):
    logout(request)
    return redirect('student_login')

# ========== 学生功能 ==========
@login_required
def dashboard(request):
    """学生仪表盘（教师自动跳转教师后台）"""
    user = request.user

    # 教师直接跳教师后台
    if hasattr(user, 'userprofile') and user.userprofile.is_teacher:
        return redirect('teacher_dashboard')

    today = timezone.now().date()
    
    # 今日作业
    try:
        homework = Homework.objects.filter(
            class_name=user.userprofile.class_name,
            is_active=True,
            due_date__gte=today
        ).first()
        
        hw_progress = None
        if homework:
            submission, _ = HomeworkSubmission.objects.get_or_create(
                homework=homework,
                student=user
            )
            total = homework.words.count()
            completed = UserWord.objects.filter(
                user=user,
                word__in=homework.words.all(),
                status='mastered'
            ).count()
            hw_progress = {
                'total': total,
                'completed': completed,
                'percent': int(completed/total*100) if total > 0 else 0
            }
    except:
        homework = None
        hw_progress = None
    
    # 统计数据
    due_count = UserWord.objects.filter(user=user, next_review__lte=timezone.now()).count()
    learned_count = UserWord.objects.filter(user=user, status='mastered').count()
    
    # 班级排名
    class_students = User.objects.filter(userprofile__class_name=user.userprofile.class_name)
    my_rank = list(class_students.annotate(
        mastered_count=Count('userword', filter=Q(userword__status='mastered'))
    ).order_by('-mastered_count').values_list('id', flat=True)).index(user.id) + 1 if user in class_students else 0
    
    context = {
        'homework': homework,
        'hw_progress': hw_progress,
        'due_count': due_count,
        'learned_count': learned_count,
        'my_rank': my_rank,
        'class_total': class_students.count()
    }
    return render(request, 'words/dashboard.html', context)

@login_required
def study(request):
    """学习模式：优先做作业，其次复习"""
    user = request.user
    
    # 检查是否有未完成的作业
    today = timezone.now().date()
    homework = Homework.objects.filter(
        class_name=user.userprofile.class_name,
        is_active=True,
        due_date__gte=today
    ).first()
    
    if homework:
        # 找作业中未掌握的单词
        hw_words = homework.words.exclude(
            id__in=UserWord.objects.filter(user=user, status='mastered').values_list('word_id', flat=True)
        )
        if hw_words.exists():
            word = random.choice(list(hw_words))
            return render(request, 'words/study.html', {
                'word': word,
                'mode': 'homework',
                'homework': homework
            })
    
    # 正常学习新词
    existing = UserWord.objects.filter(user=user).values_list('word_id', flat=True)
    new_words = Word.objects.exclude(id__in=existing)[:10]
    
    if not new_words:
        return redirect('review')
    
    word = random.choice(list(new_words))
    return render(request, 'words/study.html', {'word': word, 'mode': 'learning'})


@login_required
def training(request):
    """个性化强化训练 — 页面"""
    user = request.user

    # 统计薄弱词数量
    weak_words = UserWord.objects.filter(user=user).exclude(status='mastered')
    weak_count = weak_words.filter(wrong_count__gt=0).count()
    low_ease = weak_words.filter(ease_factor__lt=2.0).count()
    familiar_count = weak_words.filter(status='familiar').count()
    new_count = weak_words.filter(status='new').count()
    total_learned = UserWord.objects.filter(user=user).count()

    return render(request, 'words/training.html', {
        'weak_count': weak_count,
        'low_ease': low_ease,
        'familiar_count': familiar_count,
        'new_count': new_count,
        'total_learned': total_learned,
    })


@login_required
def training_challenge(request):
    """AJAX: 获取强化训练题目（个性化推送最薄弱的词）"""
    import json
    user = request.user
    mode = request.GET.get('mode', 'auto')  # auto / wrong / low_ease / spelling

    # 根据模式选词
    if mode == 'wrong':
        # 错题优先
        candidates = UserWord.objects.filter(
            user=user, wrong_count__gt=0
        ).exclude(status='mastered').select_related('word').order_by('-wrong_count')
    elif mode == 'low_ease':
        # 低 ease_factor（学起来最难的词）
        candidates = UserWord.objects.filter(
            user=user, ease_factor__lt=2.0
        ).exclude(status='mastered').select_related('word').order_by('ease_factor')
    elif mode == 'spelling':
        # 拼写训练：已 familiar 但未 mastered
        candidates = UserWord.objects.filter(
            user=user, status='familiar'
        ).select_related('word').order_by('ease_factor')
    else:
        # auto: 综合排序 — 错误多 + ease_factor 低 + 状态弱
        candidates = UserWord.objects.filter(
            user=user
        ).exclude(status='mastered').select_related('word').order_by(
            '-wrong_count', 'ease_factor', 'correct_count'
        )

    if not candidates.exists():
        return JsonResponse({'done': True, 'message': '太棒了！没有需要强化的单词了 🎉'})

    # 取前 10 个弱词中随机一个，避免总是同一个
    pool = list(candidates[:10])
    user_word = random.choice(pool)
    word = user_word.word

    # 生成 4 个选项 (1 正确 + 3 干扰)
    all_words = list(Word.objects.exclude(id=word.id).values_list('definition', flat=True))
    random.shuffle(all_words)
    wrong_defs = all_words[:3]
    # 如果库不够
    while len(wrong_defs) < 3:
        wrong_defs.append('???')

    options = wrong_defs + [word.definition]
    random.shuffle(options)

    # 决定题目类型
    if mode == 'spelling':
        q_type = 'spelling'  # 拼写题
    elif user_word.correct_count >= 2 and random.random() > 0.5:
        q_type = 'cn2en'  # 看中文选英文（更难）
    else:
        q_type = 'en2cn'  # 看英文选中文

    # 看中文选英文的选项
    if q_type == 'cn2en':
        en_words = list(Word.objects.exclude(id=word.id).values_list('word', flat=True))
        random.shuffle(en_words)
        en_options = en_words[:3] + [word.word]
        random.shuffle(en_options)
        options = en_options

    return JsonResponse({
        'word_id': word.id,
        'word': word.word,
        'pronunciation': word.pronunciation,
        'definition': word.definition,
        'type': q_type,  # en2cn / cn2en / spelling
        'options': options,
        'wrong_count': user_word.wrong_count,
        'correct_count': user_word.correct_count,
        'ease_factor': round(user_word.ease_factor, 2),
        'status': user_word.status,
    })


@login_required
@csrf_exempt
def training_answer(request):
    """AJAX: 提交强化训练答案"""
    if request.method != 'POST':
        return JsonResponse({'error': '方法不允许'}, status=405)

    word_id = request.POST.get('word_id')
    answer = request.POST.get('answer', '').strip()
    q_type = request.POST.get('type', 'en2cn')

    word = get_object_or_404(Word, id=word_id)
    user_word, _ = UserWord.objects.get_or_create(user=request.user, word=word)

    import re
    correct = False

    def clean_def(text):
        return re.sub(r'^[a-zA-Z]+\.\s*', '', text.strip()).lower()

    if q_type == 'en2cn':
        # 检查用户选的释义是否正确
        clean_answer = clean_def(answer)
        clean_correct = [clean_def(p) for p in re.split(r'[；;，,、]', word.definition) if p.strip()]
        correct = any(
            clean_answer == d or clean_answer in d or d in clean_answer
            for d in clean_correct
        ) or answer.strip() == word.definition.strip()
    elif q_type == 'cn2en':
        # 检查用户选的英文是否正确
        correct = answer.strip().lower() == word.word.lower()
    elif q_type == 'spelling':
        # 拼写检查
        correct = answer.strip().lower() == word.word.lower()

    if correct:
        user_word.correct_count += 1
        user_word.wrong_count = max(0, user_word.wrong_count - 1)  # 强化训练答对减一次错误计数
        user_word.ease_factor = min(3.0, user_word.ease_factor + 0.1)
        if user_word.correct_count >= 5 and user_word.ease_factor >= 2.0:
            user_word.status = 'mastered'
        elif user_word.correct_count >= 2:
            user_word.status = 'familiar'
        user_word.save()
        return JsonResponse({
            'correct': True,
            'message': '正确！继续加油 💪',
            'new_status': user_word.status,
            'ease_factor': round(user_word.ease_factor, 2),
        })
    else:
        user_word.wrong_count += 1
        user_word.ease_factor = max(1.3, user_word.ease_factor - 0.15)
        user_word.save()

        hint = word.definition if q_type == 'en2cn' else word.word
        return JsonResponse({
            'correct': False,
            'message': f'错了！正确答案：{hint}',
            'definition': word.definition,
            'word': word.word,
            'pronunciation': word.pronunciation,
        })


@login_required
def review(request):
    """复习模式"""
    user = request.user
    due = UserWord.objects.filter(
        user=user,
        next_review__lte=timezone.now()
    ).select_related('word').first()
    
    if not due:
        return render(request, 'words/all_caught_up.html')
    
    return render(request, 'words/study.html', {
        'user_word': due,
        'word': due.word,
        'mode': 'review'
    })

@login_required
def answer(request, word_id):
    """使用 SM-2 算法的评分：1=没记住, 2=有点印象, 3=记住了"""
    if request.method == 'POST':
        # 将 1-3 分映射到 SM-2 的 0-5 分制
        quality_map = {1: 0, 2: 3, 3: 5}
        raw_quality = int(request.POST.get('quality', 2))
        quality = quality_map.get(raw_quality, 2)
        
        word = get_object_or_404(Word, id=word_id)
        
        user_word, created = UserWord.objects.get_or_create(
            user=request.user,
            word=word
        )
        
        # ✅ 使用 SM-2 算法计算下次复习时间
        from .utils import calculate_next_review
        interval = calculate_next_review(user_word, quality)
        
        # 根据质量更新状态（用于前端展示）
        if quality >= 4:  # 3分对应5分制
            user_word.status = 'mastered'
        elif quality >= 3:  # 2分对应3分制
            user_word.status = 'familiar'
        else:
            user_word.status = 'new'
        
        user_word.save()
        
        # 更新今日统计（区分新学和复习）
        today = timezone.now().date()
        stats, _ = DailyStats.objects.get_or_create(user=request.user, date=today)
        
        if created or user_word.total_reviews <= 1:
            # 新学单词
            stats.words_learned += 1
        else:
            # 复习单词
            stats.words_reviewed += 1
        stats.save()
        
        return JsonResponse({'success': True, 'interval': interval})
    
    return JsonResponse({'success': False})

@login_required
def class_ranking(request):
    """班级排行榜"""
    user = request.user
    class_name = user.userprofile.class_name
    
    students = User.objects.filter(
        userprofile__class_name=class_name,
        userprofile__is_teacher=False
    ).annotate(
        mastered_count=Count('userword', filter=Q(userword__status='mastered')),
        homework_done=Count('homeworksubmission')
    ).order_by('-mastered_count')[:20]
    
    return render(request, 'words/class_ranking.html', {
        'students': students,
        'my_id': user.id
    })

# ========== 教师功能 ==========
@login_required
@teacher_required
def teacher_dashboard(request):
    """教师控制台"""
    teacher = request.user
    classes = UserProfile.objects.filter(
        is_teacher=False
    ).values_list('class_name', flat=True).distinct()
    
    class_data = []
    for class_name in classes:
        if not class_name:
            continue
        students = User.objects.filter(userprofile__class_name=class_name)
        stats = {
            'name': class_name,
            'student_count': students.count(),
            'total_mastered': UserWord.objects.filter(
                user__in=students,
                status='mastered'
            ).count(),
            'active_homework': Homework.objects.filter(
                class_name=class_name,
                is_active=True
            ).count()
        }
        class_data.append(stats)
    
    return render(request, 'words/teacher/dashboard.html', {
        'classes': class_data
    })

@login_required
@teacher_required
def delete_student(request, student_id):
    """删除学生账号（调试用）"""
    student = get_object_or_404(User, id=student_id)
    
    # 安全校验
    if student == request.user:
        messages.error(request, '不能删除自己')
        return redirect('student_management')
    
    if hasattr(student, 'userprofile') and student.userprofile.is_teacher:
        messages.error(request, '不能删除教师')
        return redirect('student_management')
    
    username = student.userprofile.real_name or student.username
    student.delete()
    messages.success(request, f'已删除学生 {username}')
    return redirect('student_management')

@login_required
@teacher_required
def word_management(request):
    """单词管理"""
    words = Word.objects.all().order_by('textbook', 'unit')
    return render(request, 'words/teacher/word_management.html', {'words': words})

@login_required
@teacher_required
def add_word(request):
    """添加单词"""
    if request.method == 'POST':
        Word.objects.create(
            word=request.POST.get('word'),
            pronunciation=request.POST.get('pronunciation'),
            definition=request.POST.get('definition'),
            example=request.POST.get('example'),
            unit=request.POST.get('unit', 'Unit 1'),
            textbook=request.POST.get('textbook', '课本'),
            is_core=request.POST.get('is_core') == 'on'
        )
        messages.success(request, '单词添加成功')
        return redirect('word_management')
    return render(request, 'words/teacher/add_word.html')


@login_required
@teacher_required
def bulk_add_words(request):
    """批量添加单词"""
    if request.method == 'POST':
        mode = request.POST.get('mode', 'text')
        added = 0
        skipped = 0
        errors = []

        if mode == 'text':
            # 文本粘贴模式，每行格式：单词 | 释义 | 音标(可选)
            raw = request.POST.get('bulk_text', '')
            for i, line in enumerate(raw.strip().splitlines(), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 支持 | 或 tab 分隔
                parts = [p.strip() for p in line.replace('\t', '|').split('|')]
                if len(parts) < 2:
                    errors.append(f'第{i}行格式错误（至少需要 单词|释义）：{line}')
                    continue
                word_text = parts[0]
                definition = parts[1]
                pronunciation = parts[2] if len(parts) > 2 else ''
                difficulty = 3
                if len(parts) > 3:
                    try:
                        difficulty = int(parts[3])
                    except ValueError:
                        pass

                if Word.objects.filter(word=word_text).exists():
                    skipped += 1
                    continue
                try:
                    Word.objects.create(
                        word=word_text,
                        pronunciation=pronunciation,
                        definition=definition,
                        difficulty=max(1, min(5, difficulty)),
                    )
                    added += 1
                except Exception as e:
                    errors.append(f'第{i}行保存失败：{word_text} - {e}')

        elif mode == 'file':
            # CSV / Excel 文件上传
            f = request.FILES.get('file')
            if not f:
                messages.error(request, '请选择文件')
                return render(request, 'words/teacher/bulk_add_words.html')

            fname = f.name.lower()
            rows = []

            if fname.endswith('.csv'):
                import csv, io
                text = f.read().decode('utf-8-sig')
                reader = csv.reader(io.StringIO(text))
                for row in reader:
                    rows.append(row)
            elif fname.endswith(('.xls', '.xlsx')):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(f, read_only=True)
                    ws = wb.active
                    for row in ws.iter_rows(values_only=True):
                        rows.append([str(c) if c else '' for c in row])
                except ImportError:
                    messages.error(request, '服务器未安装 openpyxl，无法读取 Excel 文件。请使用 CSV 格式。')
                    return render(request, 'words/teacher/bulk_add_words.html')
            else:
                messages.error(request, '不支持的文件格式，请上传 CSV 或 Excel 文件')
                return render(request, 'words/teacher/bulk_add_words.html')

            # 跳过表头（如果第一行看起来是表头）
            if rows and rows[0] and rows[0][0].lower() in ('word', '单词', 'english'):
                rows = rows[1:]

            for i, row in enumerate(rows, 1):
                if not row or not row[0].strip():
                    continue
                word_text = row[0].strip()
                definition = row[1].strip() if len(row) > 1 else ''
                pronunciation = row[2].strip() if len(row) > 2 else ''
                difficulty = 3
                if len(row) > 3:
                    try:
                        difficulty = int(row[3])
                    except (ValueError, TypeError):
                        pass

                if not definition:
                    errors.append(f'第{i}行缺少释义：{word_text}')
                    continue
                if Word.objects.filter(word=word_text).exists():
                    skipped += 1
                    continue
                try:
                    Word.objects.create(
                        word=word_text,
                        pronunciation=pronunciation,
                        definition=definition,
                        difficulty=max(1, min(5, difficulty)),
                    )
                    added += 1
                except Exception as e:
                    errors.append(f'第{i}行保存失败：{word_text} - {e}')

        msg = f'批量导入完成！成功 {added} 个'
        if skipped:
            msg += f'，跳过 {skipped} 个（已存在）'
        if errors:
            msg += f'，失败 {len(errors)} 个'
        messages.success(request, msg)

        if errors:
            for e in errors[:10]:  # 最多显示10条错误
                messages.warning(request, e)

        return redirect('word_management')

    return render(request, 'words/teacher/bulk_add_words.html')

@login_required
@teacher_required
def homework_management(request):
    """作业管理"""
    homeworks = Homework.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'words/teacher/homework_list.html', {'homeworks': homeworks})

@login_required
@teacher_required
def create_homework(request):
    """创建作业"""
    if request.method == 'POST':
        hw = Homework.objects.create(
            teacher=request.user,
            class_name=request.POST.get('class_name'),
            title=request.POST.get('title'),
            due_date=request.POST.get('due_date')
        )
        # 添加单词到作业
        word_ids = request.POST.getlist('words')
        hw.words.set(word_ids)
        messages.success(request, '作业发布成功')
        return redirect('homework_management')
    
    classes = UserProfile.objects.filter(
        is_teacher=False
    ).values_list('class_name', flat=True).distinct()
    words = Word.objects.all()
    
    return render(request, 'words/teacher/create_homework.html', {
        'classes': classes,
        'words': words
    })

@login_required
@teacher_required
def import_students(request):
    """批量导入学生"""
    if request.method == 'POST':
        # 简单格式：班级,学号,姓名 每行一个
        data = request.POST.get('students_data', '')
        class_name = request.POST.get('class_name')
        
        lines = data.strip().split('\n')
        created_count = 0
        
        for line in lines:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                student_id = parts[0].strip()
                real_name = parts[1].strip() if len(parts) > 1 else student_id
                
                username = f"{class_name}_{student_id}"
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username,
                        password=student_id,  # 初始密码是学号
                        first_name=real_name
                    )
                    UserProfile.objects.create(
                        user=user,
                        student_id=student_id,
                        class_name=class_name,
                        real_name=real_name
                    )
                    created_count += 1
        
        messages.success(request, f'成功导入 {created_count} 名学生')
        return redirect('student_management')
    
    classes = UserProfile.objects.filter(
        is_teacher=False
    ).values_list('class_name', flat=True).distinct()
    
    return render(request, 'words/teacher/import_students.html', {
        'classes': classes
    })

# ========== 密码修改功能（新增） ==========

@login_required
def change_password(request):
    """学生修改密码"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # 验证旧密码
        if not request.user.check_password(old_password):
            messages.error(request, '旧密码错误，请重新输入')
            return redirect('change_password')
        
        # 验证新密码
        if new_password != confirm_password:
            messages.error(request, '两次输入的新密码不一致')
            return redirect('change_password')
        
        if len(new_password) < 6:
            messages.error(request, '新密码至少需要6位字符')
            return redirect('change_password')
        
        # 修改密码
        request.user.set_password(new_password)
        request.user.save()
        
        messages.success(request, '密码修改成功！请用新密码重新登录')
        return redirect('login')
    
    return render(request, 'words/change_password.html')

@login_required
@teacher_required
def teacher_change_password(request):
    """教师修改密码"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(old_password):
            messages.error(request, '旧密码错误')
            return redirect('teacher_change_password')
        
        if new_password != confirm_password:
            messages.error(request, '两次输入的密码不一致')
            return redirect('teacher_change_password')
        
        if len(new_password) < 6:
            messages.error(request, '密码至少需要6位')
            return redirect('teacher_change_password')
        
        request.user.set_password(new_password)
        request.user.save()
        
        messages.success(request, '密码修改成功！请用新密码重新登录')
        return redirect('teacher_login')
    
    return render(request, 'words/teacher/change_password.html')


# ========== 修改学生班级（新增） ==========

@login_required
@teacher_required
def update_student_class(request, student_id):
    """修改学生班级"""
    if request.method == 'POST':
        student = get_object_or_404(User, id=student_id)
        new_class = request.POST.get('new_class')
        
        if new_class:
            profile = student.userprofile
            profile.class_name = new_class
            profile.save()
            messages.success(request, f'已将 {student.first_name or student.username} 的班级修改为 {new_class}')
        else:
            messages.error(request, '请选择班级')
    
    return redirect('student_management')


# ========== 班级管理（新增） ==========

@login_required
@teacher_required
def class_management(request):
    """管理班级名称（增删改查）"""
    from django.db.models import Count
    
    # 获取所有班级及其学生数量
    classes = UserProfile.objects.filter(
        is_teacher=False,
        class_name__isnull=False
    ).exclude(
        class_name=''
    ).values('class_name').annotate(
        student_count=Count('id')
    ).order_by('class_name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'rename':
            # 重命名班级
            old_name = request.POST.get('old_name')
            new_name = request.POST.get('new_name')
            
            if old_name and new_name:
                # 批量修改该班级所有学生的班级名称
                count = UserProfile.objects.filter(
                    class_name=old_name
                ).update(class_name=new_name)
                
                # 同时修改作业中的班级名称
                Homework.objects.filter(class_name=old_name).update(class_name=new_name)
                
                messages.success(request, f'已将 "{old_name}" 重命名为 "{new_name}"，共影响 {count} 名学生')
                return redirect('class_management')
        
        elif action == 'delete':
            # 删除班级（将该班级学生设为无班级）
            class_name = request.POST.get('class_name')
            if class_name:
                count = UserProfile.objects.filter(class_name=class_name).update(class_name='')
                messages.success(request, f'已解散班级 "{class_name}"，{count} 名学生已移出')
                return redirect('class_management')
        
        elif action == 'create':
            # 创建新班级
            new_class = request.POST.get('new_class')
            if new_class:
                messages.success(request, f'班级 "{new_class}" 已创建（有学生选择此班级后生效）')
                return redirect('class_management')
    
    return render(request, 'words/teacher/class_management.html', {
        'classes': classes
    })
# ========== 单词编辑与删除（新增） ==========

@login_required
@teacher_required
def edit_word(request, word_id):
    """编辑单词"""
    word = get_object_or_404(Word, id=word_id)
    
    if request.method == 'POST':
        word.word = request.POST.get('word')
        word.pronunciation = request.POST.get('pronunciation', '')
        word.definition = request.POST.get('definition')
        word.example = request.POST.get('example', '')
        word.example_translation = request.POST.get('example_translation', '')
        word.difficulty = int(request.POST.get('difficulty', 3))
        word.category = request.POST.get('category', '')
        word.save()
        messages.success(request, f'单词 "{word.word}" 更新成功')
        return redirect('word_management')
    
    return render(request, 'words/teacher/edit_word.html', {'word': word})

@login_required
@teacher_required
def delete_word(request, word_id):
    """删除单词"""
    word = get_object_or_404(Word, id=word_id)
    word_name = word.word
    word.delete()
    messages.success(request, f'单词 "{word_name}" 已删除')
    return redirect('word_management')
