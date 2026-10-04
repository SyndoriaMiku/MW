// MapleWeb Studio: small behaviours shared by every editor. No framework.
(function () {
  'use strict';

  // ---- Inline formsets: add rows from the empty form, mark rows deleted ----
  function setupFormset(box) {
    const prefix = box.dataset.formset;
    const total = box.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);
    const rows = box.querySelector('[data-rows]');
    const template = box.querySelector('template[data-empty-form]');
    box.querySelector('[data-add-row]')?.addEventListener('click', () => {
      const index = Number(total.value);
      const html = template.innerHTML.replace(/__prefix__/g, String(index));
      const holder = document.createElement('tbody');
      holder.innerHTML = html.trim();
      const row = holder.firstElementChild;
      rows.appendChild(row);
      total.value = String(index + 1);
      initWithin(row);
      refreshConditionals(box.closest('form'));
      row.querySelector('input:not([type=hidden]), select')?.focus();
    });
    box.addEventListener('click', (event) => {
      const button = event.target.closest('[data-delete-row]');
      if (!button) return;
      const row = button.closest('[data-row]');
      const checkbox = row.querySelector('input[name$="-DELETE"]');
      if (checkbox) {
        checkbox.checked = !checkbox.checked;
        row.classList.toggle('is-deleted', checkbox.checked);
        button.textContent = checkbox.checked ? 'Hoàn tác' : 'Xóa';
      } else {
        row.remove();
      }
    });
  }

  // ---- data-show-when="field=value1,value2": show only for those values ----
  function controlValue(form, name) {
    const controls = form.querySelectorAll(`[name="${name}"]`);
    if (!controls.length) return null;
    const first = controls[0];
    if (first.type === 'checkbox' && controls.length === 1) return first.checked ? 'on' : '';
    if (first.type === 'radio' || first.type === 'checkbox') {
      return Array.from(controls).filter((c) => c.checked).map((c) => c.value);
    }
    return first.value;
  }

  function refreshConditionals(form) {
    form.querySelectorAll('[data-show-when]').forEach((element) => {
      const [name, list] = element.dataset.showWhen.split('=');
      const wanted = list.split(',');
      const value = controlValue(form, name);
      const values = Array.isArray(value) ? value : [value];
      const visible = values.some((v) => wanted.includes(v)) || (wanted.includes('*') && values.some(Boolean));
      element.classList.toggle('hidden', !visible);
    });
  }

  // ---- Material lists stored as JSON: [{"item_template_id": 1, "quantity": 5}] ----
  function setupMaterials(input) {
    const options = JSON.parse(document.getElementById('studio-item-options')?.textContent || '[]');
    const box = document.createElement('div');
    box.className = 'materials';
    input.type = 'hidden';
    input.after(box);

    function read() {
      try { return JSON.parse(input.value || '[]') || []; } catch (e) { return []; }
    }
    function write(list) {
      input.value = JSON.stringify(list.filter((m) => m.item_template_id));
    }
    function render() {
      const list = read();
      box.innerHTML = '';
      list.forEach((material, index) => {
        const line = document.createElement('div');
        line.className = 'actions';
        const select = document.createElement('select');
        select.className = 'input';
        select.add(new Option('— chọn item —', ''));
        options.forEach((o) => select.add(new Option(o.name, String(o.id))));
        select.value = String(material.item_template_id || '');
        const qty = document.createElement('input');
        qty.type = 'number'; qty.min = '1'; qty.className = 'input'; qty.style.width = '80px';
        qty.value = material.quantity || 1;
        const remove = document.createElement('button');
        remove.type = 'button'; remove.className = 'btn ghost small'; remove.textContent = '×';
        select.addEventListener('change', () => { list[index].item_template_id = Number(select.value) || null; write(list); });
        qty.addEventListener('input', () => { list[index].quantity = Number(qty.value) || 1; write(list); });
        remove.addEventListener('click', () => { list.splice(index, 1); write(list); render(); });
        line.append(select, qty, remove);
        box.appendChild(line);
      });
      const add = document.createElement('button');
      add.type = 'button'; add.className = 'btn ghost small';
      add.textContent = list.length ? '+ nguyên liệu' : '+ nguyên liệu (trống = tự lên cấp)';
      add.addEventListener('click', () => { list.push({ item_template_id: null, quantity: 1 }); input.value = JSON.stringify(list); render(); });
      box.appendChild(add);
    }
    render();
  }

  // ---- Class growth preview: stats of a new character at a few levels ----
  function setupGrowthPreview(table) {
    const form = table.closest('form');
    const levels = table.dataset.growthPreview.split(',').map(Number);
    const base = table.dataset.base.split(',').map(Number);
    const names = ['hp_growth', 'mp_growth', 'str_growth', 'agi_growth', 'int_growth'];
    const warning = form.querySelector('[data-growth-warning]');
    function render() {
      const growth = names.map((name) => Number(form.querySelector(`[name="${name}"]`)?.value || 0));
      // Leveling adds the whole part of each growth once per level.
      const perLevel = growth.map((g) => Math.trunc(g));
      const body = table.tBodies[0];
      body.innerHTML = '';
      levels.forEach((level) => {
        const row = body.insertRow();
        row.insertCell().textContent = level;
        base.forEach((value, i) => { row.insertCell().textContent = value + perLevel[i] * (level - 1); });
      });
      const lost = names.filter((name, i) => growth[i] !== perLevel[i]).map((name) => name.split('_')[0].toUpperCase());
      warning.textContent = lost.length ? `Phần lẻ bị bỏ khi lên cấp: ${lost.join(', ')}.` : '';
    }
    form.addEventListener('input', render);
    render();
  }

  // ---- data-sortable: reorder rows by dragging the handle (or arrow keys), then save ----
  function setupSortable(form) {
    const body = form.querySelector('[data-sort-rows]');
    const save = form.querySelector('[data-sort-save]');
    const reset = form.querySelector('[data-sort-reset]');
    const status = form.querySelector('[data-sort-status]');
    const hint = status.textContent;
    const rows = () => [...body.querySelectorAll('[data-sort-row]')];
    const initial = rows().map((row) => row.dataset.sortRow);
    let dragging = null;

    function refresh() {
      rows().forEach((row, i) => { row.querySelector('[data-sort-index]').textContent = i + 1; });
      const changed = rows().map((row) => row.dataset.sortRow).join() !== initial.join();
      save.disabled = !changed;
      reset.hidden = !changed;
      status.textContent = changed ? 'Thứ tự đã thay đổi nhưng chưa lưu.' : hint;
      form.classList.toggle('is-dirty', changed);
    }

    body.addEventListener('pointerdown', (event) => {
      const handle = event.target.closest('.drag-handle');
      if (!handle || event.button !== 0) return;
      event.preventDefault();
      dragging = handle.closest('[data-sort-row]');
      dragging.classList.add('is-dragging');
      // Keep receiving moves when the pointer leaves the handle.
      try { handle.setPointerCapture(event.pointerId); } catch (error) { /* moves still reach the rows */ }
    });
    body.addEventListener('pointermove', (event) => {
      if (!dragging) return;
      // Drop before the first row whose middle is below the pointer.
      const before = rows().find((row) => {
        if (row === dragging) return false;
        const box = row.getBoundingClientRect();
        return event.clientY < box.top + box.height / 2;
      });
      if (before !== dragging.nextElementSibling) {
        body.insertBefore(dragging, before || null);
        refresh();
      }
      if (event.clientY < 48) window.scrollBy(0, -12);
      else if (event.clientY > window.innerHeight - 48) window.scrollBy(0, 12);
    });
    const drop = () => {
      dragging?.classList.remove('is-dragging');
      dragging = null;
    };
    body.addEventListener('pointerup', drop);
    body.addEventListener('pointercancel', drop);

    body.addEventListener('keydown', (event) => {
      const handle = event.target.closest('.drag-handle');
      if (!handle || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return;
      event.preventDefault();
      const row = handle.closest('[data-sort-row]');
      if (event.key === 'ArrowUp' && row.previousElementSibling) body.insertBefore(row, row.previousElementSibling);
      if (event.key === 'ArrowDown' && row.nextElementSibling) body.insertBefore(row.nextElementSibling, row);
      handle.focus();
      refresh();
    });

    reset.addEventListener('click', () => {
      const byId = Object.fromEntries(rows().map((row) => [row.dataset.sortRow, row]));
      initial.forEach((id) => body.appendChild(byId[id]));
      refresh();
    });
    form.addEventListener('submit', () => form.classList.remove('is-dirty'));
  }

  // Warn before leaving a page with an unsaved order.
  window.addEventListener('beforeunload', (event) => {
    if (document.querySelector('form.is-dirty')) event.preventDefault();
  });

  function initWithin(root) {
    root.querySelectorAll('[data-materials]').forEach(setupMaterials);
  }

  // ---- Ask before account actions; copy buttons ----
  document.addEventListener('submit', (event) => {
    const message = event.target.dataset?.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-copy]');
    if (!button) return;
    const source = document.querySelector(button.dataset.copy);
    navigator.clipboard?.writeText(source.textContent.trim()).then(
      () => { button.textContent = 'Đã sao chép'; },
      () => { window.getSelection().selectAllChildren(source); },
    );
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-formset]').forEach(setupFormset);
    document.querySelectorAll('[data-growth-preview]').forEach(setupGrowthPreview);
    document.querySelectorAll('form[data-sortable]').forEach(setupSortable);
    initWithin(document);
    document.querySelectorAll('form').forEach((form) => {
      refreshConditionals(form);
      form.addEventListener('change', () => refreshConditionals(form));
    });
  });

  window.Studio = { refreshConditionals };
})();
