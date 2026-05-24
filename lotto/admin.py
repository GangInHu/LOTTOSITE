from django.contrib import admin
from .models import LottoRound, LottoTicket

@admin.register(LottoRound)
class LottoRoundAdmin(admin.ModelAdmin):
    list_display = ['round_number', 'is_drawn', 'draw_date', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'bonus']

@admin.register(LottoTicket)
class LottoTicketAdmin(admin.ModelAdmin):
    list_display = ['user', 'round', 'get_numbers', 'purchase_type', 'rank', 'prize', 'purchase_date']
