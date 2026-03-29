from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string
from datetime import timedelta

class RegistrationCode(models.Model):
    """教师生成的注册验证码"""
    code = models.CharField(max_length=6, unique=True, verbose_name='验证码')
    class_name = models.CharField(max_length=20, verbose_name='目标班级')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='生成教师')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    is_used = models.BooleanField(default=False, verbose_name='已使用')
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='used_codes', verbose_name='使用学生')
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='使用时间')
    max_uses = models.IntegerField(default=1, verbose_name='最大使用次数')  # 1=一次性，>1=批量注册
    used_count = models.IntegerField(default=0, verbose_name='已使用次数')
    
    class Meta:
        verbose_name = '注册验证码'
        verbose_name_plural = '注册验证码管理'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.class_name} - {self.code} ({'已用完' if self.is_used else '有效'})"
    
    @classmethod
    def generate_code(cls, class_name, teacher, max_uses=1, valid_minutes=15):
        """生成6位数字验证码"""
        # 生成不重复的6位数字
        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not cls.objects.filter(code=code, is_used=False).exists():
                break
        
        expires_at = timezone.now() + timedelta(minutes=valid_minutes)
        
        return cls.objects.create(
            code=code,
            class_name=class_name,
            teacher=teacher,
            expires_at=expires_at,
            max_uses=max_uses
        )
    
    def is_valid(self):
        """检查验证码是否有效"""
        if self.is_used and self.used_count >= self.max_uses:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True
    
    def use(self, user):
        """使用验证码"""
        if not self.is_valid():
            return False
        
        self.used_count += 1
        if self.used_count >= self.max_uses:
            self.is_used = True
        
        if self.used_count == 1:  # 第一次使用记录使用者
            self.used_by = user
            self.used_at = timezone.now()
        
        self.save()
        return True

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_teacher = models.BooleanField(default=False, verbose_name='教师')
    student_id = models.CharField(max_length=20, blank=True, verbose_name='学号')
    class_name = models.CharField(max_length=20, blank=True, verbose_name='班级')
    real_name = models.CharField(max_length=50, blank=True, verbose_name='姓名')
    daily_goal = models.IntegerField(default=10, verbose_name='每日目标')
    current_streak = models.IntegerField(default=0, verbose_name='连续天数')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    
    def __str__(self):
        if self.is_teacher:
            return f"{self.real_name or self.user.username} (教师)"
        return f"{self.class_name} {self.real_name} ({self.student_id})"

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

class Homework(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='homework_created')
    class_name = models.CharField(max_length=20, verbose_name='班级')
    title = models.CharField(max_length=100, verbose_name='作业标题')
    words = models.ManyToManyField(Word, verbose_name='单词列表')
    due_date = models.DateField(verbose_name='截止日期')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name='进行中')
    
    def __str__(self):
        return f"{self.class_name} - {self.title}"

class HomeworkSubmission(models.Model):
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    completed_words = models.IntegerField(default=0, verbose_name='完成数量')
    score = models.IntegerField(default=0, verbose_name='得分')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['homework', 'student']

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