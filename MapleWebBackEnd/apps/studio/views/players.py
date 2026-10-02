from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.battles.services import BattleService
from apps.users.models import GameUser, NovaTransaction
from apps.users.nova_service import NovaError, change_nova
from apps.users.sessions import end_all_sessions

from .. import history, players_logic
from ..access import SuperuserRequiredMixin
from ..forms.players import NovaChangeForm, ReasonForm
from ..models import StudioChange


class PlayerListView(SuperuserRequiredMixin, ListView):
    template_name = 'studio/players/list.html'
    paginate_by = 50

    def get_queryset(self):
        queryset = GameUser.objects.select_related('character__character_class', 'character__job').order_by('username')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(email__icontains=query) | Q(character__name__icontains=query))
        state = self.request.GET.get('state')
        if state == 'locked':
            queryset = queryset.filter(is_active=False)
        elif state == 'staff':
            queryset = queryset.filter(is_staff=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(section='players', query=self.request.GET.get('q', ''), state=self.request.GET.get('state', ''),
                       filter_params=params.urlencode())
        return context


NOVA_ERRORS = {
    'Amount must be a non-zero whole number.': 'Số Nova phải là số nguyên khác 0.',
    'A donation must add Nova.': 'Donate chỉ được cộng Nova; dùng "Điều chỉnh" để trừ.',
    'Not enough Nova.': 'Người chơi không đủ Nova để trừ chừng này.',
    'This reference was already credited.': 'Mã donate này đã được cộng trước đó.',
}

ACTIONS = {
    'lock': 'Khóa tài khoản',
    'unlock': 'Mở khóa tài khoản',
    'logout_all': 'Đăng xuất mọi thiết bị',
    'reset_password': 'Đặt lại mật khẩu',
    'end_battle': 'Gỡ trận bị kẹt',
    'refill_stamina': 'Hồi đầy thể lực',
}


class PlayerDetailView(SuperuserRequiredMixin, View):
    """A player's account, character, items and Nova, with the safe actions."""

    def get_player(self, pk):
        return get_object_or_404(GameUser.objects.select_related('character__character_class', 'character__job'), pk=pk)

    def context(self, player, **extra):
        character = player.character
        battle = BattleService.get_active_combat_for_character(character) if character else None
        items = []
        if character is not None:
            character.update_stamina()
            items = list(character.inventory_items.select_related('template', 'equipped_in').order_by('template__name')[:200])
        return {
            'section': 'players', 'player': player, 'character': character, 'battle': battle, 'items': items,
            'nova_entries': NovaTransaction.objects.filter(user=player).order_by('-created_at', '-id')[:20],
            'history_url': history.history_url(player), 'reason_form': ReasonForm(),
            'nova_form': extra.pop('nova_form', None) or NovaChangeForm(), 'actions': ACTIONS, **extra,
        }

    def get(self, request, pk):
        player = self.get_player(pk)
        return render(request, 'studio/players/detail.html', self.context(player))

    def post(self, request, pk):
        player = self.get_player(pk)
        action = request.POST.get('action')
        if action == 'nova':
            return self.change_nova(player)
        if action not in ACTIONS:
            messages.error(request, 'Thao tác không hợp lệ.')
            return redirect(request.path)
        reason_form = ReasonForm(request.POST)
        reason = reason_form.cleaned_data['reason'] if reason_form.is_valid() else ''
        if action in ('lock', 'reset_password') and player.pk == request.user.pk:
            messages.error(request, 'Không làm thao tác này với chính tài khoản bạn đang dùng.')
            return redirect(request.path)

        character = player.character
        password = None
        summary = ACTIONS[action]
        with transaction.atomic():
            if action in ('lock', 'unlock'):
                players_logic.set_locked(player, action == 'lock')
            elif action == 'logout_all':
                end_all_sessions(player)
            elif action == 'reset_password':
                password = players_logic.reset_password(player)
            elif action == 'end_battle':
                combat = players_logic.end_stuck_battle(character) if character else None
                if combat is None:
                    messages.error(request, 'Người chơi không có trận nào đang chạy.')
                    return redirect(request.path)
                summary = f'{summary} {combat.pk} (kết quả: {combat.get_status_display()})'
            elif action == 'refill_stamina':
                if character is None:
                    messages.error(request, 'Người chơi chưa có nhân vật.')
                    return redirect(request.path)
                players_logic.refill_stamina(character)
            # The temporary password itself is never stored in the history.
            history.record(request.user, StudioChange.Action.ACTION, player, summary=summary,
                           changes={'Lý do': [None, reason]} if reason else {})
        if password is not None:
            response = render(request, 'studio/players/password.html', {'section': 'players', 'player': player, 'password': password})
            response['Cache-Control'] = 'no-store'  # shown once; keep it out of the browser cache
            return response
        messages.success(request, f'{summary}: xong.')
        return redirect(request.path)

    def change_nova(self, player):
        form = NovaChangeForm(self.request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                with transaction.atomic():
                    entry = change_nova(
                        player, data['amount'], data['kind'], reference=(data['reference'] or '').strip() or None,
                        description=data['description'], note=data['note'], created_by=self.request.user,
                    )
                    history.record(
                        self.request.user, StudioChange.Action.ACTION, player,
                        summary=f'Nova {entry.amount:+d} ({entry.get_kind_display()})',
                        changes={'Nova': [entry.balance_after - entry.amount, entry.balance_after]},
                    )
            except NovaError as exc:
                form.add_error(None, NOVA_ERRORS.get(str(exc), str(exc)))
            else:
                messages.success(self.request, f'Đã ghi {entry.amount:+d} Nova. Số dư mới: {entry.balance_after}.')
                return redirect(reverse('studio:player-detail', args=[player.pk]))
        player.refresh_from_db()
        return render(self.request, 'studio/players/detail.html', self.context(player, nova_form=form))
