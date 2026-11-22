export const tidy = (value = '') => value.replace(/\s+/g, ' ').trim();

const workflows = [
  { match: /فاتور|invoice|billing/i, name: 'الفاتورة', stages: [
    /^(معاينة|مراجعة)\s*(المسودة|الفاتورة)?$|^preview( invoice)?$/i,
    /^(فاتورة جديدة|إنشاء فاتورة|إضافة فاتورة|new invoice|create invoice)$/i,
    /^(الفواتير|فواتير المبيعات|invoices|sales invoices)$/i
  ], advice: 'راجع العميل والبنود والكميات والضريبة والإجمالي قبل الاعتماد. بعد الانتقال اطلب قراءة الواجهة للخطوة التالية.' },
  { match: /تقرير|تقارير|report/i, name: 'التقرير', stages: [
    /^(عرض التقرير|معاينة التقرير|run report|view report|preview report)$/i,
    /^(تقرير المبيعات|sales report)$/i,
    /^(التقارير|reports)$/i
  ], advice: 'حدد نوع التقرير والفترة والفلاتر، ثم راجع الإجماليات قبل التصدير. بعد الانتقال اطلب قراءة الواجهة للخطوة التالية.' }
];

export function advise(question, screen) {
  if (/اشرح|صف الشاشة|explain|overview/i.test(question)) {
    const labels = screen.elements.slice(0, 12).map(item => item.label);
    return { text: 'أنت في «' + screen.title + '».\n' + (labels.length
      ? 'تتضمن الواجهة هذه العناصر: ' + labels.join('، ') + '. اذكر ما تريد إنجازه لأحدد لك نقطة البداية.'
      : 'تعذر التعرف على عناصر يمكن إرشادك إليها في الصفحة الحالية.') };
  }
  const workflow = workflows.find(item => item.match.test(question));
  if (workflow) {
    for (const stage of workflow.stages) {
      const matches = screen.elements.filter(item => stage.test(item.label));
      if (matches.length === 1) {
        return { text: 'لإعداد ' + workflow.name + '، ابدأ من «' + matches[0].label + '».\n' + workflow.advice, target: matches[0].id };
      }
    }
    return suggestNavigation(question, screen) || { text: 'لم أجد زرًا واضحًا لهذه الخطوة في الواجهة الحالية. ' + workflow.advice };
  }
  const matches = screen.elements.filter(item => item.label.length >= 2 && question.toLowerCase().includes(item.label.toLowerCase()));
  if (matches.length === 1) return { text: 'العنصر «' + matches[0].label + '» ظاهر في الواجهة الحالية.', target: matches[0].id };
  return suggestNavigation(question, screen) || { text: 'اذكر اسم الزر كما يظهر في البرنامج، أو اطلب شرح الشاشة لعرض العناصر المتاحة.' };
}

export class ProgramMap {
  #programs = new Map();

  record(program, screen) {
    const pages = this.#programs.get(program) || new Map();
    const key = JSON.stringify([screen.path, screen.title]);
    pages.delete(key);
    pages.set(key, { path: screen.path, title: screen.title,
      labels: [...new Set(screen.elements.map(item => item.label))].slice(0, 24) });
    if (pages.size > 25) pages.delete(pages.keys().next().value);
    this.#programs.delete(program);
    this.#programs.set(program, pages);
    if (this.#programs.size > 12) this.#programs.delete(this.#programs.keys().next().value);

    const previous = [...pages.entries()].reverse().filter(([id]) => id !== key).map(([, page]) => page);
    const destinations = screen.elements.flatMap(item => {
      if (!item.destination || item.destination === screen.path) return [];
      const matches = previous.filter(page => page.path === item.destination);
      if (matches.length !== 1) return [];
      const { title, labels } = matches[0];
      return [{ target: item.id, title, labels }];
    });
    return { count: pages.size, pages: previous.slice(0, 8).map(({ title, labels }) => ({ title, labels })), destinations };
  }
}

function words(value) {
  return new Set(value.toLowerCase().replace(/[أإآ]/g, 'ا').replace(/[\u064B-\u065F\u0670]/g, '')
    .split(/[^\p{L}\p{N}]+/u)
    .map(word => word.length > 4 ? word.replace(/^ال/, '') : word)
    .filter(word => word.length > 2 && !['كيف', 'اين', 'اضغط', 'اريد', 'بدي', 'اشتي', 'اعمل', 'can', 'the', 'where'].includes(word)));
}

function suggestNavigation(question, screen) {
  const terms = words(question);
  const overlap = value => [...words(value)].filter(word => terms.has(word)).length;
  const candidates = [];
  for (const item of screen.elements) {
    const destination = screen.context?.destinations.find(link => link.target === item.id);
    const direct = overlap(item.label);
    const indirect = destination ? Math.max(overlap(destination.title), ...destination.labels.map(overlap)) : 0;
    const score = Math.max(direct * 2, indirect);
    if (score) candidates.push({ item, score, destination: direct * 2 >= indirect ? undefined : destination });
  }
  candidates.sort((left, right) => right.score - left.score);
  const [best, next] = candidates;
  if (!best || next?.score === best.score) return;
  const label = best.item.label;
  return {
    text: best.destination
      ? 'ابدأ من «' + label + '». يشير هذا الرابط إلى صفحة «' + best.destination.title +
        '» التي تضم عناصر مرتبطة بطلبك. افتحها ثم اسألني عن الخطوة التالية.'
      : 'العنصر «' + label + '» هو الأقرب إلى طلبك في الواجهة الحالية. افتحه إن كان يطابق هدفك، ثم اسألني عن الخطوة التالية.',
    target: best.item.id
  };
}
