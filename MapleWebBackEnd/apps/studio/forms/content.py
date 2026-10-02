"""Shops, special shops, quests and events."""
from django import forms
from django.forms import inlineformset_factory

from apps.characters.models import RateEvent
from apps.items.models import AuroraEvent, ItemTemplate, LumenEvent
from apps.quests.models import QuestObjective, QuestReward, QuestTemplate
from apps.shops.models import ShopCategory, ShopItem, SpecialShop, SpecialShopItem
from apps.skilles.validators import validate_material_requirements
from apps.world.models import BossDungeonTemplate, EnemyTemplate, NormalDungeonTemplate

from ..fields import PercentField, StudioModelForm

DATETIME_WIDGET = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
RESET_LABELS = [('none', 'Không reset (cả đời)'), ('daily', 'Mỗi ngày'), ('weekly', 'Mỗi tuần'), ('monthly', 'Mỗi tháng')]


def item_choices():
    return ItemTemplate.objects.order_by('name')


class RequiresFieldsBeforeModelClean:
    """
    Skip the model's clean() while a required relation is missing: those
    clean() methods read the relation and would crash instead of reporting.
    """
    model_clean_needs = ()

    def _post_clean(self):
        if any(name in self.errors for name in self.model_clean_needs) or getattr(self, '_skip_model_clean', False):
            return
        super()._post_clean()


# ---------- Shops ----------

class ShopCategoryForm(StudioModelForm):
    class Meta:
        model = ShopCategory
        fields = ('name', 'currency_type', 'required_level', 'order', 'start_date', 'end_date')
        labels = {
            'name': 'Tên danh mục', 'currency_type': 'Trả bằng', 'required_level': 'Cấp yêu cầu',
            'order': 'Thứ tự', 'start_date': 'Mở từ (UTC)', 'end_date': 'Đóng lúc (UTC)',
        }
        help_texts = {'start_date': 'Để trống cả hai = bán mãi mãi; điền cả hai = danh mục event.'}
        widgets = {'start_date': DATETIME_WIDGET, 'end_date': DATETIME_WIDGET}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'Phải sau thời điểm mở.')
        return cleaned


