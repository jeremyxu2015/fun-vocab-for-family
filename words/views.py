"""
家庭背单词应用视图
支持家长和孩子两种角色
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import random
import json
from datetime import datetime, timedelta

from .models import (
    Family, UserProfile, Word, UserWord, DailyStats, 
    FamilyTask, TaskProgress, GameProgress, PDFWordList
)
from .utils import calculate_next_review
from .pdf_service import process_pdf_and_extract_words


# ========== 装饰器 ==========

def parent_required(view_func):
    """要求用户是家长"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if not request.user.userprofile.is_parent:
                return redirect('child_dashboard')
        except:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def child_required(view_func):
    """要求用户是孩子"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            if not request.user.userprofile.is_child:
                return redirect('parent_dashboard')
        except:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ========== 认证相关 ==========

def login_page(request):
    """登录首页 - 选择家长或孩子登录"""
    # 已登录用户跳转
    if request.user.is_authenticated:
        try:
            if request.user.userprofile.is_parent:
                return redirect('parent_dashboard')
            else:
                return redirect('child_dashboard')
        except:
            pass
    return render(request, 'words/login.html')


def home(request):
    """首页 - 根据角色跳转"""
    if request.user.is_authenticated:
        try:
            if request.user.userprofile.is_parent:
                return redirect('parent_dashboard')
            else:
                return redirect('child_dashboard')
        except:
            return redirect('login')
    return redirect('login')


def parent_login(request):
    """家长登录"""
    if request.user.is_authenticated:
        try:
            if request.user.userprofile.is_parent:
                return redirect('parent_dashboard')
        except:
            pass

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                if user.userprofile.is_parent:
                    login(request, user)
                    return redirect('parent_dashboard')
                else:
                    messages.error(request, '此账号不是家长账号，请使用孩子登录入口')
            except:
                messages.error(request, '账号信息异常')
        else:
            messages.error(request, '用户名或密码错误')

    return render(request, 'words/parent_login.html')


def child_login(request):
    """孩子登录"""
    if request.user.is_authenticated:
        try:
            if request.user.userprofile.is_child:
                return redirect('child_dashboard')
        except:
            pass

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                if user.userprofile.is_child:
                    login(request, user)
                    return redirect('child_dashboard')
                else:
                    messages.error(request, '此账号是家长账号，请使用家长登录入口')
            except:
                messages.error(request, '账号信息异常')
        else:
            messages.error(request, '用户名或密码错误')

    return render(request, 'words/child_login.html')


def parent_register(request):
    """家长注册 - 创建家庭"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        nickname = request.POST.get('nickname', '')
        family_name = request.POST.get('family_name', '我的家庭')

        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
            return render(request, 'words/parent_register.html')

        # 创建家庭
        family = Family.objects.create(name=family_name)

        # 创建用户
        user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(
            user=user,
            role='parent',
            nickname=nickname or username,
            family=family,
            avatar='👨‍👩‍👧'
        )

        messages.success(request, f'注册成功！家庭邀请码：{family.invite_code}，请保存好邀请码用于添加家庭成员')
        login(request, user)
        return redirect('parent_dashboard')

    return render(request, 'words/parent_register.html')


