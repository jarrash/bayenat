const stats = [
  { label: "القضايا", value: "0", tone: "neutral" },
  { label: "الأدلة", value: "0", tone: "blue" },
  { label: "قيد المعالجة", value: "0", tone: "amber" },
  { label: "تحتاج مراجعة", value: "0", tone: "red" },
  { label: "مكتملة", value: "0", tone: "green" },
];

export default function Home() {
  return (
    <main dir="rtl" className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">منصة التحقق من الأدلة الصوتية والمرئية</div>
          <h1>Bayenat</h1>
        </div>
        <div className="topbar-actions">
          <button className="language">English</button>
          <button className="primary">+ قضية جديدة</button>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">لوحة المتابعة</p>
          <h2>من الدليل الأصلي إلى النص القابل للمراجعة.</h2>
          <p className="hero-copy">يحافظ Bayenat على سلامة الملف الأصلي، ويعرض مخرجات المحركات والاختلافات وقرارات المراجع دون استبدال الدليل أو إخفاء عدم اليقين.</p>
        </div>
        <div className="hero-note">
          <span>مبدأ أساسي</span>
          <strong>لا يوجد نص نهائي دون مراجعة بشرية.</strong>
        </div>
      </section>

      <section className="stats" aria-label="إحصاءات المنصة">
        {stats.map((stat) => (
          <article className={`stat ${stat.tone}`} key={stat.label}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </article>
        ))}
      </section>

      <section className="workspace">
        <div className="panel empty-state">
          <div className="icon">⌁</div>
          <h3>ابدأ بإنشاء قضية</h3>
          <p>أنشئ قضية، ثم أضف ملفاً صوتياً أو مرئياً. سيتم حفظ بصمة SHA-256 والبيانات الوصفية قبل بدء أي معالجة.</p>
          <button className="primary">إنشاء قضية</button>
        </div>
        <div className="panel principles">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">سير العمل</p>
              <h3>سجل الأدلة الأخير</h3>
            </div>
            <span className="muted">لا توجد سجلات بعد</span>
          </div>
          <div className="pipeline">
            {["رفع الدليل", "التحقق من السلامة", "المعالجة", "المراجعة البشرية", "التقرير"].map((step, index) => (
              <div className="pipeline-step" key={step}>
                <span>{index + 1}</span>
                <div>{step}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