class ShopItemForm(RequiresFieldsBeforeModelClean, StudioModelForm):
    model_clean_needs = ('item_template',)

    class Meta:
        model = ShopItem
        fields = ('item_template', 'price', 'stock', 'reset_cycle', 'required_level', 'order')
        labels = {
            'item_template': 'Item', 'price': 'Giá', 'stock': 'Giới hạn mua', 'reset_cycle': 'Reset giới hạn',
            'required_level': 'Cấp yêu cầu', 'order': 'Thứ tự',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item_template'].queryset = item_choices()
        self.fields['reset_cycle'].choices = RESET_LABELS
        self.fields['stock'].help_text = '0 = không giới hạn.'

    def clean(self):
        cleaned = super().clean()
        level = cleaned.get('required_level')
        # The inline formset hands the parent (possibly not saved yet) in as 'category'.
        category = cleaned.get('category')
        if category is not None and level is not None and level < category.required_level:
            self._skip_model_clean = True
            self.add_error('required_level', f'Không thấp hơn cấp của danh mục ({category.required_level}).')
        return cleaned


ShopItemFormSet = inlineformset_factory(ShopCategory, ShopItem, form=ShopItemForm, extra=0, can_delete=True)


class SpecialShopForm(StudioModelForm):
    class Meta:
        model = SpecialShop
        fields = ('name', 'is_active', 'required_level', 'order', 'start_time', 'end_time', 'description')
        labels = {
            'name': 'Tên shop', 'is_active': 'Đang mở', 'required_level': 'Cấp yêu cầu', 'order': 'Thứ tự',
            'start_time': 'Mở từ (UTC)', 'end_time': 'Đóng lúc (UTC)', 'description': 'Mô tả',
        }
        help_texts = {
            'is_active': 'Bỏ chọn để tạm đóng shop mà không xóa.',
            'start_time': 'Để trống cả hai = shop vĩnh viễn. Có thời gian = shop event, giới hạn đổi về 0 khi đợt mới bắt đầu.',
        }
        widgets = {'start_time': DATETIME_WIDGET, 'end_time': DATETIME_WIDGET, 'description': forms.Textarea(attrs={'rows': 2})}


class SpecialShopItemForm(RequiresFieldsBeforeModelClean, StudioModelForm):
    """One exchange: the item received, its limit, and the materials it costs (saved as recipe rows)."""
    model_clean_needs = ('item',)
    recipe = forms.JSONField(
        label='Nguyên liệu cần', required=False, widget=forms.TextInput(attrs={'data-materials': ''}),
    )

    class Meta:
        model = SpecialShopItem
        fields = ('item', 'recipe', 'exchange_limit', 'reset_cycle', 'is_active')
        labels = {'item': 'Nhận được', 'exchange_limit': 'Giới hạn đổi', 'reset_cycle': 'Reset giới hạn', 'is_active': 'Đang bán'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = item_choices()
        self.fields['reset_cycle'].choices = RESET_LABELS
        if self.instance.pk:
            self.initial['recipe'] = [
                {'item_template_id': recipe.item_id, 'quantity': recipe.quantity}
                for recipe in self.instance.specialshopitemrecipe_set.order_by('item_id')
            ]
        else:
            self.initial.setdefault('recipe', [])

    def clean_recipe(self):
        recipe = self.cleaned_data.get('recipe') or []
        try:
            validate_material_requirements(recipe)
        except forms.ValidationError as exc:
            raise forms.ValidationError(exc.messages)
        ids = {material['item_template_id'] for material in recipe}
        if len(ids) != len(recipe):
            raise forms.ValidationError('Mỗi nguyên liệu chỉ ghi một lần; gộp số lượng lại.')
        missing = ids - set(ItemTemplate.objects.filter(pk__in=ids).values_list('pk', flat=True))
        if missing:
            raise forms.ValidationError(f'Không có item id {sorted(missing)}.')
        return sorted(recipe, key=lambda material: material['item_template_id'])

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('DELETE') and 'recipe' in cleaned and not cleaned['recipe']:
            self.add_error('recipe', 'Cần ít nhất một nguyên liệu: game không cho đổi món không có công thức.')
        return cleaned

    def save_recipe(self):
        """Replace the item's recipe rows with the materials on the form."""
        rows = self.instance.specialshopitemrecipe_set
        rows.all().delete()
        for material in self.cleaned_data['recipe']:
            rows.create(item_id=material['item_template_id'], quantity=material['quantity'])


SpecialShopItemFormSet = inlineformset_factory(SpecialShop, SpecialShopItem, form=SpecialShopItemForm, extra=0, can_delete=True)


# ---------- Quests ----------

class QuestForm(StudioModelForm):
    class Meta:
        model = QuestTemplate
        fields = ('name', 'quest_type', 'required_level', 'prerequisite_quests', 'exp_reward', 'lumis_reward', 'description')
        labels = {
            'name': 'Tên quest', 'quest_type': 'Loại', 'required_level': 'Cấp yêu cầu',
            'prerequisite_quests': 'Phải xong quest trước', 'exp_reward': 'EXP thưởng', 'lumis_reward': 'Lumis thưởng',
            'description': 'Mô tả',
        }
        widgets = {'prerequisite_quests': forms.CheckboxSelectMultiple, 'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quest_type'].choices = [('once', 'Một lần'), ('daily', 'Hằng ngày'), ('weekly', 'Hằng tuần')]
        others = QuestTemplate.objects.order_by('required_level', 'name')
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        self.fields['prerequisite_quests'].queryset = others


OBJECTIVE_KINDS = [
    ('DEFEAT_ENEMY', 'Hạ quái'), ('COLLECT_ITEM', 'Thu thập item'),
    ('CLEAR_NORMAL_DUNGEON', 'Qua dungeon'), ('CLEAR_BOSS_DUNGEON', 'Qua dungeon boss'),
]
# kind -> (count field, target field)
OBJECTIVE_FIELDS = {kind: (count, target) for kind, count, target in QuestObjective.KINDS}


class QuestObjectiveForm(StudioModelForm):
    """One objective as kind + target + count; the page shows only the target that kind uses."""
    kind = forms.ChoiceField(label='Loại', choices=OBJECTIVE_KINDS)
    count = forms.IntegerField(label='Số lượng', min_value=1)

    class Meta:
        model = QuestObjective
        fields = ('kind', 'enemy_to_defeat', 'item_to_collect', 'dungeon_to_clear', 'boss_dungeon_to_clear', 'count')
        labels = {
            'enemy_to_defeat': 'Quái (trống = quái bất kỳ)', 'item_to_collect': 'Item',
            'dungeon_to_clear': 'Dungeon (trống = bất kỳ)', 'boss_dungeon_to_clear': 'Dungeon boss (trống = bất kỳ)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enemy_to_defeat'].queryset = EnemyTemplate.objects.order_by('level', 'name')
        self.fields['item_to_collect'].queryset = item_choices()
        self.fields['dungeon_to_clear'].queryset = NormalDungeonTemplate.objects.order_by('required_level', 'name')
        self.fields['boss_dungeon_to_clear'].queryset = BossDungeonTemplate.objects.order_by('required_level', 'name')
        if self.instance.pk and self.instance.objective_type:
            kind = self.instance.objective_type
            self.initial['kind'] = kind
            self.initial['count'] = getattr(self.instance, OBJECTIVE_FIELDS[kind][0])

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get('kind')
        if kind not in OBJECTIVE_FIELDS:
            return cleaned
        # Only the chosen kind keeps its target; the model allows exactly one kind.
        for other, (_, target) in OBJECTIVE_FIELDS.items():
            if other != kind:
                cleaned[target] = None
        if kind == 'COLLECT_ITEM' and not cleaned.get('item_to_collect'):
            self.add_error('item_to_collect', 'Chọn item cần thu thập.')
        return cleaned

    def _post_clean(self):
        kind = self.cleaned_data.get('kind')
        for other, (count_field, _) in OBJECTIVE_FIELDS.items():
            setattr(self.instance, count_field, (self.cleaned_data.get('count') or 0) if other == kind else 0)
        super()._post_clean()


QuestObjectiveFormSet = inlineformset_factory(QuestTemplate, QuestObjective, form=QuestObjectiveForm, extra=0, can_delete=True)


class QuestRewardForm(RequiresFieldsBeforeModelClean, StudioModelForm):
    model_clean_needs = ('item_template',)

    class Meta:
        model = QuestReward
        fields = ('item_template', 'quantity')
        labels = {'item_template': 'Item', 'quantity': 'Số lượng'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item_template'].queryset = item_choices()
        self.fields['quantity'].min_value = 1


QuestRewardFormSet = inlineformset_factory(QuestTemplate, QuestReward, form=QuestRewardForm, extra=0, can_delete=True)


# ---------- Events ----------

class EventTimesMixin:
    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_time'), cleaned.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'Phải sau thời điểm bắt đầu.')
        return cleaned


EVENT_LABELS = {'name': 'Tên event', 'description': 'Mô tả', 'is_active': 'Bật', 'start_time': 'Bắt đầu (UTC)', 'end_time': 'Kết thúc (UTC)'}
EVENT_WIDGETS = {'start_time': DATETIME_WIDGET, 'end_time': DATETIME_WIDGET, 'description': forms.Textarea(attrs={'rows': 2})}
EVENT_HELP = {'is_active': 'Event chỉ chạy khi được bật và đang trong khoảng thời gian (trống = không giới hạn).'}


class RateEventForm(EventTimesMixin, StudioModelForm):
    class Meta:
        model = RateEvent
        fields = ('name', 'is_active', 'start_time', 'end_time', 'exp_rate_bonus', 'lumis_rate_bonus',
                  'drop_rate_bonus', 'epic_drop_rate_bonus', 'description')
        labels = {**EVENT_LABELS, 'exp_rate_bonus': 'EXP +%', 'lumis_rate_bonus': 'Lumis +%',
                  'drop_rate_bonus': 'Rơi đồ thường +%', 'epic_drop_rate_bonus': 'Rơi đồ Epic +%'}
        help_texts = {**EVENT_HELP, 'exp_rate_bonus': '100 = x2. Mọi event đang chạy cộng dồn với nhau và với buff.'}
        widgets = EVENT_WIDGETS


class LumenEventForm(EventTimesMixin, StudioModelForm):
    success_flat_bonus = PercentField(label='Cộng tỉ lệ thành công (điểm %)', min_value=0, max_value=100, initial=0)

    class Meta:
        model = LumenEvent
        fields = ('name', 'is_active', 'start_time', 'end_time', 'success_flat_bonus', 'heavy_failure_multiplier',
                  'bonus_levels', 'description')
        labels = {**EVENT_LABELS, 'heavy_failure_multiplier': 'Nhân tỉ lệ thất bại nặng', 'bonus_levels': 'Cấp cộng thêm khi thành công'}
        help_texts = {**EVENT_HELP, 'heavy_failure_multiplier': '0 = không bao giờ vỡ đồ, 0,5 = giảm một nửa, 1 = như thường.',
                      'bonus_levels': '1 = thành công lên 2 cấp.'}
        widgets = EVENT_WIDGETS


class AuroraEventForm(EventTimesMixin, StudioModelForm):
    class Meta:
        model = AuroraEvent
        fields = ('name', 'is_active', 'start_time', 'end_time', 'tier_up_chance_multiplier', 'description')
        labels = {**EVENT_LABELS, 'tier_up_chance_multiplier': 'Nhân tỉ lệ lên bậc Aurora'}
        help_texts = {**EVENT_HELP, 'tier_up_chance_multiplier': '1,5 = tỉ lệ lên bậc gấp 1,5 lần.'}
        widgets = EVENT_WIDGETS
