'use strict';

const byId = id => document.getElementById(id);
const token = location.hash.slice(1);
history.replaceState(null, '', location.pathname);

const reports = {
  'trial-balance': {
    title: 'ميزان المراجعة',
    description: 'راجع إجمالي المدين والدائن والفرق لكل عملة خلال الفترة المحددة.',
    columns: [['account_code', 'رمز الحساب'], ['currency', 'العملة'], ['debit', 'مدين'], ['credit', 'دائن']]
  },
  accounts: {
    title: 'دليل الحسابات',
    description: 'راجع رموز الحسابات وأسماءها وتصنيفها في المصدر.',
    columns: [['code', 'الرمز'], ['name', 'الحساب'], ['kind', 'النوع'], ['currency', 'العملة']]
  },
  cashboxes: {
    title: 'الصناديق',
    description: 'راجع الصناديق والحسابات المرتبطة بها والعملات المسجلة في المصدر.',
    columns: [['code', 'الرمز'], ['name', 'الصندوق'], ['account_code', 'رمز الحساب المرتبط'], ['currency', 'العملة']]
  }
};
const navigation = [...document.querySelectorAll('nav button')];
let task = 'trial-balance';
let current;

function status(message, error = false) {
  byId('status').textContent = message;
  byId('status').toggleAttribute('data-error', error);
}

function disableControls(disabled) {
  byId('load').disabled = disabled;
  byId('start').disabled = disabled;
  byId('end').disabled = disabled;
  for (const button of navigation) button.disabled = disabled;
}

function clearReport() {
  current = undefined;
  byId('results').hidden = true;
  byId('totals').hidden = true;
}

async function request(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(10000)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}

