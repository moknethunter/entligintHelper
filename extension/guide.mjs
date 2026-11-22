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
    return { text: 'لم أجد زرًا واضحًا لهذه الخطوة في الواجهة الحالية. ' + workflow.advice };
  }
  const matches = screen.elements.filter(item => item.label.length >= 2 && question.toLowerCase().includes(item.label.toLowerCase()));
  if (matches.length === 1) return { text: 'العنصر «' + matches[0].label + '» ظاهر في الواجهة الحالية.', target: matches[0].id };
  return { text: 'اذكر اسم الزر كما يظهر في البرنامج، أو اطلب شرح الشاشة لعرض العناصر المتاحة.' };
}
