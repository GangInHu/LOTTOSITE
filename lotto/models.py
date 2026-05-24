from django.db import models
from django.contrib.auth.models import User
import random


class LottoRound(models.Model):
    """추첨 회차"""
    round_number = models.PositiveIntegerField(unique=True, verbose_name='회차')
    draw_date = models.DateField(null=True, blank=True, verbose_name='추첨일')
    num1 = models.PositiveIntegerField(null=True, blank=True)
    num2 = models.PositiveIntegerField(null=True, blank=True)
    num3 = models.PositiveIntegerField(null=True, blank=True)
    num4 = models.PositiveIntegerField(null=True, blank=True)
    num5 = models.PositiveIntegerField(null=True, blank=True)
    num6 = models.PositiveIntegerField(null=True, blank=True)
    bonus = models.PositiveIntegerField(null=True, blank=True, verbose_name='보너스')
    is_drawn = models.BooleanField(default=False, verbose_name='추첨완료')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-round_number']
        verbose_name = '로또 회차'
        verbose_name_plural = '로또 회차 목록'

    def __str__(self):
        return f"제{self.round_number}회"

    def get_numbers(self):
        if self.is_drawn:
            return sorted([self.num1, self.num2, self.num3, self.num4, self.num5, self.num6])
        return []

    def draw(self):
        """추첨 실행"""
        numbers = random.sample(range(1, 46), 7)
        self.num1, self.num2, self.num3, self.num4, self.num5, self.num6 = sorted(numbers[:6])
        self.bonus = numbers[6]
        self.is_drawn = True
        from django.utils import timezone
        self.draw_date = timezone.now().date()
        self.save()


class LottoTicket(models.Model):
    """복권 구매 내역"""
    PURCHASE_TYPE = [
        ('manual', '수동'),
        ('auto', '자동'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='구매자')
    round = models.ForeignKey(LottoRound, on_delete=models.CASCADE, verbose_name='회차')
    num1 = models.PositiveIntegerField()
    num2 = models.PositiveIntegerField()
    num3 = models.PositiveIntegerField()
    num4 = models.PositiveIntegerField()
    num5 = models.PositiveIntegerField()
    num6 = models.PositiveIntegerField()
    purchase_type = models.CharField(max_length=10, choices=PURCHASE_TYPE, default='manual')
    purchase_date = models.DateTimeField(auto_now_add=True)
    rank = models.PositiveIntegerField(null=True, blank=True, verbose_name='당첨 등수')
    prize = models.BigIntegerField(default=0, verbose_name='당첨금')
    is_checked = models.BooleanField(default=False, verbose_name='당첨확인')

    class Meta:
        ordering = ['-purchase_date']
        verbose_name = '복권 티켓'
        verbose_name_plural = '복권 티켓 목록'

    def __str__(self):
        return f"{self.user.username} - {self.round} - {self.get_numbers()}"

    def get_numbers(self):
        return sorted([self.num1, self.num2, self.num3, self.num4, self.num5, self.num6])

    def check_win(self):
        """당첨 확인"""
        if not self.round.is_drawn:
            return None

        my_nums = set(self.get_numbers())
        win_nums = set(self.round.get_numbers())
        bonus = self.round.bonus

        match_count = len(my_nums & win_nums)
        has_bonus = bonus in my_nums

        if match_count == 6:
            self.rank = 1
            self.prize = 2_000_000_000
        elif match_count == 5 and has_bonus:
            self.rank = 2
            self.prize = 60_000_000
        elif match_count == 5:
            self.rank = 3
            self.prize = 1_500_000
        elif match_count == 4:
            self.rank = 4
            self.prize = 50_000
        elif match_count == 3:
            self.rank = 5
            self.prize = 5_000
        else:
            self.rank = 0
            self.prize = 0

        self.is_checked = True
        self.save()
        return self.rank
