const heading = document.querySelector('h1');
const card = document.querySelector('.card');
const screens = {
  home: ['نظرة عامة', '<p>تدرّب على التنقل وإعداد مسودة فاتورة أو عرض تقرير باستخدام بيانات تجريبية.</p>'],
  invoices: ['الفواتير', '<p>مسودات فواتير المبيعات</p><button data-page="invoice">فاتورة جديدة</button>'],
  invoice: ['إعداد فاتورة', `<form id="invoice">
    <label>العميل <select name="customer"><option>شركة النور</option><option>مؤسسة الوفاق</option></select></label>
    <label>الكمية <input name="quantity" type="number" value="1" min="1" max="1000" required></label>
    <label>سعر الوحدة <input name="price" type="number" value="5000" min="0" max="1000000" required></label>
    <button type="submit">معاينة المسودة</button></form><div id="result" role="status"></div>`],
  reports: ['التقارير', '<p>راجع المبيعات بحسب الفترة.</p><button data-page="sales">تقرير المبيعات</button>'],
  sales: ['تقرير المبيعات', `<form id="sales"><label>الفترة <select name="period"><option value="month">هذا الشهر</option><option value="last">الشهر السابق</option></select></label>
    <button type="submit">عرض التقرير</button></form><div id="result" role="status"></div>`]
};
const money = new Intl.NumberFormat('ar-YE', { style: 'currency', currency: 'YER' });
const sales = { month: [42000, 63000], last: [27000, 41000] };

function show(page) {
  const [title, markup] = screens[page];
  heading.textContent = title;
  card.innerHTML = markup;
  for (const button of document.querySelectorAll('nav button')) {
    if (button.dataset.page === page) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
}

document.addEventListener('click', event => {
  const page = event.target.closest('button[data-page]')?.dataset.page;
  if (page && Object.hasOwn(screens, page)) show(page);
});
card.addEventListener('submit', event => {
  event.preventDefault();
  const values = new FormData(event.target);
  const result = document.getElementById('result');
  if (event.target.id === 'invoice') {
    const total = Number(values.get('price')) * Number(values.get('quantity'));
    result.textContent = 'مسودة للعميل ' + values.get('customer') + ' · الإجمالي ' + money.format(total);
    return;
  }
  const [first, second] = sales[values.get('period')];
  result.innerHTML = '<table><thead><tr><th scope="col">البند</th><th scope="col">المبيعات</th></tr></thead><tbody></tbody></table>';
  const body = result.querySelector('tbody');
  for (const [label, amount] of [['الفئة الأولى', first], ['الفئة الثانية', second], ['الإجمالي', first + second]]) {
    const row = body.insertRow();
    row.insertCell().textContent = label;
    row.insertCell().textContent = money.format(amount);
  }
});
show('home');
