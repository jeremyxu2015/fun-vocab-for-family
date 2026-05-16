from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string
from datetime import timedelta


class Family(models.Model):
    """家庭模型 - 一个家庭可以有多个家长和孩子"""
    name = models.CharField(max_length=50, verbose_name='家庭名称')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    invite_code = models.CharField(max_length=8, unique=True, verbose_name='邀请码', blank=True)
    
    class Meta:
        verbose_name = '家庭'
        verbose_name_plural = '家庭管理'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.invite_code:
            # 生成8位邀请码
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Family.objects.filter(invite_code=code).exists():
                    self.invite_code = code
                    break
        super().save(*args, **kwargs)


class UserProfile(models.Model):
    """用户档案 - 支持家长和孩子两种角色"""
    ROLE_CHOICES = [
        ('parent', '家长'),
        ('child', '孩子'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='child', verbose_name='角色')
    family = models.ForeignKey(Family, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属家庭')
    nickname = models.CharField(max_length=30, blank=True, verbose_name='昵称/小名')
    grade = models.CharField(max_length=20, blank=True, verbose_name='年级')
    avatar = models.CharField(max_length=10, blank=True, default='👶', verbose_name='头像emoji')
    daily_goal = models.IntegerField(default=10, verbose_name='每日目标')
    current_streak = models.IntegerField(default=0, verbose_name='连续天数')
    points = models.IntegerField(default=0, verbose_name='总积分')
    level = models.IntegerField(default=1, verbose_name='等级')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    
    class Meta:
        verbose_name = '用户档案'
        verbose_name_plural = '用户档案'
    
    def __str__(self):
        role_text = '家长' if self.role == 'parent' else '孩子'
        return f"{self.nickname or self.user.username} ({role_text})"
    
    @property
    def is_parent(self):
        return self.role == 'parent'
    
    @property
    def is_child(self):
        return self.role == 'child'
    
    def add_points(self, amount):
        """增加积分并自动升级"""

        self.points += amount

        # 每100积分升级
        self.level = self.points // 100 + 1

        self.save()

class Word(models.Model):
    word = models.CharField(max_length=100, unique=True, verbose_name='单词')
    pronunciation = models.CharField(max_length=100, blank=True, verbose_name='音标')
    definition = models.TextField(verbose_name='中文释义')
    example = models.TextField(blank=True, verbose_name='例句')
    example_translation = models.TextField(blank=True, verbose_name='例句翻译')
    unit = models.CharField(max_length=50, default='Unit 1', verbose_name='单元')
    textbook = models.CharField(max_length=50, default='课本词汇', verbose_name='教材')
    is_core = models.BooleanField(default=True, verbose_name='课标核心词')
    
    # ✅ 新增字段（模板需要）
    difficulty = models.IntegerField(default=3, verbose_name='难度等级', 
                                   choices=[(1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3'), 
                                           (4, 'Level 4'), (5, 'Level 5')])
    category = models.CharField(max_length=50, blank=True, verbose_name='分类', 
                               help_text='例如：CET-4、雅思、课本')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')
    
    def __str__(self):
        return self.word

class UserWord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ('new', '新学'),
        ('familiar', '熟悉'),
        ('mastered', '掌握')
    ], default='new', verbose_name='状态')
    next_review = models.DateTimeField(default=timezone.now, verbose_name='下次复习')
    correct_count = models.IntegerField(default=0, verbose_name='正确次数')
    wrong_count = models.IntegerField(default=0, verbose_name='错误次数')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ✅ SM-2 算法必需字段
    repetitions = models.IntegerField(default=0, verbose_name='连续成功次数')
    interval = models.IntegerField(default=1, verbose_name='间隔天数')
    ease_factor = models.FloatField(default=2.5, verbose_name='简易度系数')
    total_reviews = models.IntegerField(default=0, verbose_name='总复习次数')
    last_reviewed = models.DateTimeField(null=True, blank=True, verbose_name='上次复习')
    is_learned = models.BooleanField(default=False, verbose_name='是否已学')
    
    class Meta:
        unique_together = ['user', 'word']

class FamilyTask(models.Model):
    """家庭学习任务 - 家长给孩子布置的学习任务"""
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks_created', verbose_name='创建家长')
    child = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks_assigned', verbose_name='分配给孩子')
    title = models.CharField(max_length=100, verbose_name='任务标题')
    words = models.ManyToManyField(Word, verbose_name='单词列表')
    due_date = models.DateField(verbose_name='截止日期')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name='进行中')
    note = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        verbose_name = '学习任务'
        verbose_name_plural = '学习任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.child.userprofile.nickname or self.child.username} - {self.title}"


class TaskProgress(models.Model):
    """任务进度"""
    task = models.ForeignKey(FamilyTask, on_delete=models.CASCADE)
    completed_words = models.IntegerField(default=0, verbose_name='完成数量')
    score = models.IntegerField(default=0, verbose_name='得分')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['task']


class PDFWordList(models.Model):
    """PDF单词导入记录"""
    family = models.ForeignKey(Family, on_delete=models.CASCADE, verbose_name='所属家庭')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传者')
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    words_extracted = models.IntegerField(default=0, verbose_name='提取单词数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    status = models.CharField(max_length=20, choices=[
        ('pending', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败')
    ], default='pending', verbose_name='状态')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    class Meta:
        verbose_name = 'PDF导入记录'
        verbose_name_plural = 'PDF导入记录'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file_name} - {self.words_extracted}个单词"

class DailyStats(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    words_learned = models.IntegerField(default=0)
    words_reviewed = models.IntegerField(default=0)
    homework_done = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'date']


class GameProgress(models.Model):
    """游戏进度模型"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_level = models.IntegerField(default=1, verbose_name='当前关卡')
    total_score = models.IntegerField(default=0, verbose_name='总积分')
    combo = models.IntegerField(default=0, verbose_name='当前连击')
    max_combo = models.IntegerField(default=0, verbose_name='最高连击')
    lives = models.IntegerField(default=3, verbose_name='剩余生命')
    
    def add_score(self, points):
        """增加积分"""
        self.total_score += points
        self.save()
        return points
    
    def __str__(self):
        return f"{self.user.username} - 第{self.current_level}关"