"""Operations and moderation pages (superusers): market, parties, battles, boss clears, quest progress."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.battles.models import CombatInstance, Combatant
from apps.characters.models import Character
from apps.market.models import Listing, Trade, Transaction
from apps.party.models import Party, PartyMember
from apps.quests.models import CharacterQuest
from apps.world.models import DungeonClearLog

from .. import history
from ..access import SuperuserRequiredMixin
from ..models import StudioChange


class MarketView(SuperuserRequiredMixin, View):
    """Active listings, pending trades and recent sales, with the two moderation actions."""

    def get(self, request):
        query = request.GET.get('q', '').strip()
        listings = Listing.objects.filter(is_active=True).select_related('seller', 'item__template').order_by('-id')
        trades = Trade.objects.filter(status='pending').select_related('sender', 'receiver').prefetch_related('items__item__template').order_by('-created_at')
        sales = Transaction.objects.select_related('buyer', 'seller', 'item_template').order_by('-created_at')
        if query:
            listings = listings.filter(Q(seller__username__icontains=query) | Q(item__template__name__icontains=query))
            trades = trades.filter(Q(sender__username__icontains=query) | Q(receiver__username__icontains=query))
            sales = sales.filter(Q(buyer__username__icontains=query) | Q(seller__username__icontains=query) | Q(item_template__name__icontains=query))
        return render(request, 'studio/ops/market.html', {
            'section': 'market', 'query': query,
            'listings': listings[:100], 'trades': trades[:100], 'sales': sales[:100],
        })

    def post(self, request):
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()[:200]
        changes = {'Lý do': [None, reason]} if reason else {}
        with transaction.atomic():
            if action == 'cancel_listing':
                listing = get_object_or_404(Listing.objects.select_for_update(), pk=request.POST.get('pk'), is_active=True)
                # As when the seller cancels: the item stays in their inventory.
                listing.is_active = False
                listing.save(update_fields=['is_active'])
                history.record(request.user, StudioChange.Action.ACTION, listing.seller,
                               summary=f'Gỡ listing {listing.pk}: {listing.item.template.name} giá {listing.price}', changes=changes)
                messages.success(request, f'Đã gỡ listing {listing.pk}; item về lại túi người bán.')
            elif action == 'cancel_trade':
                trade = get_object_or_404(Trade.objects.select_for_update(), pk=request.POST.get('pk'), status='pending')
                trade.status = 'cancelled'
                trade.save(update_fields=['status'])
                for user in (trade.sender, trade.receiver):
                    history.record(request.user, StudioChange.Action.ACTION, user,
                                   summary=f'Hủy trade {trade.pk} ({trade.sender.username} ↔ {trade.receiver.username})', changes=changes)
                messages.success(request, f'Đã hủy trade {trade.pk}; item của hai bên được giải phóng.')
            else:
                messages.error(request, 'Thao tác không hợp lệ.')
        return redirect(request.get_full_path())


def players_by_character(character_ids):
    """{character pk: (character, account)} for linking to player pages."""
    characters = Character.objects.filter(pk__in=character_ids).select_related('user')
    return {str(c.pk): (c, getattr(c, 'user', None)) for c in characters}


class PartyListView(SuperuserRequiredMixin, ListView):
    template_name = 'studio/ops/parties.html'
    paginate_by = 50

    def get_queryset(self):
        queryset = Party.objects.select_related('leader').prefetch_related(
            Prefetch('party_members', queryset=PartyMember.objects.select_related('character__user').order_by('position')),
        ).order_by('-created_at')
        if self.request.GET.get('solo') != '1':
            queryset = queryset.filter(is_solo=False)
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(party_members__character__name__icontains=query)).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(section='parties', query=self.request.GET.get('q', ''), solo=self.request.GET.get('solo') == '1',
                       filter_params=params.urlencode())
        return context


class BattleListView(SuperuserRequiredMixin, View):
    """Battles still running, oldest activity first, so stuck ones stand out."""

    def get(self, request):
        battles = list(CombatInstance.objects.filter(status=CombatInstance.CombatStatus.IN_PROGRESS).select_related(
            'normal_dungeon', 'boss_dungeon', 'party',
        ).prefetch_related(Prefetch('combatants', queryset=Combatant.objects.filter(is_player=True))).order_by('updated_at'))
        ids = {c.objects_id for battle in battles for c in battle.combatants.all()}
        owners = players_by_character(ids)
        rows = []
        for battle in battles:
            players = [{'combatant': c, 'character': owners.get(c.objects_id, (None, None))[0],
                        'user': owners.get(c.objects_id, (None, None))[1]} for c in battle.combatants.all()]
            rows.append({'battle': battle, 'players': players, 'dungeon': battle.normal_dungeon or battle.boss_dungeon})
        return render(request, 'studio/ops/battles.html', {'section': 'battles', 'rows': rows})


class BossClearListView(SuperuserRequiredMixin, ListView):
    template_name = 'studio/ops/boss_clears.html'
    paginate_by = 100

    def get_queryset(self):
        queryset = DungeonClearLog.objects.select_related('character__user', 'dungeon').order_by('-cleared_at')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(character__name__icontains=query) | Q(dungeon__name__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(section='boss-clears', query=self.request.GET.get('q', ''), filter_params=params.urlencode())
        return context


class CharacterQuestListView(SuperuserRequiredMixin, ListView):
    template_name = 'studio/ops/character_quests.html'
    paginate_by = 100

    def get_queryset(self):
        queryset = CharacterQuest.objects.select_related('character__user', 'quest').prefetch_related(
            'objective_progress__objective',
        ).order_by('-started_at')
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(character__name__icontains=query) | Q(quest__name__icontains=query))
        status = self.request.GET.get('status')
        if status in CharacterQuest.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(section='character-quests', query=self.request.GET.get('q', ''),
                       status=self.request.GET.get('status', ''), statuses=CharacterQuest.Status.choices,
                       filter_params=params.urlencode())
        return context