def child_register(request):
    """孩子注册 - 加入家庭"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        nickname = request.POST.get('nickname', '')
        grade = request.POST.get('grade', '')
        invite_code = request.POST.get('invite_code', '').strip().upper()
        avatar = request.POST.get('avatar', '👶')

        # 验证邀请码
        try:
            family = Family.objects.get(invite_code=invite_code)
        except Family.DoesNotExist:
            messages.error(request, '邀请码无效，请向家长确认')
            return render(request, 'words/child_register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, '用户名已存在')
            return render(request, 'words/child_register.html')

        # 创建用户
        user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(
            user=user,
            role='child',
            nickname=nickname or username,
            grade=grade,
            family=family,
            avatar=avatar
        )

        messages.success(request, f'注册成功！欢迎加入 {family.name}')
        login(request, user)
        return redirect('child_dashboard')

    return render(request, 'words/child_register.html')


def logout_view(request):
    """退出登录"""
    logout(request)
    return redirect('login')


# ========== 家长功能 ==========

@login_required
@parent_required
def parent_dashboard(request):
    """家长控制台"""
    parent = request.user
    family = parent.userprofile.family

    if not family:
        messages.error(request, '您还没有创建家庭')
        return redirect('parent_register')

    # 获取家庭中的所有孩子
    children = User.objects.filter(
        userprofile__family=family,
        userprofile__role='child'
    ).select_related('userprofile')

    # 统计每个孩子的学习情况
    children_stats = []
    for child in children:
        profile = child.userprofile
        mastered = UserWord.objects.filter(user=child, status='mastered').count()
        learning = UserWord.objects.filter(user=child).exclude(status='mastered').count()
        due_count = UserWord.objects.filter(
            user=child, 
            next_review__lte=timezone.now()
        ).count()

        children_stats.append({
            'user': child,
            'profile': profile,
            'mastered': mastered,
            'learning': learning,
            'due_count': due_count
        })

    # 家庭单词总数
    total_words = Word.objects.count()

    # 待处理的任务
    active_tasks = FamilyTask.objects.filter(
        parent=parent, 
        is_active=True,
        due_date__gte=timezone.now().date()
    ).count()

    context = {
        'family': family,
        'children_stats': children_stats,
        'total_words': total_words,
        'active_tasks': active_tasks,
    }
    return render(request, 'words/parent/dashboard.html', context)


@login_required
@parent_required
def child_management(request):
    """孩子管理"""
    family = request.user.userprofile.family
    children = User.objects.filter(
        userprofile__family=family,
        userprofile__role='child'
    ).select_related('userprofile')

    # 为每个孩子计算学习统计（修复模板无法调用filter的问题）
    children_with_stats = []
    for child in children:
        mastered = UserWord.objects.filter(user=child, status='mastered').count()
        learning = UserWord.objects.filter(user=child).exclude(status='mastered').count()
        due_count = UserWord.objects.filter(user=child, next_review__lte=timezone.now()).count()

        children_with_stats.append({
            'user': child,
            'profile': child.userprofile,
            'stats': {
                'mastered': mastered,
                'learning': learning,
                'due_count': due_count,
            }
        })

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            # 通过邀请码页面已说明，这里不需要处理
            pass

        elif action == 'remove':
            child_id = request.POST.get('child_id')
            child = get_object_or_404(User, id=child_id)
            if child.userprofile.family == family:
                child.userprofile.family = None
                child.userprofile.save()
                messages.success(request, f'已将 {child.userprofile.nickname} 移出家庭')

        elif action == 'reset_password':
            child_id = request.POST.get('child_id')
            new_password = request.POST.get('new_password')
            child = get_object_or_404(User, id=child_id)
            if child.userprofile.family == family and new_password:
                child.set_password(new_password)
                child.save()
                messages.success(request, f'已重置 {child.userprofile.nickname} 的密码')

    context = {
        'children': children_with_stats,
        'family': family,
    }
    return render(request, 'words/parent/child_management.html', context)


@login_required
@parent_required
def word_management(request):
    """单词管理"""
    words = Word.objects.all().order_by('-created_at')

    # 搜索功能
    search = request.GET.get('search', '')
    if search:
        words = words.filter(
            Q(word__icontains=search) | Q(definition__icontains=search)
        )

    # 分类筛选
    category = request.GET.get('category', '')
    if category:
        words = words.filter(category=category)

    # 获取所有分类
    categories = Word.objects.values_list('category', flat=True).distinct()

    context = {
        'words': words[:100],  # 限制显示数量
        'categories': categories,
        'search': search,
        'selected_category': category,
    }
    return render(request, 'words/parent/word_management.html', context)


@login_required
@parent_required
def add_word(request):
    """添加单词"""
    if request.method == 'POST':
        Word.objects.create(
            word=request.POST.get('word'),
            pronunciation=request.POST.get('pronunciation', ''),
            definition=request.POST.get('definition'),
            example=request.POST.get('example', ''),
            example_translation=request.POST.get('example_translation', ''),
            category=request.POST.get('category', ''),
            difficulty=int(request.POST.get('difficulty', 3))
        )
        messages.success(request, '单词添加成功')
        return redirect('word_management')

    return render(request, 'words/parent/add_word.html')


@login_required
@parent_required
def bulk_add_words(request):
    """批量添加单词"""
    if request.method == 'POST':
        mode = request.POST.get('mode', 'text')
        added = 0
        skipped = 0
        errors = []

        if mode == 'text':
            raw = request.POST.get('bulk_text', '')
            for i, line in enumerate(raw.strip().splitlines(), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.replace('\t', '|').split('|')]
                if len(parts) < 2:
                    errors.append(f'第{i}行格式错误：{line}')
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
            f = request.FILES.get('file')
            if not f:
                messages.error(request, '请选择文件')
                return render(request, 'words/parent/bulk_add_words.html')

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
                    messages.error(request, '服务器未安装 openpyxl，请使用 CSV 格式')
                    return render(request, 'words/parent/bulk_add_words.html')
            else:
                messages.error(request, '不支持的文件格式')
                return render(request, 'words/parent/bulk_add_words.html')

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
            for e in errors[:10]:
                messages.warning(request, e)

        return redirect('word_management')

    return render(request, 'words/parent/bulk_add_words.html')


@login_required
@parent_required
def pdf_import(request):
    """从PDF导入单词"""
    family = request.user.userprofile.family

    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')

        if not pdf_file:
            messages.error(request, '请选择PDF文件')
            return redirect('pdf_import')

        if not pdf_file.name.lower().endswith('.pdf'):
            messages.error(request, '请上传PDF格式文件')
            return redirect('pdf_import')

        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
        if pdf_file.size > max_size:
            messages.error(request, '文件大小不能超过10MB')
            return redirect('pdf_import')

        # 创建导入记录
        import_record = PDFWordList.objects.create(
            family=family,
            uploaded_by=request.user,
            file_name=pdf_file.name,
            status='pending'
        )

        try:
            # 处理PDF并提取单词
            words, error = process_pdf_and_extract_words(pdf_file, max_words=200)

            if error:
                import_record.status = 'failed'
                import_record.error_message = error
                import_record.save()
                messages.error(request, f'处理失败：{error}')
                return redirect('pdf_import')

            if not words:
                import_record.status = 'failed'
                import_record.error_message = '未从PDF中提取到单词'
                import_record.save()
                messages.warning(request, '未从PDF中提取到单词，请确认PDF包含英语单词')
                return redirect('pdf_import')

            # 保存单词到数据库
            added = 0
            skipped = 0
            for word_data in words:
                if Word.objects.filter(word=word_data['word']).exists():
                    skipped += 1
                    continue
                Word.objects.create(
                    word=word_data['word'],
                    pronunciation=word_data.get('pronunciation', ''),
                    definition=word_data['definition'],
                    example=word_data.get('example', ''),
                    example_translation=word_data.get('example_translation', ''),
                    category='PDF导入'
                )
                added += 1

            import_record.status = 'completed'
            import_record.words_extracted = len(words)
            import_record.save()

            messages.success(request, f'成功从PDF提取 {len(words)} 个单词，新增 {added} 个，跳过 {skipped} 个（已存在）')
            return redirect('word_management')

        except Exception as e:
            import_record.status = 'failed'
            import_record.error_message = str(e)
            import_record.save()
            messages.error(request, f'处理失败：{str(e)}')
            return redirect('pdf_import')

    # 获取历史导入记录
    import_history = PDFWordList.objects.filter(family=family).order_by('-created_at')[:10]

    context = {
        'import_history': import_history,
    }
    return render(request, 'words/parent/pdf_import.html', context)


@login_required
@parent_required
def task_management(request):
    """学习任务管理"""
    parent = request.user
    family = parent.userprofile.family

    tasks = FamilyTask.objects.filter(parent=parent).order_by('-created_at')

    # 修复：传入 today 用于模板中的日期比较
    today = timezone.now().date()

    context = {
        'tasks': tasks,
        'today': today,
    }
    return render(request, 'words/parent/task_management.html', context)


@login_required
@parent_required
def create_task(request):
    """创建学习任务"""
    family = request.user.userprofile.family

    if request.method == 'POST':
        child_id = request.POST.get('child')
        title = request.POST.get('title')
        due_date = request.POST.get('due_date')
        note = request.POST.get('note', '')
        word_ids = request.POST.getlist('words')

        child = get_object_or_404(User, id=child_id)

        if child.userprofile.family != family:
            messages.error(request, '只能给家庭成员创建任务')
            return redirect('create_task')

        task = FamilyTask.objects.create(
            parent=request.user,
            child=child,
            title=title,
            due_date=due_date,
            note=note
        )
        task.words.set(word_ids)

        messages.success(request, f'任务"{title}"创建成功')
        return redirect('task_management')

    children = User.objects.filter(
        userprofile__family=family,
        userprofile__role='child'
    )
    words = Word.objects.all()[:200]  # 限制选择数量

    context = {
        'children': children,
        'words': words,
    }
    return render(request, 'words/parent/create_task.html', context)


@login_required
@parent_required
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

    return render(request, 'words/parent/edit_word.html', {'word': word})


@login_required
@parent_required
def delete_word(request, word_id):
    """删除单词"""
    word = get_object_or_404(Word, id=word_id)
    word_name = word.word
    word.delete()
    messages.success(request, f'单词 "{word_name}" 已删除')
    return redirect('word_management')


# ========== 孩子功能 ==========

@login_required
@child_required
def child_dashboard(request):
    """孩子仪表盘"""
    child = request.user
    profile = child.userprofile

    # 今日统计
    today = timezone.now().date()
    today_stats, _ = DailyStats.objects.get_or_create(user=child, date=today)

    # 总体统计
    mastered_count = UserWord.objects.filter(user=child, status='mastered').count()
    learning_count = UserWord.objects.filter(user=child).exclude(status='mastered').count()
    due_count = UserWord.objects.filter(user=child, next_review__lte=timezone.now()).count()

    # 待完成任务
    active_tasks = FamilyTask.objects.filter(
        child=child,
        is_active=True,
        due_date__gte=today
    ).count()

    # 游戏进度
    game_progress, _ = GameProgress.objects.get_or_create(user=child)

    context = {
        'profile': profile,
        'today_learned': today_stats.words_learned,
        'today_reviewed': today_stats.words_reviewed,
        'mastered_count': mastered_count,
        'learning_count': learning_count,
        'due_count': due_count,
        'active_tasks': active_tasks,
        'game_progress': game_progress,
    }
    return render(request, 'words/dashboard.html', context)


@login_required
@child_required
def study(request):
    """学习新词"""
    child = request.user

    # 检查是否有待完成的任务
    today = timezone.now().date()
    task = FamilyTask.objects.filter(
        child=child,
        is_active=True,
        due_date__gte=today
    ).first()

    if task:
        # 优先学习任务中的单词
        task_words = task.words.exclude(
            id__in=UserWord.objects.filter(user=child, status='mastered').values_list('word_id', flat=True)
        )
        if task_words.exists():
            word = random.choice(list(task_words))
            return render(request, 'words/study.html', {
                'word': word,
                'mode': 'task',
                'task': task
            })

    # 正常学习新词
    existing = UserWord.objects.filter(user=child).values_list('word_id', flat=True)
    new_words = Word.objects.exclude(id__in=existing)[:10]

    if not new_words:
        return redirect('review')

    word = random.choice(list(new_words))
    return render(request, 'words/study.html', {'word': word, 'mode': 'learning'})


@login_required
@child_required
def review(request):
    """复习单词"""
    child = request.user

    due = UserWord.objects.filter(
        user=child,
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
@child_required
def answer(request, word_id):
    """提交答案 - SM-2算法

    修复：原代码返回 JsonResponse，但 study.html 是普通表单提交，
    用户点击后会看到JSON文本。改为返回 redirect，让页面正常跳转。
    """
    if request.method == 'POST':
        quality_map = {1: 0, 2: 3, 3: 5}
        raw_quality = int(request.POST.get('quality', 2))
        quality = quality_map.get(raw_quality, 2)

        word = get_object_or_404(Word, id=word_id)

        user_word, created = UserWord.objects.get_or_create(
            user=request.user,
            word=word
        )

        interval = calculate_next_review(user_word, quality)

        if quality >= 4:
            user_word.status = 'mastered'
        elif quality >= 3:
            user_word.status = 'familiar'
        else:
            user_word.status = 'new'

        user_word.save()

        # ======================
        # 学习积分
        # ======================
        request.user.userprofile.add_points(5)

        # 更新今日统计
        today = timezone.now().date()
        stats, _ = DailyStats.objects.get_or_create(user=request.user, date=today)

        if created or user_word.total_reviews <= 1:
            stats.words_learned += 1
        else:
            stats.words_reviewed += 1
        stats.save()

        # 修复：根据当前模式决定跳转方向
        mode = request.POST.get('mode', '')
        if mode == 'review':
            return redirect('review')
        return redirect('study')

    # GET请求不允许
    return redirect('study')


@login_required
@child_required
def training(request):
    """强化训练"""
    child = request.user

    weak_words = UserWord.objects.filter(user=child).exclude(status='mastered')
    weak_count = weak_words.filter(wrong_count__gt=0).count()
    low_ease = weak_words.filter(ease_factor__lt=2.0).count()
    familiar_count = weak_words.filter(status='familiar').count()
    new_count = weak_words.filter(status='new').count()
    total_learned = UserWord.objects.filter(user=child).count()

    return render(request, 'words/training.html', {
        'weak_count': weak_count,
        'low_ease': low_ease,
        'familiar_count': familiar_count,
        'new_count': new_count,
        'total_learned': total_learned,
    })


@login_required
@child_required
def training_challenge(request):
    """AJAX: 获取强化训练题目"""
    child = request.user
    mode = request.GET.get('mode', 'auto')

    if mode == 'wrong':
        candidates = UserWord.objects.filter(
            user=child, wrong_count__gt=0
        ).exclude(status='mastered').select_related('word').order_by('-wrong_count')
    elif mode == 'low_ease':
        candidates = UserWord.objects.filter(
            user=child, ease_factor__lt=2.0
        ).exclude(status='mastered').select_related('word').order_by('ease_factor')
    elif mode == 'spelling':
        candidates = UserWord.objects.filter(
            user=child, status='familiar'
        ).select_related('word').order_by('ease_factor')
    else:
        candidates = UserWord.objects.filter(
            user=child
        ).exclude(status='mastered').select_related('word').order_by(
            '-wrong_count', 'ease_factor', 'correct_count'
        )

    if not candidates.exists():
        return JsonResponse({'done': True, 'message': '太棒了！没有需要强化的单词了 🎉'})

    pool = list(candidates[:10])
    user_word = random.choice(pool)
    word = user_word.word

    all_words = list(Word.objects.exclude(id=word.id).values_list('definition', flat=True))
    random.shuffle(all_words)
    wrong_defs = all_words[:3]
    while len(wrong_defs) < 3:
        wrong_defs.append('???')

    options = wrong_defs + [word.definition]
    random.shuffle(options)

    if mode == 'spelling':
        q_type = 'spelling'
    elif user_word.correct_count >= 2 and random.random() > 0.5:
        q_type = 'cn2en'
    else:
        q_type = 'en2cn'

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
        'type': q_type,
        'options': options,
        'wrong_count': user_word.wrong_count,
        'correct_count': user_word.correct_count,
        'ease_factor': round(user_word.ease_factor, 2),
        'status': user_word.status,
    })


@login_required
@child_required
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
        clean_answer = clean_def(answer)
        clean_correct = [clean_def(p) for p in re.split(r'[；;，,、]', word.definition) if p.strip()]
        correct = any(
            clean_answer == d or clean_answer in d or d in clean_answer
            for d in clean_correct
        ) or answer.strip() == word.definition.strip()
    elif q_type == 'cn2en':
        correct = answer.strip().lower() == word.word.lower()
    elif q_type == 'spelling':
        correct = answer.strip().lower() == word.word.lower()

    if correct:
        user_word.correct_count += 1
        user_word.wrong_count = max(0, user_word.wrong_count - 1)
        user_word.ease_factor = min(3.0, user_word.ease_factor + 0.1)
        if user_word.correct_count >= 5 and user_word.ease_factor >= 2.0:
            user_word.status = 'mastered'
        elif user_word.correct_count >= 2:
            user_word.status = 'familiar'
        user_word.save()
        # 强化训练积分
        request.user.userprofile.add_points(3)
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


# ========== 游戏功能 ==========

@login_required
@child_required
def snake_game(request):
    """贪吃蛇背单词游戏"""
    return render(request, 'words/snake_game.html')


@login_required
@child_required
def snake_word_bank(request):
    """AJAX: 返回随机释义列表"""
    words = list(Word.objects.values_list('definition', flat=True))
    random.shuffle(words)
    return JsonResponse({'definitions': words[:30]})


@login_required
@child_required
def game_challenge(request):
    """AJAX 获取挑战单词"""
    child = request.user

    review_word = UserWord.objects.filter(
        user=child,
        next_review__lte=timezone.now()
    ).select_related('word').first()

    if review_word:
        mode = 'review'
        word = review_word.word
        user_word = review_word
    else:
        learned_ids = UserWord.objects.filter(user=child).values_list('word_id', flat=True)
        new_word = Word.objects.exclude(id__in=learned_ids).first()

        if not new_word:
            return JsonResponse({'game_clear': True, 'message': '恭喜！你已学完所有单词！'})

        mode = 'new'
        word = new_word
        user_word, _ = UserWord.objects.get_or_create(user=child, word=word)

    return JsonResponse({
        'word_id': word.id,
        'word': word.word,
        'pronunciation': word.pronunciation,
        'definition': word.definition,
        'example': word.example,
        'mode': mode,
        'status': user_word.status
    })


@login_required
@child_required
@csrf_exempt
def snake_answer(request):
    """贪吃蛇游戏提交答案"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'})

    word_id = request.POST.get('word_id')
    user_input = request.POST.get('user_input', '').strip().lower()
    mode = request.POST.get('mode')

    word = get_object_or_404(Word, id=word_id)
    user_word, created = UserWord.objects.get_or_create(user=request.user, word=word)

    import re
    correct = False

    def strip_pos(text):
        return re.sub(r'^[a-zA-Z]+\.\s*', '', text.strip())

    def get_clean_definitions(definition_text):
        parts = re.split(r'[；;，,、]', definition_text)
        return [strip_pos(p).lower() for p in parts if strip_pos(p)]

    clean_defs = get_clean_definitions(word.definition)

    if mode == 'review':
        correct = any(
            user_input == d or user_input in d or d in user_input
            for d in clean_defs
        ) or user_input == word.word.lower()
    else:
        is_correct = request.POST.get('is_correct') == 'true'
        correct = is_correct

    display_defs = '、'.join(get_clean_definitions(word.definition))

    if correct:
        calculate_next_review(user_word, 5)

        request.user.userprofile.add_points(10)

        score = 10 + (user_word.correct_count * 2)

        return JsonResponse({
            'correct': True,
            'message': '回答正确！继续游戏！',
            'score': score,
            'interval': user_word.interval
        })
    else:
        user_word.wrong_count += 1
        user_word.save()

        return JsonResponse({
            'correct': False,
            'message': f'错误！正确答案是：{display_defs}',
            'game_over': mode == 'review'
        })


