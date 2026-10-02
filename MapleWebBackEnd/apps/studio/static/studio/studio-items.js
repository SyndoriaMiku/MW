// Item builder: main stat by class, stat suggestions, live preview and damage estimate.
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-item-builder]');
    if (!form) return;
    const data = JSON.parse(document.getElementById('item-builder-data').textContent);
    const classesById = Object.fromEntries(data.classes.map((c) => [String(c.id), c]));
    const jobsById = Object.fromEntries(data.jobs.map((j) => [String(j.id), j]));
    const $ = (selector) => form.querySelector(selector);
    const field = (name) => form.querySelector(`[name="${name}"]`);
    const num = (name) => Number(field(name)?.value || 0);
    const checked = (name) => Array.from(form.querySelectorAll(`[name="${name}"]:checked`)).map((c) => c.value);
    const isGear = () => ['weapon', 'armor', 'accessory'].includes(data.groups[field('item_type').value]);

    // The main stat: the single chosen class's, else the classes of the chosen jobs.
    function mainStat() {
      let classIds = checked('class_restriction');
      if (!classIds.length) classIds = [...new Set(checked('job_restriction').map((id) => String(jobsById[id].class_id)))];
      const stats = [...new Set(classIds.map((id) => classesById[id]?.main_stat).filter(Boolean))];
      return stats.length === 1 ? stats[0] : null;
    }

    function highlightMainStat() {
      const stat = mainStat();
      Object.entries(data.stat_fields).forEach(([key, name]) => {
        form.querySelector(`[data-field="${name}"]`)?.classList.toggle('is-main', key === stat);
      });
      const label = $('[data-main-stat-label]');
      label.textContent = stat ? `Chỉ số chính: ${data.stat_labels[stat]}` : 'Chọn 1 class để biết chỉ số chính';
    }

    // Weapons: picking a job fills its weapon type; show who can hold the chosen type.
    function weaponHelp(event) {
      const weaponSelect = field('weapon_type');
      const hint = $('[data-weapon-hint]');
      if (field('item_type').value !== 'weapon') { hint.textContent = ''; return; }
      if (event?.target?.name === 'job_restriction' && event.target.checked) {
        const job = jobsById[event.target.value];
        if (job?.weapon_type && !weaponSelect.value) weaponSelect.value = job.weapon_type;
      }
      const type = weaponSelect.value;
      if (!type) { hint.textContent = 'Chọn loại vũ khí ở mục 1.'; return; }
      const holders = data.jobs.filter((j) => j.weapon_type === type).map((j) => j.name);
      const open = data.jobs.filter((j) => !j.weapon_type).map((j) => j.name);
      hint.textContent = `Job cầm được loại vũ khí này: ${holders.length ? holders.join(', ') : 'chưa có job nào'}` +
        (open.length ? ` · Job chưa chọn vũ khí (cầm mọi loại): ${open.join(', ')}` : '');
    }

    function preview() {
      const typeSelect = field('item_type');
      $('[data-p-name]').textContent = field('name').value || 'Tên item';
      let sub = typeSelect.options[typeSelect.selectedIndex]?.text || '';
      if (typeSelect.value === 'weapon' && field('weapon_type').value) {
        const weapon = field('weapon_type');
        sub += ' · ' + weapon.options[weapon.selectedIndex].text;
      }
      $('[data-p-sub]').textContent = sub;
      const stats = $('[data-p-stats]');
      stats.innerHTML = '';
      if (isGear()) {
        const lines = [
          ['STR', num('str_boost')], ['AGI', num('agi_boost')], ['INT', num('int_boost')],
          ['All Stats', num('all_stats_boost')], ['ATT', num('att_boost')], ['HP', num('hp_boost')],
          ['MP', num('mp_boost')], ['Rơi đồ', num('drop_rate_boost'), '%'],
        ];
        lines.filter(([, value]) => value).forEach(([label, value, unit]) => {
          const line = document.createElement('div');
          line.className = 'p-line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = `${value > 0 ? '+' : ''}${value}${unit || ''}`;
          line.append(left, right);
          stats.appendChild(line);
        });
      } else {
        const kind = form.querySelector('[name="use_kind"]:checked');
        stats.textContent = kind && kind.value ? kind.parentElement.textContent.trim() : '';
      }
      const classNames = checked('class_restriction').map((id) => classesById[id]?.name);
      const jobNames = checked('job_restriction').map((id) => jobsById[id]?.name);
      const who = isGear() ? (jobNames.length ? jobNames : classNames).join(', ') || 'Mọi class' : '';
      $('[data-p-req]').textContent = `Yêu cầu cấp ${field('minimum_level').value || 1}${who ? ' · ' + who : ''}`;
      $('[data-p-desc]').textContent = field('description').value;
    }

    // Damage estimate with the game's formula, from the server.
    let estimateTimer = null;
    const jobSelect = document.querySelector('[data-estimate-job]');
    const levelInput = document.querySelector('[data-estimate-level]');
    function pickEstimateJob() {
      const jobIds = checked('job_restriction');
      const classIds = checked('class_restriction');
      const option = Array.from(jobSelect.options).find((o) => jobIds.includes(o.value)) ||
        Array.from(jobSelect.options).find((o) => classIds.includes(o.dataset.class));
      if (option) jobSelect.value = option.value;
    }
    function estimate() {
      clearTimeout(estimateTimer);
      estimateTimer = setTimeout(async () => {
        const box = document.querySelector('[data-estimate]');
        if (!isGear() || !jobSelect.value) return;
        const params = new URLSearchParams({ job: jobSelect.value, level: levelInput.value || 1 });
        ['att_boost', 'hp_boost', ...Object.values(data.stat_fields)].forEach((name) => params.set(name, num(name)));
        const response = await fetch(`${data.estimate_url}?${params}`, { credentials: 'same-origin' });
        const result = await response.json();
        if (!response.ok) { box.textContent = result.error || 'Không ước tính được.'; return; }
        const gain = result.with_item - result.without_item;
        const rows = [
          ['Chỉ số chính', result.main_stat],
          ['HP (gốc + item)', result.hp],
          ['STR / AGI / INT', `${result.stats.str} / ${result.stats.agi} / ${result.stats.int}`],
          ['ATT', result.stats.att],
          ['Sát thương không có item', result.without_item],
          ['Sát thương có item', `${result.with_item} (${gain >= 0 ? '+' : ''}${gain})`],
        ];
        const table = document.createElement('table');
        rows.forEach(([label, value]) => {
          const tr = table.insertRow();
          tr.insertCell().textContent = label;
          tr.insertCell().textContent = value;
        });
        box.replaceChildren(table);
      }, 250);
    }

    $('[data-suggest]').addEventListener('click', async () => {
      const params = new URLSearchParams({
        item_type: field('item_type').value,
        level: field('minimum_level').value || 1,
        main_stat: mainStat() || 'str',
      });
      const response = await fetch(`${data.suggest_url}?${params}`, { credentials: 'same-origin' });
      const result = await response.json();
      Object.entries(result.stats || {}).forEach(([name, value]) => {
        const input = field(name);
        if (input) input.value = value;
      });
      update();
    });

    // Lumen tiers are named per class and level range ("Tier 1 - Warrior 1-59"):
    // pick the one for the chosen class and level until a tier is picked by hand.
    const lumenSelect = field('lumen_tier');
    let lumenAuto = !lumenSelect.value;
    lumenSelect.addEventListener('change', () => { lumenAuto = false; });
    function pickLumenTier() {
      if (!lumenAuto || !isGear()) return;
      const classIds = checked('class_restriction');
      if (classIds.length !== 1) return;
      const className = classesById[classIds[0]].name;
      const level = num('minimum_level') || 1;
      const option = Array.from(lumenSelect.options).find((o) => {
        const range = o.text.match(/(\d+)\s*-\s*(\d+)/);
        return o.text.includes(className) && range && level >= Number(range[1]) && level <= Number(range[2]);
      });
      lumenSelect.value = option ? option.value : '';
    }

    function update(event) {
      if (event?.target !== lumenSelect) pickLumenTier();
      highlightMainStat();
      weaponHelp(event);
      preview();
      estimate();
    }

    if (!levelInput.value) levelInput.value = field('minimum_level').value || 1;
    pickEstimateJob();
    form.addEventListener('input', update);
    form.addEventListener('change', (event) => {
      if (['class_restriction', 'job_restriction'].includes(event.target.name)) pickEstimateJob();
      if (event.target.name === 'minimum_level') levelInput.value = event.target.value;
      update(event);
    });
    jobSelect.addEventListener('change', estimate);
    levelInput.addEventListener('input', estimate);
    update();
  });
})();
