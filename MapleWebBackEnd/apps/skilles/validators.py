from django.core.exceptions import ValidationError


def validate_material_requirements(value):
    """Validate SkillLevelConfig.required_materials without querying the DB."""
    if not isinstance(value, list):
        raise ValidationError('required_materials must be a list.')

    seen_template_ids = set()
    for index, requirement in enumerate(value):
        if not isinstance(requirement, dict):
            raise ValidationError(f'Material at index {index} must be an object.')
        if set(requirement) != {'item_template_id', 'quantity'}:
            raise ValidationError(
                f'Material at index {index} must contain only item_template_id and quantity.'
            )

        template_id = requirement['item_template_id']
        quantity = requirement['quantity']
        if isinstance(template_id, bool) or not isinstance(template_id, int) or template_id <= 0:
            raise ValidationError(f'item_template_id at index {index} must be a positive integer.')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError(f'quantity at index {index} must be a positive integer.')
        if template_id in seen_template_ids:
            raise ValidationError(f'Duplicate item_template_id={template_id}.')
        seen_template_ids.add(template_id)
