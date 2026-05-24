from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db.models import Sum, Count
from .models import LottoRound, LottoTicket
import random


def is_admin(user):
    return user.is_staff


def index(request):
    current_round = LottoRound.objects.filter(is_drawn=False).order_by('round_number').first()
    latest_drawn = LottoRound.objects.filter(is_drawn=True).first()
    return render(request, 'lotto/index.html', {
        'current_round': current_round,
        'latest_drawn': latest_drawn,
    })


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '회원가입이 완료되었습니다!')
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'lotto/register.html', {'form': form})


@login_required
def buy_ticket(request):
    current_round = LottoRound.objects.filter(is_drawn=False).order_by('round_number').first()
    if not current_round:
        messages.error(request, '현재 구매 가능한 회차가 없습니다.')
        return redirect('index')

    if request.method == 'POST':
        purchase_type = request.POST.get('purchase_type', 'manual')

        if purchase_type == 'auto':
            numbers = sorted(random.sample(range(1, 46), 6))
        else:
            try:
                numbers = sorted([
                    int(request.POST.get(f'num{i}')) for i in range(1, 7)
                ])
                if len(set(numbers)) != 6 or not all(1 <= n <= 45 for n in numbers):
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, '올바른 번호를 입력해주세요 (1~45, 중복 불가).')
                return render(request, 'lotto/buy_ticket.html', {'current_round': current_round, 'nums': range(1, 46)})

        ticket = LottoTicket.objects.create(
            user=request.user,
            round=current_round,
            num1=numbers[0], num2=numbers[1], num3=numbers[2],
            num4=numbers[3], num5=numbers[4], num6=numbers[5],
            purchase_type=purchase_type,
        )
        messages.success(request, f'복권 구매 완료! 번호: {numbers}')
        return redirect('my_tickets')

    return render(request, 'lotto/buy_ticket.html', {'current_round': current_round, 'nums': range(1, 46)})


@login_required
def my_tickets(request):
    tickets = LottoTicket.objects.filter(user=request.user).select_related('round')
    return render(request, 'lotto/my_tickets.html', {'tickets': tickets})


@login_required
def check_win(request, ticket_id):
    ticket = get_object_or_404(LottoTicket, id=ticket_id, user=request.user)
    if not ticket.round.is_drawn:
        messages.warning(request, '아직 추첨이 진행되지 않았습니다.')
    elif not ticket.is_checked:
        rank = ticket.check_win()
        if rank and rank > 0:
            messages.success(request, f'🎉 {rank}등 당첨! 당첨금: {ticket.prize:,}원')
        else:
            messages.info(request, '아쉽게도 낙첨되었습니다.')
    return redirect('my_tickets')


@login_required
def check_all_wins(request):
    tickets = LottoTicket.objects.filter(user=request.user, is_checked=False, round__is_drawn=True)
    count = 0
    for ticket in tickets:
        ticket.check_win()
        count += 1
    if count:
        messages.success(request, f'{count}개 티켓의 당첨 여부를 확인했습니다.')
    else:
        messages.info(request, '확인할 티켓이 없습니다.')
    return redirect('my_tickets')


def draw_history(request):
    rounds = LottoRound.objects.filter(is_drawn=True)
    return render(request, 'lotto/draw_history.html', {'rounds': rounds})


# ── 관리자 뷰 ──

@user_passes_test(is_admin)
def admin_dashboard(request):
    total_tickets = LottoTicket.objects.count()
    total_revenue = total_tickets * 1000
    rounds = LottoRound.objects.all()
    winners = LottoTicket.objects.filter(rank__gt=0)
    stats = {
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'total_rounds': rounds.count(),
        'drawn_rounds': rounds.filter(is_drawn=True).count(),
        'total_winners': winners.count(),
    }
    return render(request, 'lotto/admin_dashboard.html', {'stats': stats, 'rounds': rounds})


@user_passes_test(is_admin)
def admin_draw(request, round_id):
    round_obj = get_object_or_404(LottoRound, id=round_id)
    if round_obj.is_drawn:
        messages.warning(request, '이미 추첨이 완료된 회차입니다.')
        return redirect('admin_dashboard')

    if request.method == 'POST':
        round_obj.draw()
        # 해당 회차 모든 티켓 자동 당첨 확인
        for ticket in LottoTicket.objects.filter(round=round_obj):
            ticket.check_win()
        messages.success(request, f'{round_obj} 추첨 완료! 당첨번호: {round_obj.get_numbers()}, 보너스: {round_obj.bonus}')

        # 다음 회차 자동 생성
        next_num = round_obj.round_number + 1
        if not LottoRound.objects.filter(round_number=next_num).exists():
            LottoRound.objects.create(round_number=next_num)

        return redirect('admin_dashboard')

    return render(request, 'lotto/admin_draw.html', {'round': round_obj})


@user_passes_test(is_admin)
def admin_sales(request):
    tickets = LottoTicket.objects.select_related('user', 'round').order_by('-purchase_date')
    total = tickets.count()
    return render(request, 'lotto/admin_sales.html', {'tickets': tickets, 'total': total})


@user_passes_test(is_admin)
def admin_winners(request):
    winners = LottoTicket.objects.filter(rank__gt=0).select_related('user', 'round').order_by('rank', '-purchase_date')
    rank_summary = (
        LottoTicket.objects.filter(rank__gt=0)
        .values('rank')
        .annotate(count=Count('id'), total_prize=Sum('prize'))
        .order_by('rank')
    )
    return render(request, 'lotto/admin_winners.html', {'winners': winners, 'rank_summary': rank_summary})


@user_passes_test(is_admin)
def create_round(request):
    last = LottoRound.objects.order_by('-round_number').first()
    next_num = (last.round_number + 1) if last else 1
    LottoRound.objects.get_or_create(round_number=next_num)
    messages.success(request, f'제{next_num}회 회차가 생성되었습니다.')
    return redirect('admin_dashboard')
