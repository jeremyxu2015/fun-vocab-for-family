from django.core.management.base import BaseCommand
from words.models import Word


class Command(BaseCommand):
    help = 'Import sample words for the vocabulary app'

    def handle(self, *args, **kwargs):
        sample_words = [
            # ===== 基础词汇 (difficulty=1) =====
            {"word": "apple", "pronunciation": "/ˈæpl/", "definition": "n. 苹果", "example": "I eat an apple every day.", "example_translation": "我每天吃一个苹果。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "food"},
            {"word": "book", "pronunciation": "/bʊk/", "definition": "n. 书；书籍", "example": "This is an interesting book.", "example_translation": "这是一本有趣的书。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "school"},
            {"word": "cat", "pronunciation": "/kæt/", "definition": "n. 猫", "example": "The cat is sleeping on the sofa.", "example_translation": "猫正在沙发上睡觉。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "animal"},
            {"word": "dog", "pronunciation": "/dɒɡ/", "definition": "n. 狗", "example": "My dog is very friendly.", "example_translation": "我的狗很友好。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "animal"},
            {"word": "egg", "pronunciation": "/eɡ/", "definition": "n. 蛋；鸡蛋", "example": "I had two eggs for breakfast.", "example_translation": "我早餐吃了两个鸡蛋。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "food"},
            {"word": "fish", "pronunciation": "/fɪʃ/", "definition": "n. 鱼 v. 钓鱼", "example": "We went fishing last weekend.", "example_translation": "我们上周末去钓鱼了。", "difficulty": 1, "unit": "Unit 1", "textbook": "基础词汇", "category": "animal"},
            {"word": "happy", "pronunciation": "/ˈhæpi/", "definition": "adj. 快乐的；幸福的", "example": "She looks very happy today.", "example_translation": "她今天看起来很开心。", "difficulty": 1, "unit": "Unit 2", "textbook": "基础词汇", "category": "emotion"},
            {"word": "house", "pronunciation": "/haʊs/", "definition": "n. 房子；住宅", "example": "They live in a big house.", "example_translation": "他们住在一栋大房子里。", "difficulty": 1, "unit": "Unit 2", "textbook": "基础词汇", "category": "place"},
            {"word": "water", "pronunciation": "/ˈwɔːtər/", "definition": "n. 水", "example": "Please drink more water.", "example_translation": "请多喝水。", "difficulty": 1, "unit": "Unit 2", "textbook": "基础词汇", "category": "nature"},
            {"word": "school", "pronunciation": "/skuːl/", "definition": "n. 学校", "example": "I go to school by bus.", "example_translation": "我坐公交车上学。", "difficulty": 1, "unit": "Unit 2", "textbook": "基础词汇", "category": "school"},

            # ===== 初级词汇 (difficulty=2) =====
            {"word": "beautiful", "pronunciation": "/ˈbjuːtɪfl/", "definition": "adj. 美丽的；漂亮的", "example": "What a beautiful sunset!", "example_translation": "多美的日落啊！", "difficulty": 2, "unit": "Unit 3", "textbook": "初级词汇", "category": "description"},
            {"word": "important", "pronunciation": "/ɪmˈpɔːrtnt/", "definition": "adj. 重要的", "example": "This is a very important meeting.", "example_translation": "这是一个非常重要的会议。", "difficulty": 2, "unit": "Unit 3", "textbook": "初级词汇", "category": "description"},
            {"word": "exercise", "pronunciation": "/ˈeksərsaɪz/", "definition": "n. 锻炼；练习 v. 运动", "example": "Regular exercise is good for health.", "example_translation": "经常锻炼对健康有益。", "difficulty": 2, "unit": "Unit 3", "textbook": "初级词汇", "category": "activity"},
            {"word": "together", "pronunciation": "/təˈɡeðər/", "definition": "adv. 一起；共同", "example": "Let's work together on this project.", "example_translation": "让我们一起做这个项目吧。", "difficulty": 2, "unit": "Unit 3", "textbook": "初级词汇", "category": "general"},
            {"word": "weather", "pronunciation": "/ˈweðər/", "definition": "n. 天气", "example": "The weather is nice today.", "example_translation": "今天天气很好。", "difficulty": 2, "unit": "Unit 3", "textbook": "初级词汇", "category": "nature"},
            {"word": "remember", "pronunciation": "/rɪˈmembər/", "definition": "v. 记住；记得", "example": "Please remember to bring your homework.", "example_translation": "请记得带你的作业。", "difficulty": 2, "unit": "Unit 4", "textbook": "初级词汇", "category": "action"},
            {"word": "different", "pronunciation": "/ˈdɪfrənt/", "definition": "adj. 不同的", "example": "These two pictures look different.", "example_translation": "这两张图片看起来不一样。", "difficulty": 2, "unit": "Unit 4", "textbook": "初级词汇", "category": "description"},
            {"word": "favorite", "pronunciation": "/ˈfeɪvərɪt/", "definition": "adj. 最喜欢的 n. 最爱的人/物", "example": "What's your favorite color?", "example_translation": "你最喜欢的颜色是什么？", "difficulty": 2, "unit": "Unit 4", "textbook": "初级词汇", "category": "description"},
            {"word": "problem", "pronunciation": "/ˈprɒbləm/", "definition": "n. 问题；难题", "example": "Can you solve this math problem?", "example_translation": "你能解出这道数学题吗？", "difficulty": 2, "unit": "Unit 4", "textbook": "初级词汇", "category": "school"},
            {"word": "friendly", "pronunciation": "/ˈfrendli/", "definition": "adj. 友好的；亲切的", "example": "The people here are very friendly.", "example_translation": "这里的人非常友好。", "difficulty": 2, "unit": "Unit 4", "textbook": "初级词汇", "category": "description"},

            # ===== 中级词汇 (difficulty=3) =====
            {"word": "adventure", "pronunciation": "/ədˈventʃər/", "definition": "n. 冒险；奇遇", "example": "The trip was a great adventure.", "example_translation": "这次旅行是一次很棒的冒险。", "difficulty": 3, "unit": "Unit 5", "textbook": "中级词汇", "category": "general"},
            {"word": "communicate", "pronunciation": "/kəˈmjuːnɪkeɪt/", "definition": "v. 交流；沟通", "example": "It's important to communicate clearly.", "example_translation": "清晰沟通是很重要的。", "difficulty": 3, "unit": "Unit 5", "textbook": "中级词汇", "category": "action"},
            {"word": "environment", "pronunciation": "/ɪnˈvaɪrənmənt/", "definition": "n. 环境", "example": "We should protect the environment.", "example_translation": "我们应该保护环境。", "difficulty": 3, "unit": "Unit 5", "textbook": "中级词汇", "category": "nature"},
            {"word": "experience", "pronunciation": "/ɪkˈspɪriəns/", "definition": "n. 经验；经历 v. 体验", "example": "She has a lot of teaching experience.", "example_translation": "她有丰富的教学经验。", "difficulty": 3, "unit": "Unit 5", "textbook": "中级词汇", "category": "general"},
            {"word": "opportunity", "pronunciation": "/ˌɒpərˈtjuːnəti/", "definition": "n. 机会", "example": "Don't miss this great opportunity.", "example_translation": "别错过这个好机会。", "difficulty": 3, "unit": "Unit 5", "textbook": "中级词汇", "category": "general"},
            {"word": "technology", "pronunciation": "/tekˈnɒlədʒi/", "definition": "n. 技术；科技", "example": "Technology is changing our lives.", "example_translation": "科技正在改变我们的生活。", "difficulty": 3, "unit": "Unit 6", "textbook": "中级词汇", "category": "science"},
            {"word": "challenge", "pronunciation": "/ˈtʃælɪndʒ/", "definition": "n. 挑战 v. 挑战", "example": "This exam is a big challenge for me.", "example_translation": "这次考试对我来说是个大挑战。", "difficulty": 3, "unit": "Unit 6", "textbook": "中级词汇", "category": "general"},
            {"word": "knowledge", "pronunciation": "/ˈnɒlɪdʒ/", "definition": "n. 知识；学识", "example": "Knowledge is power.", "example_translation": "知识就是力量。", "difficulty": 3, "unit": "Unit 6", "textbook": "中级词汇", "category": "school"},
            {"word": "encourage", "pronunciation": "/ɪnˈkʌrɪdʒ/", "definition": "v. 鼓励；激励", "example": "Teachers should encourage students to think.", "example_translation": "老师应该鼓励学生思考。", "difficulty": 3, "unit": "Unit 6", "textbook": "中级词汇", "category": "action"},
            {"word": "incredible", "pronunciation": "/ɪnˈkredəbl/", "definition": "adj. 难以置信的；极好的", "example": "The view from the mountain was incredible.", "example_translation": "山上的风景令人难以置信。", "difficulty": 3, "unit": "Unit 6", "textbook": "中级词汇", "category": "description"},

            # ===== 中高级词汇 (difficulty=4) =====
            {"word": "accomplish", "pronunciation": "/əˈkɒmplɪʃ/", "definition": "v. 完成；实现", "example": "She accomplished all her goals this year.", "example_translation": "她今年完成了所有目标。", "difficulty": 4, "unit": "Unit 7", "textbook": "中高级词汇", "category": "action"},
            {"word": "consequence", "pronunciation": "/ˈkɒnsɪkwəns/", "definition": "n. 后果；结果", "example": "You must face the consequences of your actions.", "example_translation": "你必须面对你行为的后果。", "difficulty": 4, "unit": "Unit 7", "textbook": "中高级词汇", "category": "general"},
            {"word": "determination", "pronunciation": "/dɪˌtɜːmɪˈneɪʃn/", "definition": "n. 决心；毅力", "example": "Her determination helped her succeed.", "example_translation": "她的决心帮助她获得了成功。", "difficulty": 4, "unit": "Unit 7", "textbook": "中高级词汇", "category": "emotion"},
            {"word": "enthusiasm", "pronunciation": "/ɪnˈθjuːziæzəm/", "definition": "n. 热情；热忱", "example": "He spoke with great enthusiasm.", "example_translation": "他充满热情地讲话。", "difficulty": 4, "unit": "Unit 7", "textbook": "中高级词汇", "category": "emotion"},
            {"word": "magnificent", "pronunciation": "/mæɡˈnɪfɪsnt/", "definition": "adj. 壮丽的；极好的", "example": "The palace is truly magnificent.", "example_translation": "这座宫殿真的很壮丽。", "difficulty": 4, "unit": "Unit 7", "textbook": "中高级词汇", "category": "description"},

            # ===== 高级词汇 (difficulty=5) =====
            {"word": "serendipity", "pronunciation": "/ˌserənˈdɪpəti/", "definition": "n. 意外发现珍奇事物的本领；机缘凑巧", "example": "Meeting her was pure serendipity.", "example_translation": "遇见她纯属机缘巧合。", "difficulty": 5, "unit": "Unit 8", "textbook": "高级词汇", "category": "advanced"},
            {"word": "ephemeral", "pronunciation": "/ɪˈfemərəl/", "definition": "adj. 短暂的；朝生暮死的", "example": "Fashion is ephemeral, changing with every season.", "example_translation": "时尚是短暂的，每季都在变化。", "difficulty": 5, "unit": "Unit 8", "textbook": "高级词汇", "category": "advanced"},
            {"word": "resilience", "pronunciation": "/rɪˈzɪliəns/", "definition": "n. 恢复力；弹力；顺应力", "example": "She showed great resilience in the face of adversity.", "example_translation": "她在逆境中表现出了极大的韧性。", "difficulty": 5, "unit": "Unit 8", "textbook": "高级词汇", "category": "advanced"},
            {"word": "ambiguous", "pronunciation": "/æmˈbɪɡjuəs/", "definition": "adj. 模棱两可的；含糊不清的", "example": "The contract is ambiguous in this section.", "example_translation": "合同的这一部分表述含糊。", "difficulty": 5, "unit": "Unit 8", "textbook": "高级词汇", "category": "advanced"},
            {"word": "pragmatic", "pronunciation": "/præɡˈmætɪk/", "definition": "adj. 实用的；务实的", "example": "We need a pragmatic solution to this problem.", "example_translation": "我们需要一个务实的解决方案。", "difficulty": 5, "unit": "Unit 8", "textbook": "高级词汇", "category": "advanced"},
        ]

        count = 0
        for item in sample_words:
            word, created = Word.objects.get_or_create(
                word=item['word'],
                defaults=item
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f'成功导入 {count} 个新单词，共 {len(sample_words)} 个检查完毕'))