function element(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function renderReport(result) {
  current = result;
  const columns = reports[result.task].columns;
  const header = document.createElement('tr');
  for (const [, label] of columns) {
    const cell = element('th', label);
    cell.scope = 'col';
    header.append(cell);
  }
  document.querySelector('thead').replaceChildren(header);
  document.querySelector('tbody').replaceChildren(...result.rows.map(record => {
    const row = document.createElement('tr');
    for (const [key] of columns) row.append(element('td', record[key] ?? '—'));
    return row;
  }));

  const period = result.period ? ' · الفترة: ' + result.period.start + ' إلى ' + result.period.end : '';
  byId('evidence').textContent = result.source.label + ' · ' + result.source.object +
    ' · ' + new Date(result.source.read_at_utc).toLocaleString('ar') + period;
  byId('results').hidden = false;
  byId('export').disabled = result.status !== 'complete';
  if (result.status === 'empty') {
    status('لا توجد سجلات لهذا الطلب في المصدر الحالي.');
  } else if (result.status === 'truncated') {
    status('تم عرض أول 500 سجل. يتوفر التنزيل والإجماليات للنتائج المكتملة فقط.');
  } else {
    status('السجلات المقروءة: ' + result.rows_returned);
  }

  const totals = result.totals_by_currency;
  if (totals) {
    byId('total-cards').replaceChildren(...totals.map(total => {
      const card = document.createElement('article');
      const details = document.createElement('dl');
      const metrics = [['مدين', total.debit], ['دائن', total.credit], ['الفرق', total.difference],
        ['النتيجة', total.balanced ? 'متساوٍ' : 'يوجد فرق']];
      for (const [label, value] of metrics) details.append(element('dt', label), element('dd', value));
      card.append(element('h3', total.currency), details);
      return card;
    }));
    byId('totals').hidden = false;
  }
}

for (const button of navigation) {
  button.addEventListener('click', () => {
    task = button.dataset.task;
    for (const item of navigation) item.removeAttribute('aria-current');
    button.setAttribute('aria-current', 'page');
    byId('title').textContent = reports[task].title;
    byId('description').textContent = reports[task].description;
    const usesDates = task === 'trial-balance';
    byId('dates').hidden = !usesDates;
    byId('start').required = byId('end').required = usesDates;
    clearReport();
    status('');
  });
}

for (const id of ['start', 'end']) {
  byId(id).addEventListener('change', () => {
    if (!current) return;
    clearReport();
    status('تغيّرت الفترة. اقرأ المصدر لعرض السجلات الجديدة.');
  });
}

byId('report').addEventListener('submit', async event => {
  event.preventDefault();
  const query = { task, learn: byId('learn').checked };
  if (task === 'trial-balance') {
    query.start = byId('start').value;
    query.end = byId('end').value;
  }
  disableControls(true);
  clearReport();
  status('جارٍ قراءة المصدر…');
  try {
    const report = await request('/api/report', query);
    renderReport(report);
    if (report.learning_error) byId('memory-status').textContent = 'جُلب التقرير وتعذر حفظ تفضيل الاستخدام.';
    else if (query.learn) refreshMemory({ action: 'read' });
  } catch (error) {
    status(error.message || 'تعذر الاتصال بالخدمة المحلية.', true);
  } finally {
    disableControls(false);
  }
});

function csvCell(value, trustedDecimal = false) {
  const text = String(value ?? '');
  const isFormula = /^[\s\uFEFF]*[=+\-@＝＋－＠]/u.test(text) || /^[\t\r\n]/.test(text);
  return '"' + (isFormula && !trustedDecimal ? "'" : '') + text.replaceAll('"', '""') + '"';
}

byId('export').addEventListener('click', () => {
  if (current?.status !== 'complete') return;
  const columns = reports[current.task].columns;
  const rows = [columns.map(([, label]) => csvCell(label))];
  for (const record of current.rows) {
    rows.push(columns.map(([key]) => csvCell(record[key], ['debit', 'credit'].includes(key))));
  }
  const url = URL.createObjectURL(new Blob(['\uFEFF' + rows.map(row => row.join(',')).join('\r\n')],
    { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  const period = current.period ? '-' + current.period.start + '-' + current.period.end : '';
  link.download = 'daleel-' + current.task + period + '.csv';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function start() {
  if (!token) {
    status('افتح رابط الجلسة الكامل من نافذة التشغيل على هذا الكمبيوتر.', true);
    return;
  }
  try {
    const source = await request('/api/source', {});
    byId('source-label').textContent = source.label;
    if (source.demo) {
      byId('start').value = '2026-11-01';
      byId('end').value = '2026-11-30';
      status('الفترة المعروضة تحتوي على بيانات تدريبية.');
    }
    disableControls(false);
    byId('review-button').disabled = false;
  } catch (error) {
    status(error.message || 'تعذر الاتصال بالخدمة المحلية.', true);
  }
}

start();

const templates = {
  accounting: 'حدد الكيان والفترة ومصدر السجل.\nطابق المجاميع والحسابات المساعدة وسجّل الفروقات.\nأرسل الملاحظات ومسودة النتائج إلى المراجع المسؤول.',
  engineering: 'سجّل رقم الملف والإصدار ومتطلبات المشروع المعتمدة.\nقارن بنود التسليم بالمتطلبات ووثّق الاختلافات والأسئلة المفتوحة مع مواضعها.\nأحل الحسابات والقرارات الفنية إلى المهندس المسؤول للتحقق والاعتماد.',
  legal: 'حدد نوع المستند والإصدار والولاية القضائية والغرض من المراجعة.\nاستخرج بنود المراجعة المطلوبة وحدد موضع كل بند وسجل النقاط التي تحتاج تفسيرًا.\nأحل تفسير النصوص وتقييم الالتزامات واعتماد الملاحظات إلى المراجع المختص.'
};

function renderMemory(memory) {
  byId('memory').hidden = !memory.enabled;
  byId('learn-setting').hidden = !memory.enabled;
  if (!memory.enabled) {
    byId('learn').checked = false;
    return;
  }
  const suggestion = reports[memory.suggestion];
  byId('suggestion').hidden = !suggestion;
  byId('suggestion').textContent = suggestion ? 'التقرير الأكثر استخدامًا: ' + suggestion.title : '';
  byId('procedures').replaceChildren(...memory.procedures.map(procedure => {
    const item = document.createElement('li');
    const remove = element('button', 'حذف الإجراء');
    remove.type = 'button';
    remove.onclick = () => {
      if (confirm('حذف هذا الإجراء من مساحة العمل؟')) refreshMemory({ action: 'delete', id: procedure.id });
    };
    item.append(element('strong', procedure.title), element('p', 'المرجع: ' + procedure.reference),
      element('pre', procedure.steps), remove);
    return item;
  }));
}

async function refreshMemory(payload) {
  try {
    renderMemory(await request('/api/workspace', payload));
    byId('memory-status').textContent = '';
    return true;
  } catch (error) {
    byId('memory-status').textContent = error.message || 'تعذر تحديث الذاكرة.';
    return false;
  }
}

byId('template').onclick = () => {
  const steps = byId('steps');
  if (!steps.value.trim()) steps.value = templates[byId('role').value];
  else byId('memory-status').textContent = 'أفرغ الخطوات الحالية أولًا إذا أردت إدخال القالب.';
};
byId('clear-usage').onclick = async () => {
  if (confirm('مسح إحصاءات استخدام التقارير؟') && await refreshMemory({ action: 'clear-usage' })) {
    byId('learn').checked = false;
  }
};
byId('procedure').onsubmit = async event => {
  event.preventDefault();
  const button = byId('save-procedure');
  button.disabled = true;
  const saved = await refreshMemory({ action: 'save', role: byId('role').value,
    title: byId('procedure-title').value, reference: byId('reference').value, steps: byId('steps').value });
  if (saved) {
    event.target.reset();
    byId('memory-status').textContent = 'حُفظ الإجراء في ملف مساحة العمل.';
  }
  button.disabled = false;
};
if (token) refreshMemory({ action: 'read' });

function describeChange(change, index) {
  const operations = { insert: 'إضافة', delete: 'حذف', replace: 'تعديل' };
  const details = document.createElement('details');
  const parts = document.createElement('div');
  parts.className = 'change-columns';
  for (const [title, lines, start] of [
    ['النسخة السابقة', change.before_lines, change.before_start],
    ['النسخة الجديدة', change.after_lines, change.after_start]
  ]) {
    if (!lines.length) continue;
    const column = document.createElement('div');
    column.append(element('strong', title), element('pre', lines.map((line, offset) => (start + offset) + ' | ' + line).join('\n')));
    parts.append(column);
  }
  details.append(element('summary', (index + 1) + '. ' + operations[change.operation]), parts);
  return details;
}

async function documentText(input) {
  const file = input.files[0];
  if (!file || file.size > 32768) throw new Error('اختر ملفين نصيين بحجم لا يتجاوز 32 كيلوبايت لكل ملف.');
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
  } catch {
    throw new Error('تعذرت قراءة الملف كنص UTF-8.');
  }
}

byId('review-form').onsubmit = async event => {
  event.preventDefault();
  const controls = Array.from(event.target.elements);
  for (const control of controls) control.disabled = true;
  byId('changes').replaceChildren();
  byId('review-status').textContent = 'جارٍ مقارنة النصوص…';
  try {
    const [before, after] = await Promise.all([documentText(byId('before-file')), documentText(byId('after-file'))]);
    const result = await request('/api/review', { before, after });
    byId('review-status').textContent = result.changes.length
      ? 'مجموعات الفروق · إضافة ' + result.counts.insert + ' · حذف ' + result.counts.delete + ' · تعديل ' + result.counts.replace
      : 'لم تظهر فروق بين محتويات الأسطر.';
    byId('changes').replaceChildren(...result.changes.map(describeChange));
  } catch (error) {
    byId('review-status').textContent = error.message || 'تعذرت المقارنة.';
  } finally {
    for (const control of controls) control.disabled = false;
  }
};