@login_required
@child_required
def game_study(request):
    """游戏模式：闯关背单词"""
    child = request.user
    progress, _ = GameProgress.objects.get_or_create(user=child)

    words_per_level = 5
    difficulty = min(progress.current_level // 5 + 1, 5)

    words = list(Word.objects.filter(difficulty=difficulty)[:words_per_level])

    if len(words) < words_per_level:
        words = list(Word.objects.order_by('?')[:words_per_level])

    if not words:
        messages.info(request, '还没有导入单词，请联系家长添加单词！')
        return redirect('child_dashboard')

    word = random.choice(words)

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
@child_required
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
        progress.combo += 1
        if progress.combo > progress.max_combo:
            progress.max_combo = progress.combo
        points = progress.add_score(10)
        request.user.userprofile.add_points(10)

        calculate_next_review(user_word, 5)

        if progress.combo >= 5:
            progress.current_level += 1
            progress.combo = 0
            progress.lives = min(progress.lives + 1, 5)
            progress.save()
            return JsonResponse({
                'correct': True,
                'points': points,
                'level_up': True,
                'message': f'🎉 通关！进入第 {progress.current_level} 关！'
            })
    else:
        progress.combo = 0
        progress.lives -= 1
        progress.save()

        if progress.lives <= 0:
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


# ========== 密码修改 ==========

@login_required
def change_password(request):
    """修改密码"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, '旧密码错误')
            return redirect('change_password')

        if new_password != confirm_password:
            messages.error(request, '两次输入的密码不一致')
            return redirect('change_password')

        if len(new_password) < 6:
            messages.error(request, '密码至少需要6位')
            return redirect('change_password')

        request.user.set_password(new_password)
        request.user.save()

        messages.success(request, '密码修改成功！请重新登录')
        return redirect('login')

    return render(request, 'words/change_password.html')


# ========== 联机对战（保留原有功能） ==========

import string as _string
import time as _time

_MP_ROOMS = {}

def _clean_old_rooms():
    now = _time.time()
    expired = [k for k, v in _MP_ROOMS.items() if now - v.get('created', 0) > 1800]
    for k in expired:
        del _MP_ROOMS[k]

@login_required
@csrf_exempt
def mp_create_room(request):
    _clean_old_rooms()
    for _ in range(100):
        code = ''.join(random.choices(_string.digits, k=4))
        if code not in _MP_ROOMS:
            break
    _MP_ROOMS[code] = {
        'creator': request.user.id,
        'creator_name': request.user.userprofile.nickname or request.user.username,
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
    code = request.POST.get('room_code', '')
    room = _MP_ROOMS.get(code)
    if not room:
        return JsonResponse({'error': '房间不存在'})
    if room['started']:
        return JsonResponse({'error': '房间已开始'})
    if room['joiner']:
        return JsonResponse({'error': '房间已满'})
    room['joiner'] = request.user.id
    room['joiner_name'] = request.user.userprofile.nickname or request.user.username
    room['started'] = True
    return JsonResponse({'ok': True, 'opponent': room['creator_name']})

@login_required
def mp_room_status(request):
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
    code = request.POST.get('room_code', '')
    if code in _MP_ROOMS:
        del _MP_ROOMS[code]
    return JsonResponse({'ok': True})
